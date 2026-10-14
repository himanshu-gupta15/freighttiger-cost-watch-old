"""End-to-end run: shipments -> weekly metrics -> flags -> note matching -> reasons -> CSV + log."""

import csv
import json
import math
import time
from pathlib import Path

from . import config
from .explain import build_reason, pct
from .llm import load_llm
from .metrics import load_shipments, weekly_route_costs
from .notes import classify_effects_with_llm, load_notes
from .retrieval import note_index
from .verdict import JUSTIFIED, UNEXPLAINED, assess

FLAG_LABEL = {UNEXPLAINED: "Yes", JUSTIFIED: "No (justified)"}


def run(llm_backend: str = "local", output_csv: Path = config.OUTPUT_DIR / "flags.csv",
        log_json: Path | None = config.OUTPUT_DIR / "run_log.json", progress=print) -> dict:
    started = time.perf_counter()
    weekly = weekly_route_costs(load_shipments())
    progress(f"{len(weekly)} route-weeks across {weekly['route'].nunique()} routes")

    llm = load_llm(llm_backend)
    notes = load_notes()
    if llm is not None:
        notes = classify_effects_with_llm(notes, llm)
    index = note_index(notes)
    routes = sorted(weekly["route"].unique())

    rows, sources = [], {}
    for row in weekly.itertuples(index=False):
        a = assess(row, index)
        reason, source = build_reason(a, llm, routes)
        if a.triggers:
            sources[f"{a.route} {a.week_of}"] = source
            progress(f"  {a.route} {a.week_of}: {a.verdict} {a.note.note_id if a.note else ''} [{source}]")
        rows.append(output_row(a, reason))

    write_csv(rows, output_csv)
    log = build_log(llm_backend, llm, notes, rows, sources, time.perf_counter() - started)
    if log_json:
        Path(log_json).write_text(json.dumps(log, indent=2, default=str))
        if llm is not None:
            Path(log_json).with_name("llm_calls.jsonl").write_text(
                "".join(json.dumps(c) + "\n" for c in llm.calls))
    return log


def output_row(a, reason: str) -> dict:
    own = ("n/a (no prior weeks)" if math.isnan(a.vs_own_pct)
           else f"{pct(a.vs_own_pct)} vs this route's past average")
    peer = ("n/a (no similar routes this week)" if math.isnan(a.vs_peer_pct)
            else f"{pct(a.vs_peer_pct)} vs similar-length routes this week")
    return {
        "route": a.route,
        "week_of": a.week_of.isoformat(),
        "cost_per_tonne_km": f"{a.cost:.2f}",
        "vs_own_history": own,
        "vs_similar_routes": peer,
        "flagged": FLAG_LABEL.get(a.verdict, "No"),
        "matched_note_id": a.note.note_id if a.note else "",
        "reason": reason,
    }


def write_csv(rows: list[dict], path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=config.OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def build_log(backend, llm, notes, rows, sources, seconds) -> dict:
    flagged = [r for r in rows if r["flagged"] != "No"]
    return {
        "llm_backend": backend,
        "runtime_seconds": round(seconds, 1),
        "rows": len(rows),
        "flagged_unexplained": sum(r["flagged"] == "Yes" for r in rows),
        "justified": sum(r["flagged"] == "No (justified)" for r in rows),
        "flag_rows": [{k: r[k] for k in ("route", "week_of", "flagged", "matched_note_id")} for r in flagged],
        "explanation_source": sources,
        "notes": [{"note_id": n.note_id, "applies_to": n.applies_to,
                   "window": f"{n.window_start} to {n.window_end}", "window_rule": n.window_rule,
                   "rule_effect": n.rule_effect, "rule_evidence": n.rule_evidence,
                   "llm_effect": n.llm_effect, "usable_as_justification": n.raises_cost} for n in notes],
        "llm_usage": llm.usage() if llm is not None else {"calls": 0, "input_tokens": 0, "output_tokens": 0},
        "settings": {k: getattr(config, k) for k in (
            "HISTORY_WEEKS", "OWN_HISTORY_FLAG_PCT", "PEER_FLAG_PCT", "OPEN_ENDED_NOTE_WEEKS",
            "MAGNITUDE_TOLERANCE_PCT", "NEARBY_NOTE_DAYS", "LLM_MODEL", "LLM_SEED")},
    }
