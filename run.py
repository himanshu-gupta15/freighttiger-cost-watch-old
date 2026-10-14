"""Run the cost watcher over shipment_records.csv.

    python run.py                 # local open-source LLM (Qwen2.5-1.5B-Instruct, CPU, greedy)
    python run.py --llm none      # rules + templates only, no model needed
"""

import argparse
from pathlib import Path

from costwatch import config
from costwatch.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--llm", choices=["local", "none"], default="local")
    parser.add_argument("--out", type=Path, default=config.OUTPUT_DIR / "flags.csv")
    parser.add_argument("--log", type=Path, default=config.OUTPUT_DIR / "run_log.json")
    args = parser.parse_args()

    log = run(args.llm, args.out, args.log)
    usage = log["llm_usage"]
    print(f"\nWrote {args.out} ({log['rows']} rows): {log['flagged_unexplained']} flagged, "
          f"{log['justified']} justified.")
    print(f"LLM: {usage['calls']} calls, {usage['input_tokens']} input tokens, "
          f"{usage['output_tokens']} output tokens. Runtime {log['runtime_seconds']}s.")


if __name__ == "__main__":
    main()
