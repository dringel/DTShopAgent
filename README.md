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

**Student in the course? Skip straight to [Getting Started](#getting-started-students) below — you do not need anything else on this page.**

**TA or instructor? Read `TA_ONBOARDING.md` first, then `COURSE_PLAN_1WEEK.md`.**
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
> economy/frontier, tier order counterbalanced across days per student)
> on Thursday and Friday, partner-blinded, all verdicts captured in one
> blind Friday session, capstone
> white paper after. Standing simplifications: the agent writes the
> purchase profile itself in a one-time questionnaire-blind bootstrap
> session, then it is frozen for all four runs (`data-pipeline/` is an
> optional research
> add-on); infrastructure is GitHub Codespaces on free personal
> accounts; the agent shops the full site with only
> browsing-history-derived modules banned and every candidate's
> provenance logged (daily history pause + measured contamination
> index).

## Getting Started (Students)

Everything below happens in your browser. You never install anything on
your own laptop, and you never need `git` — GitHub builds you a cloud
computer with one click.

**Tonight — before class:**

1. **Three accounts, if you don't already have them:** [GitHub](https://github.com/join) ·
   [Anthropic Console](https://console.anthropic.com) (create an API key,
   and set a spending limit while you're there — it's your own money) ·
   your own real Amazon India account (its order history is half of what
   makes your agent yours).
2. **Copy the lab:** on this page, click green **Code** → **Codespaces**
   tab → **Create codespace on main** — that builds your own private
   copy automatically. Wait for the terminal to print `Setup complete.`
   before typing anything.
3. **Add your key:** the first time you run `dtlab-start` (below), it
   asks for your API key directly — input is hidden as you paste, and it
   is checked against Anthropic before it's saved. Never paste your key
   anywhere else.
4. **Amazon prep, inside the Lab Desktop** (Ports tab → port `6080` →
   Open in Browser): sign in, then Accounts & Lists → Browsing History →
   gear icon → **Pause History → 1 day** → Remove all items from view.
   **Repeat this every lab morning** — the pause lasts only one day.
5. **The questionnaire** (~30 min, do it in one sitting, answer as
   yourself, not aspirationally): link is on the course LMS, not here —
   this repository is public and the form isn't meant for the open
   internet. Submit it tonight; profiles are generated overnight, so
   late means no profile for the lab.

**In the lab, in this order:**

| Command | What it does |
|---|---|
| `dtlab-shop` | Records your own shopping pick per task, before the agent runs |
| `dtlab-start` | Runs the agent for one condition — pre-flight checks, then launches |
| `dtlab-persona on` / `off` | Set **before every run** — the TA announces this live in class |
| `dtlab-history on` / `off` | Set **before every run** — whether the agent gets your order history |
| `dtlab-tier economy` / `frontier` | Set **once per lab day** — the TA announces this too |
| `dtlab-runs` | Lists every run you have done, including ones you redid |
| `dtlab-results` | Shows where every file from every run is saved, and puts that folder in the VS Code explorer |
| `dtlab-cart` | Screenshots and verifies the cart right after each run, then empty it (Delete, never "Save for later") |
| `dtlab-verdict` | After all your runs: blind rating of every agent pick against your own |
| `dtlab-pack` | Builds the one file you submit — `DT2026-###_evidence.zip` — cleaned and validated automatically. It is written to `~/dtlab/`, which is outside your repo folder; run `dtlab-results` to put that folder in the explorer |

