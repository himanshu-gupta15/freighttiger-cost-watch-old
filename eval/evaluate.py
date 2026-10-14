"""Score an output CSV. Exits non-zero if any check fails.

    python eval/evaluate.py [output/flags.csv]

Checks:
  1. format       - header/order identical to sample_output_format_v2.csv; field values well-formed
  2. numbers      - every row's cost and both baselines recomputed by an INDEPENDENT pure-Python
                    implementation (csv + datetime, no pandas, no costwatch import)
  3. sample rows  - the three rows in the sample file are reproduced
  4. labels       - flags/verdicts/note ids vs hand labels (eval/expected_flags.csv)
  5. citations    - every justified row re-audited against hand-labelled note facts (eval/note_labels.csv)
  6. note reading - rule reader / LLM reader / combined vs hand labels (needs output/run_log.json)
"""

import csv
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval"


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def independent_metrics():
    """Reference implementation written separately from costwatch/metrics.py."""
    cost, tkm, rtype = defaultdict(float), defaultdict(float), {}
    for s in read_csv(ROOT / "shipment_records.csv"):
        d = date.fromisoformat(s["shipment_date"])
        key = (f"{s['origin']}-{s['destination']}", d - timedelta(days=d.weekday()))
        cost[key] += float(s["freight_cost_inr"])
        tkm[key] += float(s["quantity_tonnes"]) * float(s["distance_km"])
        rtype[key[0]] = s["route_type"]
    cpt = {k: cost[k] / tkm[k] for k in cost}
    out = {}
    for (route, week), c in cpt.items():
        prior = [cpt[(route, week - timedelta(weeks=i))] for i in range(1, 9) if (route, week - timedelta(weeks=i)) in cpt]
        peers = [v for (r, w), v in cpt.items() if w == week and r != route and rtype[r] == rtype[route]]
        own = (c / (sum(prior) / len(prior)) - 1) * 100 if prior else None
        peer = (c / (sum(peers) / len(peers)) - 1) * 100 if peers else None
        out[(route, week.isoformat())] = (f"{c:.2f}", own, peer)
    return out


