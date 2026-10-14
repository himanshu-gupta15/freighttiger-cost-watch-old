# Reproducibility check

Three fresh-process runs of `python run.py --llm local`.

| Run | Rows | Flagged (Yes) | Justified | SHA-256 of CSV |
|---|---|---|---|---|
| 1 | 728 | 16 | 4 | `b51c93f0496e31e1...` |
| 2 | 728 | 16 | 4 | `b51c93f0496e31e1...` |
| 3 | 728 | 16 | 4 | `b51c93f0496e31e1...` |

- Graded columns (route, week_of, cost_per_tonne_km, vs_own_history, vs_similar_routes, flagged, matched_note_id): **0 differing rows** across runs.
- `reason` column: 0 differing rows across runs.
- Files byte-identical: **yes**.