Run `dtlab-persona status`, `dtlab-history status` or `dtlab-tier status`
any time you're not sure what's currently set — never guess. Full detail
on every step is in
[Student experience](#student-experience-the-whole-thing-from-their-side)
further down this page.

**Doing a run again.** You can repeat any condition as many times as you
like, and you can redo your own `dtlab-shop` session too. Nothing is
overwritten: the run you replace is moved to `~/dtlab/runs_history/`
and stays there, and both commands ask before they archive anything.
`dtlab-runs` shows you everything you have done, and `dtlab-results`
shows you where each run's files are saved and adds that folder to the
VS Code explorer (your lab files live in `~/dtlab/`, outside the repo
folder, which is why they are not visible there by default). Your evidence pack
records how many attempts each run took, so a redo is something you
can just do — not something to hide or work around.

**If something breaks:** read what the terminal printed, tell a TA,
say what you already tried. Don't edit any files by hand, and when you
redo a run say what went wrong — a recorded problem is useful data; a
silently patched one isn't.

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
   frozen commit, so all 161 students get an instant environment built
   from the same frozen image (a runtime commit check catches stale
   prebuilds).

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

6. **What is actually distributed to students: ONE link.** At design
   freeze the repo is made **public** and prebuilds are enabled; the
   LMS handout then carries the repo's codespace deep link
   (`https://codespaces.new/dringel/DTShopAgent?quickstart=1`).
   A codespace can be created by anyone who can *read* a repo and is
   billed to the creating account's own free quota — so a student
   needs exactly two things: a free github.com account (created in
   Session 6) and that link. Clicking it lands on GitHub's "Create
   codespace" page; one more click builds their private container
   from the frozen commit. Students have read-only access to the
   repo, which is what makes "no route to push" a mechanical fact,
   not a rule. Nothing else is distributed — no zip, no installer,
   no fork, no clone.

In short: the only people who ever clone this repo are the instructor,
the TA, and GitHub's own build machinery. Freeze the design, get CI
green, enable prebuilds, publish the one link — that commit IS the
course environment.

## Who uses what (one repo, three audiences)

This is deliberately ONE repo — students' codespaces, the TA's checklists,
and the research apparatus all build from the same commit, which is what
makes the experiment reproducible. It may become public later; nothing in
it is sensitive by design (student data never enters the repo — the
`.gitignore` data patterns are belt-and-suspenders for lab machines).
Who needs which parts:

**Students** never work "in the repo" — they open the codespace link
from the LMS handout (see "How this actually runs" #6), click *Create
codespace*, and
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
│   ├── SOUL_ablated.md                ← questionnaire-free variant for the ablated runs of the 2×2 (purchase profile only)
│   ├── SOUL_bootstrap.md              ← the one-time questionnaire-blind bootstrap session (writes the frozen purchase profile; no shopping)
│   └── SOUL_sandbox.md                ← practice-store variant (smoke test / flagged-account fallback)
├── questionnaire/
│   ├── questionnaire_instrument_source.md ← AUTHORITATIVE instrument source: 115 items + design notes (edit here first, then re-transfer to the CSV)
│   ├── questionnaire_items.csv        ← THE course instrument: 115 real items generated from the source doc
│   ├── AUTHORING_GUIDE.md             ← column contract + transfer conventions (stems embedded, likert5 anchors, constraint flag)
│   ├── build_form.gs                  ← Apps Script: auto-builds the Google Form from the CSV (consent + opt-out fields, field validations)
│   ├── HEDUT_POLL.md                  ← the Session-10 in-class HED/UT poll: instrument, build, run, and analyzer hookup
│   └── make_persona.py                ← Form responses row → persona_survey.md/.csv + persona_meta.json (opt-out aware, completeness-strict)
├── TA_ONBOARDING.md                   ← start here: reading order + open work items + installer-pin procedure
├── tests/
│   ├── simulate_submission.sh         ← regression harness for the validation chain (sandboxed HOME, no browser needed)
│   ├── test_start_flow.sh             ← regression suite for the dtlab-start 4-run state machine (sandboxed HOME)
│   ├── test_instrument_lockstep.py    ← guards CSV ↔ source-doc ↔ config ↔ persona-generator lockstep
│   ├── test_analyze_cohort.py         ← synthetic-cohort test of the report generator (incl. null-simulation Type-I guard)
│   └── check_docs.py                  ← CI doc-checker: links resolve, no stale terms, paths referenced correctly
├── assets/
│   └── ringelai.png                   ← RingelAI logo (embedded in the grader report + cohort report)
├── docs/
│   ├── design_rationale.md            ← the rationale for all design choices, alternatives, accepted risks
│   ├── CHANGELOG.md                   ← the LIVE T-21 dry-run list + change record
│   ├── CONSENT_AND_DATA_USE.md        ← the student-facing consent sheet of record (data-flow map incl.)
│   ├── TASK_CATEGORIES.md             ← the 11-category catalog: selection rationale, sources, HED/UT plan
│   ├── SYLLABUS_BLURB.md              ← copy-paste syllabus text (sessions, lab project, capstone)
│   ├── archive/                       ← retired design documents, kept for the record
│   └── sample_report.html             ← SAMPLE cohort report (synthetic data) — what analyze_cohort.py produces
├── COURSE_PLAN_1WEEK.md               ← THE operative plan (single authority on the route decision): Sessions 6–10, 3 h/day per section, N=161
├── data-pipeline/                     ← OPTIONAL research add-on (post-course precise history via official export)
│   └── clean_privacy_export.py        ← official Amazon export → schema v1
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
    ├── hermes_config.template.yaml    ← per-run Hermes model config template (the ONE schema patch point for the pinned release)
    ├── provision.sh                   ← builds the golden VM image (instructor, once per architecture)
    └── student_start.sh               ← the one command students run (`dtlab-start`) — used on BOTH routes
(counterbalance.csv joins the repo root at design freeze — instructor-generated
from the roster by tools/make_counterbalance.py; provisioning refuses to build
without it.)
```

## Precise history capture (OPTIONAL research add-on — official export only)

> Not part of the student flow: deliverable #2 is the agent-written
> `purchase_profile.md`. The `data-pipeline/` cleaner below exists only for
> the optional post-course validation subsample (research_protocol.md §5).

`clean_privacy_export.py` converts Amazon's official Privacy Central
("Request Your Data") export into the frozen **`dtlab-orders-v1` schema +
a provenance sidecar** — authoritative unit prices and quantities from
Amazon's own DSAR tool, with no automated site access and no DOM
dependence. Consenting students request the export after the course
(delivery ranges from hours to about a month, which no longer matters
once the lab week is over) and the cleaner runs on
`Retail.OrderHistory*.csv`; privacy minimization is built in — order IDs,
addresses, payment and carrier data are dropped before the file reaches
anything else.

## Questionnaire pipeline (Google Forms → Sheet → VM)

1. Instructor: the instrument is authored — `questionnaire_items.csv` holds
   the real **115 items** (15 demographics, 57 validated-scale items from 12
   published scales, 22 amazon.in behavior, 12 values/constraints with
   VC01–VC05 flagged `constraint=1`, 9 predictive), generated from the
   authoritative `questionnaire/questionnaire_instrument_source.md`. Any instrument change
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
ever diverge. Two predictive items (PR02, PR08) are research-only: they
name upcoming purchases, so they stay in the research CSV but are never
rendered into the agent-visible persona — 113 of the 115 items reach the
agent, and the pre-flight gate checks that rendered count
(`make_persona.py::AGENT_HIDDEN_ITEMS` is the authoritative set). Constraint semantics travel
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
- Provider and model are configured **per run, not interactively**:
  `dtlab-start` generates each run's `$HERMES_HOME/config.yaml` from
  `provisioning/hermes_config.template.yaml` with the pinned model ID
  for that run's tier, verifies it, and fails closed on any mismatch —
  no `hermes setup` provider step is relied on. `dtlab-start` collects
  each student's
  key on first run — silently (input hidden, so it can never appear in a
  screen recording), verified against the Claude API (fail-closed; a
  network failure needs a typed TA `OVERRIDE`, which is recorded),
  stored only in a 600-permission `~/.dtlab_env` file,
  and redacted from any packed log by `dtlab-pack`. A one-time
  confirmation that the ~$20 spend limit is set is recorded and packed.
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
- **Model tier is a within-student factor, counterbalanced across
  days** (plan of record): each agent runs on the economy tier (Claude
  Haiku class) on one lab day and the frontier tier (Claude Sonnet
  class) on the other, in the order the counterbalance sheet assigns —
  the course's live answer to "will a better model do better?",
  identified separately from the day. The exact pinned model ID is
  written into each run's own Hermes configuration by `dtlab-start`
  (which refuses to launch on any mismatch) and recorded per run in
  the manifest (research_protocol.md §1).
- Students verify their spend limit on their own Claude Console
  **dashboard** during the setup checklist; pre-flight asks for
  confirmation, and cost questions are answered from each student's own
  usage view.
- **Questionnaire ablation is ON** (`DTLAB_PERSONA_FACTOR=1`): on each
  lab day the agent runs the task set twice — persona run (questionnaire
  + purchase profile) vs. ablated run (purchase profile only, persona
  files quarantined away from the agent, ablated SOUL, fresh per-run
  Hermes home) — in per-day counterbalanced
  order, with blind verdicts for all runs captured once on Friday,
  per-task head-to-heads, and the
  pick-overlap measure in every manifest. Combined with the tier factor
  this yields the four-run 2×2 (see COURSE_PLAN_1WEEK.md; `dtlab-start`
  walks runs 1–4 and the packer validates per run).

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
   To paste from the host into that Linux desktop, use noVNC's clipboard
   side panel, then press **Ctrl+V** inside Chromium (**Cmd+V does not
   apply** inside the remote desktop).
3. (No data-export step — on Thursday, before any shopping run, your
   agent reads your order history once in a short questionnaire-blind
   **bootstrap session** and writes your purchase profile, which is
   then frozen and shared by all four runs.)
4. Wednesday: pause Browsing History (pre-flight gate), then
   **`dtlab-shop`** — shop the task set yourself in the instrumented
   browser (clickstream logged: searches, product views, cart clicks),
   confirm your picks. Everything lands in the quarantined human
   folder, which the
   agent is barred from reading; your picks are now committed (one
   attempt — a redo needs a TA reset).
5. Thursday and Friday: two agent runs per day — persona and ablated
   grounding, on that day's model tier. **The TA announces the setting
   live in class before each run** — listen for it, then set the
   matching switch before you run `dtlab-start`:
   ```bash
   dtlab-persona on      # TA says "persona on" — grounded run
   dtlab-persona off     # TA says "persona off" — ablated run
   dtlab-tier economy    # TA says "economy tier"
   dtlab-tier frontier   # TA says "frontier tier"
   dtlab-persona status  # check what's currently set, any time
   dtlab-tier status
   ```
   Set persona before every single run — it applies to the next run
   only. The tier switch applies once per day (whichever day hasn't
   already picked a tier) and does not need repeating per run. If you
   are unsure what's currently active, run the `status` commands above
   before typing anything — never guess.
   **You never watch your own agent**: you and your partner swap seats
   for every run; the partner handles CAPTCHAs, runs `dtlab-cart` after
   each run (automatic cart screenshot + parsed cart contents into
   `~/dtlab/evidence/`, checked on the spot against the agent's picks —
   fix any mismatch before emptying), records intervention counts,
   and empties the cart between runs — always with **Delete**,
   never "Save for later" (saved items stay parked on the account and
   corrupt later runs' cart evidence; `dtlab-cart` warns if it sees
   them). `dtlab-start` walks each run (pre-flight, history re-pause
   gate, payment check, per-run SOUL + model configuration);
   `dtlab-record` captures the
   screen (start it only after login). You do NOT open your agent's
   artifacts on Thursday — judgment is blind and happens once.
6. Friday, after run 4: **the blind verdict session** — `dtlab-verdict`
   presents each task's four picks in a randomized Run A–D order
   (nothing tells you which was persona/ablated or economy/frontier)
   and captures, per task and run, your verdict (better/identical/
   equivalent/inferior), satisfaction ratings (1–10), and a one-line
   rationale, then the head-to-heads — all before the mapping is
   revealed. Stored answers are final; the Overall reflections come
   after the reveal.
7. Friday close: `dtlab-pack` (validates everything, redacts
   keys/PII from logs, scans the final archive) → download the single
   `DT2026-###_evidence.zip`
   via the VS Code explorer → upload it to the **BITSoM LMS**
   assignment → stop the codespace.

## The seven deliverables and how they're captured

| # | Deliverable | File in the submission zip | Produced by |
|---|---|---|---|
| 1 | Questionnaire with answers | `persona_survey.csv` + `.md` | Google Form → `make_persona.py` |
| 2 | Purchase history | `purchase_profile.md` — written by the agent from the logged-in Your Orders pages ONCE, in the pre-treatment questionnaire-blind bootstrap session (capped at ~30 orders/12 months; every claim traceable to a seen order), then frozen read-only and hash-verified at every run; a per-run snapshot is packed. Precise raw CSV only via the optional post-course add-on. | bootstrap session (`dtlab-start` Phase 0) |
| 3 | The 5 category tasks, in the student's randomized order | `tasks.md` | generated from `tasks_config.csv`; ordered per student by `dtlab-start` |
| 4 | Full agent trace, all four runs | `run1/`…`run4/decision_log.md` + per-run `hermes_logs/` (each run launches in its own Hermes home, so exactly one transcript set maps to each run; a completed run without a trace blocks the pack) | SOUL.md protocol + per-run Hermes home |
| 5 | Items the agent added to basket, per run | `run1/`…`run4/agent_picks.csv` + `cart_run1..4.png`/`.json` (automatic screenshot + parsed cart contents via `dtlab-cart`, cross-checked against the picks — `cart_verified` per run) | SOUL.md protocol + `dtlab-cart` |
| 6 | The student's own pick per task + HOW they shopped | `human_picks.csv` + `human_session.jsonl` (clickstream: searches, product views, cart clicks, timestamps; one committed attempt) | `dtlab-shop` (log_human_session.py), quarantined outside every agent path |
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
picks-vs-cart cross-check), collects each run's Hermes transcripts
from that run's own Hermes home (per-run; a completed run without a
trace is a blocking issue), computes SHA-256
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
category link; rationale and sources in `docs/TASK_CATEGORIES.md`).
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

