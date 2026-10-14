# Evaluation report

Output: `output/flags.csv`

| Check | Result | Detail |
|---|---|---|
| format: header matches sample exactly | PASS | ['route', 'week_of', 'cost_per_tonne_km', 'vs_own_history', 'vs_similar_routes', 'flagged', 'matched_note_id', 'reason'] |
| format: flagged/matched_note_id/reason consistent | PASS | 0 bad rows |
| numbers: all route-weeks match independent recomputation | PASS | 728 route-weeks, 0 mismatches [] |
| sample row reproduced: Delhi-Jaipur 2024-11-11 | PASS | ours: ['4.17', "+35.5% vs this route's past average", '+21.0% vs similar-length routes this week', 'Yes', ''] |
| sample row reproduced: Ahmedabad-Mumbai 2025-01-20 | PASS | ours: ['3.29', "+29.5% vs this route's past average", '+22.5% vs similar-length routes this week', 'No (justified)', 'N002'] |
| sample row reproduced: Mumbai-Pune 2025-09-15 | PASS | ours: ['3.98', "+9.2% vs this route's past average", '+23.6% vs similar-length routes this week', 'Yes', ''] |
| labels: detection precision = 1.0 | PASS | precision 1.00 (20 predicted) |
| labels: detection recall = 1.0 | PASS | recall 1.00 (20 labelled) |
| labels: verdict + note id match on every labelled week | PASS | 20/20 [] |
| citations: every justified row cites a cost-raising note for that route and week | PASS | 4/4 sound [] |
| note reading: combined reader correct on all notes | PASS | rules 10/10, LLM 8/10, combined (both must agree) 10/10 |

**11/11 checks passed.**
