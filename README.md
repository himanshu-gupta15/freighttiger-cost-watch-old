# Freight cost watcher

Finds routes whose cost per tonne-km is rising in a way that looks out of the ordinary.
It checks the context notes for a genuine reason, and says in plain English whether the
rise is **justified** (citing the exact note) or **unexplained** (flagged for a human).

**Result on the given data:** 728 route-weeks scored. **16 flagged as unexplained** and
**4 justified** (N001 ×2, N002, N003). All 3 sample rows are reproduced exactly, and all
11 eval checks pass. Three fresh runs produce byte-identical output. The run uses
14 calls to a local open-source LLM and costs $0.

## Quick start

```bash
pip install -r requirements.txt
python run.py                    # full run -> output/flags.csv, output/run_log.json, output/llm_calls.jsonl
python run.py --llm none         # same verdicts, no model needed (template wording)
python eval/evaluate.py          # 11 checks -> eval/report.md
python -m pytest                 # 26 unit tests
python scripts/repro_check.py    # 3 fresh runs + diff -> output/repro/repro_report.md
python ask.py "why did Chennai-Bangalore get pricier in March 2025?"
```

The first `--llm local` run downloads Qwen2.5-1.5B-Instruct (2.9 GB) from Hugging Face.
After that it runs offline (`HF_HUB_OFFLINE=1`).

## Deliverables

| What | Where |
|---|---|
| Output CSV (exact sample columns) | `output/flags.csv` |
| Reproducibility check, 3 runs | `output/repro/repro_report.md` (+ `run1..3.csv`) |
| Token / cost log, one full run | `output/token_cost_log.md` (+ `llm_calls.jsonl`, `run_log.json`) |
| Eval harness + labelled set | `eval/evaluate.py`, `eval/expected_flags.csv`, `eval/note_labels.csv`, `eval/report.md` |
| Q&A examples (stretch goal) | `output/qa_examples.md` |

## How it works

```
shipment_records.csv
   │  metrics.py    week_of = Monday; cost/tkm = Σcost / Σ(tonnes×km) per route-week
   │                own-history avg (prior ≤8 weeks), peer avg (same route_type, excl. self)
   ▼
728 route-weeks ── verdict.py: flag rule ──► 708 normal  (template reason, no LLM)
   │ 20 candidates
   ▼
context_notes.csv ── notes.py: parse each note → scope, active window, effect, size
   │                 effect read twice: phrase rules AND local LLM; usable only if both say "increase"
   ▼
retrieval.py: TF-IDF vector index ranks the notes for the route-week
verdict.py:   keep a note only if  scope ∋ route  ∧  window ∩ week ≠ ∅  ∧  raises cost
              ∧ (all-routes note ⇒ not a gap vs peers)  ∧  (rise ≤ size the note states + 5pp)
   ├─ a note survives → "No (justified)" + matched_note_id
   └─ none survives   → "Yes" + every note checked and why it was rejected
   ▼
explain.py: code writes the verdict, note id, dates, and numbers; the LLM paraphrases the cited
            note (justified rows only); a validator checks the text, with a template fallback
   ▼
output/flags.csv
```

**The LLM never decides a verdict.** It is used where language understanding helps
and its output can be checked: a second reading of the notes, a paraphrase of the cited note,
and Q&A summaries. In every case a deterministic check sits between the LLM and the output.

### Definitions (graded fields)

- **Weekly cost:** `Σ freight_cost / Σ (quantity_tonnes × distance_km)` over the route-week's shipments.
  This is a ratio of totals (tonne-km weighted), not a mean of per-shipment ratios. Only the
  ratio of totals reproduces the sample's 4.17 / 3.29 / 3.98; the plain mean gives 4.16 / 3.28 / 3.97.
- **vs own history:** mean of the route's weekly cost over the 8 calendar weeks strictly
  before the current week. **Fewer than 8 prior weeks:** every route starts on 2024-01-01, so
  the first week has no history. Its output reads `n/a (no prior weeks)` and it is never flagged.
  Weeks 2024-01-08 to 2024-02-19 use the 1 to 7 weeks available. No padding, no extrapolation.
  The window is calendar-based, so a missing week would shrink it rather than reach further back.
  (No route has a gap in this data.)
- **vs similar routes:** mean weekly cost of the *other* routes with the same `route_type` in the
  same week. Short and Long have 2 routes each, so a route's peer there is just the other route.
- **Output rows:** all 728 route-weeks, so every baseline can be checked. `flagged` is `Yes`
  (rising, unusual, unexplained), `No (justified)` (rising and unusual, but a note explains it),
  or `No` (normal).

