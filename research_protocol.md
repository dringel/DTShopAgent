# Research protocol — Digital Twin Shopping Agent Lab
**Data schemas, pseudonymization, consent, and cohort dataset assembly**
Version: dtlab-protocol-v1 (July 2026)

## 1. What the study yields

Per participant (N = cohort size), the design produces a paired-choice dataset:

| Unit | Variables |
|---|---|
| Participant | 115 coded questionnaire items (dtlab-persona-v1; authoritative source: `questionnaire_instrument_source.md` — 15 demographics, 57 validated-scale items from 12 published scales per the Toubia et al. 2025 Twin-2K-500 battery selections, 22 amazon.in shopping-behavior items, 12 values/constraints of which VC01–VC05 are CONSTRAINT items, 9 predictive items); purchase profile as agent-extracted `purchase_profile.md` (traceable-claims rule in SOUL.md; precise dtlab-orders-v1 CSV only for the optional post-course export add-on subgroup); demographics |
| Participant × session | human shopping-process clickstream (dtlab-humanlog-v1.3): search queries, product views (ASIN + dwell sequence), cart-add clicks, filters/sorts — captured passively by log_human_session.py BEFORE the agent runs |
| Task × participant (5 per participant; categories + count from tasks_config.csv) | human pick made first (uncontaminated: the student never sees the agent before choosing) (title, ASIN, price, stated reasoning), agent pick (title, ASIN, price), agent decision log with item-code citations, sponsored-listing flag, human intervention count, student's better/identical/equivalent/inferior verdict (dtlab-verdicts-v1) |

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
participants are human-first. The agent then runs the SAME task set four
times: grounding (persona = questionnaire + purchase profile vs. ablated
= purchase profile only; persona files physically removed and an ablated
SOUL swapped in for ablated runs) × model tier (economy / Claude Haiku
class on day 1 vs. frontier / Claude Sonnet class on day 2). Grounding
order is counterbalanced within each day (per-day P_FIRST/NP_FIRST,
stratified by section); tier is deliberately confounded with day — the
course's "will a better model do better?" arc — and is stated as such;
the within-day run-order estimate from the counterbalanced grounding
order bounds plausible day-order effects. All four runs are verdicted
against the same pre-registered human picks, with per-task head-to-heads
and pick-overlap measures across runs. Enforcement is mechanical: the
packer verifies one run per cell, verdicts for all runs, and the
**manipulation check** (an ablated run's decision log must cite zero
persona item codes); condition, tier, order, head-to-heads, and overlap
are recorded in the manifest. The earlier H_FIRST/A_FIRST order-arm
factor is retired: the primary estimands (questionnaire effect, tier
effect) are within-participant contrasts across runs that share the same
human-perturbed account, so human-session carry-over common to all runs
cancels in those contrasts; the absolute agreement level carries the
contamination index (computed per run) as covariate. **Assessment
blinding:** no participant watches their own agent — self-selected pairs
swap seats for every run (PERSONALIZATION_PROTOCOL.md Layer 4); owners
first meet their agent's choices as artifacts when writing the
comparison memo. Consent notes: the partner sees the owner's purchase
profile and picks during runs; ablated runs are blind to CONSTRAINT
items (harmless under add-to-cart-only; violations become a measured
outcome). All Anthropic model settings remain at defaults (agent runs
are interactive tool-use sessions, not elicitation calls).

The agent-side treatment is the **Evidence-Citation Protocol (ECP)**,
implemented in `agent/SOUL.md`: every candidate rejection and selection
must cite a persona item code or the agent's own purchase profile, plus
an explicit anti-stereotyping rule (no preferences inferred from
demographic group membership). Full definition and design rationale:
`questionnaire/questionnaire_instrument_source.md` §1.

