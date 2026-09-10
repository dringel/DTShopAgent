# Research protocol — Digital Twin Shopping Agent Lab
**Data schemas, pseudonymization, consent, and cohort dataset assembly**
Version: dtlab-protocol-v1 (July 2026)

## 1. What the study yields

Per participant (N = cohort size), the design produces a paired-choice dataset:

| Unit | Variables |
|---|---|
| Participant | 115 coded questionnaire items (dtlab-persona-v1; authoritative source: `questionnaire/questionnaire_instrument_source.md` — 15 demographics, 57 validated-scale items from 12 published scales per the Toubia et al. 2025 Twin-2K-500 battery selections, 22 amazon.in shopping-behavior items, 12 values/constraints of which VC01–VC05 are CONSTRAINT items, 9 predictive items); purchase profile as agent-extracted `purchase_profile.md` (traceable-claims rule in SOUL.md; precise dtlab-orders-v1 CSV only for the optional post-course export add-on subgroup); demographics |
| Participant × session | human shopping-process clickstream (dtlab-humanlog-v1.5): search queries, product views (ASIN + view-sequence timestamps — not full dwell instrumentation), cart-add clicks, filters/sorts, task boundaries — captured passively by log_human_session.py BEFORE the agent runs; one committed attempt |
| Task × participant (5 per participant; categories + count from tasks_config.csv) | human pick made first (uncontaminated: the student never sees the agent before choosing) (title, ASIN, price, stated reasoning), agent pick (title, ASIN, price), agent decision log with item-code citations, sponsored-listing flag, partner-recorded intervention counts per run, student's better/identical/equivalent/inferior verdict (dtlab-verdicts-v2, captured blind in one Friday session) |

