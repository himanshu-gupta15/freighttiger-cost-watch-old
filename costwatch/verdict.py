"""Decide, per route-week: normal, justified (with the exact note), or unexplained.

The verdict is fully deterministic. The LLM never decides it; it only (a) co-signs that a
note describes a cost increase (see notes.py) and (b) phrases the explanation afterwards.
"""

import math
from dataclasses import dataclass, field
from datetime import timedelta

from . import config
from .notes import Note
from .retrieval import VectorIndex

NORMAL, JUSTIFIED, UNEXPLAINED = "normal", "justified", "unexplained"


@dataclass
class Assessment:
    route: str
    route_type: str
    week_of: object
    cost: float
    own_history_avg: float
    own_history_weeks: int
    peer_avg: float
    vs_own_pct: float
    vs_peer_pct: float
    triggers: list[str] = field(default_factory=list)
    verdict: str = NORMAL
    note: Note | None = None
    rejected: list[tuple[Note, str]] = field(default_factory=list)

    @property
    def week_end(self):
        return self.week_of + timedelta(days=6)


def assess(row, index: VectorIndex) -> Assessment:
    a = Assessment(route=row.route, route_type=row.route_type, week_of=row.week_of,
                   cost=row.cost_per_tonne_km, own_history_avg=row.own_history_avg,
                   own_history_weeks=row.own_history_weeks, peer_avg=row.peer_avg,
                   vs_own_pct=row.vs_own_history_pct, vs_peer_pct=row.vs_similar_pct)
    a.triggers = flag_triggers(a.vs_own_pct, a.vs_peer_pct)
    if not a.triggers:
        return a

    usable, a.rejected = [], []
    for note, _score in index.search(retrieval_query(a)):
        if not note.applies_to_route(a.route) or note.days_from_week(a.week_of) > config.NEARBY_NOTE_DAYS:
            continue  # not about this route/time at all; not worth mentioning
        problem = why_note_does_not_explain(note, a)
        if problem:
            a.rejected.append((note, problem))
        else:
            usable.append(note)

    # Prefer a note about this specific route over a blanket "All Routes" note;
    # within each group keep retrieval rank order (stable sort).
    usable.sort(key=lambda n: n.is_all_routes)
    if usable:
        a.verdict, a.note = JUSTIFIED, usable[0]
    else:
        a.verdict = UNEXPLAINED
    return a


def flag_triggers(vs_own_pct: float, vs_peer_pct: float) -> list[str]:
    """Rising AND out of the ordinary vs own history or vs similar routes."""
    rising = not math.isnan(vs_own_pct) and vs_own_pct > 0
    triggers = []
    if rising and vs_own_pct >= config.OWN_HISTORY_FLAG_PCT:
        triggers.append("own_history")
    if rising and not math.isnan(vs_peer_pct) and vs_peer_pct >= config.PEER_FLAG_PCT:
        triggers.append("similar_routes")
    return triggers


def retrieval_query(a: Assessment) -> str:
    origin, destination = a.route.split("-", 1)
    return (f"{a.route} {origin} {destination} freight cost rise higher trip costs surcharge "
            f"fuel diesel price toll flooding weather festival disruption detour "
            f"{a.week_of:%B %Y} {a.week_end:%B}")


def why_note_does_not_explain(note: Note, a: Assessment) -> str | None:
    """Return None if the note genuinely explains this rise, else a plain-English reason."""
    if not note.covers_week(a.week_of):
        return (f"its window ({note.window_start} to {note.window_end}) does not cover this week "
                f"({a.week_of} to {a.week_end})")
    if note.rule_effect != "increase":
        return f"it does not describe a cost increase (it says \"{note.rule_evidence}\")"
    if not note.raises_cost:
        return "the rule check and the LLM check disagree on whether it describes a cost increase, so it is not relied on"
    if note.is_all_routes and "similar_routes" in a.triggers:
        return (f"it applies to all routes, so it cannot explain why this route is {a.vs_peer_pct:+.1f}% "
                f"above similar routes that faced the same change")
    if note.magnitude_pct and a.vs_own_pct > note.magnitude_pct[1] + config.MAGNITUDE_TOLERANCE_PCT:
        low, high = note.magnitude_pct
        return (f"it describes a rise of about {low:g}-{high:g}%, but this route is up {a.vs_own_pct:+.1f}% "
                f"vs its own average, more than the note accounts for")
    return None
