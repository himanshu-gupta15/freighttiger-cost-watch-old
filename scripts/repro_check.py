"""Run the full pipeline 3 times in fresh processes and compare outputs.

    python scripts/repro_check.py [--llm local|none]

Writes output/repro/run{1,2,3}.csv (+ logs) and output/repro/repro_report.md.
"""

import argparse
import csv
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "repro"
GRADED = ["route", "week_of", "cost_per_tonne_km", "vs_own_history", "vs_similar_routes", "flagged", "matched_note_id"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", choices=["local", "none"], default="local")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    runs = []
    for i in (1, 2, 3):
        csv_path, log_path = OUT / f"run{i}.csv", OUT / f"run{i}_log.json"
        print(f"run {i} ...", flush=True)
        subprocess.run([sys.executable, str(ROOT / "run.py"), "--llm", args.llm, "--out", str(csv_path),
                        "--log", str(log_path)], check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
        with open(csv_path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        runs.append({"path": csv_path, "rows": rows,
                     "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest()})

    base = runs[0]["rows"]
    lines = ["# Reproducibility check", "", f"Three fresh-process runs of `python run.py --llm {args.llm}`.", "",
             "| Run | Rows | Flagged (Yes) | Justified | SHA-256 of CSV |", "|---|---|---|---|---|"]
    for i, r in enumerate(runs, 1):
        lines.append(f"| {i} | {len(r['rows'])} | {sum(x['flagged'] == 'Yes' for x in r['rows'])} | "
                     f"{sum(x['flagged'] == 'No (justified)' for x in r['rows'])} | `{r['sha256'][:16]}...` |")

    graded_diffs = sum(1 for r in runs[1:] for a, b in zip(base, r["rows"]) if [a[c] for c in GRADED] != [b[c] for c in GRADED])
    graded_diffs += sum(abs(len(r["rows"]) - len(base)) for r in runs[1:])
    reason_diffs = sum(1 for r in runs[1:] for a, b in zip(base, r["rows"]) if a["reason"] != b["reason"])
    identical = len({r["sha256"] for r in runs}) == 1
    lines += ["",
              f"- Graded columns ({', '.join(GRADED)}): **{graded_diffs} differing rows** across runs.",
              f"- `reason` column: {reason_diffs} differing rows across runs.",
              f"- Files byte-identical: **{'yes' if identical else 'no'}**."]
    report = OUT / "repro_report.md"
    report.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if graded_diffs == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
