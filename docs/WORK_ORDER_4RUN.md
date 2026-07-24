# Work order — four-run 2×2 support (grounding × tier)

**For:** Claude Code, working in this repo. **Status of this document:**
IMPLEMENTED 2026-07-23, all suites green — kept as the spec of record
for the change (see the matching docs/CHANGELOG.md entry). The
"still open" list at the bottom is closed except N4 (commit/push —
the instructor's call).

**Context.** The plan of record (COURSE_PLAN_1WEEK.md,
research_protocol.md §1) is a within-student 2×2: every agent runs the
task set FOUR times — grounding (persona | ablated) × tier (economy on
day 1 | frontier on day 2) — with per-day counterbalanced grounding
order, universal partner-blinding, all students human-first. Current
tooling supports exactly TWO runs (`runs/run1`, `runs/run2`, condition
∈ {persona, ablated}). Extend it to four without weakening any existing
guard. The docs are already written to the target design; this order
closes the code gap.

## 1. `provisioning/student_start.sh`

- Run bookkeeping: `~/dtlab/runs/run1..run4`, each with `condition.txt`
  (persona|ablated), `tier.txt` (economy|frontier), `started_at.txt`.
- Day logic: runs 1–2 = economy, runs 3–4 = frontier (constants in
  `dtlab_config.env`: `DTLAB_DAY1_TIER='economy'`,
  `DTLAB_DAY2_TIER='frontier'`, overridable). Prompt once per day for
  that day's grounding order (`persona_order_day1.txt`,
  `persona_order_day2.txt` — per-day P_FIRST/NP_FIRST from the LMS
  sheet); derive each run's condition from day order + run index.
- Reuse the existing state machine per pair of runs: archive the
  previous run's `decision_log.md` + `agent_picks.csv` into its run dir
  before the next run; persona files hold/restore per condition; SOUL
  swap per condition (unchanged mechanics, now four transitions).
- **Friday gate:** before run 3, require fresh confirmation of the
  browsing-history re-pause (the 1-day pause has lapsed) — same
  self-attest pattern as the existing gate.
