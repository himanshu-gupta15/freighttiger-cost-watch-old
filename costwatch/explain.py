"""Plain-English reasons.

Verdict, note id, dates and numbers always come from code (a fixed prefix). For justified
rows the LLM adds a short paraphrase of the cited note, which is validated before use;
on any validation failure a template quoting the note verbatim is used instead.
Unexplained rows are fully deterministic: in testing the model mis-stated the metrics
there ("+3.0% vs last week") while adding nothing the template does not already say.
"""

import re

from . import config
from .verdict import JUSTIFIED, NORMAL, Assessment

_NOTE_ID_RE = re.compile(r"\bN\d{3}\b")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def pct(value: float) -> str:
    return f"{value:+.1f}%"


def build_reason(a: Assessment, llm, all_routes: list[str]) -> tuple[str, str]:
    """Return (reason, source) where source is 'template', 'llm' or 'template_fallback (...)'."""
    if a.verdict == NORMAL:
        return normal_reason(a), "template"
    if a.verdict != JUSTIFIED:
        return f"{unexplained_prefix(a)} Worth a human review. {rejected_notes_text(a)}", "template"

    prefix = justified_prefix(a)
    if llm is None:
        return f"{prefix} {quote_note(a)}", "template"
    body = " ".join(llm.generate(_SYSTEM, f"{facts_text(a)}\n\n{_TASK}",
                                 max_new_tokens=config.LLM_EXPLANATION_MAX_TOKENS,
                                 purpose=f"explain {a.route} {a.week_of}").split())
    problem = validate_explanation(body, a, all_routes)
    if problem:
        return f"{prefix} {quote_note(a)}", f"template_fallback ({problem})"
    return f"{prefix} {body}", "llm"


# ---------- deterministic parts ----------

def justified_prefix(a: Assessment) -> str:
    n = a.note
    return (f"Justified: matches note {n.note_id} dated {n.date} ({n.applies_to}, in effect "
            f"{n.window_start} to {n.window_end}), which covers this week.")


def unexplained_prefix(a: Assessment) -> str:
    return (f"Flagged: cost is {pct(a.vs_own_pct)} vs this route's past average and "
            f"{pct(a.vs_peer_pct)} vs similar routes, with no supporting note.")


def quote_note(a: Assessment) -> str:
    return f"The note says: \"{a.note.text}\""


def rejected_notes_text(a: Assessment) -> str:
    if not a.rejected:
        return "No matching note found for this route or date range."
    parts = [f"{n.note_id} ({n.date}) does not count: {why}." for n, why in a.rejected]
    return "Notes checked: " + " ".join(parts)


def normal_reason(a: Assessment) -> str:
    if a.own_history_weeks == 0:
        return "Not flagged: first week on record, so there is no past average to compare against."
    text = (f"Not flagged: {pct(a.vs_own_pct)} vs own past average and {pct(a.vs_peer_pct)} vs similar "
            f"routes, within normal range.")
    if a.vs_peer_pct >= config.PEER_FLAG_PCT:
        text += " Well above similar routes, but not rising vs its own recent average this week."
    return text


# ---------- LLM part (justified rows only) ----------

_SYSTEM = ("You explain freight cost alerts to a logistics manager in plain English. "
           "Use ONLY the facts given. Never add causes, numbers, dates, routes or note ids that are not in the facts. "
           "Write at most 2 short sentences.")

_TASK = ("In 1-2 sentences, say what the note reports happened and why that makes this week's higher cost on "
         "this route reasonable. Describe only what the note says. Do not quote any cost or percentage figures "
         "except ones written in the note itself. Do not mention any other note.")


def facts_text(a: Assessment) -> str:
    n = a.note
    return "\n".join([
        f"Route: {a.route} ({a.route_type} route), week {a.week_of} to {a.week_end}.",
        "This week's cost per tonne-km on this route is unusually high versus its own recent average.",
        f"Verdict: JUSTIFIED by note {n.note_id}.",
        f"Note {n.note_id} (dated {n.date}, applies to {n.applies_to}, in effect {n.window_start} to "
        f"{n.window_end}): \"{n.text}\"",
    ])


def validate_explanation(text: str, a: Assessment, all_routes: list[str]) -> str | None:
    """Return None if the LLM text is safe to publish, else what was wrong with it."""
    if not text:
        return "empty"
    if len(text.split()) > config.LLM_EXPLANATION_MAX_WORDS:
        return "too long"
    if extra := set(_NOTE_ID_RE.findall(text)) - {a.note.note_id}:
        return f"mentions other note(s): {sorted(extra)}"
    # Only figures the note itself contains (incl. its dates) may appear in the paraphrase.
    note_facts = f"{a.note.text} {a.note.date} {a.note.window_start} {a.note.window_end}"
    if extra := _numbers(text) - _numbers(note_facts):
        return f"numbers not in the note: {sorted(extra)}"
    if other := [r for r in all_routes if r != a.route and r.lower() in text.lower()]:
        return f"mentions other route(s): {other}"
    if re.search(r"\bunexplained\b|\bno (?:supporting )?note\b|\bnot justified\b", text, re.IGNORECASE):
        return "contradicts verdict"
    return None


def _numbers(text: str) -> set[str]:
    """Numbers normalised so '08' == '8' and '5.0' == '5'."""
    return {f"{float(raw):g}" for raw in _NUMBER_RE.findall(text)}