def main(output_path):
    rows = read_csv(output_path)
    by_key = {(r["route"], r["week_of"]): r for r in rows}
    results, failures = [], []

    def check(name, ok, detail):
        results.append((name, ok, detail))
        if not ok:
            failures.append(name)

    # 1. format
    with open(ROOT / "sample_output_format_v2.csv", newline="") as fh:
        sample_header = next(csv.reader(fh))
    with open(output_path, newline="") as fh:
        header = next(csv.reader(fh))
    notes = {n["note_id"] for n in read_csv(ROOT / "context_notes.csv")}
    bad = [r for r in rows if r["flagged"] not in ("Yes", "No", "No (justified)")
           or (r["flagged"] == "No (justified)") != bool(r["matched_note_id"])
           or (r["matched_note_id"] and r["matched_note_id"] not in notes)
           or not r["reason"]]
    check("format: header matches sample exactly", header == sample_header, f"{header}")
    check("format: flagged/matched_note_id/reason consistent", not bad, f"{len(bad)} bad rows")

    # 2. numbers
    ref = independent_metrics()
    fmt = lambda v, suffix: f"{v:+.1f}% {suffix}" if v is not None else None  # noqa: E731
    mismatches = []
    for key, (c, own, peer) in ref.items():
        r = by_key.get(key)
        if r is None:
            mismatches.append((key, "missing"))
            continue
        if r["cost_per_tonne_km"] != c:
            mismatches.append((key, "cost"))
        if own is not None and r["vs_own_history"] != fmt(own, "vs this route's past average"):
            mismatches.append((key, "vs_own_history"))
        if peer is not None and r["vs_similar_routes"] != fmt(peer, "vs similar-length routes this week"):
            mismatches.append((key, "vs_similar_routes"))
    check("numbers: all route-weeks match independent recomputation",
          not mismatches and len(rows) == len(ref), f"{len(ref)} route-weeks, {len(mismatches)} mismatches {mismatches[:3]}")

    # 3. sample rows
    for s in read_csv(ROOT / "sample_output_format_v2.csv"):
        r = by_key.get((s["route"], s["week_of"]), {})
        same = all(r.get(k) == s[k] for k in ("cost_per_tonne_km", "vs_own_history", "vs_similar_routes",
                                               "flagged", "matched_note_id"))
        check(f"sample row reproduced: {s['route']} {s['week_of']}", same,
              f"ours: {[r.get(k) for k in ('cost_per_tonne_km', 'vs_own_history', 'vs_similar_routes', 'flagged', 'matched_note_id')]}")

    # 4. labels
    expected = {(e["route"], e["week_of"]): e for e in read_csv(EVAL / "expected_flags.csv")}
    predicted = {k for k, r in by_key.items() if r["flagged"] != "No"}
    tp = len(predicted & expected.keys())
    precision = tp / len(predicted) if predicted else 1.0
    recall = tp / len(expected) if expected else 1.0
    wrong = [(k, by_key[k]["flagged"], by_key[k]["matched_note_id"], e["expected_flagged"], e["expected_note_id"])
             for k, e in expected.items() if k in by_key and
             (by_key[k]["flagged"], by_key[k]["matched_note_id"]) != (e["expected_flagged"], e["expected_note_id"])]
    check("labels: detection precision = 1.0", precision == 1.0, f"precision {precision:.2f} ({len(predicted)} predicted)")
    check("labels: detection recall = 1.0", recall == 1.0, f"recall {recall:.2f} ({len(expected)} labelled)")
    check("labels: verdict + note id match on every labelled week", not wrong, f"{len(expected) - len(wrong)}/{len(expected)} {wrong[:3]}")

    # 5. citations
    note_labels = {n["note_id"]: n for n in read_csv(EVAL / "note_labels.csv")}
    unsound = []
    for r in rows:
        if not r["matched_note_id"]:
            continue
        n = note_labels[r["matched_note_id"]]
        week = date.fromisoformat(r["week_of"])
        ok = (n["raises_cost"] == "yes"
              and n["scope"] in ("All Routes", r["route"])
              and date.fromisoformat(n["window_start"]) <= week + timedelta(days=6)
              and week <= date.fromisoformat(n["window_end"])
              and r["matched_note_id"] in r["reason"])
        if not ok:
            unsound.append((r["route"], r["week_of"], r["matched_note_id"]))
    n_justified = sum(1 for r in rows if r["matched_note_id"])
    check("citations: every justified row cites a cost-raising note for that route and week",
          not unsound, f"{n_justified - len(unsound)}/{n_justified} sound {unsound}")

    # 6. note reading
    log_path = Path(output_path).with_name("run_log.json")
    if log_path.exists():
        notes_log = json.loads(log_path.read_text())["notes"]
        truth = {k: v["raises_cost"] == "yes" for k, v in note_labels.items()}
        score = lambda f: sum(f(n) == truth[n["note_id"]] for n in notes_log)  # noqa: E731
        rule = score(lambda n: n["rule_effect"] == "increase")
        combined = score(lambda n: n["usable_as_justification"])
        has_llm = notes_log[0]["llm_effect"] is not None
        llm = score(lambda n: n["llm_effect"] == "increase") if has_llm else None
        detail = f"rules {rule}/10, LLM {llm if has_llm else 'n/a'}/10, combined (both must agree) {combined}/10"
        check("note reading: combined reader correct on all notes", combined == len(truth), detail)

    report = ["# Evaluation report", "", f"Output: `{Path(output_path).relative_to(ROOT)}`", "",
              "| Check | Result | Detail |", "|---|---|---|"]
    report += [f"| {name} | {'PASS' if ok else 'FAIL'} | {detail} |" for name, ok, detail in results]
    report += ["", f"**{len(results) - len(failures)}/{len(results)} checks passed.**"]
    (EVAL / "report.md").write_text("\n".join(report) + "\n")
    for name, ok, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name} -- {detail}")
    print(f"\n{len(results) - len(failures)}/{len(results)} checks passed. Report: eval/report.md")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "output" / "flags.csv"))