(`pip install pandas plotly`, versions pinned in ci.yml; scipy
optional.) Useful flags: `--decisions decisions.csv` (auditable
include/exclude overrides for quarantined packs), `--export-runs` /
`--export-hth` (the `dtlab-runs-v1` / `dtlab-hth-v1` research tables),
`--hedut hedut_responses.csv` (the Session-10 HED/UT poll), and
`--identified` (instructor-only diagnostic copy with pseudonyms in
hover — the default class report carries none).
**See [docs/sample_report.html](docs/sample_report.html) for a complete
sample** — generated from a small synthetic cohort fabricated by
`tests/test_analyze_cohort.py` and clearly titled as such; every number
in it is fake, but the layout, charts, statistics, and branding are
exactly what a real cohort produces. The output
is ONE self-contained HTML report for the class debrief: verdict
distributions by task, grounding, and tier,
acceptable-pick rates with cluster-bootstrap 95% CIs, head-to-head
winners and pick overlap, own-vs-agent satisfaction ratings, price
scatter and listed-price
budget compliance, brand/price alignment with the purchase profile,
history-length descriptives, contamination against the cross-student
permutation baseline, a statistics table (H1–H3 with student-level
sign-flip permutation p-values, Holm-adjusted over exactly that family;
everything else exploratory), robustness rows, quarantine and
version-count tables, and a data-quality
section. Packs with validation issues, mismatched configurations, or
duplicate IDs are quarantined from the confirmatory set by default and
listed with machine-readable reasons. Charts are plotly (hover/zoom
live in the HTML).

