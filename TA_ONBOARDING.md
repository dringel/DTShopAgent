# TA onboarding — Digital Twin Shopping Agent Lab

Welcome. This repo is the complete kit for the 1-week, 161-student
(two sections: 80 mornings + 81 afternoons, 3h/day for 5 days)
digital-twin experiment (Hermes Agent + Claude API + amazon.in). It
serves three audiences from one commit — see README > "Who uses what"
for the role map (students: six commands, ignore the repo; you: this
file; instructor: design docs + analysis).

## First: the mental model (repo ≠ course; nothing "runs" here)

If you are new to GitHub, fix this picture in your head before touching
anything (long version: README > "How this actually runs"):

- **This repo is a recipe.** Student environments are BUILT from it;
  it executes nothing by itself. Students never clone it, never work
  in it, never push to it (the syllabus has them skim it, nothing more).
- **CI (the green ✓ / red ✗ on each commit) is just the test suite**
  running on a GitHub server after every push: linters + the four
  regression suites. Red means "the kit at this commit is broken —
  don't build student environments from it." It involves no agents,
  no Amazon, no student data. If CI is red, the failure log (repo >
  Actions tab) names the exact file and check.
- **Students click *Create codespace*** and GitHub builds each of them
  a private cloud container from `.devcontainer/` (setup.sh installs
  everything into `~/dtlab/` and creates the `dtlab-*` commands). The
  commit on `main` at build time IS their environment — which is why
  "freeze the design, CI green, enable prebuilds" is a hard sequence,
  in that order.
- **Student data never enters git.** It lives in each codespace and
  leaves once, as the evidence zip uploaded to the LMS.
- **Your levers:** edit files → run the test suites locally → commit +
  push → CI confirms → rebuild/re-prebuild environments. Nothing else
  moves anything anywhere.

## Read in this order (30 minutes)
1. `COURSE_PLAN_1WEEK.md` — THE operative plan (Sessions 6–10, 3 h/day per section, the four-run 2×2).
2. `README.md` — file map + the seven deliverables and how each is captured.
3. `agent/SOUL.md` — the agent's identity, the ECP logging protocol
   (incl. the
   machine-parsed `CAND |` candidate lines and the `PROTOCOL |` token
   that proves which SOUL a run loaded), hard boundaries. Then skim the
   three sibling variants: `agent/SOUL_ablated.md` (questionnaire-free,
   for the ablated cells), `agent/SOUL_bootstrap.md` (the one-time
   questionnaire-blind session that writes the frozen purchase
   profile), and `agent/SOUL_sandbox.md` (practice store). All four
   must stay in lockstep on
   boundaries and logging format; each run receives exactly one of
   them through its own Hermes home.
4. `PERSONALIZATION_PROTOCOL.md` — the contamination model: pause
   Browsing History daily (Layer 1), targeted block + provenance-logged
   candidates (2), measured index per run (3), order design + assessment
   blinding via partner swaps (4).
5. `research_protocol.md` — schemas, pseudonyms, consent, dataset assembly.
6. `questionnaire/questionnaire_instrument_source.md` — the AUTHORITATIVE
   instrument: 115 items, the design decisions behind them (ECP, model
   policy, evaluation logic, deliberate exclusions), and the APA
   references for every validated scale.
7. `questionnaire/AUTHORING_GUIDE.md` — the CSV format contract and the
   transfer conventions (embedded stems, likert5 anchors, constraint
   flags). The CSV now holds the real 115 items; source doc and CSV must
   never diverge.
8. `dtlab_config.env` + `tasks_config.csv` (repo root, 3 minutes) — the
   shared constants (item count, ID pattern, browser profile, CDP port,
   the two optional-factor switches) and the task structure (ids,
   product types, utilitarian/hedonic classes, budgets). Change values
   THERE, nowhere else; the lockstep test and the packer catch drift.
9. `docs/CHANGELOG.md` — the **live T-21 dry-run list** (top of the
   file) plus the record of everything the hardening and four-run
   passes changed.