- Crash-resume prompts must name the run number and condition ("resume
  run 3 (frontier, ablated)?").
- Retire the legacy per-student `TIER_FACTOR` prompt (tier is per run
  now); keep `~/dtlab/tier.txt` writing for backward compatibility but
  the packer should prefer per-run tier files.
- Retire the H_FIRST/A_FIRST arm prompt and ordering branches: ALL
  students are human-first. Pre-flight hard-requires
  `human_picks.csv` + `human_session.jsonl` before ANY agent run. Keep
  writing `arm.txt` as `H_FIRST` for manifest backward compatibility.

## 2. `tools/pack_evidence.py`

- Ablation detection generalizes: any of `runs/run1..run4` present.
  Stage every existing run dir (copy, never move; adopt workspace
  leftovers into the highest-numbered started run, as today).
- Validation per existing run: 3 picks with valid ASINs, decision log
  present, condition + tier recorded. A missing run is a validation
  ISSUE naming the run; the pack still builds (partial packs are data —
  see the run-stall risk row in COURSE_PLAN).
- Verdict keys become `"{task}_{condition}_{tier}"` (e.g.
  `1_persona_economy`); comparison sections are headed
  `## Task N (persona run, economy)` etc. — extend the anti-cascade
  per-section parser and the template accordingly. Ratings keyed the
  same way.
- Head-to-head lines, machine-parsed, one block per contrast:
  `Task N winner (economy): persona|ablated|tie`,
  `Task N winner (frontier): persona|ablated|tie`,
  `Task N better model (persona): frontier|economy|same`,
  `Task N better model (ablated): frontier|economy|same`.
- Manipulation check runs against BOTH ablated logs.
- Contamination index computed per run (keyed condition_tier).
- `ablation` manifest block: per-run {condition, tier, started_at},
  per-day grounding order, the four head-to-head maps, pick-overlap
  sets (persona vs ablated within tier; economy vs frontier within
  grounding), manipulation-check results.
- Cart evidence: expect `cart_run1..4.png` in `~/dtlab/evidence/`
  (missing shots = issue naming the run).
- `parse_candidates` already tolerates arbitrary `source=` strings —
  add a normalizer that buckets provenance into
  {search, carousel, buy_again, product_page_link, category_page,
  other} and store both raw and bucket.
- Env metadata: record per-run model IDs if Hermes exposes them
  (`DTLAB_MODEL_ID_DAY1/2` fallback).

## 3. Templates + `tools/make_task_docs.py`

- `comparison_ablation.md` generator: per task, FOUR compact blocks
  (verdict + two ratings each, one Attribution line) — prose analysis
  ONCE per task ("across the four runs, what explains the pattern?"),
  not per block; then the head-to-head section with the four
  machine-parsed lines per task; Overall gains the tier question
  ("what did the frontier model demonstrably buy over the economy
  model, and was it worth ~10× the token price?").
- `tasks.md` generator: the two standardized prompts stay (persona /
  ablated); add one line telling the student dtlab-start announces which
  prompt to use for each run.
- Regenerate shipped templates from the 3-task config and keep them
  byte-identical to generator output (add the round-trip harness check
  while at it).

## 4. `tools/analyze_cohort.py`

- Ingest 4-run manifests: rows keyed (student, task, condition, tier).
  Backward-compatible with 2-run and single-run packs (older synthetic
  fixtures must still parse).
- New/updated charts: verdict distributions faceted grounding × tier;
  acceptable-rate 2×2 grid with cluster CIs; tier paired contrast
  (frontier − economy within student, per grounding) with CI + test;
  grounding × tier interaction estimate; provenance-mix chart (share of
  candidates per source bucket, agent vs human surfaces note);
  head-to-head charts for both contrast families.
- Stats table: tier effect (paired, cluster-bootstrap, Holm family);
  day/run-order caveat row (tier confounded with day; report the
  within-day run-order estimate as the bound).
- Update `tests/test_analyze_cohort.py` fabricator to 4-run zips (keep
  some 2-run/single students for backward-compat coverage) and
  regenerate `docs/sample_report.html`.

## 5. Tests (extend `tests/simulate_submission.sh`)

- 4-run happy path (per-run conditions/tiers, verdict keys, ratings,
  four head-to-head families, overlap sets, per-run contamination).
- Missing run 4 → issue names run 4, pack still builds.
- Manipulation check fires on either ablated log.
- Friday-gate + per-day order files exercised via the student_start
  state machine if a scripted walk is added (recommended; see REVIEW
  W2).
- Legacy 2-run pack still validates (backward compat).

## 6. Doc sync after implementation

- README "seven deliverables" table: deliverable #4/#5 wording to
  run1..4; sample report screenshots.
- TA_ONBOARDING harness-check references (check numbers).
- `dtlab_config.env`: add the day-tier constants; retire the
  `DTLAB_TIER_FACTOR` comment block.
- design_rationale: harmonize any remaining two-run phrasing (§5b
  already notes the 2×2).
- CHANGELOG entry + tick the relevant T-21 items.

## 7. Automated cart evidence — `dtlab-cart` (replaces manual screenshots)

- New `tools/capture_cart.py` (+ `dtlab-cart` alias in both
  provisioners): connects to the ALREADY-RUNNING lab browser over CDP
  (`DTLAB_CDP_PORT`, same profile — playwright `connect_over_cdp`),
  opens the amazon.in cart page, and saves BOTH `cart_runN.png`
  (full-page screenshot) and `cart_runN.json` (parsed line items:
  asin, title, unit price, qty) into `~/dtlab/evidence/`. Run number
  auto-detected from the run state, overridable with `--run N`.
- Cart selectors live in one SELECTORS dict (single patch point,
  dry-run validated, degrade to screenshot-only with a warning if
  parsing fails).
- Packer: prefer `cart_runN.json` when present and **cross-check
  `agent_picks.csv` against the actual cart contents** — the agent's
  self-reported picks verified against ground truth. Mismatch =
  non-blocking warning naming the items; match = `cart_verified: true`
  per run in the manifest. Screenshot still embedded in report.html;
  a manual screenshot remains a valid fallback (no json → no
  cross-check, noted).
- Cart EMPTYING stays a human action (the kit performs no destructive
  actions on the student's account); `dtlab-cart` ends by reminding the
  partner to empty the cart before the next run.

## 8. Structured verdict capture — `dtlab-verdict` (replaces memo editing)

The evaluation is already machine-parsed (verdict + rating lines), but
hand-editing a markdown file across four runs invites format errors at
N=161. Replace the editing with a guided prompt:

- New `tools/capture_verdicts.py` (+ `dtlab-verdict` alias), UX like
  `confirm_picks`: for each task × run — verdict
  (better/identical/equivalent/inferior, input validated), own-pick
  rating and agent-pick rating (1–10), and a one-line free-text
  rationale. Then per-task head-to-heads (grounding winner per tier,
  tier winner per grounding) and the four Overall reflection questions
  (multiline free text).
- Writes `~/dtlab/workspace/verdicts.csv` (schema `dtlab-verdicts-v1`:
  student_id, task_id, condition, tier, verdict, rating_self,
  rating_agent, rationale) plus `overall_reflections.md`. Idempotent
  and resumable: Thursday fills the economy rows, Friday the rest;
  re-running lets the student revise an answer.
- 'identical' is still ASIN-verified by the packer, which now reads
  `verdicts.csv` as the primary source (markdown comparison parsing
  retained as fallback for backward compat); manifest fields
  (`verdicts`, `ratings`, head-to-heads) unchanged for the analyzer,
  plus a `rationales` passthrough.
- `templates/comparison*.md` shrink to the reflective document only (or
  are retired); `make_task_docs.py` updated accordingly.

## 9. LMS submission flow (BITSoM)

- Students upload the single `DT2026-###_evidence.zip` to a BITSoM LMS
  file-upload assignment; the TA bulk-downloads all submissions into
  one folder and runs `analyze_cohort.py --zips <folder>`.
- LMS bulk downloads often RENAME files (name/ID prefixes). The
  analyzer already resolves identity from the zip's internal root
  folder + manifest `student_id`, never the filename — add a test that
  feeds an LMS-style renamed zip (`lastname_12345_DT2026-042_evidence.zip`)
  through the analyzer to lock this in.
- Keep zips comfortably under LMS upload limits: screen recordings are
  now OPTIONAL evidence (partner blinding + parsed cart JSON + Hermes
  transcripts already cover the trail redundantly); RECORDINGS.txt
  notes their absence without failing validation.

## Status at implementation (from REVIEW_2026-07-23) — since closed except N4

Sandbox fallback implementation (C1 — `DTLAB_SANDBOX=1` end-to-end),
smoke-test SOUL carve-out (C3), `price_in_profile_range` None fix (C4),
README register numbering (C5a), commit + push + CI green (N4), D10
source-doc line + lockstep content check (N1/N2), `student_start.sh`
state-machine test (W2 — now more important with four runs).
