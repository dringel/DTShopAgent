# Kit changelog

## 2026-07-24 — Doc alignment pass (audit Part A)

- **Session topics aligned to the published syllabus:** the Hermes +
  SOUL.md deep dive moves to Session 8 (Wed), the "When to Specialize"
  lecture to Session 9 (Thu) as a 30-minute opener; Thursday's run
  slots are ~55 minutes each and Monday's freed block becomes codespace
  build + lab-tour time (COURSE_PLAN_1WEEK.md session tables).
- **Retired-design text removed from current-voice sections:**
  design_rationale §2/§7/§9/§10 and questionnaire_instrument_source §1
  now describe the operative within-student tier-by-day 2×2 (no order
  arms, no between-subjects tier); research_protocol §1 verdict
  vocabulary updated to better/identical/equivalent/inferior and the
  ablation factor stated as adopted (dtlab-choices-v1.1 operative).
- **Command surface corrected to six commands** (dtlab-cart and
  dtlab-verdict restored) in CLOUD_SETUP, VM_DISTRIBUTION, and
  TA_ONBOARDING; verdict capture (not the comparison memo) named as the
  owners' first contact in PERSONALIZATION_PROTOCOL and
  design_rationale; TA_ONBOARDING's license section now points at
  LICENSE.md; README build checklist reflects the student-owned-key
  model and the pseudonym/order/pair LMS sheet.
- **Capstone wording (recorded):** the capstone is an individual white
  paper of up to 5 pages (supersedes the earlier 3–5 page essay
  wording; operative text in COURSE_PLAN_1WEEK.md and
  docs/SYLLABUS_BLURB.md).
- Smaller consistency fixes: VC06 labeled a stated-preference item (not
  CONSTRAINT) in TASK_CATEGORIES; Tuesday-morning straggler
  regeneration in COURSE_PLAN's risk table; five-task cost figure in
  design_rationale §2; dry-run wording in root-level files.

## 2026-07-24 — CI fixed (ruff 0.16 drift) + "how this runs" explainers

- **CI failure root-caused and fixed:** ruff 0.16.0 (installed fresh by
  CI on every run) expanded its default rule set; local installs on
  0.15.x kept passing — same command, different rules. Fix: `ruff.toml`
  at the repo root now selects the rule set EXPLICITLY (deliberate
  exclusions documented in-file), and ci.yml pins `ruff==0.16.0` so
  local and CI stay byte-identical; bump both together. The useful
  new-default findings were adopted (executable bits restored on all
  shebanged scripts, import ordering, `startswith` tuples, explicit
  `subprocess.run(check=)`, shadowed loop variables renamed);
  `_to_delete/` excluded from linting.
- **Plain-language architecture explainers added** (for novices):
  README > "How this actually runs" and TA_ONBOARDING > "First: the
  mental model" — the repo is a recipe that executes nothing; CI is
  only the test suite (green ✓ = safe to build environments from that
  commit); students click *Create codespace* and get a private
  container built FROM the repo (no cloning, no pushing); student data
  never enters git; the VM fallback is instructor-built. Freeze →
  CI green → prebuilds, in that order.

## 2026-07-23 — Monday-assigned setup + syllabus week-2 text

- **Nothing is assigned to students before Session 6** (instructor
  constraint). The pre-week student checklist is replaced by **Monday
  homework, assigned in Session 6, due Monday 22:00**: consent, the
  115-item Form, Anthropic account/key/$20 limit. This works because
  the questionnaire needs only the Form link + pseudonym (any device —
  no repo or codespace dependency); personas are batch-generated Monday
  night. Session 6's checkpoint 1 becomes "codespace built + Lab
  Desktop opens" (no key needed); the agent smoke run and key entry
  move to Tuesday's checkpoint 2. Docs updated: COURSE_PLAN (before-
  the-week/Monday-homework sections, Session 6/7 tables, risk rows),
  README, TA_ONBOARDING, research_protocol §4, design_rationale §2.
- **docs/SYLLABUS_BLURB.md** now carries the punchy week-2 syllabus
  block (session hooks + preps + links + Monday-homework line) ahead of
  the lab-project and capstone blurbs.


## 2026-07-23 — Post-revision consistency review (full-repo pass)

Independent review after the major revision; all suites re-run green in
a clean environment (harness 49, start-flow 57, lockstep, analyzer,
ruff, shellcheck). Fixes applied:

- **Spend limit unified at $20** (TA_ONBOARDING, research_protocol §4,
  design_rationale §2 — three stale ~$10 mentions).
- **Catalog count corrected to 11** (6 utilitarian incl. laptop, 5
  hedonic) in README, COURSE_PLAN, TA_ONBOARDING, research_protocol;
  `docs/TASK_CATEGORIES_10.md` brought fully current: laptop entry
  added (Crowley et al. PCs-as-utilitarian anchor, stakes-gradient
  role, no-OS-signal ecosystem test), active-five status and
  randomized-order mechanics documented, retired gift footnote and
  stale search-only wording replaced, budget-pair table updated.
- **Humanlog schema refs unified at v1.3** (research_protocol §1 table
  + §6 registry now name v1.3 with the additive v1.1/v1.2/v1.3 notes).
- **PR09 annotations updated** in the instrument source and
  AUTHORING_GUIDE (general stated-preference item; keep-or-swap at
  freeze) — item wording untouched, lockstep green.
- **PERSONALIZATION Layer 1** now states the daily re-pause cadence
  (Wed/Thu/Fri) instead of the retired one-day "both sessions" framing.
- **design_rationale**: §8 no-ask-back now says all three SOULs; the
  §8 seven-deliverables paragraph modernized (dtlab-cart cross-check,
  dtlab-verdict capture, per-run bookkeeping — replaces comparison.md/
  arm-era wording).
- **.gitignore** extended for the new runtime artifacts: verdicts.csv,
  head_to_heads.csv, overall_reflections.md, task_order.txt,
  persona_order_day*.txt, sandbox.txt, cart_run*, *.bak.
- Local junk (__pycache__/, .DS_Store, .ruff_cache/) moved out of the
  working tree to _to_delete/ for manual deletion.


## 2026-07-23 — Task set: five self-purchase categories, randomized order

Instructor decision (same day, after the 4-run implementation): the
classic replenish/considered/gift frames are RETIRED — this experiment
estimates how well a twin buys for its own person; gift buying (a third
party) and habitual replenishment are different research questions.