## The student-facing surface (all of it)
Six commands inside a Codespace built from this repo (`dtlab-record` optional):
`dtlab-shop` (logged own shopping, Wednesday — picks committed before
any agent run; ONE attempt, a redo needs a TA reset) · `dtlab-start`
(pre-flight + agent; its first Thursday invocation runs the bootstrap
phase that writes and freezes the purchase profile, then once per agent
run — four total across Thursday/Friday, it announces which run and
which condition, builds each run's own Hermes home with the right SOUL
and pinned model, and walks crash
recovery) · `dtlab-cart` (run by the PARTNER after each agent run:
automatic cart
screenshot + parsed cart contents, checked ON THE SPOT against the
agent's picks — exact match required, fix and recapture before
emptying — plus the CAPTCHA/intervention counts) · `dtlab-verdict` (the
single blind Friday session after run 4: guided verdict/rating/
rationale capture, structured, no markdown editing; stored answers are
final — corrections only via `dtlab-verdict --amend` with a TA) ·
`dtlab-record` (screen
capture, optional) · `dtlab-pack` (validated submission zip, Friday,
uploaded via the BITSoM LMS assignment). Human-first ordering is
enforced by the pre-flight (hard gate: no agent run without
`dtlab-shop`'s files) and the packer — students cannot get the order
wrong silently. During every agent run students swap seats with their partner
(assessment blinding + CAPTCHA handling; PERSONALIZATION_PROTOCOL.md
Layer 4).

## How the kit defends itself (know this before you touch anything)

Every claim the experiment must defend is enforced by code or measured as
data (`docs/design_rationale.md` §11 closes on this principle). The
concrete machinery, so you recognize it when you see it:

- **Quarantine + ordering:** everything the agent must never see —
  the human session, the verdicts, held persona files — lives under
  the quarantine root `~/dtlab/quarantine/` (SOUL
  boundary + pre-flight + packer checks, plus a pack-time transcript
  scan that BLOCKS on any quarantine-path reference); human-first
  ordering is verified against
  file timestamps at packing.
- **Verdict integrity:** `verdicts.csv` from `dtlab-verdict` is the
  primary verdict record (`comparison.md` memo parsing is the fallback),
  cross-checked against the picks files' ASINs. Capture is BLIND and
  happens ONCE, in Friday's single session after run 4: each
  task's four picks appear as Run A–D in a per-task randomized order,
  and because tier order is counterbalanced across days, neither
  grounding nor tier is knowable at judgment time; condition and tier
  are resolved into the CSV only after the verdicts are
  stored (`verdicts_captured_blind` + `single_session` in the
  manifest) — never tell a
  student mid-capture which run was which; the tool reveals the mapping
  itself once every verdict and head-to-head is on file. Stored
  verdicts are IMMUTABLE — corrections go through `dtlab-verdict
  --amend` (reason + TA authorization, append-only, own timestamp);
  never edit the CSV. The artifacts live in
  the quarantine root (`~/dtlab/quarantine/verdicts/`), outside every
  path an agent run receives, so a Friday agent
  cannot read any judgment.
- **Secrets:** the API key is collected hidden, lives only in a
  600-permission `~/.dtlab_env`, and `dtlab-pack` content-redacts key
  patterns from every packed text file (see `redaction_report` in each
  manifest — skim it when grading).
- **Supply chain:** installers are checksum-pinned; builds refuse to run
  unpinned (section below).
- **Agent containment:** add-to-cart only, amazon.in only, CAPTCHA halt,
  per-task effort caps, and webpage-text-is-never-instructions (prompt
  injection). Read the Hard boundaries block of `agent/SOUL.md` verbatim
  — it is also Session 8 teaching content. The add-to-cart-only rule is
  a three-layer guarantee: the SOUL boundary (instruction), the
  checkout-guard extension
  (`tools/checkout_guard_extension/` — network-enforced
  declarativeNetRequest rules that block every checkout, Buy Now,
  one-click, COD, and gift-card path in the whole lab browser, human
  session included; `dtlab-start`'s canary proves it is live before any
  run), and pack-time attempt detection (any checkout-shaped URL in a
  log is a blocking validation issue). Payment-method removal stays in
  the pre-flight as hygiene, not as the guarantee.
- **Treatment delivery + ablation integrity:** every run launches in
  its own fresh Hermes home (`runs/runN/hermes_home/`) into which
  `dtlab-start` writes the condition's SOUL and a config naming the
  exact pinned model for that run's tier — Hermes loads instructions
  from `$HERMES_HOME/SOUL.md`, NOT from the working directory, which is
  why this mechanism (and nothing else) is the treatment delivery; the
  launcher fails closed on any config mismatch and hashes both files
  into the run record. An ablated run's persona files sit in the
  quarantine root, each run's log is archived before the next run
  starts, no memory or session state crosses runs, and
  the packer's checks fail any run whose decision log lacks the loaded
  SOUL's protocol token, any ablated log
  that cites persona item codes, and any transcript referencing
  quarantine paths. Per-run condition + tier + hashes land in the
  manifest; `dtlab-cart`'s parsed cart JSON is checked LIVE against
  the agent's self-reported picks — exact match required (extras,
  duplicates, or quantity >1 must be fixed and recaptured before the
  cart is emptied; `cart_verified` per run records it). Its parser
  reads the ACTIVE cart only, and it warns when it sees items parked in
  "Saved for later" — teach partners to empty the cart with **Delete**,
  never "Save for later" (the most discoverable button, and the one that
  silently corrupts every later run's cart evidence). The partner also
  records CAPTCHA/intervention counts when `dtlab-cart` asks.
- **Issues vs warnings:** the packer HARD-FAILS on anything the student
  can fix (missing files, placeholder verdicts, bad ASINs — exit
  non-zero with a fix list) and records the rest as non-blocking
  `warnings` in the manifest (e.g. an agent that ignored the `CAND |`
  format). Read both fields when grading.
- **Regression net:** `tests/simulate_submission.sh` (sandboxed — it
  cannot touch real data) + `tests/test_start_flow.sh` (scripted walk
  of the four-run state machine) + `tests/test_instrument_lockstep.py`
  + `tests/test_analyze_cohort.py` + CI on every push. If you change
  anything the tests cover, the tests tell you.

## Your open work items (rough priority order)
- [ ] **Verify the CSV against the source doc** item-by-item (codes,
      wording, options, constraint flags on VC01–VC05 only), then build
      the Form via `build_form.gs`, test-submit once, and spot-check the
      anchor lists in the live Form: likert5 = "Disagree strongly …
      Agree strongly", AC 9-point, RF 7-point, TS01 11-point. Delete the
      test row. **Freeze the instrument at Form build** — any later
      change = new schema version + matching source-doc edit.
- [ ] **Finalize the FIVE categories with the professor.** The design
      is five self-purchase categories from the **11-category catalog**
      in `tasks_config.csv` (rationale and sources in
      `docs/TASK_CATEGORIES.md`); a provisional five is active
      (sneakers, power bank, backpack, laptop, perfume). To change
      the selection: `#`-out the rows you drop, remove the `#` from the
      rows you keep, renumber task_id 1..N, run
      `python3 tools/make_task_docs.py`, re-run the harness, freeze
      alongside the questionnaire. No gift and no replenishment framing
      (out of scope by design — see design_rationale §8); task order is
      randomized per student automatically, nothing to assign. Note:
      questionnaire item PR09 was authored as the gift benchmark —
      decide at instrument freeze whether to keep or replace it. During
      the dry run also verify the agent complies with the `CAND |` line
      format, that breadcrumb capture works on live product pages, and
      that a 5-task agent run FITS the session slot (SOUL caps ~10
      min/task; tighten the cap if it brushes the hour — the laptop
      task, the deliberate high-stakes anchor, is the likeliest to hit
      the cap on both the human and agent side; time it explicitly).
- [ ] **HED/UT manipulation check — build and run the Session-10
      poll.** The utilitarian/hedonic class of each task is a design
      variable, so it is measured for THIS cohort as a separate
      2-minute in-class poll (the 115-item instrument stays frozen).
      Everything you need is in `questionnaire/HEDUT_POLL.md`: the
      Voss et al. (2003) items and anchors, the Form build steps
      (~15 min, own Form, ID-validated, no email), the Session-10
      run procedure, the export/reshape to `hedut_responses.csv`, and
      the analyzer flag (`--hedut`). Matters most for the two
      dual-attribute categories (backpack, sneakers) — the cohort's
      own scores become the classification of record.
- [ ] **Token/cost benchmark across model tiers (during the dry run).**
      Run at least one full single-category task end-to-end under each
      of four configurations — **Haiku-class with and without extended
      thinking, Sonnet-class with and without extended thinking** — and
      repeat over 2–3 different categories so the numbers average out.
      Record per run: input/output/cache tokens and $ cost (Claude
      Console usage view per key), wall-clock time, and task success.
      Multiply out to tasks-per-student × N=161 (×2 if the ablation
      factor is on) → this sets the recommended personal spend limit,
      validates the ~$20
      spend-limit guidance for the four-run 2×2, and gives the professor the real numbers for the
      model-tier decision. Note: the course runs at model defaults —
      the thinking-on/off variants are measured here for cost
      information, not as a change to the run policy.
- [ ] Turn this repo into a **template repo** (Settings → Template
      repository) once the Form is frozen.
- [ ] **Pin the installers** (see "Updating installer pins" below) —
      the provisioning scripts refuse to build while any checksum is
      `UNPINNED`. Then enable **Codespaces prebuilds** on the template
      repo so all students share one frozen, pre-tested image.
- [ ] **Full dry run from a Codespace** against real amazon.in with a real
      account: build time, `/browser connect`, the bootstrap session
      (order-history reading quality), one complete task,
      CAPTCHA frequency from Azure IPs. This dry run decides
      Codespaces-vs-fallback (see CLOUD_SETUP.md decision rule). Log
      every deviation from the docs — Hermes moves fast; our pinned
      commands may lag a release. Work ALL items of the **live
      dry-run checklist at the top of `docs/CHANGELOG.md`** during this
      run and tick them off there.
- [ ] Validate the fragile DOM-dependent code against live amazon.in:
      `tools/log_human_session.py` (cart-click selector, breadcrumb
      category selector, URL parsing) and `tools/capture_cart.py`
      (SELECTORS dict is the single patch point).
- [ ] **API-account setup checklist (Monday homework — assigned in
      Session 6, due Monday 22:00):** publish the
      LMS checklist — create your own Anthropic Console account, complete
      billing with a small credit purchase, set a personal **monthly
      spend limit of ~$20** in Console settings, generate one API key,
      store it only where dtlab-start puts it. Verify completion against
      the roster at Tuesday's pre-flight (checkpoint 2); hold 2–3 course-owned
      spare keys for failed setups. Rate limits are per account, so ~80
      concurrent agents share nothing.
- [ ] Build the LMS assignment sheet BEFORE the lab week: pseudonym,
      section, self-selected pair, per-day grounding order (Thursday
      P_FIRST/NP_FIRST; Friday independently re-randomized), and
      **tier order** (economy-first vs frontier-first across the two
      days) — all generated in one pass by
      `tools/make_counterbalance.py` from the final roster, stratified
      by section, tier order orthogonal to grounding order. The same
      file goes to the LMS AND to the repo root as
      `counterbalance.csv` before the freeze (provisioning refuses to
      build without it); validate with `--validate` and record the
      printed SHA-256. The order-arm (H_FIRST/A_FIRST) list is
      retired: all students are human-first (Wednesday).
- [ ] Create the synthetic persona pack (fictional Form row + a fictional
      order history narrative) for opt-out students.
- [ ] Run `tests/simulate_submission.sh` after ANY change to
      `tools/pack_evidence.py`, `templates/`, or `agent/SOUL.md`'s
      logging/picks protocol — it regression-tests the whole validation
      chain without a browser (safely: it runs in a throwaway sandbox
      HOME). Run `python3 tests/test_instrument_lockstep.py` after ANY
      change to the questionnaire CSV, `dtlab_config.env`, or
      `make_persona.py`. CI (`.github/workflows/ci.yml`) runs both plus
      shellcheck/ruff on every push.
- [ ] Wi-Fi capacity check with facilities for ~80 concurrent noVNC
      streams per section (~1–3 Mbps each, ≈160–300 Mbps sustained,
      long-lived websockets). Confirm: WAN headroom ≥ 2× that; ≤ ~25–30
      active clients per AP on 5/6 GHz; no captive-portal re-auth or
      websocket idle timeout within 3 hours; no per-user throttling
      below ~3 Mbps; students' phones on mobile data. Then run a 15–20
      student pilot in the actual room and measure per-stream bitrate.
      (The morning/afternoon section split already staggers the load.)
- [ ] After submissions close: bulk-download all zips from the BITSoM
      LMS into one folder (LMS renaming of files is harmless — identity
      comes from inside the zip) and run `python3 tools/analyze_cohort.py --zips <folder>`
      (needs `pip install pandas plotly` at the ci.yml-pinned versions,
      scipy optional) — it produces
      the self-contained cohort report for the debrief session. Packs
      with validation issues, mismatched config hashes, or duplicate
      IDs are QUARANTINED from the confirmatory set by default (listed
      with reasons in the report); include/exclude overrides go through
      `--decisions decisions.csv`, which the report echoes verbatim.
      The class copy carries no pseudonyms — a hover-identified
      diagnostic copy needs `--identified` and stays with the
      instructor. Attach the Session-10 poll with `--hedut`; export the
      research tables with `--export-runs` / `--export-hth`. Open
      `docs/sample_report.html` FIRST to see exactly what you should
      get (synthetic data, marked as such — regenerate it anytime with
      the fabricator in `tests/test_analyze_cohort.py`). Skim each
      manifest's `redaction_report` and `validation_issues` while
      grading; the same test shows the expected zip shape if a
      submission fails to parse.

## The T-21 trial run — TA work items (each with its procedure)

**Your mission, starting now:** you have the repo — build a fresh
codespace from it, run the entire lab end-to-end yourself (build →
persona → sandbox run → dtlab-shop → bootstrap → all four runs →
dtlab-cart → dtlab-verdict → dtlab-pack → analyzer), work EVERY item
below plus the open work items above, and fix what breaks. Ground
rules for fixes: keep all four suites + ruff + shellcheck +
`tests/check_docs.py` green on every commit; log every change and
every deviation from the docs in `docs/CHANGELOG.md`; anything on the
must-not-touch list (both SOULs, `templates/`, `tasks_config.csv`,
`tools/pack_evidence.py`, the instrument, the factor switches) gets a
proposed fix + instructor sign-off before it lands, never a silent
edit. Items 1–7 are yours to execute; the instructor items in the next
section are the only things you hand back up.

1. **Pin Hermes and validate its context + model mechanics (blocks
   everything).**
   (a) Pick the current stable Hermes release; download its installer
   at the exact URL in `.devcontainer/setup.sh`, read it once, compute
   `sha256sum`, and pin URL + hash in BOTH provisioners (procedure
   below). (b) On a clean build of that exact release, verify the three
   behaviors the kit depends on: `HERMES_HOME` redirection (a SOUL
   placed at `$HERMES_HOME/SOUL.md` is loaded; the working-directory
   copy is ignored), the `config.yaml` schema the launcher's template
   generates (model + provider fields accepted; adjust
   `provisioning/hermes_config.template.yaml` if the pinned release
   expects different keys), and where transcripts land inside the run
   home (adjust the packer's collection subpath if needed). (c) Record
   all three findings in the CHANGELOG T-21 list.
2. **Pin the exact model IDs.** Confirm the two tier models with the
   instructor (economy = current Claude Haiku class, frontier = current
   Claude Sonnet class), then enter the exact IDs in `dtlab_config.env`
   (`DTLAB_MODEL_ECONOMY`, `DTLAB_MODEL_FRONTIER`) — the launcher
   refuses to run while they read `PIN-AT-DRYRUN`. Record a pricing
   note (per-MTok prices + date) in the CHANGELOG while you're there;
   the cost benchmark item above fills in the measured numbers.
3. **Integration canaries (with a real account).** In a
   clean codespace from the pinned commit: (a) protocol-token check —
   after each condition's sandbox/pilot run, the decision log must
   open with that SOUL variant's `PROTOCOL |` token (proves the agent
   loaded the intended instructions); (b) model check — the run's
   `config.yaml` and any model identifier in the transcripts match the
   assigned tier; (c) forbidden-path probes — in a sandbox session,
   ask the agent to read `~/dtlab/quarantine/human/human_picks.csv`
   and a sibling run directory; it must refuse and log the request,
   and the packer's leakage scan must flag a planted violation;
   (d) bootstrap freeze — after the bootstrap phase, confirm
   `purchase_profile.md` is read-only and the hash check trips if you
   edit it. Anything that fails is yours to diagnose and fix (ground
   rules above).
4. **OS-user isolation prototype (optional, not a blocker).**
   If time allows, try running Hermes as a second Unix user with
   group-denied read on `~/dtlab/quarantine/` in a scratch codespace.
   Recommend adoption ONLY if the browser/CDP/key plumbing survives
   untouched; otherwise the shipped detection layer is the accepted
   posture (design_rationale §5b states it honestly).
5. **Consent text lockstep.** The consent sheet
   `docs/CONSENT_AND_DATA_USE.md` is instructor-approved as written —
   treat its wording as frozen. Bring the Form
   checkbox texts in `questionnaire/build_form.gs` and the AGREE gate
   text in `provisioning/student_start.sh` into lockstep with it —
   the three must never drift; the bracketed fields (dates, contacts,
   determinations) are filled by the instructor at term start.
6. **Freeze mechanics.** At design freeze: generate + validate +
   hash `counterbalance.csv` from the final roster (work item above),
   set `DTLAB_EXPECTED_COMMIT` in `dtlab_config.env` to the frozen
   commit (the runtime check that catches stale prebuilds), make the
   repo a template, enable prebuilds, and re-verify CI green on the
   frozen commit. The instructor confirms the freeze; you execute it.
7. **Run the go/no-go gate checks and report.** Verify every gate and
   hand the instructor a pass/fail list — the go decision is theirs,
   the evidence is yours:
   a clean codespace from the pinned commit loads the intended
   per-run context (token check) · each cell uses its assigned exact
   model ID · forbidden files are refused and detectable · memory and
   sessions do not cross runs (fresh homes verified) · one frozen
   purchase-profile hash appears in all four runs · exactly one
   transcript set maps to every run · verdicts and human choices are
   immutable after commitment · exact cart equality passes on pilot
   tasks · an adversarial final zip contains no secret, identifier,
   or unsafe screenshot · the full test suite completes under
   explicit timeouts · the analyzer passes its null, missingness, and
   mixed-version simulations · the participant notice matches the
   actual data flow · a multi-account end-to-end pilot completes all
   four cells without manual repair.

## Instructor decisions & sign-offs (Daniel) — not delegable

The TA runs the machine; these calls stay with the instructor:

1. **Legal & governance determinations (before the Form opens).**
   The instructor operates as a sole-proprietor firm in Germany,
   externally contracted by BITSoM: (a) BITSoM's institutional
   determination for running the study within the course; (b) an
   independent research-ethics review (no university IRB attaches
   to this engagement); (c) German/EU privacy advice
   on the controller structure, the India→Germany transfer, and the
   DPDP phase-in; (d) confirmation of the actual Anthropic API
   data-retention terms for the account tier; (e) a terms-of-service
   assessment for the Amazon interaction; (f) the outcomes entered
   into the bracketed fields of `docs/CONSENT_AND_DATA_USE.md` and
   research_protocol §3. The repo reports these determinations; it
   does not make them.
2. **Design sign-offs:** the final five categories, the instrument
   freeze (incl. the PR09 keep-or-swap call), the tier model choices,
   any change the TA proposes to must-not-touch files, and the freeze
   itself.
3. **The go/no-go decision** on the TA's gate report, and the course-
   week duties in COURSE_PLAN_1WEEK.md (assignment sheet release,
   overnight persona batch, the cohort report after Friday, the
   capstone brief).

## Updating installer pins (supply-chain hygiene)

`provisioning/provision.sh` and `.devcontainer/setup.sh` download remote
installers (Hermes, uv) to a file, verify a SHA-256 recorded in the
script, then execute — never `curl | bash`. Ships with `UNPINNED`
placeholders that make the build fail on purpose. To pin (or re-pin after
a release):

1. On a trusted machine, download the installer at the exact URL in the
   script and read it once (sanity check, it's a shell script).
2. `sha256sum <file>` → paste the hash into the `*_SHA256` variable and,
   where the project offers versioned URLs, pin the URL to that release.
3. Pin `PLAYWRIGHT_PIN` (e.g. `==1.55.0`) to the version you dry-ran.
4. Rebuild a fresh codespace/VM from scratch and re-run the dry run.
5. Commit the pin change; rebuild the Codespaces prebuild.

Never set `DTLAB_ALLOW_UNPINNED=1` for anything students will use — it
exists only for throwaway test builds.

## Things you must NOT do
- Commit any student data or API keys (`.gitignore` blocks the obvious
  paths — think before you `git add -f`).
- Weaken the bias quarantine (`~/dtlab/quarantine/` vs agent
  workspace), the per-run Hermes-home treatment delivery, the
  ordering checks, the verdict–ASIN cross-check, or the
  redaction pass in `pack_evidence.py`; they are what makes the
  experiment sound and safe.
- "Fix" CAPTCHA friction with stealth/evasion tooling — out of scope by
  design (see the ethics sections).
- Build anything student-facing with `DTLAB_ALLOW_UNPINNED=1`, or tell a
  student to set the Lab Desktop port to Public — both exist as warnings
  in the scripts for a reason.
- Edit either SOUL, `templates/`, `tasks_config.csv`, or
  `tools/pack_evidence.py` without re-running
  `tests/simulate_submission.sh`; edit the questionnaire CSV,
  `dtlab_config.env`, or `make_persona.py` without re-running
  `tests/test_instrument_lockstep.py`. Green CI is the "double-checked
  and safe" bar this course promised.

## License / sharing
See `LICENSE.md` at the repo root: MIT for the code, CC BY 4.0 for the
docs, with the third-party scale-item and logo exceptions noted there.