Everything else — Hermes, Playwright, Chromium, SOUL.md, scripts, aliases —
is pre-baked by `.devcontainer/setup.sh` (Codespaces, primary) or
`provisioning/provision.sh` (VM fallback).

## Build checklist (TA executes; instructor signs off)

- [ ] Consent & data-use sheet finalized and staged on the LMS
      (`docs/CONSENT_AND_DATA_USE.md` — set the withdrawal date and
      contact; partner-pairing disclosure included; see
      research_protocol.md §3)
- [ ] Build Form via Apps Script; test-submit once; confirm response Sheet
- [ ] Pin installer checksums (TA_ONBOARDING.md), make the repo a template,
      enable Codespaces prebuilds
- [ ] **Dry run of the full path yourself from a codespace**, ~3 weeks out
      (T-21): build, persona generation, `dtlab-shop`, `/browser connect`,
      Bootstrap, one full task, `dtlab-pack` — working the T-21 dry-run
      list at the top of `docs/CHANGELOG.md`
- [ ] Confirm the student-key model end-to-end: every student's own Anthropic account, one key, ~$20 monthly spend limit (Monday homework); 2–3 course-owned spare keys staged for setup casualties
- [ ] LMS: assignment sheet (pseudonym + per-day grounding order + tier order + pair — one make_counterbalance.py output), evidence upload slot
- [ ] Synthetic persona pack for opt-outs (fictional Form row — generate
      once, reuse; doubles as the flagged-account sandbox path)
