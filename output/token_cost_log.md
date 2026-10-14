# Token / cost log: one full run

Command: `python run.py`, over all 2,940 shipments (728 route-weeks, 7 routes).
Raw per-call data: `output/llm_calls.jsonl`. Totals are also in `output/run_log.json`.

| Item | Value |
|---|---|
| Model | Qwen/Qwen2.5-1.5B-Instruct (open weights, Apache-2.0), run locally on CPU |
| Decoding | greedy (`do_sample=False`, i.e. temperature 0), seed 0, float32 |
| LLM calls | **14** |
| Input tokens | **2,327** |
| Output tokens | **239** |
| LLM time | 29.6 s (Apple M4 CPU); whole run 33.5 s |
| Cost | **$0.00**: no API, open weights. The only cost is a one-off 2.9 GB model download plus local CPU time. |

For scale: if the same 2,566 tokens went to a hosted model priced at $1 per million tokens,
the run would cost about $0.003.

## Where the calls go

| Purpose | Calls | Input tok | Output tok | Why it is needed |
|---|---|---|---|---|
| Classify each context note: does it describe a cost increase? | 10 (one per note) | 1,244 | 35 | Second, independent reader next to the phrase rules. A note is usable only if both agree. |
| Explain a justified row (paraphrase of the cited note) | 4 (one per justified row) | 1,083 | 204 | Plain-English reason. Validated before use, with a template fallback. |
| Unexplained or normal rows | 0 | 0 | 0 | Deterministic text. The model added nothing there and mis-stated metrics in testing. |

## Why the call count is this low

- The number of calls scales with *notes + justified rows*, not with shipments or route-weeks.
  708 of 728 route-weeks are normal and never reach the model.
- No call is made per flagged row just to restate numbers; code does that exactly.
- Q&A (`ask.py`) is outside the full run: one extra call per question (about 600–900 input tokens),
  and only when evidence was found.

## Earlier design, for comparison

The first version also had the LLM write text for unexplained rows: **30 calls, 6,823 input
and 870 output tokens.** The extra 16 calls produced text that mis-stated the metrics
(for example "+3.0% compared to last week" for a value measured against the 8-week average),
so they were removed. Fewer tokens and better output.