- **`tasks_config.csv`:** active set = five self-purchase categories.
  Provisional five (instructor-tuned same day: sneakers over sunscreen;
  laptop over chocolate/gift — a rejected gift variant is recorded
  below): **sneakers, power bank, backpack, laptop, perfume** — 3
  utilitarian + 2 hedonic, sneakers/backpack and power bank/perfume as
  price-matched hedonic/utilitarian pairs, and the laptop
  (₹40,000–1,20,000, new catalog row; ceiling reaches MacBooks — the
  Apple-vs-Windows choice is a clean brand-ecosystem inference test
  since the lab container leaks no OS signal) as the HIGH-STAKES
  anchor: a considered durable where a wrong agent pick clearly
  hurts, giving the set a stakes gradient from ₹800 accessory to
  ₹1.2L laptop.
  **The teaching team makes the final pick** (TA_ONBOARDING work
  item); the remaining candidates stay as `#` catalog rows (now 11,
  chocolate re-parked); all frames are "Self-purchase". A
  gift-for-best-friend fifth category was considered and REJECTED
  (same reasoning as the morning ruling: modeling a third party is a
  different research question; PR09 would have leaked the answer to
  the persona run). Templates
  regenerated (5 tasks; students edit NOTHING in tasks.md any more);
  `templates/human_picks.csv` extended to 5 rows. Instrument note:
  PR09 (authored as the gift benchmark) stays a general
  stated-preference item — keep or swap at instrument freeze.
- **Per-student randomized task order** (what an agent picks in one
  category can influence the next): derived deterministically from the
  pseudonym (per-task SHA-256 ranking — no LMS column, mechanically
  reproducible), randomized ACROSS students, held CONSTANT within a
  student (human session + all four runs, so every within-student
  contrast faces identical sequences). Enforced, not instructed:
  `dtlab-start` re-orders the tasks.md sections at pre-flight
  (idempotent; announces the order; writes `~/dtlab/task_order.txt`),
  `dtlab-shop` presents tasks and confirms picks in the same order,
  both standardized prompts say to work in tasks.md order, and the
  packer records `task_order` + `task_order_expected` in the manifest
  (non-blocking warning when tasks.md was re-sorted by hand). The
  analyzer adds per-row task_position and a late-vs-early
  position-effect stat row (cluster-bootstrap CI). The order function
  is in LOCKSTEP across student_start.sh, log_human_session.py, and
  pack_evidence.py (marked at each site).
- **Tests:** the harness's fixture environments now carry their OWN
  compact 3-task config (the validation chain is config-driven, so
  fixtures stay stable when the team changes the shipped five);
  check 17 verifies the 5-task templates byte-identical + the in-order
  prompt line; new check 24 (task-order recorded, hand-re-sort
  warned); start-flow check 11 (pre-flight re-orders tasks.md,
  idempotent, announced). The analyzer fabricator moved to the
  5-category set with task_order manifests; sample report regenerated
  (pure 2x2, five categories, no legacy 'single' series).
- **No asking back (autonomy is the treatment).** All three SOULs now
  forbid the agent from asking the human anything during a task
  (CAPTCHA halt is the sole exception): where the grounding is silent
  it notes the gap and chooses conservatively. Rationale
  (design_rationale §8): a deployed agent would ask back — that
  interactive regime is a different study, and a mid-run answer is
  un-ablatable information that would contaminate the grounding
  contrast. The partner instruction in dtlab-start matches: never
  answer agent questions; log the exchange as an intervention.
- **Consistency sweep:** `tasks_config_6task_example.csv` modernized
  to a self-purchase worked example (old replenish/gift rows removed);
  sandbox SOUL's gift-interpretation example generalized; README
  deliverable #6 wording de-hardcoded from "3 items"; stale "3 tasks"
  phrasing removed from the analyzer's stats note and the packer's
  fallback comment; sample report regenerated from the current config.
- **Shopping-process length is now measured** (instructor request:
  time, steps, searches, filters, products viewed before selection).
  New ECP line in all three SOULs: `SRCH | task= | query= | filters=`
  per search the agent runs (schema dtlab-searches-v1 →
  `manifest.searches`; missing SRCH lines = warning, like CAND). New
  `manifest.process` block: human {session duration, searches, views,
  filter_sorts, cart_adds, per_task {minutes, searches, views,
  filters}} and per-run agent {duration_min: started_at → picks-file
  mtime}. **dtlab-shop is now a guided one-task-at-a-time session**
  (humanlog v1.3: task_start/task_end events, Enter after each
  cart-add) — instructor's point: humans DO shop one item at a time,
  so per-task attribution of every metric is exact by construction
  (`attribution: task_markers`); cart-add segmentation along the
  assigned order remains the approximate fallback for logs without
  markers (`cart_add_segments`).
  Products-viewed already existed (CAND). Analyzer: three new charts
  (searches per task twins-vs-human; run duration vs human session —
  same unit, both cover the task set once; human minutes per task) and
  two stat rows (Deliberation time: frontier − economy paired run
  duration; human-vs-agent time descriptive). Per-task AGENT timing
  needs Hermes transcript timestamps — dry-run item 2 covers the
  transcript format. Harness checks 14 (SRCH parse + missing-SRCH
  warning) and 25 (process block end-to-end).
- **Timing flag:** 5 tasks x ~10-min SOUL cap brushes the ~60-min run
  slots — dry-run timing check added (COURSE_PLAN risk row +
  TA_ONBOARDING); tighten the per-task cap or trim a category if
  needed; the laptop task is the likeliest to hit the cap on both the
  human and agent side. Docs synced: README (task-set section
  rewritten), COURSE_PLAN (design paragraph, session 7, run-stall risk
  row), research_protocol §1 + §6 (order fields), design_rationale §8
  (decision + rationale recorded).

## 2026-07-23 — Four-run 2×2 tooling implemented (WORK_ORDER_4RUN closed)

The code gap specified in `docs/WORK_ORDER_4RUN.md` is closed; the spec
file is kept (banner marks it implemented). All suites green: harness
42, start-flow 51, lockstep 16, analyzer (10-student mixed synthetic
cohort incl. LMS-renamed + sandbox zips); ruff + shellcheck clean.

