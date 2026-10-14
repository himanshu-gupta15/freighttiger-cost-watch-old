# Q&A examples

Generated with `python ask.py "<question>"` against `output/flags.csv`.

## Q: why did Chennai-Bangalore get pricier in March 2025?

```
For Chennai-Bangalore, March, 2025: 1 week(s) justified by note(s) N001; 2 week(s) flagged as UNEXPLAINED (no supporting note; needs human review).

Evidence:
- Chennai-Bangalore week of 2025-03-03: 3.48/tonne-km, +22.8% vs this route's past average, +32.0% vs similar-length routes this week -> justified by N001. Justified: matches note N001 dated 2025-02-24 (Chennai-Bangalore, in effect 2025-02-24 to 2025-03-08), which covers this week. The note indicates heavy flooding on the Chennai-Bangalore highway from February 24 to March 8 caused longer detours and increased trip costs. This explains the unusual high cost for this week's transport on the route.
- Chennai-Bangalore week of 2025-03-10: 3.57/tonne-km, +22.1% vs this route's past average, +33.8% vs similar-length routes this week -> UNEXPLAINED. Flagged: cost is +22.1% vs this route's past average and +33.8% vs similar routes, with no supporting note. Worth a human review. Notes checked: N001 (2025-02-24) does not count: its window (2025-02-24 to 2025-03-08) does not cover this week (2025-03-10 to 2025-03-16). N009 (2025-03-17) does not count: its window (2025-03-17 to 2025-03-23) does not cover this week (2025-03-10 to 2025-03-16).
- Chennai-Bangalore week of 2025-03-17: 3.47/tonne-km, +13.7% vs this route's past average, +33.5% vs similar-length routes this week -> UNEXPLAINED. Flagged: cost is +13.7% vs this route's past average and +33.5% vs similar routes, with no supporting note. Worth a human review. Notes checked: N001 (2025-02-24) does not count: its window (2025-02-24 to 2025-03-08) does not cover this week (2025-03-17 to 2025-03-23). N009 (2025-03-17) does not count: it does not describe a cost increase (it says "returned to normal").
```

## Q: anything odd on Delhi-Jaipur in November 2024?

```
For Delhi-Jaipur, November, 2024: 2 week(s) flagged as UNEXPLAINED (no supporting note; needs human review).

Evidence:
- Delhi-Jaipur week of 2024-11-11: 4.17/tonne-km, +35.5% vs this route's past average, +21.0% vs similar-length routes this week -> UNEXPLAINED. Flagged: cost is +35.5% vs this route's past average and +21.0% vs similar routes, with no supporting note. Worth a human review. No matching note found for this route or date range.
- Delhi-Jaipur week of 2024-11-18: 4.09/tonne-km, +27.6% vs this route's past average, +19.7% vs similar-length routes this week -> UNEXPLAINED. Flagged: cost is +27.6% vs this route's past average and +19.7% vs similar routes, with no supporting note. Worth a human review. No matching note found for this route or date range.
```

## Q: was the diesel price rise a problem?

```
For weeks where note(s) N003 were checked: 1 week(s) justified by note(s) N003; 1 week(s) flagged as UNEXPLAINED (no supporting note; needs human review).

Evidence:
- Mumbai-Delhi week of 2025-05-12: 2.28/tonne-km, +11.6% vs this route's past average, +6.7% vs similar-length routes this week -> justified by N003. Justified: matches note N003 dated 2025-05-05 (All Routes, in effect 2025-05-05 to 2025-06-29), which covers this week. The note indicates that diesel prices increased nationwide starting this week, which has pushed up transportation costs across all routes by about 5-7%. This explains the unusual high cost per tonne-km observed for this route during the specified period.
- Mumbai-Pune week of 2025-06-23: 3.76/tonne-km, +6.2% vs this route's past average, +20.6% vs similar-length routes this week -> UNEXPLAINED. Flagged: cost is +6.2% vs this route's past average and +20.6% vs similar routes, with no supporting note. Worth a human review. Notes checked: N003 (2025-05-05) does not count: it applies to all routes, so it cannot explain why this route is +20.6% above similar routes that faced the same change.
```

## Q: what happened with Mumbai-Pune costs in December?

```
For Mumbai-Pune, December: 4 week(s) flagged as UNEXPLAINED (no supporting note; needs human review).

Evidence:
- Mumbai-Pune week of 2025-12-01: 4.39/tonne-km, +7.7% vs this route's past average, +37.4% vs similar-length routes this week -> UNEXPLAINED. Flagged: cost is +7.7% vs this route's past average and +37.4% vs similar routes, with no supporting note. Worth a human review. No matching note found for this route or date range.
- Mumbai-Pune week of 2025-12-08: 4.43/tonne-km, +7.2% vs this route's past average, +38.8% vs similar-length routes this week -> UNEXPLAINED. Flagged: cost is +7.2% vs this route's past average and +38.8% vs similar routes, with no supporting note. Worth a human review. No matching note found for this route or date range.
- Mumbai-Pune week of 2025-12-15: 4.39/tonne-km, +4.4% vs this route's past average, +35.5% vs similar-length routes this week -> UNEXPLAINED. Flagged: cost is +4.4% vs this route's past average and +35.5% vs similar routes, with no supporting note. Worth a human review. No matching note found for this route or date range.
- Mumbai-Pune week of 2025-12-22: 4.49/tonne-km, +5.7% vs this route's past average, +38.9% vs similar-length routes this week -> UNEXPLAINED. Flagged: cost is +5.7% vs this route's past average and +38.9% vs similar routes, with no supporting note. Worth a human review. No matching note found for this route or date range.
```

## Q: anything on Kolkata-Bhubaneswar in June 2025?

```
Nothing was flagged or justified for: Kolkata-Bhubaneswar, June, 2025. Every week in that scope was within the normal range.
```