- [ ] Only if the VM fallback is activated: golden images per
      VM_DISTRIBUTION.md (two architectures) + published SHA-256 hashes

## Known-fragility register

1. **Hermes release drift** — commands/paths may shift between now and fall
   2026; the docs are canonical, the handout is best-effort. The
   version-sensitive surfaces each have ONE patch point, validated
   against the pinned release at the dry run:
   `provisioning/hermes_config.template.yaml` (model-config schema),
   the transcript-collection subpath in `tools/pack_evidence.py`, and
   the `HERMES_HOME` delivery in `provisioning/student_start.sh`.
2. **Amazon export format drift** — `clean_privacy_export.py` matches
   `Retail.OrderHistory*` headers fuzzily across export versions; if
   Amazon renames columns, its ALIASES map is the single patch point.
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
   from `questionnaire/questionnaire_instrument_source.md`; any edit that touches only one
   of the two creates silent drift — always change the source doc first,
   re-transfer, and keep `EXPECTED_ITEMS=115` in sync.

## Troubleshooting (lab week)

- **Wrong or revoked API key** — `dtlab-start` verifies the key against
  the Claude API before storing it and refuses rejected keys on the
  spot. If a stale key is already stored (agent runs fail with auth
  errors), reset it and re-enter:

  ```bash
  rm ~/.dtlab_env
  ```

  then run `dtlab-start` again. Rebuilding the container also clears the
  key by design — re-entering it is expected, not a fault.

- **"Stale prebuild" refusal at pre-flight** — the codespace was built
  from a commit older than the course freeze (`DTLAB_EXPECTED_COMMIT`).
  Rebuild the container (Command Palette → "Codespaces: Rebuild
  Container") or create a fresh codespace; the check exists so no one
  runs the week on an outdated kit.

- **Codespace stops mid-run (idle timeout)** — set the idle timeout to
  240 minutes at [github.com/settings/codespaces](https://github.com/settings/codespaces)
  **before Thursday**, and keep the VS Code tab active during agent
  runs: the noVNC Lab-Desktop tab alone does not count as activity, so
  a codespace can suspend under a running agent.
