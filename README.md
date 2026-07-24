<img src="assets/ringelai.png" alt="RingelAI" width="90" align="right">

# Digital Twin Shopping Agent Lab

**Daniel M. Ringel** · [ringel.AI](https://www.ringel.ai)

Course + experiment kit: 161 MBA students (two sections: 80 mornings,
81 afternoons) each configure a Hermes agent (Claude API backend) as
their consumer digital twin, shop a standardized task set themselves,
then send the twin to shop it FOUR times in a within-student 2×2 —
with/without the questionnaire × economy/frontier model — and compare
(assessment-blinded), producing a paired human/agent
choice-and-process dataset.

**New here? Read `TA_ONBOARDING.md` first, then `COURSE_PLAN_1WEEK.md`.**
Run `bash tests/simulate_submission.sh` after touching the validation
chain and `python3 tests/test_instrument_lockstep.py` after touching the
instrument or `dtlab_config.env` (CI runs both, plus shellcheck/ruff, on
every push). Never commit student data or keys (`.gitignore` covers the
obvious paths).

Turnkey package for the MBA module: Hermes Agent + Claude API + amazon.in,
with a research-grade data pipeline.

> **START HERE for the 161-student lab week: `COURSE_PLAN_1WEEK.md`.**
> It is the single authority on the plan: Sessions 6–10, picks committed
> Wednesday, the four agent runs (2×2: persona/ablated ×
> economy/frontier) on Thursday and Friday, partner-blinded, capstone
> white paper after. Standing simplifications: the agent reads the purchase
> history itself at Bootstrap (`data-pipeline/` is an optional research
> add-on); infrastructure is GitHub Codespaces on free personal
> accounts; the agent shops the full site with only
> browsing-history-derived modules banned and every candidate's
> provenance logged (daily history pause + measured contamination
> index).

## How this actually runs (read this first if you're new to GitHub)

A common misconception, worth clearing up before anything else: **this
repository never "runs" the course, and students never clone it or run
it locally.** The repo plays three separate roles:

1. **It is the recipe, not the kitchen.** Everything here — the agent's
   identity files, the task config, the tools, the checklists — is the
   single source of truth the course environments are BUILT from.
   Editing a file here changes what future environments contain; it
   executes nothing by itself.

2. **The only thing that executes "on GitHub" is the test suite.**
   Every push triggers `.github/workflows/ci.yml` on a throwaway GitHub
   server: it lints the code and runs the four regression suites
   (submission packer, pre-flight state machine, questionnaire
   lockstep, synthetic cohort report). No agent runs, no browser opens,
   no student data exists there — it is purely a quality gate. A red ✗
   on a commit means "do not build student environments from this
   commit"; a green ✓ means the kit is internally consistent. That is
   the entire meaning of CI here.

3. **Students get a personal cloud computer built FROM the repo — one
   click, no git.** The repo is a template: a student clicks *Create
   codespace* and GitHub builds them a private container in the cloud
   using `.devcontainer/` — `devcontainer.json` says what machine to
   make, `setup.sh` runs once automatically and installs Hermes,
   Chromium, and all lab tooling into `~/dtlab/`, creating the
   `dtlab-*` commands. From then on the student lives entirely inside
   that container (its terminal + the browser-based Lab Desktop). The
   repo is the blueprint; the codespace is the building. With
   **prebuilds** enabled, GitHub bakes the image ahead of time from the
   frozen commit, so all 161 students get an instant, bit-identical
   environment.

4. **Nothing ever flows back into the repo.** Personas, logs, picks,
   and the evidence zip exist only inside each student's codespace and
   leave it exactly once — as the zip uploaded to the LMS. Students
   have no reason (or route) to push commits; the `.gitignore` data
   patterns are belt-and-suspenders for lab machines.

5. **The one "local" path involves no students either:** if Codespaces
   is unavailable, the INSTRUCTOR runs `provisioning/provision.sh` once
   on a clean VM, snapshots it, and distributes the image
   (`provisioning/VM_DISTRIBUTION.md`). Students import a VM; still no
   cloning.

In short: the only people who ever clone this repo are the instructor,
the TA, and GitHub's own build machinery. Freeze the design, get CI
green, enable prebuilds — that commit IS the course environment.

## Who uses what (one repo, three audiences)

This is deliberately ONE repo — students' codespaces, the TA's checklists,
and the research apparatus all build from the same commit, which is what
makes the experiment reproducible. It may become public later; nothing in
it is sensitive by design (student data never enters the repo — the
`.gitignore` data patterns are belt-and-suspenders for lab machines).
Who needs which parts:

**Students** never work "in the repo" — they click *Create codespace* and
then live entirely in the terminal commands and the LMS handout:
- Their whole surface: `dtlab-shop` · `dtlab-start` · `dtlab-cart` ·
  `dtlab-verdict` · `dtlab-record` · `dtlab-pack`. Nothing to edit by
  hand — `tasks.md` is generated and pre-flight orders it into each
  student's randomized task order.
- Worth reading if curious: `agent/SOUL.md` (it IS course content) and
  this section.
- Safe to ignore: everything else — `provisioning/`, `questionnaire/`,
  `tools/`, `tests/`, `docs/`, `data-pipeline/`, all config files. The
  handout, not this README, is the student instruction set.

**TA** — start at `TA_ONBOARDING.md` (reading order, open work items,
installer-pin procedure, the must-not-do list) and work the live T-21
dry-run list at the top of `docs/CHANGELOG.md`. Operating surface:
`questionnaire/` (Form build), `tools/make_all_personas.py` (overnight
batch), `tests/` (run after ANY change to guarded files),
`tasks_config.csv` + `tools/make_task_docs.py` (if the task set
changes), CI. Should not touch without instructor sign-off: both SOULs,
`templates/`, `tools/pack_evidence.py`, the instrument, budgets/factors
in the config files — all frozen design.

**Instructor / researcher** — owns the design and the term-start
decisions (task set, model tier, ablation factor — all switches in
`dtlab_config.env` / `tasks_config.csv`). Design reasoning:
`docs/design_rationale.md`; research apparatus: `research_protocol.md`
(consent, DPDP, schemas, dataset assembly),
`questionnaire/questionnaire_instrument_source.md` (authoritative
instrument), `PERSONALIZATION_PROTOCOL.md` (contamination model);
after submissions: `tools/analyze_cohort.py` (cohort report) and the
frozen-dataset assembly in research_protocol §5. `data-pipeline/` is
the optional post-course add-on, instructor-only.

## Contents

```
dt-lab/
├── README.md                          ← you are here
├── dtlab_config.env                   ← shared constants (item count, ID pattern, browser profile, CDP port, factor switches) — change here, nowhere else
├── tasks_config.csv                   ← THE task structure (ids, product types, utilitarian/hedonic classes, budgets) — packer/logger/report all read it
├── tasks_config_6task_example.csv     ← worked 6-task self-purchase example (adds the speaker as a 6th category)
├── research_protocol.md               ← consent, pseudonyms, schemas, dataset assembly
├── agent/
│   ├── SOUL.md                        ← agent identity + ECP decision-log protocol (CAND lines), hard boundaries, injection hardening
│   └── SOUL_ablated.md                ← questionnaire-free variant for the ablated runs of the 2×2 (purchase profile only)
├── questionnaire/
│   ├── questionnaire_instrument_source.md ← AUTHORITATIVE instrument source: 115 items + design notes (edit here first, then re-transfer to the CSV)
│   ├── questionnaire_items.csv        ← THE course instrument: 115 real items generated from the source doc
│   ├── AUTHORING_GUIDE.md             ← column contract + transfer conventions (stems embedded, likert5 anchors, constraint flag)
│   ├── build_form.gs                  ← Apps Script: auto-builds the Google Form from the CSV
│   └── make_persona.py                ← Form responses row → persona_survey.md + .csv
├── TA_ONBOARDING.md                   ← start here: reading order + open work items + installer-pin procedure
├── tests/
│   ├── simulate_submission.sh         ← regression harness for the validation chain (sandboxed HOME, no browser needed)
│   ├── test_start_flow.sh             ← regression suite for the dtlab-start 4-run state machine (sandboxed HOME)
│   ├── test_instrument_lockstep.py    ← guards CSV ↔ source-doc ↔ config ↔ persona-generator lockstep
│   └── test_analyze_cohort.py         ← synthetic-cohort test of the report generator
├── assets/
│   └── ringelai.png                   ← RingelAI logo (embedded in the grader report + cohort report)
├── docs/
│   ├── design_rationale.md            ← the rationale for all design choices, alternatives, accepted risks
│   ├── CHANGELOG.md                   ← the LIVE T-21 dry-run list + change record
│   └── sample_report.html             ← SAMPLE cohort report (synthetic data) — what analyze_cohort.py produces
├── COURSE_PLAN_1WEEK.md               ← THE operative plan (single authority on the route decision): Sessions 6–10, 3 h/day per section, N=161
├── data-pipeline/                     ← OPTIONAL research add-on (post-course precise history via official export)
│   ├── clean_privacy_export.py        ← official Amazon export → schema v1
│   ├── scrape_orders.py               ← manual-login + Playwright scrape → schema v1
│   └── enrich_brands.py               ← resolves authoritative brand per ASIN
├── templates/
│   ├── tasks.md                       ← deliverable #3: the 5 category tasks (generated from tasks_config.csv; ordered per student at pre-flight)
│   ├── human_picks.csv                ← deliverable #6: pre-registered student picks (structured)
│   ├── comparison.md                  ← single-run fallback memo (machine-parsed; dtlab-verdict is primary)
│   └── comparison_ablation.md         ← four-run 2x2 fallback memo (generated; dtlab-verdict is primary)
├── tools/
│   ├── pack_evidence.py               ← `dtlab-pack`: validates + redacts + bundles ALL 7 deliverables into one zip
│   ├── log_human_session.py           ← `dtlab-shop`: instrumented human shopping session (quarantined output)
│   ├── capture_cart.py                ← `dtlab-cart`: partner-run cart screenshot + parsed cart JSON per run (CDP attach)
│   ├── capture_verdicts.py            ← `dtlab-verdict`: guided verdict/rating/rationale capture (verdicts.csv)
│   ├── dtlab_browser.sh               ← the ONE browser launcher (shared profile + CDP port for human AND agent sessions)
│   ├── make_all_personas.py           ← instructor batch persona generation (+ --strip-email research copy)
│   ├── make_task_docs.py              ← instructor: regenerate tasks.md + comparison templates from tasks_config.csv
│   └── analyze_cohort.py              ← instructor: folder of submitted zips → self-contained plotly report for the class debrief
├── PERSONALIZATION_PROTOCOL.md        ← Amazon's memory of the account: keep baseline personalization, reduce/block/measure within-experiment contamination
├── .devcontainer/                     ← devcontainer.json + setup.sh (AT REPO ROOT so Codespaces auto-detects it)
├── .github/workflows/ci.yml           ← CI: shellcheck + ruff + both test suites on every push
├── CLOUD_SETUP.md                     ← the Codespaces route (PRIMARY infra for the 1-week format)
└── provisioning/                      ← the local-VM FALLBACK route
    ├── VM_DISTRIBUTION.md             ← hypervisor choice + the staged testing funnel & triage table
    ├── host_check.sh / host_check.ps1 ← student-side host compatibility check (fallback route only)
    ├── provision.sh                   ← builds the golden VM image (instructor, once per architecture)
    └── student_start.sh               ← the one command students run (`dtlab-start`) — used on BOTH routes
```

## The two-path history capture (OPTIONAL research add-on — why both scripts exist)

> Not part of the student flow: deliverable #2 is the agent-written
> `purchase_profile.md`. The `data-pipeline/` scripts below exist only for
> the optional post-course validation subsample (research_protocol.md §5).

| | Privacy Central export (preferred) | Scraper (fallback / instant) |
|---|---|---|
| Accuracy | Authoritative unit price, qty, ASIN | Best-effort DOM parsing; per-item price occasionally missing |
| Speed | Request at T−14; usually arrives in hours–days, SLA up to ~1 month | ~4 s per order, immediate |
| Fragility | Stable file format | Breaks when Amazon changes its DOM — validate on dry run |
| ToS posture | Fully sanctioned (it's Amazon's own DSAR tool) | Automated access; mitigated by manual login + polite pacing, residual risk disclosed in syllabus |

Both emit the **identical schema (`dtlab-orders-v1`) + a provenance sidecar**,
so the cohort dataset is uniform regardless of path, with `capture_method` as
a covariate. Assign the export request at T−14; the scraper exists so nobody
is blocked on lab day. `enrich_brands.py` runs after either path.

## Questionnaire pipeline (Google Forms → Sheet → VM)

1. Instructor: the instrument is authored — `questionnaire_items.csv` holds
   the real **115 items** (15 demographics, 57 validated-scale items from 12
   published scales, 22 amazon.in behavior, 12 values/constraints with
   VC01–VC05 flagged `constraint=1`, 9 predictive), generated from the
   authoritative `questionnaire_instrument_source.md`. Any instrument change
   goes into the source doc first, then the CSV (the two must never
   diverge). Import the CSV into a Google Sheet (tab "items"), paste
   `build_form.gs` into Apps Script, run `buildForm()`. Link responses to a
   Sheet. **That response Sheet IS the cohort persona dataset** — one row
   per student, consistent coding, zero transcription.
2. Students complete the Form (~30 min) using their `DT2026-###` pseudonym.
3. Instructor exports the response Sheet as `responses.csv` and distributes
   it (or per-student slices).
4. Student, in the codespace (or the instructor batch-runs
   `make_all_personas.py` overnight and distributes per-student zips):
   `python3 ~/dtlab/tools/make_persona.py --responses responses.csv --student-id DT2026-042`
   → drops `persona_survey.md` (agent copy, item-coded) and
   `persona_survey.csv` (research copy) into the workspace.

Item codes are the connective tissue: the Form headers carry them, the
persona file preserves them, and `SOUL.md` obliges the agent to cite them in
its decision log — which is what makes the logs codeable into
`dtlab-choices-v1` and the citation-fidelity analysis possible. The pipeline
is agnostic to your coding scheme (any 1–4 letters + 1–3 digits) and item
count; the count lives ONCE in `dtlab_config.env` (`DTLAB_EXPECTED_ITEMS`,
currently **115**, with a matching fallback in
`provisioning/student_start.sh`) and
`tests/test_instrument_lockstep.py` fails if CSV, config, and fallback
ever diverge. Constraint semantics travel
via the CSV's `constraint` column → a `[CONSTRAINT]` flag in the persona
file → SOUL.md's constraints-always-win rule, so no item codes are ever
hard-coded anywhere.

## Claude API configuration

- **Each student uses their own Anthropic account and API key** (created
  as Monday-evening homework per the LMS setup checklist: Console
  account, billing,
  a small credit purchase, a personal **monthly spend limit of ~$20** set
  in Console settings, then one API key). Rate limits are therefore
  per-student — ~80 concurrent agents share nothing, and one agent's
  ~4–12 requests/minute sits far below any per-account limit; prompt-cache
  reads do not count toward input-token limits on current models.
- During image build, run `hermes setup` and select **Anthropic** as
  provider with the key left blank; `dtlab-start` collects each student's
  key on first run — silently (input hidden, so it can never appear in a
  screen recording), stored only in a 600-permission `~/.dtlab_env` file,
  and redacted from any packed log by `dtlab-pack`.
- **Model policy: Anthropic models only, all settings at defaults** (no
  temperature or sampling overrides — agent runs are interactive tool-use
  sessions, not elicitation calls). Budget guidance: a full task-set run
  is typically well under $1–2 in Sonnet tokens and far less on Haiku;
  the four-run 2×2 lands around $3–6 per student — the recommended
  personal spend limit is **$20**. Hermes supports Anthropic prompt
  caching, which helps because the persona + history are re-read each run
  (cache reads are also exempt from per-account input-token rate limits).
  The personal ~$20 spend limit is the cap: it covers all four runs of
  the 2×2 with slack, and the student controls it end to end.
- **Model tier is a within-student factor by day** (plan of record):
  every agent runs on the economy tier (Claude Haiku class) on Thursday
  and the frontier tier (Claude Sonnet class, e.g. `claude-sonnet-4-6`)
  on Friday — the course's live answer to "will a better model do
  better?". Tier is recorded per run in the manifest; the day-tier
  confound is acknowledged in the methods (research_protocol.md §1).
- Students verify their spend limit on their own Claude Console
  **dashboard** during the setup checklist; pre-flight asks for
  confirmation, and cost questions are answered from each student's own
  usage view.
- **Questionnaire ablation is ON** (`DTLAB_PERSONA_FACTOR=1`): on each
  lab day the agent runs the task set twice — persona run (questionnaire
  + purchase profile) vs. ablated run (purchase profile only, persona
  files physically removed, ablated SOUL) — in per-day counterbalanced
  order, with verdicts for both runs, per-task head-to-heads, and the
  pick-overlap measure in every manifest. Combined with the tier factor
  this yields the four-run 2×2 (see COURSE_PLAN_1WEEK.md; the 4-run
  tooling is implemented — `dtlab-start` walks runs 1–4, the packer
  validates per run, spec kept at docs/WORK_ORDER_4RUN.md).

## Student experience (the whole thing, from their side)

1. Monday (Session 6): GitHub account + codespace created in class;
   that evening's homework (assigned Monday, due 22:00): consent, the
   115-item Form (~30 min, phone is fine), own Anthropic account + API
   key + $20 spend limit. Personas are generated centrally overnight.
2. Monday–Tuesday, in class: create/log into GitHub → **Create
   codespace** (~4–6 min first build; instant with prebuilds) → open the
   forwarded **Lab Desktop** port (noVNC; per-codespace password printed
   in the terminal — NEVER set the port to Public) → Tuesday: API key
   in, persona zip in, pre-flight green, sandbox smoke run watched.
3. (No data-export step — the agent reads the order history itself
   during its Bootstrap on the first run of each day.)
4. Wednesday: pause Browsing History (pre-flight gate), then
   **`dtlab-shop`** — shop the task set yourself in the instrumented
   browser (clickstream logged: searches, product views, cart clicks),
   confirm your picks. Everything lands in `~/dtlab/human/`, which the
   agent is barred from reading; your picks are now committed.
5. Thursday (economy model) and Friday (frontier model): two agent runs
   per day — persona and ablated grounding in your assigned order.
   **You never watch your own agent**: you and your partner swap seats
   for every run; the partner handles CAPTCHAs, runs `dtlab-cart` after
   each run (automatic cart screenshot + parsed cart contents into
   `~/dtlab/evidence/`, cross-checked against the agent's picks at pack
   time), and empties the cart between runs. `dtlab-start` walks each run (pre-flight, history re-pause
   gate, payment check, SOUL/persona swaps); `dtlab-record` captures the
   screen (start it only after login).
6. After each day's runs: open your agent's artifacts for the first
   time and run **`dtlab-verdict`** — a guided prompt that captures,
   per task and run, your verdict (better/identical/equivalent/
   inferior), satisfaction ratings (1–10) for your pick and the
   agent's, and a one-line rationale; structured data, no markdown
   editing.
7. Friday close: `dtlab-verdict` (head-to-heads, the tier question,
   Overall reflections) → `dtlab-pack` (validates everything, redacts
   keys/PII from logs) → download the single `DT2026-###_evidence.zip`
   via the VS Code explorer → upload it to the **BITSoM LMS**
   assignment → stop the codespace.

## The seven deliverables and how they're captured

| # | Deliverable | File in the submission zip | Produced by |
|---|---|---|---|
| 1 | Questionnaire with answers | `persona_survey.csv` + `.md` | Google Form → `make_persona.py` |
| 2 | Purchase history | `purchase_profile.md` — written by the agent itself from the logged-in Your Orders pages (mandatory Bootstrap in SOUL.md; capped at ~30 orders/12 months; every claim traceable to a seen order). Precise raw CSV only via the optional post-course add-on. | agent Bootstrap |
| 3 | The 5 category tasks, in the student's randomized order | `tasks.md` | generated from `tasks_config.csv`; ordered per student by `dtlab-start` |
| 4 | Full agent trace, all four runs | `run1/`…`run4/decision_log.md` + `hermes_logs/` (session transcripts auto-collected since the run marker) | SOUL.md protocol + `dtlab-start` marker |
| 5 | Items the agent added to basket, per run | `run1/`…`run4/agent_picks.csv` + `cart_run1..4.png`/`.json` (automatic screenshot + parsed cart contents via `dtlab-cart`, cross-checked against the picks — `cart_verified` per run) | SOUL.md protocol + `dtlab-cart` |
| 6 | The student's own pick per task + HOW they shopped | `human_picks.csv` + `human_session.jsonl` (clickstream: searches, product views, cart clicks, timestamps) | `dtlab-shop` (log_human_session.py), quarantined in `~/dtlab/human/` |
| 7 | Assessment per task per run | `verdicts.csv` (verdict, ratings 1–10, one-line rationale — captured by the guided `dtlab-verdict` prompt, ASIN-cross-checked) + `overall_reflections.md` | `dtlab-verdict` |

Beyond the seven deliverables, every zip also carries: per-task 1-10
satisfaction ratings for own vs agent picks (from `dtlab-verdict`; the
comparison-memo parse remains as fallback), a `config_snapshot/`
(config, arm, per-day grounding orders, tier, kit version), a
`file_inventory` in the manifest (per-file SHA-256
+ size + last-modified timestamp — the audit trail of what the student
changed and when), and a `SUBMISSION_INFO.txt` stamp; every path inside
the zip sits under the student's `DT2026-###/` folder, so each extracted
file is uniquely attributable.

`dtlab-pack` validates all seven (one row per task in each picks file,
real ASINs,
per-run condition + tier recorded, verdicts present and consistent for
every run — it cross-checks each verdict against the
ASINs, enforcing 'identical' exactly when agent and student chose the same
product — plus the manipulation check on every ablated log and the
picks-vs-cart cross-check), auto-collects Hermes session
logs modified since `dtlab-start` touched the run marker, computes SHA-256
hashes into `manifest.json`, and renders `report.html` — a single
self-contained page with the side-by-side picks tables (one per run),
verdicts, embedded cart screenshots, and the decision logs inline, so
graders never unzip anything. Invalid packs still produce the zip but
exit non-zero and list what to fix — a lost run is an issue naming the
run, never a lost student. Cohort assembly (research_protocol.md §5)
then reduces to concatenating the CSVs across zips — deliverables 1, 2,
5, 6, 7 are already in final schema, and the verdicts/head-to-heads are
in each manifest.json.

## Task set: five self-purchase categories, randomized order

The task structure lives in **`tasks_config.csv`** (task_id, frame,
product_type, category_class utilitarian/hedonic, budget range,
amazon.in category link) — the single source the pre-flight, packer,
human logger, and cohort report all read. The plan of record: **five
self-purchase categories** from the **11-category catalog** (6
utilitarian, 5 hedonic, budget-paired, each with its amazon.in
category link; rationale and sources in `docs/TASK_CATEGORIES_10.md`).
Every task is buying for YOURSELF — the earlier gift and replenishment
frames are retired (buying for a third party and habitual replenishment
are different research questions). A **provisional five** ships active
(sneakers, power bank, backpack, laptop, perfume); **the teaching
team makes the final pick** by editing the `#` activation flags. To
change the set:

1. In `tasks_config.csv`: add `#` to rows you drop, remove it from rows
   you keep, renumber task_id 1..N.
2. `python3 tools/make_task_docs.py` — regenerates `templates/tasks.md`
   and both comparison templates to match (the harness checks they stay
   byte-identical).
3. Re-run the test harness; freeze the task set before lab day (it is
   part of the design, like the questionnaire).

**Task order is randomized per student** (what an agent picks in one
category can influence the next): the order derives deterministically
from the pseudonym, `dtlab-start` re-orders `tasks.md` accordingly at
pre-flight, the human shops in the same order, and it stays constant
across all four agent runs — randomized across students, so position
effects cancel at cohort level and the analyzer reports the
position-effect estimate. The packer records the executed order and
warns if `tasks.md` was re-sorted by hand.

The `amazon_url` column scopes each category for the instructor, TA,
and handout; the agent shops the full site under SOUL.md's targeted
rules (browsing-history-derived modules banned, every candidate
provenance-logged), and students shop naturalistically. Time budget:
each additional task ≈ +8–10 min human session and ~10 min per agent
run (SOUL per-task effort cap) — verify 5-task run timing in the dry
run; the laptop task (the high-stakes anchor) is the one most likely
to dominate both the human session and the agent's effort cap. The
report automatically adds the utilitarian-vs-hedonic fidelity
breakdown when both classes exist.

**Process data is machine-parsed:** agents must log every candidate as a
`CAND | task= | asin= | category= | price= | sponsored= | source=` line
(ECP, both SOULs); the human logger records the category breadcrumb on
every product view. Together these make consideration-set size and
agent-vs-human search overlap (Jaccard) computable per student.

## Cohort analysis (instructor, after submissions)

Download all zips from the LMS into one folder, then:

```bash
python3 tools/analyze_cohort.py --zips ~/Downloads/submissions --out cohort_report.html
```

(`pip install pandas plotly`; scipy optional for exact tests.)
**See [docs/sample_report.html](docs/sample_report.html) for a complete
sample** — generated from 8 synthetic students fabricated by
`tests/test_analyze_cohort.py` and clearly titled as such; every number
in it is fake, but the layout, charts, statistics, and branding are
exactly what a real cohort produces. The output
is ONE self-contained HTML report for the class debrief: verdict
distributions by task and agent type (persona / ablated / single),
acceptable-pick rates with 95% CIs, head-to-head winners and pick overlap
(ablation design), own-vs-agent satisfaction ratings, price scatter and
budget compliance, brand/price alignment with the purchase profile,
history-length descriptives, contamination by arm, a statistics table
(sign test, binomial, two-proportion, Wilcoxon), and a data-quality
section. Charts are plotly (hover/zoom live in the HTML).

Everything else — Hermes, Playwright, Chromium, SOUL.md, scripts, aliases —
is pre-baked by `.devcontainer/setup.sh` (Codespaces, primary) or
`provisioning/provision.sh` (VM fallback).

## Build checklist (instructor)

- [ ] Ethics approval (BITSoM process + DPDP; see research_protocol.md §3)
      + consent sheet incl. the partner-pairing disclosure
- [ ] Build Form via Apps Script; test-submit once; confirm response Sheet
- [ ] Pin installer checksums (TA_ONBOARDING.md), make the repo a template,
      enable Codespaces prebuilds
- [ ] **Dry run of the full path yourself from a codespace**, ~3 weeks out
      (T-21): build, persona generation, `dtlab-shop`, `/browser connect`,
      Bootstrap, one full task, `dtlab-pack` — working the T-21 dry-run
      list at the top of `docs/CHANGELOG.md`
- [ ] Confirm the student-key model end-to-end: every student's own Anthropic account, one key, ~$20 monthly spend limit (Monday homework); 2–3 course-owned spare keys staged for setup casualties
- [ ] LMS: assignment sheet (pseudonym + per-day grounding order + pair), evidence upload slot
- [ ] Synthetic persona pack for opt-outs (fictional Form row — generate
      once, reuse; doubles as the flagged-account sandbox path)
- [ ] Only if the VM fallback is activated: golden images per
      VM_DISTRIBUTION.md (two architectures) + published SHA-256 hashes

## Known-fragility register

1. **Hermes release drift** — commands/paths may shift between now and fall
   2026; the docs are canonical, the handout is best-effort.
2. **Amazon DOM drift** — affects `scrape_orders.py` and `enrich_brands.py`
   only; the SELECTORS dict is the single patch point.
3. **Installer pins** — `provision.sh` and `.devcontainer/setup.sh`
   refuse to build until the Hermes/uv installer URLs and SHA-256s are
   pinned (procedure in TA_ONBOARDING.md); verify against the official
   Nous Research site at pin time.
4. **Form header parsing** in `make_persona.py` assumes titles keep their
   `CODE.` prefix — don't rename questions inside the Form after building.
5. **Breadcrumb + cart selectors** — the human logger's category capture
   reads `#wayfinding-breadcrumbs_feature_div`, and `dtlab-cart` parses
   the cart page via its own SELECTORS dict; both are DOM-dependent and
   must be validated against live amazon.in in the dry run (both degrade
   gracefully: empty categories / screenshot-only, never an error).
6. **Instrument lockstep** — the real 115 items are in place (the EX0x
   hard-fail guards in the Form builder and persona generator now pass, and
   remain as protection against accidental reversion). The CSV is generated
   from `questionnaire_instrument_source.md`; any edit that touches only one
   of the two creates silent drift — always change the source doc first,
   re-transfer, and keep `EXPECTED_ITEMS=115` in sync.