This supports at minimum: PROCESS comparison between human and agent
shopping (consideration-set size and overlap, query formulation, search
depth, dwell allocation, sponsored exposure) — arguably the most novel
contribution, since outcome agreement with divergent processes and process
mimicry with divergent outcomes are entirely different twin properties;
human–agent agreement rates by task type (with the per-participant
contamination index from each manifest as a covariate — see
PERSONALIZATION_PROTOCOL.md); price-delta
analysis; sponsored-capture analysis; the identical-vs-equivalent split (exact
product convergence vs. functional substitution) as a twin-fidelity
measure; which questionnaire constructs predict
agreement (feature-importance on persona items); stated-vs-revealed preference
conflicts and how the agent resolved them; and citation-fidelity analysis
(are the agent's cited profile facts real or confabulated — connect to your
GenAI quality-assurance metascience agenda).

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
- **Jurisdiction.** The cohort sits at BITSoM (Mumbai, India): the
  operative data-protection regime is India's **Digital Personal Data
  Protection Act (DPDP) 2023** — purchase history, questionnaire answers,
  and the clickstream are personal data; lawful basis = consent obtained
  as above (specific, informed, withdrawable); the instructor's
  institution acts as data fiduciary and minimization/pseudonymization
  are implemented in the pipeline. Obtain approval through BITSoM's (or
  the host institution's) ethics process, plus the instructor's home IRB
  (UNC) if required for the research use. Keep GDPR language only if EU
  exchange students are expected in the cohort; verify at term start.

## 4. Data-minimization guarantees (implemented in code)

- `clean_privacy_export.py` / `scrape_orders.py` write ONLY:
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
   (the provenance sidecars give you capture-method covariates).
3. Build `cohort_choices.csv` by joining each zip's `agent_picks.csv`,
   `human_picks.csv`, and manifest verdicts (all machine-readable); only
   `cited_codes` / `citation_valid_share` require coding from the decision
   logs, and those follow the numbered SOUL.md protocol.
4. Join on `student_id` + task number. Freeze, hash, archive.
5. For the class debrief (not the frozen research dataset):
   `tools/analyze_cohort.py --zips <folder-of-zips>` reads every
   manifest + CSV directly and renders the cohort report (verdicts by
   task and agent type, CIs, head-to-head, overlap, ratings, price/brand
   alignment, contamination, data quality). It is a reporting view over
   the same machine-parsed fields; the frozen dataset above remains the
   analysis-of-record.

## 6. Schema registry

- `dtlab-persona-v1`: student_id, item_code, construct, question, answer,
  constraint {0|1}. Codes/constructs are defined by the 115-item
  instrument (`questionnaire_instrument_source.md` is the authoritative
  source; `questionnaire_items.csv` its machine transfer); the instrument
  is frozen at Form launch and versioned thereafter.
- `dtlab-orders-v1`: student_id, order_date, brand_guess[/brand,
  brand_source], product_title, asin, unit_price_inr, quantity,
  capture_method.
- `dtlab-humanlog-v1.3` (JSONL events): ts, student_id, type
  {session_start|search|product_view|cart_add|filter_sort|nav|session_end},
  plus type-specific fields (query/page/sort; asin/title). v1.1 adds
  `category` (the product page's breadcrumb) to product_view; v1.2 adds
  `ref` (the amazon ref= slug of the view — the surface the click came
  from, bucketed by the analyzer into the same provenance buckets as
  the agent's CAND source= field); v1.3 adds the task_start/task_end
  markers of the guided one-task-at-a-time session. All additive, older
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
  (1–10), rationale (one-line free text), verdict_at_utc (capture
  timestamp per row). **Capture is BLIND:** each task presents the runs'
  picks in a per-task randomized order labeled Run A–D (order derived
  from sha256(student|task|run), reproducible); condition and tier are
  never shown before a verdict is stored and are resolved into the CSV
  post-hoc — the manifest records `verdicts_captured_blind`. Pairwise
  head-to-heads are asked against the same blind labels and resolved the
  same way; the label→run mapping is revealed only after capture, before
  the Overall reflections (which reference tiers by design).
  Head-to-heads and the Overall reflections are captured in the same
  session (overall_reflections.md); all verdict artifacts live in
  `~/dtlab/verdicts/`, outside the agent workspace.
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
- `dtlab-choices-v1` (coded from logs): student_id, task_id, chooser
  {human|agent}, asin, title, price_inr, sponsored {0|1}, n_candidates,
  n_interventions, verdict {better|identical|equivalent|inferior} (agent choice relative to the participant's own pre-registered pick; 'identical' is ASIN-verified by the packer, so it is an objective category while the other three are the participant's judgment), cited_codes
  (pipe-list), citation_valid_share (0–1). The questionnaire-ablation
  factor is adopted (plan of record); the operative schema is
  `dtlab-choices-v1.1`, adding `condition`
  {persona|ablated|single} and, per participant × task, `hth_winner`
  {persona|ablated|tie} from the manifest's `ablation.head_to_head`.

Version any change; never mutate a frozen schema.