- **`student_start.sh`: four-run state machine.** `runs/run1..run4`,
  each with `condition.txt` + `tier.txt` + `started_at.txt`; runs 1–2 =
  `DTLAB_DAY1_TIER` (economy), runs 3–4 = `DTLAB_DAY2_TIER` (frontier;
  constants in `dtlab_config.env`). Per-day grounding order prompted
  once per day (`persona_order_day1/2.txt`); condition derived from
  day order + run index; crash-resume prompts name run, tier, and
  condition. Day-2 gate: before run 3 the browsing-history re-pause
  (lapsed 1-day pause) must be freshly confirmed. The H_FIRST/A_FIRST
  arm prompt and the legacy per-student `TIER_FACTOR` prompt are
  retired: all students are human-first (`arm.txt` auto-written
  H_FIRST; `dtlab-shop`'s files are a hard pre-flight gate), and tier
  is per run (`~/dtlab/tier.txt` still written for backward compat).
  Also implemented: `DTLAB_SANDBOX=1` end-to-end (C1/C3 — sandbox SOUL,
  soft gates, books.toscrape.com, marker hygiene, packer stamp +
  report banner + analyzer exclusion) and the `DTLAB_TEST=1` hook the
  state-machine test drives (W2).
- **`pack_evidence.py`: three design generations auto-detected**
  (single / legacy 2run / 2x2 via per-run tier files). 2x2 packs:
  verdict keys `{task}_{condition}_{tier}`; per-run validation (picks,
  ASINs, condition, tier, decision log); a missing run is an issue
  NAMING the run, the pack still builds; manipulation check on EVERY
  ablated log; contamination per condition_tier; ablation manifest
  block with per-run {condition, tier, started_at}, per-day grounding
  orders, the four head-to-head maps (grounding winner per tier, tier
  winner per grounding), four pick-overlap sets, per-run
  manipulation-check results, `cart_verified`; per-run model IDs from
  `DTLAB_MODEL_ID_DAY1/2` (fallback `DTLAB_MODEL_ID`); CAND `source=`
  strings normalized into provenance buckets {search, carousel,
  buy_again, product_page_link, category_page, other} (raw kept).
- **`dtlab-cart` (new `tools/capture_cart.py`).** Partner-run cart
  evidence: attaches over CDP to the already-running lab browser
  (`DTLAB_CDP_PORT`, same profile), saves `cart_runN.png` (full-page)
  + `cart_runN.json` (parsed asin/title/price/qty; SELECTORS dict is
  the single patch point, degrades to screenshot-only). Packer prefers
  the JSON and cross-checks `agent_picks.csv` against the actual cart
  (mismatch = non-blocking warning naming items; match =
  `cart_verified: true` per run). Cart EMPTYING stays a human action.
- **`dtlab-verdict` (new `tools/capture_verdicts.py`).** Guided,
  input-validated capture replacing memo editing: per task × run —
  verdict (ASIN-consistent choices enforced live), own/agent ratings
  (1–10), one-line rationale → `verdicts.csv` (dtlab-verdicts-v1);
  per-task head-to-heads for every contrast whose two cells exist →
  `head_to_heads.csv`; Overall reflections (incl. the tier question)
  → `overall_reflections.md`, asked once all four runs exist.
  Idempotent + resumable (Thursday economy rows, Friday the rest).
  The packer reads these as the PRIMARY verdict source (`rationales`
  passthrough in the manifest); comparison.md parsing stays as the
  backward-compatible fallback.
- **Templates regenerated from the generator** (now byte-identical,
  enforced by a harness round-trip check): `comparison_ablation.md` is
  the 2x2 memo — four compact blocks per task (verdict + two ratings +
  one Attribution line), ONE per-task synthesis section, four
  machine-parsed head-to-head lines per task, Overall with the tier
  question; `tasks.md` notes that dtlab-start announces which prompt
  each run uses.
- **`analyze_cohort.py`: 4-run ingestion** (rows keyed student × task
  × condition × tier; 2-run and single-run packs still parse; sandbox
  packs excluded with a stderr note). New/updated: verdicts faceted
  grounding × tier; acceptable-rate 2×2 grid with cluster CIs;
  grounding head-to-head per tier + NEW tier head-to-head per
  grounding; pick-overlap per contrast family; candidate provenance-
  mix chart (source buckets); stats rows for the tier effect (paired,
  overall + per grounding, McNemar + cluster bootstrap, in the Holm
  family), the grounding × tier interaction, frontier win share, the
  within-day run-order estimate, and the tier-confounded-with-day
  caveat row. Fixed in passing (C4): `price_in_profile_range` is now
  None (excluded) when either price is unknown, instead of False.
- **LMS flow locked in tests:** the analyzer test feeds an LMS-renamed
  zip (`lastname_12345_DT2026-042_evidence.zip`) — identity resolves
  from inside the zip; a fabricated sandbox pack must be skipped.
  `docs/sample_report.html` regenerated from the new 10-student mixed
  synthetic cohort (visually verified). Screen recordings remain
  optional (RECORDINGS.txt notes absence, never fails validation).
- **Both provisioners** ship the two new tools + `dtlab-cart` /
  `dtlab-verdict` aliases. Docs synced: README (student surface,
  deliverables #4/#5/#7 wording, contents tree, fragility-register
  renumbering — C5a), TA_ONBOARDING, design_rationale §5b Bootstrap
  note, dtlab_config.env (day-tier constants; TIER_FACTOR retired).
- **The human joins the report as a reference series (same-day
  follow-up).** The human logger now records the amazon `ref=` slug on
  every product view (`dtlab-humanlog-v1.2`, additive; the slug in the
  logged URL path serves as fallback for older logs), and the analyzer
  buckets it into the SAME provenance buckets as the agent's CAND
  `source=` field — the provenance chart shows agent candidates and
  human views side by side (caveats labeled: candidates vs views,
  undocumented slugs, T-21 item 14). The human's own picks also join
  the alignment/compliance chart (brand-in-profile, price-in-profile-
  range, task budget; no sponsored flag in the human log) and the
  consideration-set chart (session views ÷ tasks, labeled as an
  approximation since clickstream views are not task-attributed);
  verdict/rating/price charts already contain the human by
  construction, head-to-heads are agent-vs-agent by design. The human
  series renders in a neutral dark everywhere. `docs/sample_report.html`
  is now generated from a PURE 2x2 synthetic cohort (the shape the real
  cohort produces — no legacy 'single' series); the analyzer test keeps
  the mixed cohort (2x2 + 2run + single + renamed + sandbox) for
  backward-compat coverage (`fabricate_cohort(mixed=...)`).
- Still open (instructor's call): commit + push + CI on GitHub (N4 —
  git state stays untouched by design), and the dry-run-only T-21
  items below (now 14: cart selectors + ref-slug mapping added).

## 2026-07-23 — Plan of record: the four-run 2×2, full-site agent, capstone essay

Instructor decisions folded into the kit (docs updated; tooling gap
specified in `docs/WORK_ORDER_4RUN.md` for Claude Code):

- **Design:** within-student 2×2 — grounding (persona/ablated) × model
  tier (economy Thursday / frontier Friday), four agent runs per
  student against Wednesday-committed human picks. Grounding order
  counterbalanced per day; tier confounded with day by design (stated
  in methods). `DTLAB_PERSONA_FACTOR=1` shipped; legacy per-student
  tier factor superseded. Spend-limit guidance now $20.
- **Order arms retired:** all students human-first (Wednesday). The
  primary estimands are within-student contrasts across runs sharing
  the same human-perturbed account, so common carry-over cancels;
  absolute agreement keeps pause + targeted block + per-run index.
- **Assessment blinding universal:** nobody watches their own agent —
  self-selected pairs swap seats every run (CAPTCHAs, cart screenshots,
  cart emptying by the partner); owners meet their agent's output as
  artifacts when writing the memo. Consent names the pairing.
- **Agent browses the full site:** the search-only rule is replaced by
  a targeted ban on browsing-history-derived modules only ("Previously
  viewed", "Inspired by your browsing history", "Keep shopping for") +
  autosuggest, with every candidate provenance-logged
  (`source=search#rank|carousel:<name>|buy_again|product_page_link|
  category_page`). Both SOULs, PERSONALIZATION Layer 2, and
  design_rationale §7 updated; process comparison becomes symmetric and
  choice-architecture exposure becomes a measured variable.
- **Week integrated with Sessions 6–10** (COURSE_PLAN_1WEEK.md fully
  rewritten): Mon intro+Hermes/SOUL, Tue architectures+build-complete,
  Wed model-portfolio lecture + dtlab-shop, Thu economy runs 1–2,
  Fri frontier runs 3–4 + hyperpersonalization debrief; pre-week
  checklist (consent, Form, Anthropic account, GitHub) due Sunday.
  Capstone = individual 3–5 page essay on own pack + cohort report
  (`docs/SYLLABUS_BLURB.md`).
- **Evidence capture automated (work-ordered):** `dtlab-cart` replaces
  manual cart screenshots — CDP-attached capture of screenshot + parsed
  cart JSON per run, cross-checked against agent_picks.csv at pack time
  (cart_verified per run); cart emptying stays a human action. Verdict
  capture moves from markdown editing to the guided `dtlab-verdict`
  prompt (verdicts.csv, schema dtlab-verdicts-v1: verdict + ratings +
  one-line rationale per task × run, plus head-to-heads and Overall
  reflections) — structured, resumable, format-error-free at N=161.
  Submission flow pinned to the BITSoM LMS (bulk-download renaming is
  harmless; identity lives inside the zip); screen recordings demoted
  to optional evidence. Specs: WORK_ORDER_4RUN §7–9.
- Docs updated: COURSE_PLAN (rewrite), PERSONALIZATION (Layers 2+4,
  methods paragraph), SOUL + SOUL_ablated, README (intro, factors,
  student experience), research_protocol §1, TA_ONBOARDING,
  dtlab_config.env, design_rationale (§5b, §6, §7), SYLLABUS_BLURB
  (new), WORK_ORDER_4RUN (new). All suites re-run green.

## THE T-21 dry-run list (live — the one canonical copy)

Things that cannot be verified from code; work through ALL of them in the
instructor dry run. (Older entries below carry earlier snapshots of this
list; this section is the maintained one.)

1. **Hermes `/browser connect` mechanics** — verify it attaches to the
   CDP port (`DTLAB_CDP_PORT=9222`) and profile launched by
   `tools/dtlab_browser.sh`; adjust the constant if the pinned release
   expects something else.
2. **Hermes transcript paths** — `pack_evidence.py` guesses `~/.hermes`
   and `~/.config/hermes`; confirm, or override with
   `DTLAB_HERMES_DIRS=/path/one:/path/two`.
3. **Installer pins** — pin Hermes/uv URLs + SHA-256 and the Playwright
   version in both provisioners (TA_ONBOARDING.md > "Updating installer
   pins"); builds refuse to run unpinned.
4. **noVNC password rotation** — confirm the rotation in
   `.devcontainer/setup.sh` actually takes effect in a built codespace.
5. **Model ID capture** — confirm how the pinned Hermes exposes the
   model actually used; until then set `DTLAB_MODEL_ID` for the
   manifest.
6. **Codespaces quotas** — reconcile the 120 vs 180 core-hours figures
   against GitHub's current docs (`CLOUD_SETUP.md`).
7. **Google Forms scale** — one `buildForm()` run creates all 115
   questions + 16 page breaks without hitting Apps Script quotas.
8. **Browser profile sharing** — Playwright (`executable_path` = system
   chromium) and the agent session tolerate the shared
   `~/.dtlab-browser-profile` (version skew was the risk).
9. **Breadcrumb selector** — `#wayfinding-breadcrumbs_feature_div`
   still yields categories on live amazon.in product pages (degrades to
   empty category, never an error).
10. **CAND compliance** — the agent actually follows the `CAND |` line
    format under the pinned Hermes/model; check the dry-run manifest's
    `candidates` and `warnings` fields.
11. **Token/cost benchmark across tiers** — one full single-category
    task under Haiku-class and Sonnet-class, each with and without
    extended thinking, repeated over 2–3 categories; record tokens, $,
    wall-clock, success (TA_ONBOARDING work item). Sets the per-key cap
    and informs the model-tier decision.
12. **Category links** — spot-check the `amazon_url` browse-node links
    in `tasks_config.csv` still resolve to the intended categories on
    live amazon.in.
13. **Cart selectors (`dtlab-cart`)** — validate the SELECTORS dict in
    `tools/capture_cart.py` against the live amazon.in cart page (run
    a real agent-filled cart through `dtlab-cart`, check
    `cart_runN.json` items + the packer's `cart_verified` result;
    parsing failure degrades to screenshot-only by design).
14. **Human ref= provenance mapping** — during the dry-run human
    session, spot-check that amazon's ref= slugs on product views
    (search results, a carousel, Buy Again, a category page) land in
    the right buckets via `analyze_cohort.py::bucket_ref` (unknown
    slugs fall to 'other' by design; adjust the mapping there).

## 2026-07-23 — Task-category catalog, HED/UT measurement, tier cost benchmark

- **10-category catalog shipped in `tasks_config.csv`** (5 utilitarian:
  sunscreen, power bank, backpack, kettle, umbrella; 5 hedonic:
  chocolate, perfume, sneakers, speaker, room décor), budget-paired
  across classes, each row carrying its amazon.in category link in the
  new `amazon_url` column. Rows are activated/deactivated with a leading
  `#` on task_id; all four task-config readers (packer, human logger,
  make_task_docs, cohort analyzer) skip `#` rows. Selection rationale +
  per-category sources: `docs/TASK_CATEGORIES_10.md`. Classic 3-task
  design remains the active default — behavior unchanged.
- **make_task_docs.py brace fix**: generated templates now emit single
  braces (`{better|...}`), matching the shipped hand-authored templates.
- **HED/UT manipulation check** added as a TA work item: Voss et al.
  (2003) 10-item scale for the chosen categories (questionnaire add-on
  or in-class poll); cohort-measured scores are the classification of
  record for dual-attribute categories (backpack, sneakers).
- **Tier cost benchmark** added to the TA list + dry-run list: Haiku vs
  Sonnet, each with/without extended thinking, over 2–3 single-category
  runs — tokens, $, wall-clock, success — to set per-key caps and inform
  the model-tier decision (course policy stays model defaults).
- Wording pass across docs for a consistent package voice
  (PERSONALIZATION_PROTOCOL, CLOUD_SETUP, design_rationale,
  TA_ONBOARDING); no substantive changes.
- **Cohort corrected to N=161** (two sections: 80 mornings + 81
  afternoons, 3h/day × 5 days) across all docs — replaces the earlier
  N=180 planning figure. Derived numbers updated: ~80 per arm for the
  equivalence-margin power text, ~80 peak concurrency (the section split
  staggers Wi-Fi/API load by itself), 161 keys + spares, per-section
  triage estimates. Arms and optional factors randomize stratified by
  section.
- **API key model switched to student-owned Anthropic accounts**
  (instructor decision, 2026-07-23; reverses design_rationale §2's
  earlier single-workspace choice, rationale updated in place). Each
  student creates their own Console account before lab week (LMS
  checklist: billing, small credit purchase, personal ~$10 monthly spend
  limit, one key). Rate limits are per account — ~80 concurrent agents
  share no pool; cache reads are exempt from input-token limits. Docs
  updated: README, COURSE_PLAN (prep item + risk row), TA_ONBOARDING
  (setup-checklist work item), research_protocol §4, design_rationale
  §2, student_start.sh prompt text. 2–3 course-owned spare keys remain
  for failed setups.
- **Wi-Fi risk quantified** for the BITSoM rooms (rated 100 concurrent):
  ~80 noVNC streams × 1–3 Mbps ≈ 160–300 Mbps sustained in long-lived
  websockets. IT checklist added (WAN headroom 2×, ≤25–30 active
  clients/AP, no captive-portal re-auth or websocket idle timeout within
  3h, no per-user throttle <3 Mbps, phones on mobile data) + a 15–20
  student pilot in the actual room.
- All suites re-run green: harness 20/20, lockstep 13/13, ruff,
  shellcheck.

## 2026-07-22 — Standalone instrument source + author attribution

- `questionnaire/questionnaire_instrument_source.md` is now fully
  standalone: all references to the earlier source document and its
  Korea artifacts removed; §1 reframed as "Design decisions"
  (included/excluded with ALL reasoning retained — validated-scale
  selection per the Twin-2K-500 battery, ECP definition,
  serialization, exclusion rationale citing the funhouse-mirrors
  mega-study); §3 replaced with a full APA reference list (13 entries,
  DOIs, verified against publisher/arXiv sources); §4 checklist updated
  to the config-file era; author byline added. Item wording in §2 is
  untouched (lockstep test green). Cross-references in
  research_protocol.md, design_rationale.md, and TA_ONBOARDING.md
  updated to the standalone framing.
- Author attribution "Daniel M. Ringel · ringel.AI" added to the grader
  report footer (report.html in every zip), the cohort report footer,
  SUBMISSION_INFO.txt, and the README byline.
- Every figure in the cohort report is branded IN the figure itself
  (survives PNG export and copy-into-slides), placement legend-aware:
  charts with a right-side legend carry the mark directly UNDER the
  legend, aligned with its column and styled like a legend entry
  (logo, then the clickable bare-text "ringel.AI" link); charts without
  one carry it bottom-right in the margin band. One change in
  `style_fig()` covers all charts; pixel xshifts keep the logo/text
  pairing exact at any responsive width, and the under-legend y
  position is derived from the legend entry count. `tasks_config.csv` gained an optional `short_name` column so
  config-derived task labels stay readable on faceted axes (both
  shipped configs updated; older configs fall back to a truncated
  product_type).

## 2026-07-22 — Branding, audience map, repo hygiene

- The RingelAI logo lives at `assets/ringelai.png` and is embedded
  (base64, self-contained) in the grader report (`dtlab-pack`'s
  report.html; provisioners copy the logo to `~/dtlab/assets/`, missing
  file degrades silently) and the cohort report
  (`analyze_cohort.py --logo` to override), plus the README header.
- `docs/sample_report.html` added: a complete cohort report generated
  from the 8 synthetic students in `tests/test_analyze_cohort.py`,
  titled "SAMPLE … (synthetic data)" — referenced from the README and
  TA_ONBOARDING so everyone sees the deliverable before real data
  exists. Regenerate after analyzer changes:
  fabricate zips via the test's `make_zip`, then
  `analyze_cohort.py --zips <dir> --out docs/sample_report.html`.
- Class-facing terminology unified in the report: agent types defined
  once in the header (persona / ablated / single); session-order arms
  spelled out as "Human first" / "Agent first" (chart, stats, quality
  table); ablation run order spelled out as "Persona run first" /
  "Ablated run first"; quality-table row labels renamed to match
  ("Session-order arms (counterbalanced)", "Ablation run order
  (counterbalanced)"). Raw codes remain untouched in data, manifests,
  and assignment sheets.
- Report polish: header logo carries the ringel.AI link beneath it;
  verdict-chart task labels break onto two lines (id / short name) so
  narrow facet columns stay readable; arm labels are spelled out
  class-facing ("Human first" / "Agent first") in the contamination
  chart, the arm-effect stat row, and the Data quality table (raw
  H_FIRST/A_FIRST codes remain in the data and manifests).
- README gained "Who uses what" — the one-repo/three-audiences map
  (students: four commands + handout, ignore the repo; TA:
  TA_ONBOARDING + tests + Form/persona tooling, frozen-design files
  need instructor sign-off; instructor/researcher: design docs,
  protocol, instrument, factor switches, cohort analysis) — written for
  the eventual public release; no student data ever enters the repo.
- The completed 2026-07 work order was removed (its content is fully
  reflected in this changelog).
- Fixed in passing: the Codespaces setup.sh was not copying
  `tasks_config.csv` into `~/dtlab/` (the VM provisioner was) — both
  routes now ship it, along with the logo.
- Repo hygiene (same day, earlier): `.gitignore` rewritten — the
  runtime-data pattern `human_picks.csv` had silently kept
  `templates/human_picks.csv` untracked since the initial commit (fresh
  clones would fail provisioning); a `!templates/human_picks.csv`
  negation re-includes it. Junk removed; `.ruff_cache/`,
  `cohort_report.html`, `arm.txt`, `persona_order.txt`, `.dtlab_env`
  etc. added to ignores. `questionnaire_instrument_source.md` moved
  into `questionnaire/` (instructor decision); references updated.

## 2026-07-22 — Structured process logging + configurable task sets

**Structured candidate logging (makes the process comparison
computable).** Both SOULs now require one machine-parsed line per
candidate: `CAND | task= | asin= | category=<breadcrumb> | price= |
sponsored= | source=search#rank`. The packer parses these into
`manifest.json.candidates` (schema `dtlab-candidates-v1`) and gains a
non-blocking **warnings** channel (recorded + printed, exit code
unchanged) for agent non-compliance and malformed candidate ASINs. The
human logger captures the product page's category breadcrumb on every
product_view (`dtlab-humanlog-v1.1`, additive). The cohort report adds
consideration-set-size chart and the agent-vs-human search-overlap
(Jaccard) stat with cluster-bootstrap CI.

**Configurable task sets.** `tasks_config.csv` (task_id, frame,
product_type, category_class utilitarian/hedonic, budgets) is the
single source of task structure: pre-flight-independent, read by the
packer (row counts, verdict keys, head-to-head lines all follow it —
harness check 15), the human logger (pick confirmation prompts, task
count), and the analyzer (task names, budgets, category classes travel
inside each zip's config_snapshot, so submissions are self-describing).
`tools/make_task_docs.py` regenerates tasks.md + both comparison
templates from the config. Shipped: 3-task default (identical to the
classic design; all tests unchanged) + `tasks_config_6task_example.csv`
(sunscreen, in-ear BT headphones, power bank / gift, sweater, LED TV —
3 utilitarian + 3 hedonic). The report adds a fidelity-by-category-class
chart and a paired utilitarian−hedonic stat row whenever both classes
exist. Doc guidance (README "Task set" section, COURSE_PLAN term-start
bullet): pair classes at similar price points to avoid budget
confounds; 6 tasks ≈ +40–50 min human and +45–60 min agent time, and 6
tasks + ablation does not fit one 3-hour session.

Tests: harness checks 14 (CAND parsing + warning path) and 15 (task
count follows the config); analyzer synthetic cohort now carries
candidates, humanlog categories, and a config snapshot, with section
assertions extended. All suites green; shellcheck/ruff clean.

## 2026-07-22 — Robust inference layer in analyze_cohort.py

The cohort report's statistics were upgraded from naive to
publication-grade; every number is reproducible (seeded bootstrap,
n_boot=4000, seed=2026).

- **Cluster-robust CIs everywhere.** Tasks (and both ablation runs)
  cluster within students, so every headline rate, difference, and the
  rate chart's error bars now use a cluster bootstrap that resamples
  STUDENTS; the naive Wilson CI is still shown, labeled, next to the
  overall rate for comparison.
- **Confirmatory contrasts.** Questionnaire effect (persona − ablated)
  as mean of within-student paired differences with bootstrap CI,
  McNemar exact test on discordant tasks, and Cohen's h; head-to-head
  win share with cluster CI + binomial test; sponsored-capture paired
  contrast; price fidelity |log(agent/human price)| paired contrast
  (continuous twin-fidelity measure); run-order effect (run 2 − run 1)
  — the estimate the P_FIRST/NP_FIRST counterbalance exists to enable.
- **Arm effect + equivalence.** Cluster-bootstrap CI, Cohen's h, and
  the pre-registered TOST at ±10 pp via the 90%-CI-inclusion rule;
  plus a minimum-detectable-effect row (report MDE, never post-hoc
  power).
- **Multiplicity.** Holm-Bonferroni adjustment across all p-values in
  the table, shown next to the raw p.
- **Robustness table.** The headline acceptable rate per agent type
  under four specifications: main, excluding packs with validation
  issues, excluding thin purchase profiles (<3 parsed orders), and a
  strict outcome definition (better/identical only).
- **Convergent validity.** New chart (rating delta by verdict category)
  + Spearman ρ row — checks that the categorical verdicts and the 1-10
  ratings measure the same construct.
- Fixed in passing: in mixed cohorts (ablation + single students) the
  paired pivots previously dropped every row via the stray 'single'
  column; conditions are now filtered before pivoting. Test assertions
  extended (incl. a no-NaN-in-stats-table check).

Not computable from the packed data (deliberately not faked): citation-
fidelity shares (needs the human coding pass over decision logs per
research_protocol §5), persona-item → agreement feature importance
(runs on the frozen cohort dataset, not the class report), and human-vs-
agent consideration-set overlap (agent candidates live in free-text
logs; would need a stricter logging format — possible SOUL v2 change).

## 2026-07-22 — Submission completeness + cohort analysis report

**Student side (extends `dtlab-pack` — no new command).** The evidence
zip now additionally carries: per-task **satisfaction ratings** (1-10,
own pick vs agent pick, per run in the ablation design — new machine-
parsed lines in both comparison templates, validated for range at pack
time and recorded as `ratings` in the manifest); a **`config_snapshot/`**
(dtlab_config.env, arm/tier/condition-order files, kit version); a
**`file_inventory`** in the manifest (per-file SHA-256 + bytes +
last-modified UTC timestamp — the audit trail of what the student
changed and when, since copy2 preserves source mtimes);
`first_agent_run_started_utc`; and a **`SUBMISSION_INFO.txt`** stamp.
Every path in the zip sits under `DT2026-###/`, so each extracted file
is uniquely attributable to the student. Harness check 7 extended.

**Instructor side (new `tools/analyze_cohort.py`).** Folder of submitted
zips → ONE self-contained HTML report (plotly-express, plotly.js
inlined) for the in-class debrief: verdict distributions by task × agent
type (persona/ablated/single), acceptable-pick rates with 95% Wilson
CIs, head-to-head winners + pick overlap (ablation), own-vs-agent
ratings, agent-vs-human price scatter with budget diagonals, brand and
price-range alignment against the purchase profile's compact order
lines, history-length descriptives (incl. does-more-history-help
scatter), contamination by arm, a statistics table (paired sign test,
binomial head-to-head, two-proportion arm test with the
equivalence-margin caveat, Wilcoxon on ratings; exact tests when scipy
is present), and a data-quality/coverage section. Charts follow the
validated reference palette (distinct hues per agent type; diverging
blue↔gray↔red for verdict polarity; per-facet ticks on free scales);
all ten charts were rendered and visually verified. Deps: pandas +
plotly (scipy optional). `DTLAB_DEBUG_PNG=<dir>` exports every chart as
PNG for chart QA (needs kaleido).

**Tests/CI.** New `tests/test_analyze_cohort.py` fabricates a synthetic
8-student cohort (6 ablation + 2 single) and asserts the report builds
with all sections; CI runs it after installing pandas/plotly/scipy.
Docs updated: README (submission contents + cohort-analysis section),
TA_ONBOARDING (post-course work item), research_protocol §5 (reporting
view vs analysis-of-record).

## 2026-07-22 — Optional questionnaire-ablation factor (within-subject)

New design factor, default OFF (`DTLAB_PERSONA_FACTOR` in
`dtlab_config.env`); the single-run flow is byte-for-byte unchanged while
disabled. When enabled, the agent runs the SAME three tasks twice —
persona run (questionnaire + purchase profile) vs. ablated run (purchase
profile only) — in counterbalanced P_FIRST/NP_FIRST order, estimating the
questionnaire's marginal value (rationale: `design_rationale.md` §5b;
protocol: `research_protocol.md` §1).

- **`agent/SOUL_ablated.md`** (new): PP-only grounding, same hard
  boundaries + injection hardening + effort caps; explicitly barred from
  persona files and `~/dtlab/persona_hold/`. Both SOULs now reuse an
  existing `purchase_profile.md` instead of re-bootstrapping (holds
  revealed-preference grounding constant across runs).
- **`student_start.sh`**: prompts the assigned condition order; walks
  run 1 → run 2 with crash-safe resume prompts; ENFORCES workspace state
  per condition (persona files physically moved to the hold dir for the
  ablated run, SOUL swapped from kit-owned copies in `~/dtlab/soul/`);
  archives run 1's decision log before run 2 (the ablated agent can
  never read a persona-citing log); swaps in the ablation comparison
  template only while the standard one is unfilled (.bak kept); records
  per-run condition + start time; the arm marker is now touch-once
  (earliest agent start), preserving the arm-ordering semantics.
- **`pack_evidence.py`**: stages `run1/`+`run2/` with conditions;
  validates 3 picks + ASINs per run, verdicts for BOTH runs (run-labeled
  comparison sections, same anti-cascade parsing), head-to-head lines,
  and the **manipulation check** (ablated log cites zero persona item
  codes → hard issue). Manifest gains an `ablation` block (order,
  conditions, start times, head-to-head, pick-overlap tasks,
  manipulation-check result); contamination index computed per run;
  report.html shows both runs; sha256 keys are now staging-relative
  paths (also fixes a latent name-collision in single-run mode).
- **`templates/comparison_ablation.md`** (new): per-task blocks for both
  runs, machine-parsed `Task N winner: persona|ablated|tie` head-to-head,
  constraint-blindness question in Overall. `templates/tasks.md` gains
  the ablated-run standardized prompt.
- **Tests**: harness checks 11–13 (two-run happy path incl.
  persona-files-in-hold, manipulation-check violation, wrong-template
  detection); all 16 checks green, shellcheck/ruff clean.
- **Docs**: research_protocol §1 + schema note (`dtlab-choices-v1.1`
  adds `condition`/`hth_winner` if adopted), PERSONALIZATION_PROTOCOL
  Layer 4 pt 5 (cross-run carry-over = counterbalanced order effect;
  pick overlap is a result, not contamination), README optional-factors
  bullet, COURSE_PLAN term-start decision bullet (+45 min, double key
  cap, consent note), TA_ONBOARDING work item.
- Known limits: consent sheet must name the ablated run's
  constraint-blindness; per-key spend cap should be doubled; the
  manipulation check can in principle false-positive if a product name
  contains an item-code-shaped token (accepted — it surfaces to a TA,
  packs still build).

## 2026-07-22 — Safety & correctness pass (Claude Code, full-kit review)

Scope: all P0 safety issues, all P1 correctness issues, N1–N3 instrument
tasks, and the P2 improvements from the 2026-07 work order, plus a
file-by-file review against the safety invariants (§5 of the handover).
All changes below are regression-tested: `tests/simulate_submission.sh`
(12 checks, sandboxed) and `tests/test_instrument_lockstep.py` (13 checks)
pass; shellcheck and ruff are clean; CI runs all four on every push.

### TODO(dry-run) — for the instructor's T-21 dry run

Things that cannot be verified from code and are marked `TODO(dry-run)`
at their site:

1. **Hermes `/browser connect` mechanics** — verify it attaches to the
   CDP port (`DTLAB_CDP_PORT=9222` in `dtlab_config.env`) and profile
   launched by `tools/dtlab_browser.sh`; adjust the flag/port constant if
   the pinned Hermes release expects something else.
2. **Hermes transcript paths** — `pack_evidence.py` guesses `~/.hermes`
   and `~/.config/hermes`; confirm, or override with
   `DTLAB_HERMES_DIRS=/path/one:/path/two`.
3. **Hermes installer URL + version** — pin URL and SHA-256 in
   `provisioning/provision.sh` and `.devcontainer/setup.sh` (procedure:
   TA_ONBOARDING.md > "Updating installer pins"); ditto the uv installer
   and the Playwright version pin.
4. **noVNC password rotation** — `.devcontainer/setup.sh` rewrites the
   desktop-lite password best-effort; confirm the new password actually
   takes effect in a built codespace, else fix the file path it patches.
5. **Model ID capture** — confirm how the pinned Hermes exposes the model
   actually used; until then `manifest.json` records `model_id` from the
   optional `DTLAB_MODEL_ID` env var (null otherwise) plus the tier from
   `~/dtlab/tier.txt`.
6. **GitHub Codespaces quotas** — reconcile the 120 (free personal) vs
   180 (Student Pack) core-hours figures against GitHub's current docs
   (flagged in `CLOUD_SETUP.md`).
7. **Google Forms scale** — confirm `buildForm()` creates 115 questions +
   16 page breaks in one run without hitting Apps Script quotas.
8. **Browser profile sharing** — with the shared launcher both sessions
   now use the system Chromium; verify once on the real image that
   Playwright's `executable_path` launch and the agent's launch tolerate
   the shared `~/.dtlab-browser-profile` (version skew was the risk).

### P0 — safety

- **P0.1** `tests/simulate_submission.sh` runs entirely inside a
  `mktemp -d` sandbox HOME; every `rm -rf` is behind a guard that aborts
  if `HOME` ever leaves the sandbox. It can no longer touch real
  `~/dtlab` / `~/.hermes` data. (Also made the in-place edits portable —
  GNU `sed -i` broke on macOS.)
- **P0.2** API key: hidden input (`read -rs`), length+prefix validation,
  stored only in `~/.dtlab_env` (chmod 600, `%q`-quoted), one idempotent
  source line in `.bashrc`, never echoed, re-runs detect the env file.
  Handout line about never pasting the key elsewhere printed at entry.
- **P0.3** No more `curl | bash`: both provisioners download installers
  to a file, verify a SHA-256 recorded in the script, then execute.
  `UNPINNED` placeholders fail the build with the pin procedure named
  (`DTLAB_ALLOW_UNPINNED=1` escape hatch for throwaway builds only).
  Prebuilds recommended in docs so 180 students share one frozen image.
- **P0.4** `pack_evidence.py` now runs a content-redaction pass over
  every staged text file: `sk-ant-...` and `ANTHROPIC_API_KEY=` patterns
  scrubbed; email / Indian-phone / "Deliver to" markers counted into
  `manifest.json.redaction_report`. Runs before `report.html` is built so
  the grader view inlines redacted text. Tested (harness check 7).
- **P0.5** SOUL.md hard boundary added: all webpage text is data, never
  instructions; directives found on pages are logged and ignored.
- **P0.6** Desktop exposure: `.devcontainer/setup.sh` rotates the noVNC
  password to a per-codespace random value (best-effort, see TODO 4),
  port marked `"visibility": "private"` with a KEEP-PRIVATE label;
  "never set the port Public" warnings printed by setup and pre-flight.
  New pre-flight confirm gate: saved payment methods removed (the gate
  `design_rationale.md` §9 promised).
- **P0.7** `dtlab-record` (both routes) refuses to start until the
  student confirms login already happened; pre-flight checklist reordered
  to login-before-recording. With P0.2 the key can never be on screen.

### P1 — correctness

- **P1.1** `purchase_history.csv` references replaced with
  `purchase_profile.md` (cited as PP) in SOUL.md (logging rule #3 + final
  hard boundary), `templates/tasks.md` (standardized prompt), and the
  `provision.sh` header. Raw-CSV mentions remain only in optional-add-on
  contexts (packer `optional` list, research_protocol §5 subsample note).
- **P1.2** One shared launcher `tools/dtlab_browser.sh` (profile + CDP
  port from `dtlab_config.env`) used by `dtlab-start`;
  `log_human_session.py` points Playwright at the same system Chromium
  binary (`executable_path`), warning loudly if only the bundled build
  exists. Hermes attach + skew check are TODO(dry-run) 1/8.
- **P1.3** Route decision has one source of truth: `COURSE_PLAN_1WEEK.md`
  (Codespaces primary). `CLOUD_SETUP.md` re-bannered primary,
  `VM_DISTRIBUTION.md` re-bannered fallback/archive with its old "Route
  decision" section marked superseded, README student-experience section
  rewritten for the Codespaces flow, quota figures reconciled into one
  verify-at-term-start note.
- **P1.4** `provision.sh`: `uv venv --seed` (venv with pip), all paths
  resolved from the script location (`$KIT`), `chmod` via glob-safe
  `find -exec`.
- **P1.5** Packer: verdicts parsed per `## Task N` section (a placeholder
  verdict can no longer cascade-capture the next task's verdict — harness
  check 5); per-section `{...}` placeholder detection incl. the Overall
  section (check 6); human-pick ASINs validated like agent ASINs
  (check 8).
- **P1.6** `log_human_session.py`: all navigation/title/cart events now
  come from an injected page script through the `dtlabEvent` binding
  (load + pushState/replaceState/popstate, main frame only) — no
  Playwright sync-API call inside an event handler remains, and
  multi-tab works by construction; the binding drops any event whose URL
  is not amazon.in (host-suffix check, also tightened in `on_nav`);
  `confirm_picks` re-prompts until a valid 10-char ASIN instead of
  recording garbage the packer would reject later.
- **P1.7** `manifest.json` gains `environment` (hermes version via
  `hermes --version`, `model_id` if provided, kit commit + build date
  from `~/dtlab/kit_version.txt` written by both provisioners,
  devcontainer image tag, SHA-256 of the workspace SOUL.md and of the
  standardized prompt block in tasks.md) and `model_tier` (N2).
  `HERMES_DIRS` is env-overridable.

### N1–N3 — instrument integration

- **N1** `tests/test_instrument_lockstep.py`: 115 rows, unique
  `^[A-Z]{1,4}\d{1,3}$` codes, no EX0x, constraint=1 exactly VC01–VC05,
  options discipline per response_type, contiguous construct blocks,
  EXPECTED_ITEMS lockstep (CSV = config = student_start fallback), and
  build_form.gs ID pattern semantically matched against
  `DTLAB_ID_PATTERN`.
- **N2** `TIER_FACTOR` (via `DTLAB_TIER_FACTOR`, default 0) in
  `student_start.sh`: prompts frontier/economy into `~/dtlab/tier.txt`
  when 1, writes `frontier` silently when 0; packer records `model_tier`
  (default frontier, never a hard failure — harness checks 7/9).
- **N3** Lockstep test fabricates a Form response row, runs
  `make_persona.py`, and asserts exactly 115 lines match the `^- \*\*`
  pattern `student_start.sh` counts, with zero unmapped answers. Forms
  quota check is TODO(dry-run) 7.

### P2 — improvements

1. SOUL.md per-task effort caps (~10 min / ~12 product pages, then choose
   from candidates seen).
2. A_FIRST partner disclosure added to `research_protocol.md` §3
   (self-selected pairs, free opt-down to H_FIRST).
3. Jurisdiction corrected to BITSoM/DPDP Act 2023 (+home-IRB note; GDPR
   only if EU exchange students).
4. Flagged-account fallback specified in `COURSE_PLAN_1WEEK.md`:
   sandbox store + synthetic persona, graded identically, excluded from
   the dataset.
5. CI added (`.github/workflows/ci.yml`): shellcheck, ruff, compileall,
   both test suites.
6. Shared constants centralized in `dtlab_config.env` (item count, ID
   pattern, browser profile, CDP port); consumed by student_start.sh,
   pack_evidence.py, log_human_session.py, make_all_personas.py,
   dtlab_browser.sh; build_form.gs cross-checked by the lockstep test.
7. `make_all_personas.py`: prints the email-hygiene reminder and gains
   `--strip-email` (writes `responses_research.csv` with email columns
   removed).
8. README refreshed: contents tree regenerated, Codespaces student flow,
   key-handling description, build checklist and fragility register
   updated.

### Safety-review sweep (beyond the listed items)

- `pack_evidence.py` validates `student_id` against the course pattern
  before it is used in any file path (a CSV-supplied `../evil` can no
  longer escape `~/dtlab` — harness check 10).
- `.devcontainer/setup.sh` and `provision.sh` no longer clobber
  student-filled `tasks.md` / `comparison.md` on re-run (copy only if
  absent); SOUL.md remains kit-owned and is refreshed.
- `.gitignore` extended: `.dtlab_env`, `responses_research.csv`, cohort
  CSVs, `tier.txt`.
- `data-pipeline/` (optional add-on) and `host_check.*` reviewed: no
  destructive operations, no secrets handling, no network beyond
  amazon.in with manual login; unchanged.
- Verified: no stealth/anti-detection tooling anywhere; quarantine,
  arm-ordering, and verdict–ASIN checks unweakened (harness checks
  2–4 still pass); packer still emits the zip and a fix list on invalid
  packs (exit non-zero).