**Design (plan of record): a within-participant 2×2 across four agent
runs.** The task set is five self-purchase categories from the
11-category catalog (tasks_config.csv; gift and replenishment frames
retired — buying for a third party and habitual replenishment are
different research questions). **Task order is randomized across
participants and held constant within participant** (derived
deterministically from the pseudonym; dtlab-start enforces it by
re-ordering tasks.md, the packer records the executed order): what an
agent picks in one category can influence the next, so order is
neutralized across the cohort while every within-participant contrast
compares runs that faced the identical sequence. Every participant
shops the task set once themselves
(Wednesday), committing their picks before any agent run — all
participants are human-first. Before any treatment run, the agent
writes the participant's **purchase profile once, in a dedicated
questionnaire-blind bootstrap session** (persona files held, dedicated
bootstrap SOUL); the profile is then frozen read-only, hash-verified at
every run start, and shared by all four runs, so revealed-preference
grounding is identical — and persona-uncontaminated — in every cell.
The agent then runs the SAME task set four
times: grounding (persona = questionnaire + purchase profile vs. ablated
= purchase profile only; persona files removed from the agent's
workspace and quarantined, an ablated SOUL swapped in, and every run
launched in a fresh per-run Hermes home so no memory or session state
crosses runs) × model tier (economy / Claude Haiku class vs. frontier /
Claude Sonnet class). **Tier order is counterbalanced across days at the
participant level** (half of each section runs economy on day 1 and
frontier on day 2, the other half the reverse, per the counterbalance
sheet), so the tier contrast is identified separately from the day;
the day effect itself is estimable as an exploratory contrast. Grounding
order is counterbalanced within each day (per-day P_FIRST/NP_FIRST,
stratified by section, orthogonal to tier order); the within-day
run-order estimate from the counterbalanced grounding order bounds
plausible order effects. All four runs are verdicted
against the same pre-registered human picks, with per-task head-to-heads
and pick-overlap measures across runs. Enforcement is mechanical: the
launcher writes each run's exact model configuration and instruction
file into that run's Hermes home and fails closed on any mismatch; the
packer verifies one run per cell, verdicts for all runs, the per-run
instruction-token check (the decision log must open with the loaded
SOUL variant's protocol token), and the
**manipulation check** (an ablated run's decision log must cite zero
persona item codes); condition, tier, order, per-run context and
configuration hashes, head-to-heads, and overlap
are recorded in the manifest. The earlier H_FIRST/A_FIRST order-arm
factor is retired: the primary estimands (questionnaire effect, tier
effect) are within-participant contrasts across runs that share the same
human-perturbed account, so human-session carry-over common to all runs
cancels in those contrasts; the absolute agreement level is read
against the per-run contamination index and its cross-student
permutation baseline (robustness subgroup, never a regression
covariate). **Assessment
blinding:** no participant watches their own agent — self-selected pairs
swap seats for every run (PERSONALIZATION_PROTOCOL.md Layer 4) — and all
verdicts are captured in **one blind Friday session** after run 4: each
task presents the four runs' picks under randomized Run A–D labels, so
neither grounding nor tier is knowable at judgment time; stored verdicts
are immutable (corrections are append-only, TA-authorized, and
timestamped separately), and the label→run mapping is revealed only
after every verdict and head-to-head is on file. Consent notes: the
partner sees the owner's purchase
profile and picks during runs; ablated runs are blind to CONSTRAINT
items (harmless under add-to-cart-only; violations become a measured
outcome). All Anthropic model settings remain at defaults (agent runs
are interactive tool-use sessions, not elicitation calls); the exact
model ID per run is pinned before the course, written into each run's
configuration, and recorded in the manifest.

### Hypotheses and primary endpoints

The confirmatory family is exactly three within-participant contrasts,
all on the primary DV, the **acceptable-pick rate** — the share of
tasks whose verdict is better/identical/equivalent (the quality
metric):

- **H1 — grounding:** persona vs. ablated acceptable-pick rate.
- **H2 — tier:** frontier vs. economy acceptable-pick rate. Tier order
  is counterbalanced across days at the participant level, so this
  contrast is identified separately from the day; the day-2 − day-1
  difference is reported as an exploratory contrast alongside it.
- **H3 — grounding × tier:** the questionnaire effect differs between
  tiers, computed from matched participant × task records that carry
  all four cells (the interaction is formed within task and participant
  first, then averaged — never from cell means over differing task
  subsets), with complete-cell coverage reported.

Holm-Bonferroni adjustment applies to exactly this family {H1, H2, H3}
and to nothing else; confirmatory p-values are student-level sign-flip
permutation tests on per-participant mean differences (participants are
the exchangeable units), reported next to cluster-bootstrap CIs. Every
other quantity the analyzer reports —
head-to-heads, sponsored capture, price fidelity, satisfaction, order
and position effects, day effect, subgroup splits — is exploratory,
unadjusted, and labeled as such in the report. The secondary
descriptive metric is
the **agreement/fidelity rate** — identical/equivalent verdicts only
(did the twin converge on or substitute the human's choice) — reported
alongside the quality metric, never adjusted.

**Missing data (pre-specified).** The primary analyses use complete
pairs (H1, H2) and complete four-cell records (H3); a pair or cell
drops when a run's verdict is missing or invalid. The analyzer reports
missingness and validation failures broken down by condition and tier
(the selection-gradient check: if one cell fails more often, its
contrast inherits a selection risk and is flagged), plus one
sensitivity row recomputing H1 on participants with all four cells.
Submissions with validation issues are quarantined from the
confirmatory set by default; every exclusion is listed with a
machine-readable reason, and overrides happen only through an explicit,
report-echoed decisions file. Alternative missingness handling is
sensitivity analysis, never primary.

The agent-side treatment is the **Evidence-Citation Protocol (ECP)**,
implemented in `agent/SOUL.md`: every candidate rejection and selection
must cite a persona item code or the agent's own purchase profile, plus
an explicit anti-stereotyping rule (no preferences inferred from
demographic group membership). Full definition and design rationale:
`questionnaire/questionnaire_instrument_source.md` §1.

This supports at minimum: PROCESS comparison between human and agent
shopping (consideration-set size and overlap of logged agent candidates
vs observed human product views — two different measurement processes,
named as such in the report; query formulation; search depth;
view-sequence timing; sponsored share of the agent's candidates and
picks, self-logged and spot-checkable against screenshots — the human
log carries no sponsored flag) — arguably the most novel
contribution, since outcome agreement with divergent processes and process
mimicry with divergent outcomes are entirely different twin properties;
human–agent agreement rates by task type (with the per-run
contamination index from each manifest read against its permutation
baseline — see PERSONALIZATION_PROTOCOL.md); price-delta
analysis; sponsored-capture analysis; the identical-vs-equivalent split (exact
product convergence vs. functional substitution) as a twin-fidelity
measure; which questionnaire constructs predict
agreement (feature-importance on persona items); stated-vs-revealed preference
conflicts and how the agent resolved them; and citation-fidelity analysis
(are the agent's cited profile facts real or confabulated — connect to your
GenAI quality-assurance metascience agenda).

## 1a. Design and analysis decisions of record (10 September 2026)

Recorded here because the code implements them and later readers will
otherwise infer the wrong intent from §1, which still describes the
retired 2x2 as the plan of record.

**The design is THREE grounding conditions on one fixed tier.** Every
run is Claude Haiku class. The three twins are `persona` (questionnaire
+ purchase history), `ablated` (purchase history only, questionnaire
removed from the workspace), and `nohistory` (questionnaire only,
frozen purchase profile removed from the workspace). Both factors off
is refused. The model-tier factor of the 2x2 is retired; the frontier
tier survives only as an optional extra run and is not part of any
contrast. `pack_evidence.py` records this as `design: "3cond"`.

**The history effect is NOT pre-registered — instructor decision
(Ringel, 10 Sept).** The confirmatory family stays as it was; the
history contrast (persona − nohistory, reported as H1b) is EXPLORATORY
by choice, not by oversight, and must be reported as such. This is a
deliberate decision taken BEFORE the data was seen, and it is recorded
here with its date for exactly that reason.

**What this does NOT mean:** `nohistory` runs are collected, packed,
exported and charted like any other condition. Pre-registration status
governs how a contrast is REPORTED, never whether its rows reach the
dataset. Dropping the third twin from an export would delete a third of
the design; `analyze_cohort.py` includes all three grounding conditions
in `dtlab-runs-v1` and `dtlab-cells-v1`.

### The across-student outcome table (Ringel, 10 September)

The primary across-student result is a grid of **category x twin**
cells: 5 product categories x 3 twins = **15 cells**. Within each cell
sits one distribution over the four-level ordinal scale the student
gave — `better`, `identical`, `equivalent`, `inferior` — as counts. A
bar chart per cell; 15 charts.

Worked shape (illustrative numbers): for backpacks, the persona twin
might be 70 better / 30 identical / 30 equivalent / 21 worse. The same
category under a different twin gives a different distribution, and the
same twin across categories gives another.

**These are BASE COUNTS, and they are the deliverable of this step.**
Significance testing — differences in distributions or shares between
twins within a category, or across categories — is a SEPARATE second
step performed on this table. It is deliberately not folded into the
export, so the counts can be inspected and agreed before any test is
chosen.

Produced by:

```
python3 tools/analyze_cohort.py --zips <dir> --export-cells cells.csv
```

`dtlab-cells-v1` columns: `task_id, category_class, twin, verdict, n,
n_students, share`. The grid is zero-filled — an unobserved verdict
level is a row with `n = 0`, never a missing row, so no cell can
silently understate its denominator.

## 2. Pseudonymization

- Each student receives a course-issued ID: `DT2026-###`. The ID ↔ name
  mapping lives in ONE file, held by the instructor, stored separately from
  all research data, deleted at end of study.
- Every artifact (questionnaire row, purchase CSV, decision log, evidence
  pack) carries only the pseudonym. Scripts enforce this: `student_id` is a
  required argument and the Form validates the ID pattern.
- The Google Form collects institutional email for submission integrity;
  before analysis, export the response sheet, verify one-row-per-ID, then
  DELETE the email column from the research copy.

## 3. Consent and opt-out

- The instrument includes sensitive-category items (religion D09/D10,
  political views D12, family income D11, sex assigned at birth D04);
  each carries an explicit "Prefer not to say" opt-out, and the consent
  sheet must name these categories and the opt-out. (Relevant to DPDP/
  ethics review; D10's opt-out was added by instructor decision
  2026-07-22.)
- Written information sheet + consent BEFORE the questionnaire opens.
  Consent covers: (a) use of pseudonymized questionnaire responses,
  purchase-history extracts, and agent logs for research and potential
  publication; (b) that participation in the *course exercise* is required
  but inclusion in the *research dataset* is optional and separable;
  (c) right to withdraw data until the anonymization/analysis date. The
  consent sheet must explicitly cover the shopping-session clickstream
  (what is captured, what is excluded, that it stays local until packed).
- **Partner-pairing disclosure.** The universal assessment-blinding
  protocol (PERSONALIZATION_PROTOCOL.md Layer 4) means a classmate
  babysits every one of your agent runs and sees your agent narrate
  your purchase profile and picks. That is a real disclosure of
  personal shopping data to a peer and the consent sheet must name it
  explicitly. Pairs are self-selected (students choose a partner they
  are comfortable with); a student who prefers not to pair may request
  a TA babysitter instead, without explanation or grade impact.
- Non-consenting or opt-out students use the synthetic persona pack; their
  course grade is unaffected and their data never enters the dataset.
- **Jurisdiction and governance.** The cohort sits at BITSoM (Mumbai,
  India): collection happens in India, where the **Digital Personal
  Data Protection Act (DPDP) 2023** applies as its provisions enter
  into force under the phased commencement schedule — purchase history,
  questionnaire answers,
  and the clickstream are personal data; lawful basis = consent obtained
  as above (specific, informed, withdrawable). The instructor teaches
  as an **independent external instructor contracted by BITSoM** (not
  BITSoM faculty), operating as a sole-proprietor firm based in
  Germany, and conducts the research in his own
  academic capacity. He is the **data controller**; the pseudonymized
  dataset is transferred to and processed in Germany, where the
  **GDPR governs the processing**, and data-subject rights run for as
  long as the pseudonym mapping exists (after its destruction the
  dataset carries no direct identifiers and continues to be handled as
  pseudonymized research data). The governance instruments of this
  protocol are documented informed consent, code-enforced minimization
  and pseudonymization, and the external determinations recorded at
  term start: [BITSoM institutional determination], [independent ethics
  review], and [privacy/data-transfer advice for the controller
  structure]. This protocol reports those determinations; it does not
  substitute for them.
- **Consent instrument and capture points.** The student-facing sheet is
  `docs/CONSENT_AND_DATA_USE.md` (released in Session 6, walked through
  in class before the Form opens). It carries the two confirmations —
  (1) *understanding*: the agent browses and acts, add-to-cart only, on
  the student's own logged-in amazon.in account, and questionnaire /
  purchase-history profile / clickstream / agent logs / verdicts are
  collected under pseudonym and submitted once for anonymized analysis;
  (2) *consent*: pseudonymized data is used in the research the class
  conducts together, the anonymized cohort report is returned to the
  class, no other student receives access to anyone's data, and the
  instructor retains the anonymized dataset for scientific research and
  potential aggregate publication. Capture is layered: two required
  checkboxes at the top of the Form (timestamped with the response), a
  one-time typed AGREE acknowledgment in `dtlab-start` before the first
  real agent run (recorded in the evidence pack's manifest), and the LMS
  release acknowledgment.

## 4. Data-minimization guarantees (implemented in code)

- `clean_privacy_export.py` writes ONLY:
  `student_id, order_date, brand, product_title, asin, unit_price_inr,
  quantity, capture_method` (+ provenance sidecar). Order IDs, addresses,
  payment data, and carrier data never reach the workspace or the dataset.
- `student_start.sh` refuses to launch if raw export files or PII-named
  files sit in the agent workspace.
- API keys belong to the students' own Anthropic accounts. Each account
  carries a personal monthly spend limit (~$20, set during the Monday
  checklist and confirmed at pre-flight); the key lives only in the
  student's 600-permission env file, is content-redacted from every
  packed artifact by `dtlab-pack`, and the student can delete it from
  their Console the moment the course ends.

## 5. Cohort dataset assembly (instructor, after Friday submissions close)

Students submit ONE zip via the **BITSoM LMS** file-upload assignment:
`DT2026-###_evidence.zip`, produced and validated by `dtlab-pack`
(tools/pack_evidence.py). The TA bulk-downloads all submissions into one
folder; LMS bulk downloads may rename the files (name/ID prefixes) —
harmless, because identity resolves from the zip's internal
`DT2026-###/` root and the manifest, never the filename. It contains all seven
deliverables plus `manifest.json` (SHA-256 hashes, validation results,
extracted verdicts) and `report.html` (grader view). Screen recordings are optional evidence (the partner-blinding protocol,
parsed cart contents, and Hermes transcripts already cover the trail);
when made, they are uploaded separately due to size and indexed in the
zip's RECORDINGS.txt.

Assembly steps:
1. Concatenate all `persona_survey.csv` → `cohort_personas.csv`.
2. Collect all `purchase_profile.md` files (deliverable #2). Only if the
   optional post-course add-on ran for a validation subsample:
   concatenate those students' `purchase_history.csv` → `cohort_orders.csv`
   (with their provenance sidecars).
3. Export the run-level analysis table: `tools/analyze_cohort.py
   --export-runs cohort_runs.csv --export-hth cohort_hth.csv`
   (schema `dtlab-runs-v1` / `dtlab-hth-v1`, §6) — one record per
   participant × task × run, joined from each zip's picks files and
   manifest; only
   `cited_codes` / `citation_valid_share` require coding from the decision
   logs, and those follow the numbered SOUL.md protocol.
4. Join on `student_id` + task number. Freeze, hash, archive. Zips
   quarantined by the homogeneity and validity gates (mismatched
   config/instrument hashes, validation issues, duplicate IDs) stay out
   of the frozen confirmatory dataset; the quarantine list and reasons
   are archived with it.
5. For the class debrief (not the frozen research dataset):
   `tools/analyze_cohort.py --zips <folder-of-zips>` reads every
   manifest + CSV directly and renders the cohort report (verdicts by
   task and agent type, CIs, head-to-head, overlap, ratings, price/brand
   alignment, contamination, data quality). It is a reporting view over
   the same machine-parsed fields; the frozen dataset above remains the
   analysis-of-record. Metric names are fixed: **acceptable-pick rate**
   = better/identical/equivalent (quality, the primary DV of H1–H3);
   **agreement/fidelity rate** = identical/equivalent only (secondary,
   descriptive) — the analyzer and this protocol use them identically.

## 6. Schema registry

- `dtlab-persona-v1`: student_id, item_code, construct, question, answer,
  constraint {0|1}. Codes/constructs are defined by the 115-item
  instrument (`questionnaire/questionnaire_instrument_source.md` is the authoritative
  source; `questionnaire_items.csv` its machine transfer); the instrument
  is frozen at Form launch and versioned thereafter.
- `dtlab-orders-v1`: student_id, order_date, brand_guess,
  product_title, asin, unit_price_inr, quantity, capture_method.
- `dtlab-humanlog-v1.5` (JSONL events) — the authoritative event
  registry: ts, student_id, type
  {session_start|search|product_view|cart_add|filter_sort|nav|
  task_start|task_end|session_end},
  plus type-specific fields (query/page/sort; asin/title; task_id on
  the task markers). v1.1 adds
  `category` (the product page's breadcrumb) to product_view; v1.2 adds
  `ref` (the amazon ref= slug of the view — the surface the click came
  from, bucketed by the analyzer into the same provenance buckets as
  the agent's CAND source= field); v1.3 adds the task_start/task_end
  markers of the guided one-task-at-a-time session; v1.4 adds
  listing-grid cart_add capture; v1.5 adds `attempt_id` (the human
  session is one committed attempt — a rerun requires a TA reset,
  prior attempts are archived append-only, and the packer validates
  exactly one committed attempt). All additive, older
  parsers unaffected. Checkout, payment, and auth paths are never logged;
  non-amazon browsing is never logged.
- `dtlab-candidates-v1` (machine-parsed from decision logs by the
  packer, per the ECP's mandatory `CAND |` line format): per run ×
  task, list of {asin, category, price, sponsored, source=search#rank}.
  Lands in `manifest.json.candidates`; enables consideration-set size
  and agent-vs-human search-overlap (process comparison) without any
  human coding. Agent non-compliance is a recorded warning, not a pack
  failure.
- `dtlab-searches-v1` (machine-parsed `SRCH |` lines, same mechanism):
  per run × task, list of {query, filters} — every search the agent
  ran, verbatim, with any filters/sort applied. Lands in
  `manifest.json.searches`; non-compliance is a warning.
- Process-length block (`manifest.json.process`): human {duration_min,
  searches, product_views, filter_sorts, cart_adds, per_task — per
  task {minutes, searches, product_views, filter_sorts}, plus an
  `attribution` field}. dtlab-shop walks the student through the
  tasks ONE AT A TIME in their assigned order and stamps
  task_start/task_end events (humanlog v1.3), so per-task attribution
  is EXACT by construction (`attribution: task_markers`); for logs
  without markers the timestamped clickstream is segmented at the
  cart-add events along the assigned order instead
  (`cart_add_segments`, approximate, requires exactly one cart-add
  per task). Per-run agent {duration_min: started_at → last write of
  the run's picks file}. Per-task AGENT timing requires the Hermes
  transcript timestamps (dry-run item; the transcripts are packed
  either way).
- `dtlab-verdicts-v2` (written by the guided `dtlab-verdict` prompt;
  supersedes v1 additively): student_id, task_id, condition
  {persona|ablated}, tier {economy|frontier}, verdict
  {better|identical|equivalent|inferior} ('identical' ASIN-verified by
  the packer), rating_self (1–10, one judgment per task), rating_agent
  (1–10), rationale (one-line free text), verdict_at_utc (set once, at
  first store). **Capture is BLIND and happens in ONE Friday session
  after run 4:** each task presents the four runs'
  picks in a per-task randomized order labeled Run A–D (order derived
  from sha256(student|task|run), reproducible); with tier order
  counterbalanced across days, neither condition nor tier is knowable
  at judgment time; both are resolved into the CSV
  post-hoc — the manifest records `verdicts_captured_blind` and
  `single_session`. **Stored rows are immutable:** re-running the tool
  never re-elicits or overwrites a stored verdict, rating, or
  timestamp; corrections are appended to `verdicts_amendments.csv`
  (row key, new value, reason, TA authorization, amended_at_utc) with
  the original untouched, and the analyzer applies amendments last-wins
  while reporting their count. Pairwise
  head-to-heads are asked against the same blind labels and resolved the
  same way; the label→run mapping is revealed only after every verdict
  and head-to-head is on file, before
  the Overall reflections (which reference tiers by design and run
  last, post-reveal).
  Head-to-heads and the Overall reflections are captured in the same
  session (overall_reflections.md); all verdict artifacts live in
  the quarantine root (`~/dtlab/quarantine/verdicts/`), outside the
  agent workspace and outside every path an agent run receives.
- Cart ground truth: `cart_runN.json` per run (asin, title,
  unit price, qty — parsed from the live cart by `dtlab-cart`), cross-
  checked against `agent_picks.csv` at pack time (`cart_verified` per
  run in the manifest).
- Task structure: `tasks_config.csv` (task_id, frame, product_type,
  category_class {utilitarian|hedonic}, budget range) — packed into
  every zip's config_snapshot; the analysis reads it from there, so the
  dataset is self-describing under any task set. Per-participant task
  order: `manifest.task_order` (executed, parsed from tasks.md) and
  `task_order_expected` (derived from the pseudonym via per-task
  SHA-256 ranking — the same function in student_start.sh,
  log_human_session.py, and pack_evidence.py).
- `dtlab-runs-v1` — **the operative run-level analysis schema of the
  2×2**: one record per participant × task × run, carrying student_id,
  run, day, run_order_in_day, condition {persona|ablated}, tier
  {economy|frontier}, model_id, provider, hermes_version, verdict,
  rating_self, rating_agent, rationale (redacted), verdict_at_utc,
  amended {0|1}, agent_asin, agent_price, human_asin, human_price,
  sponsored, n_candidates, n_searches, contamination_index, task_id,
  task_position, category_class, tasks_config_sha256, soul_sha256,
  config_sha256, purchase_profile_sha256, instrument_version,
  kit_version, sensitive_items_excluded, verdicts_captured_blind.
  Exported by the analyzer (`--export-runs`); H1–H3 are exactly
  reconstructable from this table alone. Mixed schema generations are
  rejected by default.
- `dtlab-hth-v1`: the blind pairwise judgments as their own table —
  student_id, task_id, contrast {grounding_economy|grounding_frontier|
  tier_persona|tier_ablated}, winner (resolved from the blind labels
  post-hoc). Exported alongside the runs table (`--export-hth`).
- `dtlab-choices-v1` / `dtlab-choices-v1.1` (legacy, retained for
  packs from earlier design generations): student_id, task_id, chooser
  {human|agent}, asin, title, price_inr, sponsored {0|1}, n_candidates,
  n_interventions, verdict {better|identical|equivalent|inferior} (agent choice relative to the participant's own pre-registered pick; 'identical' is ASIN-verified by the packer, so it is an objective category while the other three are the participant's judgment), cited_codes
  (pipe-list), citation_valid_share (0–1); v1.1 adds `condition`
  {persona|ablated|single} and `hth_winner`. It cannot carry the full
  four-cell design — `dtlab-runs-v1` supersedes it for the 2×2.

Version any change; never mutate a frozen schema.
