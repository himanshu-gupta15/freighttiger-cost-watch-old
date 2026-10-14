"""Turn free-text context notes into checkable facts: scope, active window, effect, size.

Two independent readers decide whether a note describes a cost *increase*:
  1. deterministic phrase rules (auditable, below), and
  2. the local LLM (classify_effects_with_llm).
A note may justify a cost rise only if BOTH say "increase". Disagreement => not usable.
This is deliberately conservative: a missed justification costs a human review, a
fabricated one is the failure the brief penalises most.
"""

import csv
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

from . import config

INCREASE, NO_INCREASE = "increase", "no_increase"
ALL_ROUTES = "all routes"

# Phrases that mean "this note is NOT a reason for a cost rise". Checked first: they win.
NO_EFFECT_PATTERNS = [
    r"not (?:significantly )?affected",
    r"not part of this dataset",
    r"no (?:significant|major) disruptions?",
    r"remained (?:normal|stable)",
    r"returned to normal",
    r"improved",
    r"without a rate change",
    r"absorbed",
]
# Phrases that mean costs went up.
INCREASE_PATTERNS = [
    r"higher [\w\s]*costs?",
    r"surcharge",
    r"pushing up [\w\s]*costs?",
    r"prices? rose",
    r"costs? (?:rose|increased|went up)",
]

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_RANGE_RE = re.compile(r"from (\w{3})\w* (\d{1,2}) to (\w{3})\w* (\d{1,2})", re.IGNORECASE)
_MAGNITUDE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*%")


@dataclass(frozen=True)
class Note:
    note_id: str
    date: date
    applies_to: str
    text: str
    window_start: date
    window_end: date
    window_rule: str
    rule_effect: str
    rule_evidence: str
    magnitude_pct: tuple | None
    llm_effect: str | None = None  # None when no LLM was used

    @property
    def is_all_routes(self) -> bool:
        return self.applies_to.strip().lower() == ALL_ROUTES

    @property
    def raises_cost(self) -> bool:
        llm_agrees = self.llm_effect is None or self.llm_effect == INCREASE
        return self.rule_effect == INCREASE and llm_agrees

    def applies_to_route(self, route: str) -> bool:
        return self.is_all_routes or self.applies_to.strip().lower() == route.lower()

    def covers_week(self, week_of: date) -> bool:
        return self.window_start <= week_of + timedelta(days=6) and week_of <= self.window_end

    def days_from_week(self, week_of: date) -> int:
        """0 if the window overlaps the week, else the gap in days."""
        week_end = week_of + timedelta(days=6)
        if self.covers_week(week_of):
            return 0
        return (self.window_start - week_end).days if self.window_start > week_end \
            else (week_of - self.window_end).days


def load_notes(path=config.NOTES_CSV) -> list[Note]:
    with open(path, newline="", encoding="utf-8") as fh:
        return [parse_note(r["note_id"], r["date"], r["applies_to"], r["note"]) for r in csv.DictReader(fh)]


def parse_note(note_id: str, date_str: str, applies_to: str, text: str) -> Note:
    note_date = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    start, end, window_rule = parse_window(note_date, text)
    effect, evidence = classify_effect_by_rules(text)
    return Note(note_id=note_id.strip(), date=note_date, applies_to=applies_to.strip(), text=text.strip(),
                window_start=start, window_end=end, window_rule=window_rule,
                rule_effect=effect, rule_evidence=evidence, magnitude_pct=parse_magnitude(text))


def parse_window(note_date: date, text: str) -> tuple[date, date, str]:
    match = _RANGE_RE.search(text)
    if match and match.group(1).lower() in _MONTHS and match.group(3).lower() in _MONTHS:
        start = date(note_date.year, _MONTHS[match.group(1).lower()], int(match.group(2)))
        end = date(note_date.year, _MONTHS[match.group(3).lower()], int(match.group(4)))
        if end < start:  # range crosses a year boundary
            end = end.replace(year=end.year + 1)
        return start, end, "explicit date range in note"
    week_start = note_date - timedelta(days=note_date.weekday())
    if re.search(r"starting this week|from this week onwards?", text, re.IGNORECASE):
        end = week_start + timedelta(weeks=config.OPEN_ENDED_NOTE_WEEKS) - timedelta(days=1)
        return week_start, end, f"open-ended ('starting this week'), capped at {config.OPEN_ENDED_NOTE_WEEKS} weeks"
    return week_start, week_start + timedelta(days=6), "no range stated: the week of the note date"


def classify_effect_by_rules(text: str) -> tuple[str, str]:
    for pattern in NO_EFFECT_PATTERNS:
        if match := re.search(pattern, text, re.IGNORECASE):
            return NO_INCREASE, match.group(0)
    for pattern in INCREASE_PATTERNS:
        if match := re.search(pattern, text, re.IGNORECASE):
            return INCREASE, match.group(0)
    return NO_INCREASE, "no cost-increase wording found"


def parse_magnitude(text: str) -> tuple | None:
    match = _MAGNITUDE_RE.search(text)
    return (float(match.group(1)), float(match.group(2))) if match else None


_CLASSIFY_SYSTEM = """You classify logistics notes. Answer with one word only.
INCREASE = the note says freight/trip/transport costs went UP (e.g. surcharge, detours raising cost, fuel price rise).
NO_INCREASE = the note says costs were not affected, conditions were normal/stable, things improved or returned to normal, costs were absorbed without a rate change, or the affected routes are not in scope."""


def classify_effects_with_llm(notes: list[Note], llm) -> list[Note]:
    """Second, independent reading of each note. Unparseable answers count as NO_INCREASE."""
    classified = []
    for note in notes:
        answer = llm.generate(_CLASSIFY_SYSTEM, f"Note: {note.text}\nAnswer:",
                              max_new_tokens=config.LLM_CLASSIFY_MAX_TOKENS, purpose=f"classify {note.note_id}")
        word = answer.strip().upper()
        effect = INCREASE if word.startswith("INCREASE") else NO_INCREASE
        classified.append(replace(note, llm_effect=effect))
    return classified