### Flag rule and why these thresholds

A week is a candidate when it is **rising** (above its own 8-week average) **and** either:

- **≥ 10% above its own history.** In calm periods (Jan to Oct 2024) the weekly deviation has
  σ ≈ 2.9%, and the largest was 8.6%. So 10% is about 3.5σ.
- **≥ 20% above similar routes.** Routes carry a stable premium or discount against their peers.
  Mumbai-Pune normally runs about 10% above Delhi-Jaipur, and the largest calm-period gap was 16.6%.
  This rule exists to catch slow **creep**. A creeping route drags its own rolling average up,
  so its own-history change stays small (Mumbai-Pune: +3 to +9%), while the gap to peers
  reaches +39%.

This catches every planted event and nothing in the calm periods. The thresholds sit in
`costwatch/config.py`.

### When does a note justify a rise?

All of these must hold:

1. **Right route:** `applies_to` is the route or "All Routes".
2. **Right time:** the note's active window overlaps the Monday-to-Sunday week.
   - Explicit range ("from Feb 24 to Mar 8"): those dates.
   - "Starting this week" (N003): 8 weeks from that week. Open-ended notes are capped because
     after 8 weeks the rise is inside the rolling baseline. Without a cap, a May diesel note
     could "explain" a December rise.
   - Otherwise: the week of the note's date.
3. **It actually raises cost.** Notes saying costs were *not* affected, conditions were normal or
   improved, or costs were absorbed "without a rate change" never count. This is read twice:
   by phrase rules and by the LLM. **Both must agree.**
4. **An "All Routes" note cannot explain a gap vs peers.** The peers got the same diesel rise,
   so diesel can explain a route rising against its *own* history, not against *similar routes*.
5. **The size fits.** If the note quantifies the rise ("roughly 5–7%"), the route's own-history
   rise must be ≤ the upper bound + 5 percentage points (about 2σ of noise).

If several notes pass, a route-specific note beats an "All Routes" one, then retrieval rank decides.
If none passes, the row is **unexplained**, and the reason lists each nearby note and why it was rejected.

## Findings

| Route | Weeks | Verdict | Why |
|---|---|---|---|
| Delhi-Jaipur | 2024-11-11, 11-18 | **Unexplained** | +35.5% / +27.6% spike. No note for this route near that time. |
| Ahmedabad-Mumbai | 2025-01-20 | Justified, **N002** | Festival-week surcharge, same week. |
| Chennai-Bangalore | 2025-02-24, 03-03 | Justified, **N001** | Flooding Feb 24 to Mar 8, with detours and higher trip costs. |
| Chennai-Bangalore | 2025-03-10, 03-17 | **Unexplained** | Still +22% / +14%, but N001's window ended Mar 8. N009 says the route *returned to normal*, which is not a cost reason. |
| Mumbai-Delhi | 2025-05-12 | Justified, **N003** | Diesel +5–7% on all routes. +11.6% is within that plus noise, and the route is not unusual against its peers. |
| Mumbai-Pune | 2025-06-23 | **Unexplained** | +20.6% vs peers. N003 hit the peers too, so it can't explain the gap. |
| Mumbai-Pune | 10 weeks, 2025-09-15 to 12-22 | **Unexplained** | Steady creep, reaching +39% vs peers. N006 ("stable demand") and N010 ("no rate change") are explicitly not reasons. |

Traps the system avoids: stretching N001 past Mar 8; citing N009, N010, N006, N005, N004, or N007;
citing an "All Routes" note for a route-specific gap. Coromandel Carriers, a transporter that
appears only on Delhi-Chennai, prices in line with the others, so nothing is flagged there.

## How I convinced myself it is right

`python eval/evaluate.py` runs 11 checks (see `eval/report.md`):

| Check | Result |
|---|---|
| Header and column order identical to the sample; `flagged` / `matched_note_id` consistent | pass |
| **All 728 rows' numbers match an independent recomputation** (plain Python `csv` + `datetime`, no pandas, no shared code) | 728/728 |
| The 3 sample rows reproduced (numbers, flag, note id) | 3/3 |
| Hand-labelled set (`eval/expected_flags.csv`, 20 weeks, each with a rationale): detection precision / recall | 1.00 / 1.00 |
| Verdict + note id per labelled week | 20/20 |
| **Citation audit:** every justified row re-checked against hand-labelled note facts (route, window, raises cost) | 4/4 |
| Note reading vs hand labels | rules 10/10, **LLM 8/10**, combined 10/10 |

Plus **26 unit tests** (`tests/`). They cover:

- the Sunday-to-Monday week boundary;
- the ratio-of-totals cost formula;
- the history window: ≤ 8 weeks and no look-ahead;
- the peer average excluding the route itself;
- each rejection rule;
- the validator rejecting invented note ids, numbers, and routes;
- a perturbation test: moving N002 to another route moves the justification with it.

**What the eval taught me** (these are the reasons for the design):

- **The LLM alone would fabricate a justification.** Qwen2.5-1.5B reads N010 ("compliance costs
  were absorbed … without a rate change") and N007 ("improved road conditions") as cost
  *increases*. N010 is an "All Routes" note in the same week as the Mumbai-Pune creep.
  Trusting the model would have produced exactly the confident wrong reason the brief warns
  about. Hence the **two-reader agreement rule**.
- **LLM explanations for unexplained rows were wrong in subtle ways.** Every number was real but
  attached to the wrong meaning: "+3.0% compared to last week" for a value measured against the
  8-week average, and "+23% for similar routes" when it was this route's gap. So unexplained rows
  are deterministic, and justified-row paraphrases may only contain numbers that appear in the note.
- **Q&A summaries invented causes** ("fluctuating market conditions") and left out unexplained weeks.
  They now pass a grounding check: note ids and numbers must come from the evidence, there is no
  speculative wording, and unexplained weeks must be acknowledged. Otherwise only the deterministic
  answer is shown. The evidence rows are always printed.

**Caveat:** I wrote the labels myself, from reading the notes and the weekly series, before
writing the matching code. They are an independent statement of intent, not ground truth from
FreightTiger. The numeric checks (recomputation, sample rows) do not depend on my judgement.

## Reproducibility

- Metrics, flags, and note matching are pure functions of the input. The vector-search ranking
  rounds scores and breaks ties by position.
- LLM: CPU, float32, **greedy decoding** (equivalent to temperature 0), `torch.manual_seed(0)`,
  `torch.use_deterministic_algorithms(True)`.
- **Result:** 3 fresh-process runs give **byte-identical CSVs**, reasons included. They are also
  identical to `output/flags.csv`. See `output/repro/repro_report.md`.
- **Proof that the LLM cannot move a verdict:** `--llm none` (no model at all) gives 0 differences
  in all graded columns against the LLM run. Only the reason wording differs.

## Cost of running it

One full run: **14 LLM calls, 2,327 input tokens, 239 output tokens, $0** (local open-weights
model). That is 10 calls to read the notes and 4 to explain justified rows. Normal weeks never
touch the model. Details: `output/token_cost_log.md`.

## Trade-offs and limitations

- **A 1.5B local model, not a large hosted one.** It is free, private, and deterministic, and the
  guardrails handle its weaknesses. A stronger model would make paraphrases and Q&A fail validation
  less often, but the verdicts would not change. The backend is one class (`costwatch/llm.py`).
- **TF-IDF instead of an embedding model.** It is exact, deterministic, and needs no download, which
  suits 10 notes. Retrieval only *ranks*: correctness comes from the scope/window/effect checks,
  so a weaker retriever cannot produce a wrong citation, at worst a missed one. A light stemmer
  handles "flood" vs "flooding". Swapping in embeddings means changing one class.
- **The phrase rules are tuned to this note style.** New notes with unseen wording fall to
  "no increase" (the conservative side), and the LLM must also agree. A larger note set would need
  more phrases or a stronger model as the second reader.
- **Thresholds are data-driven but global.** Per-route σ-based thresholds would adapt better to
  routes with different volatility.
- **Peer groups for Short and Long have one peer each,** so one route's spike shows up as a
  negative gap on its peer. That is harmless here, because only rising routes are flagged.
- **Some unusual weeks are left unflagged.** A week above its peers but at or below its own recent
  average is reported as `No`, with a note in the reason (e.g. Mumbai-Pune 2025-11-10 inside the creep).

## Project layout

```
run.py, ask.py             CLIs (full run; questions about the results)
costwatch/config.py        every threshold, with its justification
costwatch/metrics.py       weekly cost/tkm, own-history and peer baselines
costwatch/notes.py         note parsing: scope, window, effect (rules + LLM), size
costwatch/retrieval.py     TF-IDF vector index
costwatch/verdict.py       flag rule + note matching → normal / justified / unexplained
costwatch/explain.py       reason text: deterministic prefix, validated LLM paraphrase
costwatch/llm.py           local Qwen wrapper with token accounting
costwatch/qa.py            Q&A over the results with grounding checks
eval/                      labelled set, note labels, evaluate.py, report.md
tests/                     unit tests
scripts/repro_check.py     3-run reproducibility check
output/                    flags.csv, logs, repro runs, Q&A examples
```
