"""Answer plain-English questions about the assistant's own findings (output/flags.csv).

Pipeline: parse route / month / year from the question -> filter result rows. If nothing
parses, vector-search the context notes (e.g. "diesel" -> N003) and take the rows that cite
or reject that note; failing that, vector-search the rows themselves. Then: a deterministic
headline (counts, note ids), an optional LLM summary that must pass grounding checks, and
the evidence rows, which are always printed.
"""

import csv
import re
from datetime import date

from . import config
from .retrieval import VectorIndex, note_index

_MONTHS = {name: i for i, name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"], start=1)}
_NOTE_ID_RE = re.compile(r"\bN\d{3}\b")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_SPECULATION_RE = re.compile(r"\b(suggests?|likely|probably|possibly|perhaps|may have|might|could|market|demand|"
                             r"conditions|because of|due to|caused by)\b", re.IGNORECASE)
_ADMITS_UNEXPLAINED_RE = re.compile(r"unexplained|no (?:supporting |matching )?note|no reason|review", re.IGNORECASE)
NOTE_MATCH_MIN_SCORE = 0.1  # unrelated notes score 0.0 once stop words are removed


def load_results(path=config.OUTPUT_DIR / "flags.csv") -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["week"] = date.fromisoformat(r["week_of"])
    return rows


def parse_question(question: str, routes: list[str]) -> tuple[list[str], int | None, int | None]:
    q = question.lower()
    matched = [r for r in routes if r.lower() in q or all(city.lower() in q for city in r.split("-"))]
    if not matched:  # a single city => every route touching it
        matched = [r for r in routes if any(re.search(rf"\b{city.lower()}\b", q) for city in r.split("-"))]
    month = next((i for name, i in _MONTHS.items() if re.search(rf"\b(?:{name}|{name[:3]})\b", q)), None)
    year = int(m.group(0)) if (m := re.search(r"\b20\d\d\b", q)) else None
    return matched, month, year


def find_evidence(question: str, rows: list[dict], notes) -> tuple[list[dict], str]:
    routes = sorted({r["route"] for r in rows})
    matched, month, year = parse_question(question, routes)
    scope = [r for r in rows
             if (not matched or r["route"] in matched)
             and (month is None or r["week"].month == month)
             and (year is None or r["week"].year == year)]
    label = ", ".join(filter(None, [" / ".join(matched),
                                    date(2000, month, 1).strftime("%B") if month else "", str(year or "")]))
    if not (matched or month or year):
        hits = [n.note_id for n, score in note_index(notes).search(question) if score >= NOTE_MATCH_MIN_SCORE]
        if hits:
            scope = [r for r in rows if any(note_id in r["reason"] for note_id in hits)]
            label = f"weeks where note(s) {', '.join(hits)} were checked"
        else:
            index = VectorIndex(rows, [f"{r['route']} {r['week']:%B %Y} {r['flagged']} {r['reason']}" for r in rows])
            scope = [row for row, s in index.search(question, k=10) if s > 0]
            label = "best text matches"
    return [r for r in scope if r["flagged"] != "No"], label


def headline(evidence: list[dict], scope: str) -> str:
    justified = [r for r in evidence if r["matched_note_id"]]
    unexplained = [r for r in evidence if not r["matched_note_id"]]
    parts = []
    if justified:
        ids = ", ".join(sorted({r["matched_note_id"] for r in justified}))
        parts.append(f"{len(justified)} week(s) justified by note(s) {ids}")
    if unexplained:
        parts.append(f"{len(unexplained)} week(s) flagged as UNEXPLAINED (no supporting note; needs human review)")
    return f"For {scope}: " + "; ".join(parts) + "."


def evidence_lines(evidence: list[dict]) -> str:
    lines = []
    for r in evidence:
        label = f"justified by {r['matched_note_id']}" if r["matched_note_id"] else "UNEXPLAINED"
        lines.append(f"- {r['route']} week of {r['week_of']}: {r['cost_per_tonne_km']}/tonne-km, "
                     f"{r['vs_own_history']}, {r['vs_similar_routes']} -> {label}. {r['reason']}")
    return "\n".join(lines)


_SYSTEM = ("You answer questions about freight cost alerts using ONLY the evidence rows given. "
           "For justified weeks, give the reason stated in the cited note. For UNEXPLAINED weeks, say that no "
           "supporting note was found and they need human review; never guess a cause. "
           "Never add numbers, dates or note ids that are not in the evidence. Answer in at most 3 sentences.")


def grounding_problem(summary: str, evidence: list[dict], evidence_text: str, question: str) -> str | None:
    numbers = lambda t: {f"{float(x):g}" for x in _NUMBER_RE.findall(t)}  # noqa: E731
    if set(_NOTE_ID_RE.findall(summary)) - {r["matched_note_id"] for r in evidence if r["matched_note_id"]}:
        return "cites a note that justifies none of the evidence rows"
    if numbers(summary) - numbers(evidence_text + " " + question):
        return "number not in evidence"
    if _SPECULATION_RE.search(summary):
        return "speculates"
    if any(not r["matched_note_id"] for r in evidence) and not _ADMITS_UNEXPLAINED_RE.search(summary):
        return "omits the unexplained weeks"
    return None


def answer(question: str, rows: list[dict], notes, llm=None) -> str:
    evidence, scope = find_evidence(question, rows, notes)
    if not evidence:
        return (f"Nothing was flagged or justified for: {scope}. "
                "Every week in that scope was within the normal range.")
    head, evidence_text = headline(evidence, scope), evidence_lines(evidence)
    if llm is not None:
        prompt = (f"Evidence:\n{evidence_text}\n\nQuestion: {question}\n\nFacts summary: {head}\n"
                  "Answer the question in plain English. Mention both the justified weeks (with the note's reason) "
                  "and the UNEXPLAINED weeks (no supporting note, need review), if there are any.")
        summary = " ".join(llm.generate(_SYSTEM, prompt, max_new_tokens=120, purpose="qa").split())
        if grounding_problem(summary, evidence, evidence_text, question) is None:
            head = f"{head}\n{summary}"
    return f"{head}\n\nEvidence:\n{evidence_text}"
