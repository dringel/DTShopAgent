# HED/UT manipulation-check poll — instrument and procedure

The cohort-measured hedonic/utilitarian classification of the five
active task categories. Runs as a **2-minute in-class poll at the
opening of Session 10** (all four agent runs are scheduled, none of the
day's outcomes are known, and the categories are maximally familiar
from three days of shopping them). It is deliberately a separate micro
instrument: the 115-item course questionnaire stays frozen and the
lockstep suite never sees these items.

## Instrument

Scale: Voss, Spangenberg & Grohmann (2003), the 10-item semantic
differential — five hedonic and five utilitarian item pairs, each rated
on a 7-point scale anchored by the two poles. For **each of the five
active categories** (sneakers, power bank, backpack, laptop, perfume —
read them from the current `tasks_config.csv` if the set changed at
freeze), the student rates the category ("Buying <category> for
yourself is …"):

| Code | Left anchor (1) | Right anchor (7) | Subscale |
|---|---|---|---|
| HU01 | not fun | fun | hedonic |
| HU02 | dull | exciting | hedonic |
| HU03 | not delightful | delightful | hedonic |
| HU04 | not thrilling | thrilling | hedonic |
| HU05 | unenjoyable | enjoyable | hedonic |
| HU06 | ineffective | effective | utilitarian |
| HU07 | unhelpful | helpful | utilitarian |
| HU08 | not functional | functional | utilitarian |
| HU09 | unnecessary | necessary | utilitarian |
| HU10 | impractical | practical | utilitarian |

Item order within a category: hedonic and utilitarian items
interleaved as listed. Category order: the five categories in
`task_id` order for everyone (a 2-minute poll does not warrant
per-student randomization; note this in the methods).

## Build (TA, ~15 minutes, before Friday)

1. Create a separate Google Form titled "DT Lab — category poll"
   (NOT the consumer-profile Form; nothing here touches the frozen
   instrument).
2. First question: participant ID, same `DT2026-###` validation pattern
   as the main Form. No email collection.
3. One page per category: header "Buying <category> for yourself
   is …", then the ten 7-point items titled `HU01.` … `HU10.` (dot
   prefix, same convention as the main Form) with the anchor pairs
   above. All required.
4. Link responses to a Sheet. Test-submit once; delete the test row.

## Run (Session 10, minute 0–3)

Project the Form link/QR at the session open, before the day's runs
start. Phones are fine. Students who miss it can submit until the
dataset freeze; the analyzer handles partial coverage.

## Data association

1. Export the response Sheet as `hedut_responses.csv`. Expected
   columns: the ID column plus, per category page, the ten `HU01.` …
   `HU10.` item columns (the export carries the category page context
   in the header; reshape to long form with columns
   `student_id, task_id, HU01..HU10` — one row per student ×
   category — before handing it to the analyzer; the TA does this
   reshape once, in the sheet or a five-line script).
2. Run the cohort analysis with the poll attached:
   `python3 tools/analyze_cohort.py --zips <folder> --hedut
   hedut_responses.csv`.
3. The analyzer computes per-category hedonic (HU01–HU05) and
   utilitarian (HU06–HU10) subscale means with cluster CIs, reports
   them alongside the category-class analysis, and marks the measured
   scores — not the literature labels — as the classification of
   record. Without the file, the literature-based labels stay in
   place and are labeled as such.

## Reference

Voss, K. E., Spangenberg, E. R., & Grohmann, B. (2003). Measuring the
hedonic and utilitarian dimensions of consumer attitude. *Journal of
Marketing Research, 40*(3), 310–320.
https://doi.org/10.1509/jmkr.40.3.310.19238
