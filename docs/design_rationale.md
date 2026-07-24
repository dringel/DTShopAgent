# Design Rationale — Digital Twin Shopping Agent Lab

**What this document is.** The definitive record of every consequential
design decision in this package, with the argument for it and the
alternatives that were considered and rejected. It exists so that anyone
working on the kit (TA, co-instructor, future self) understands
not just *what* the design is but *why it must be this way* — and which
parts are load-bearing versus merely convenient. Operational details live
in `COURSE_PLAN_1WEEK.md`; this file carries the reasoning.

**What the lab is.** 161 MBA students (two sections of 80 and 81) each
configure an autonomous agent
as their consumer digital twin (grounded in a 115-item questionnaire and
their real amazon.in purchase history), shop five standardized
self-purchase category tasks both
themselves and via the agent under a counterbalanced order design, and
evaluate the agent's choices against their own. The exercise is
simultaneously a course module on agentic AI and a paired human/agent
choice-and-process experiment.

---

## 1. Agent framework: Hermes Agent

**Decision.** Hermes Agent (Nous Research, open-source, MIT) is the agent
runtime, driving a local Chromium browser over CDP via its built-in
browser tools.

**Why.** Four properties align exactly with the lab's needs. (1) A
customizable persistent identity file (`SOUL.md`) is the natural home for
the digital-twin directive, decision rules, mandatory logging protocol,
and hard boundaries — the entire experimental treatment is one readable
text file students can inspect, which is itself course content. (2)
Built-in browser automation that can attach to a *local, visible, already
logged-in* Chromium session: the student authenticates manually, then
hands the warm session to the agent. (3) Session transcripts are written
to local disk, giving an audit trail without any additional
instrumentation. (4) Self-hosted and open-source: no vendor account per
student, full inspectability, and pedagogical honesty — students see the
whole machine.

**Rejected.** *OpenClaw*: its architectural center of gravity is
multi-user, multi-platform chat gateway routing — capability the lab
doesn't use, complexity the lab pays for. *A purpose-built Playwright
script*: maximally controllable but it would be a scripted demo, not an
agent; the course is about agentic systems, and Hermes's autonomous
tool-use loop is the object of study. *Claude-native consumer agents
(e.g. browser-agent products)*: lower setup friction, but less
inspectable/configurable identity, less structured local logging, and the
course narrative is deliberately built on an open-source stack.

**Accepted risk.** Hermes releases fast; commands, config surfaces, and
log paths drift between versions. Mitigation: the docs-are-canonical
norm, a pinned dry run on the final environment before the course week,
and a TA work item to log every deviation.

## 2. Model backend: Claude API, student-owned accounts

**Decision (updated 2026-07).** Claude (Sonnet-class) via each student's
**own Anthropic account and API key**, set up as day-1 homework from an
LMS checklist (Console account, billing, small credit purchase, a
personal ~$20 monthly spend limit, one key). The pre-flight collects the
key with hidden input into a 600-permission env file; the packer redacts
key patterns from every artifact.

**Why.** Agentic browser loops need a frontier-quality model to be
reliable enough for a *timed classroom session* — a failed run at minute
70 of a 3-hour session with ~80 people has no retry slack. Sonnet-class
models deliver that reliability at a cost where a full five-task run is
well under $1–2 (the four-run 2×2 lands around $3–6); a ~$20 personal
spend limit covers retries, making total
course cost trivial against 15 contact hours. Student-owned accounts
distribute rate limits — every account has its own request and token
budget, so ~80 concurrent agents share nothing, and prompt-cache reads
are exempt from input-token limits on current models. Each student also
leaves the course owning a working API account — itself a course
outcome.

**Rejected.** *Local models (Ollama etc.)*: "free" is illusory here — on
CPU-only cloud containers or student laptops, small local models are too
slow and too error-prone for multi-step browser control; the failure mode
is silent classroom chaos. Retained only as an optional "hard mode"
footnote. *A single course workspace issuing per-student keys*: central
caps and a kill switch are attractive, but one org-level rate-limit pool
under ~80 concurrent browser agents is the binding constraint, and
generating, distributing, and revoking 161 keys is avoidable logistics.
The per-account spend limit replaces the central cap; the cost of losing
the central kill switch is bounded by that same limit (~$20/student).

**Model policy (2026-07 update).** Anthropic models only, **all settings
at defaults** — no temperature or sampling overrides. (Temperature-0
discipline belongs to survey-elicitation protocols; our agent runs are
interactive tool-use sessions, a different regime.)
The second factor of the 2×2 is model tier, **within student by day**:
**economy tier** (Claude Haiku class) on day 1, **frontier tier**
(Claude Sonnet class) on day 2, tier recorded per run in the manifest —
a capability-vs-fidelity comparison at near-zero design cost. Tier is
deliberately confounded with day and stated as such in the methods
(`COURSE_PLAN_1WEEK.md`). (See `questionnaire_instrument_source.md` §1.)

## 3. Infrastructure: GitHub Codespaces on free personal accounts

**Decision.** The environment is a devcontainer at the repo root:
students create a plain (free) GitHub account, open the template repo,
click *Create codespace*, and get a bit-identical Linux desktop (noVNC in
a browser tab) with Hermes, Chromium, and all lab tooling pre-provisioned.

**Why.** Three constraints dominate at N=161 in one week: identical
environments, near-zero per-student setup, and zero dependence on
heterogeneous student hardware. Codespaces is the only free option that
satisfies all three. Every free personal GitHub account includes 120
core-hours/month (≈60 h runtime on the 2-core machine the config
requests) against a lab consuming ~8–10 h — no Student Pack, no
verification latency, no GitHub Classroom dependency. Setup is "create an
account, click a link, wait four minutes," which fits inside Session 6
with a triage buffer.

**Rejected.** *Local VMs (VirtualBox/UTM golden images)*: the earlier
primary route. Sound at small N with lead time, it collapses under 161
students × heterogeneous laptops × one week: two CPU architectures, BIOS
virtualization toggles, Hyper-V conflicts, RAM-starved hosts — a
hypervisor help desk the course cannot staff. Retained in
`provisioning/` (with host-check scripts and a triage table) strictly as
a fallback. *GitHub Classroom*: adds an organizational dependency for a
billing benefit the free personal quota already covers. *Oracle Cloud
Always Free*: generous specs but per-student account signup with card
verification and capacity lotteries — not classroom-reliable.
*Instructor-hosted cloud fleet*: most controlled, but makes the
instructor a sysadmin for the week; kept as plan C.

**Accepted risk — the one real cost.** Codespaces egress from Azure
datacenter IPs, which Amazon's anti-bot systems treat with more suspicion
than residential IPs: more login OTPs, more mid-run CAPTCHAs. Three
compensations: the human-first session-warming effect (§6), the SOUL
rule that the agent halts at every CAPTCHA for human handling, and a
mandatory instructor dry run from a codespace against real amazon.in
*before the course week* that decides Codespaces-vs-fallback empirically
rather than on day 3. Deliberately out of scope: stealth/anti-detection
tooling — wrong lesson in a course about responsible agentic AI, and
unnecessary given the mitigations.

## 4. Purchase history: the agent reads it itself

**Decision.** There is no data-extraction pipeline in the student flow.
The agent's mandatory Bootstrap step (in `SOUL.md`) is: in the already
logged-in browser, open *Your Orders*, review roughly the last 12 months
under a hard effort cap (~30 orders / ~8 minutes), and write
`purchase_profile.md` — categories and frequencies, repeat brands, price
points, conspicuous absences, inferred decision style — with the rule
that **every claim must be traceable to an order actually seen**. That
file then serves as the revealed-preference ground truth for all tasks
and as deliverable #2.

**Why.** The alternative was a three-script pipeline (official
Privacy-Central export cleaner, Playwright scraper fallback, brand
enrichment) hanging off Amazon's export SLA of hours-to-weeks — a T−14
lead time that a one-week course simply does not have, plus DOM-fragile
code needing per-term validation. Letting the agent read the history
itself deletes all of it, requires zero student effort, and is
pedagogically superior: watching your agent walk your order history and
write down who it thinks you are is the most instructive three minutes of
the course. The traceability rule imports reference-verification
discipline into the agent's self-briefing and makes confabulated
"history" auditable against the session transcript.

**Trade-off, priced in.** Agent-read history is less precise than
the official export (no guaranteed completeness, no exact unit
economics). Accepted because the profile's role is preference grounding,
not accounting — and the precise path survives as an optional
*post-course* research add-on (`data-pipeline/`) for a consenting
validation subsample, where the export's latency no longer matters.

## 5. The questionnaire: instructor-authored, code-addressed, pipeline-enforced

**Decision.** The instrument is the instructor's: **115 items**, authored
in `questionnaire_instrument_source.md` (the authoritative source; the
CSV is its machine transfer) in a fixed CSV contract (`item_code,
construct, question, response_type, options, constraint`). Composition:
15 India-adapted demographics, **57 items from 12 published, validated
consumer scales** (selection follows the Toubia et al. 2025 Twin-2K-500
battery — Big Five, Need for Cognition, agentic/communal values,
minimalism, green values, social desirability, individualism/
collectivism, regulatory focus, tightwad–spendthrift, need for
uniqueness, self-monitoring, maximization), 22 amazon.in
shopping-behavior items, 12 values/constraints (VC01–VC05 carry the
CONSTRAINT flag), and 9 predictive items that give the verdict capture
direct stated-preference benchmarks (PR09 was authored for a gift
task; see §8 on its status under the self-purchase task set). Using
validated scales makes the persona citable and comparable across
studies rather than ad hoc. An Apps Script builds the Google Form from
the CSV; responses land in one Sheet (one row per student = the cohort
persona dataset); a batch tool generates per-student persona files
overnight. Item codes are the load-bearing element: they appear in Form
headers, survive into the persona file, and `SOUL.md` obliges the agent
to cite them verbatim in its decision log.

**The agent-side treatment now has a name: the Evidence-Citation
Protocol (ECP).** Two components, both in `SOUL.md`: (1) every rejection
and selection cites a persona item code or the purchase profile; (2) an
explicit anti-stereotyping rule — never infer preferences from
demographic group membership, only from this person's stated answers
and observed behavior. What this lab deliberately does NOT adopt from
the survey-simulation paradigm: persona-format comparison arms, a
heuristics-and-biases holdout battery, a retest wave, and temperature-0
elicitation discipline — all apparatus for validating *simulated survey
answers*, whereas this lab validates *executed behavior* (real picks vs.
real picks, logged process vs. logged process). See
`questionnaire/questionnaire_instrument_source.md` §1 for the full
included/excluded record and §3 for the scale references.

**Why each piece.** *Instructor-authored*: instrument design is the
professor's scientific contribution; the real items are now in place, and
the EX0x placeholder hard-fail guards remain in the Form builder and
persona generator as protection against accidental reversion to examples.
*Form-from-CSV rather than a shared
sheet*: forced responses, validated pseudonym IDs, one-submission-per-
person, and zero transcription between collection and dataset. *Codes as
citation vocabulary*: they make the agent's reasoning machine-auditable —
every rejection and selection must point at a specific item or the
purchase profile, enabling the citation-fidelity analysis (are the
agent's cited profile facts real or invented?) that connects this lab to
the broader GenAI-quality-assurance research agenda. *The `constraint`
flag*: inviolable rules (allergies, dietary/religious exclusions, hard
budget rules) travel as data, so "constraints always win" holds under any
coding scheme without hard-coding a single item anywhere.

## 5b. Optional questionnaire-ablation factor: what does the instrument buy?

**Decision (2026-07; now ON as the plan of record).** A within-subject
ablation: the agent runs the same task set with persona grounding
(questionnaire + purchase profile) and ablated grounding (purchase
profile alone) in counterbalanced order, while the human shops once. In
the operative plan this runs on BOTH lab days — once per model tier —
forming the four-run 2×2 (grounding × tier) described in
research_protocol §1; tier is confounded with day by design and stated
as such.

**Why.** The literature is genuinely unclear on how much of a twin's
fidelity comes from stated preferences versus revealed behavior; this
design turns the questionnaire's marginal value into an estimand instead
of an assumption. The within-person contrast is the strong version: each
student is their own control, and three measures fall out per
participant — paired verdicts against the same human picks, a per-task
head-to-head (which twin chose better for me), and direct pick overlap
between the two runs (identical picks = the questionnaire changed
nothing on that task).

**Why same tasks rather than a second task set.** A second set would
avoid cross-run search carry-over but costs a doubled human session
(every task needs a human benchmark), loses the head-to-head and the
overlap measure, and adds a task-set × condition confound. Same-tasks
keeps the human session unchanged and converts carry-over into an
estimable order effect via P_FIRST/NP_FIRST counterbalancing — the
same counterbalancing logic used throughout the design.

**Enforcement, not instruction (the house principle).** The ablated run
does not merely *ignore* the questionnaire: `dtlab-start` physically
moves the persona files out of the workspace (into `~/dtlab/persona_hold/`,
which the ablated SOUL is barred from), swaps in an ablated SOUL variant,
and archives run 1's decision log before run 2 starts (so the ablated
agent can never read a persona-citing log). The packer then runs a
**manipulation check** — the ablated decision log must cite zero persona
item codes — and records condition, order, head-to-head winners, and
pick overlap in the manifest. Regression-tested end to end.

**Accepted risks.** (a) The ablated run is blind to CONSTRAINT items
(allergies, exclusions) — harmless under add-to-cart-only, and any
violation becomes a measured outcome plus comparison-memo material; the
consent sheet names it. (b) Roughly +45 minutes of agent time per
student; the week's spare classroom hours absorb it. (c) Bootstrap runs
once per day — later runs reuse the existing purchase_profile.md, holding
revealed-preference grounding constant across conditions by design.

## 6. Order of shopping: human-first with universal assessment blinding

**Decision (updated 2026-07-23, supersedes the two-arm design below).**
All students shop first (Wednesday), committing picks before any agent
run; the agent then runs the task set four times in the within-student
2×2 (grounding × tier; §5b and research_protocol §1). The
H_FIRST/A_FIRST counterbalance is retired: the primary estimands are now
within-student contrasts across agent runs that share the same
human-perturbed account, so human-session carry-over common to all runs
cancels in those contrasts, and the absolute agreement level is read
against the per-run contamination index and its cross-student
permutation baseline (PERSONALIZATION_PROTOCOL Layers 1–3). What the arms bought — an experimental order-effect
estimate — is given up for a simpler week and a stronger design where it
matters. **Blinding is now universal rather than arm-specific:** no
student watches their own agent, ever. Watching your own agent reason
anchors the later verdicts and satisfaction ratings, so self-selected
pairs swap seats for every run — the partner babysits, handles CAPTCHAs,
screenshots and empties the cart — and owners first meet their agent's
choices as artifacts in `dtlab-verdict`'s structured capture. The
pairing disclosure is in
the consent sheet.

**Original two-arm design (retained for the record).** Students are randomized (stratified, pre-assigned) into two
arms. **H_FIRST**: the student shops the three tasks first in an
instrumented browser (`dtlab-shop`, clickstream logged), confirms picks,
then the agent runs. **A_FIRST**: the agent runs first — *babysat by a
partner, not the owner* — then the student shops, blinded to the agent's
output until their own picks are committed. Human-side artifacts live in
`~/dtlab/human/`, which the agent is barred from reading; ordering and
quarantine are enforced by pre-flight checks and by timestamp validation
at packing, with the arm recorded in every manifest.

**Why the structure.** Whoever goes second is exposed to the other's
influence through two distinct channels: *observation* (seeing the other
shopper's process/choices) and *platform carry-over* (Amazon's session-
level personalization perturbed by the first shopper). Observation is the
larger channel and is fully closable: H_FIRST closes it for the human by
construction; A_FIRST closes it via partner-babysitting (CAPTCHA-solving
needs no account knowledge; the babysitter screenshots and empties the
cart). What remains in each arm is platform carry-over — onto the agent
in H_FIRST, onto the human in A_FIRST — which is exactly what the
randomization estimates (§7). Enforcement is mechanical, not trusted:
`dtlab-start` refuses out-of-order launches, the packer rejects
timestamp-inconsistent submissions and quarantine leaks, and all of it is
regression-tested (`tests/simulate_submission.sh`).

**Why the human's process is logged at all.** `dtlab-shop` passively
captures searches, product views, cart clicks, and filter changes
(explicitly excluding keystrokes, non-Amazon browsing, and
checkout/payment/auth paths). This upgrades the study from outcome
comparison to **process comparison** — consideration-set size and
overlap, query formulation, search depth, sponsored exposure, human vs.
agent — arguably the design's most novel contribution, and it costs the
student nothing: pick confirmation at session end auto-generates their
picks file.

## 7. Personalization and contamination: keep, reduce, block, measure, randomize

**Decision.** Amazon's *long-run* account personalization is deliberately
kept; *within-experiment* carry-over is handled by four layers.

**Keep the baseline (the part that is a feature).** The account's
history-shaped environment is the participant's real choice context.
Both shoppers face it identically at baseline; the twin's task is to
choose as this person would *in this person's world*. Sterilizing it
(fresh accounts, incognito) would destroy ecological validity and the
history grounding simultaneously.

**Layer 1 — reduce:** on lab-day morning, students **pause Browsing
History for 1 day** (Browsing History → gear → Pause History) and remove
existing items from view. The pause, unlike the permanent toggle, is
purpose-built for temporary use and self-reverses — nothing left changed
on 161 personal accounts. It closes the browsing-driven surfaces
("previously viewed", "inspired by your browsing"), which are the
contamination channel, while purchase-driven surfaces remain (baseline,
wanted). Known limits: enforcement is a self-attested gate in
`dtlab-start` (the ceiling of verifiability at scale), and pausing kills
the visible channel, not provably every internal session signal — hence
the layers below.

**Layer 2 — targeted block + measured provenance (agent side, updated
2026-07-23):** the agent shops the full site like the human — anything
less would make the process comparison an artifact and forbid the agent
from encountering the choice architecture the study wants to observe.
Only browsing-history-derived modules ("Previously viewed", "Inspired by
your browsing history", "Keep shopping for") are banned — empty anyway
when Layer 1's pause works; the ban is the failsafe — plus search-box
autosuggest. Every candidate's provenance is logged in its CAND line
(`search#rank`, `carousel:<name>`, `buy_again`, `product_page_link`,
`category_page`), turning surface reliance into a measured variable.

**Layer 3 — measure:** the packer computes a per-run **contamination
index** into the manifest — the share of each run's candidate set (CAND
lines) the human had viewed, with pick-level overlap as a secondary
field and missing-verdict tasks listed explicitly. Residual carry-over
becomes a measured quantity, not a hand-wave: the analyzer reports it
against a cross-student permutation baseline (same-category shopping
overlaps naturally even at zero contamination) and re-runs the headline
rates excluding the top-quartile-index runs as a robustness subgroup —
never as a regression covariate.

**Layer 4 — order design & assessment blinding:** all students are
human-first with the human picks physically quarantined, and within each
day the grounding order is counterbalanced (P_FIRST/NP_FIRST), so the
within-day run-order effect is directly estimable (see
PERSONALIZATION_PROTOCOL.md Layer 4). Statistical commitment, stated in
advance: "no significant order effect" is *not* automatically evidence
of absence. The analysis reports the CI on the within-day run-order and
task-position effects against an equivalence margin (±10 pp on
task-level outcome rates). The claim this design supports is:
within-day order effects on outcomes are bounded below the margin, with
the two dominant channels independently closed by Layers 1–2 and
residuals measured by Layer 3; day-level differences are carried by the
tier-by-day factor and stated as such in the methods.

## 8. Tasks, verdict scale, and deliverables

**Task set: five self-purchase categories, configurable as data
(decision 2026-07-23).** The task structure lives in `tasks_config.csv`
(id, frame, product type, utilitarian/hedonic category class, budget
range); pre-flight, packer, human logger, and the cohort report all
read it, and `tools/make_task_docs.py` regenerates the student
documents from it — so the task set is a design parameter, not
hard-coded prose. The operative design is **five self-purchase
categories drawn from the catalog** (a provisional five ships active —
sneakers, power bank, backpack, laptop, perfume: sneakers/backpack and
power bank/perfume are price-matched hedonic/utilitarian pairs, and
the laptop (₹40,000–1,20,000 — the ceiling deliberately reaches
MacBooks) is the HIGH-STAKES anchor — a considered durable where a
wrong agent pick clearly hurts, so twin fidelity is tested along a
stakes gradient from ₹800 accessory to ₹1.2L laptop. The cohort is
second-year MBAs in placement season, so the framing is vivid; the
Apple-vs-Windows choice is itself a clean brand-ecosystem inference
test, because the agent runs in the lab's Linux container and gets NO
signal from the student's own device — ecosystem preference must come
from the questionnaire and the purchase profile (Apple accessories in
the order history, stated brand items) or it does not come at all.
The teaching team makes the final pick and re-runs the generator +
harness.) A gift-for-best-friend fifth category was
considered and rejected: modeling a third party is a different
research question, and questionnaire item PR09 (which asks the
student to describe that exact gift) would have handed the persona
run the answer verbatim while the ablated run had nothing — a
confounded contrast, not a grounding test. The earlier replenishment and gift frames
are retired from the active set: this experiment estimates how well a
twin buys FOR ITS OWN PERSON; gift buying (modeling a third party) and
habitual replenishment are different research questions and would
confound the category contrast. With five categories spanning both
classes, the utilitarian-vs-hedonic fidelity contrast is a
within-student estimate. (Instrument note: predictive item PR09 was
authored as the gift task's stated-preference benchmark; with no gift
task it stays a general stated-preference item — swap or keep at
instrument freeze, teaching-team call.) The same confound gets the same
remedy inside the active set: PR02 (next planned online purchase) and
PR08 (item currently in cart/wishlist) name upcoming purchases, so they
are research-only — answered in the Form and kept in the research CSV as
stated-preference benchmarks, but never rendered into the agent-visible
persona (113 of the 115 items reach the agent;
`make_persona.py::AGENT_HIDDEN_ITEMS` is the authoritative set).

**No asking back (autonomy is the treatment).** All three SOULs (the
sandbox variant included) forbid the
agent from asking the human anything during a task (the CAPTCHA halt
is the sole exception): where the grounding files are silent, it must
note the gap and choose conservatively. A deployed shopping agent
would ask clarifying questions — that interactive regime is a
different (and interesting) study; this lab measures the fully
autonomous twin, so clarification would contaminate the grounding
contrast (a student's answer mid-run is un-ablatable information).
The partner protocol matches: partners never answer agent questions,
and any such exchange is logged as an intervention.

**Task order randomized across students (same decision).** What an
agent puts in the cart for one category can influence the next (budget
anchoring, brand momentum, platform state), so shopping order is a
nuisance variable. Each student gets a randomized task order, derived
deterministically from their pseudonym (no LMS column, mechanically
reproducible), which `dtlab-start` enforces by re-ordering the
sections of tasks.md at pre-flight. The order is held CONSTANT within
a student — human session and all four agent runs — so every
within-student contrast (grounding, tier, human-vs-agent) compares
runs that faced identical task sequences; across students the order is
random, so position effects cancel at cohort level and are estimable
(the analyzer reports the late-vs-early position contrast). The packer
records the executed order and warns when tasks.md was re-sorted by
hand.

**Process data is machine-parsed (2026-07).** The ECP requires one
`CAND | task= | asin= | category= | price= | sponsored= | source=`
line per candidate in the decision log (both SOUL variants), and the
human-session logger captures the category breadcrumb on every product
view. The packer parses candidates into the manifest (non-compliance
is a warning, never a failed pack), which makes the process comparison
— consideration-set sizes and agent-vs-human search overlap — a
computed quantity instead of a hand-coding project. This is the same
enforce-or-measure principle applied to the study's most novel
dependent variable.

**Verdict scale: `better | identical | equivalent | inferior`** (agent's
choice relative to the student's own). Superior to a naive
better/worse/equal because it separates *exact product convergence*
(identical) from *functional substitution* (equivalent) — two different
levels of twin fidelity. And `identical` is not self-reported: the packer
cross-checks every verdict against the two picks files' ASINs, rejecting
`identical` on differing ASINs and any other verdict on matching ones —
turning one category into an objective, verified measurement.

**Seven deliverables, one validated file.** Questionnaire (persona
files), purchase profile (agent-written once, reused across runs), the
tasks as given (in the student's assigned order), the full agent trace
per run (decision logs + auto-collected Hermes session transcripts),
agent picks per run (structured CSV + `dtlab-cart`'s screenshot and
parsed cart contents, cross-checked against the picks), human picks +
shopping clickstream, and the structured evaluation captured by
`dtlab-verdict` (verdicts, ratings, rationales, head-to-heads, Overall
reflections). `dtlab-pack` validates all of it (row counts, real ASINs,
verdict–ASIN consistency, quarantine, human-first ordering, per-run
condition/tier bookkeeping, the manipulation check), writes SHA-256
hashes and the full design metadata into `manifest.json`, renders a
self-contained `report.html` for graders, and emits one zip. Invalid packs still produce the zip but exit non-zero with
an explicit fix list — a student cannot silently submit an incomplete
pack, and the instructor cannot receive one without knowing what's
missing. Cohort assembly then reduces mostly to concatenating CSVs; only
citation-fidelity coding touches free text.

**Reproducibility metadata (2026-07).** Each manifest also records which
twin produced the run: Hermes version, model tier (and model ID where
capturable), SHA-256 of the exact SOUL.md and of the standardized prompt
block in tasks.md, kit commit, and image tag. Cheap to collect, and it is
what lets the cohort analysis rule out version confounds — at N=161 over
two days, "everyone ran the same twin" must be verifiable, not assumed.

**Why no browser plugin for logging.** An earlier idea. Rejected because
the three-layer trail already in hand — Hermes session transcripts, the
mandated agent-written decision log, and screen recording — covers the
agent side redundantly, and `dtlab-shop`'s Playwright instrumentation
covers the human side, all inside one codebase with no extension
distribution, no developer-mode installs, and no third browser-permission
conversation with 161 students.

## 9. Safety, ethics, and account risk

**Hard boundaries, in the agent's identity file:** add-to-cart only;
never checkout, addresses, payments, account settings, or subscriptions;
order-history pages are the only account pages it may open; halt at every
CAPTCHA; per-task effort caps (~10 min / ~12 product pages) so a run can
never loop unboundedly at N=161. **Prompt-injection hardening (2026-07):**
the agent reads arbitrary third-party content (listings, reviews, seller
text), so SOUL.md declares all webpage text data-never-instructions and
requires logging any listing that appears to address an AI agent —
which is itself course content for the SOUL walk-through in Session 8.
Students remove saved payment methods from the lab browser profile —
now a pre-flight confirm gate in `dtlab-start`, not just a handout line —
and carts are emptied after evidence capture.

**Secrets and recordings (2026-07 hardening).** The API key is collected
with hidden input, stored only in a 600-permission `~/.dtlab_env`, and
never echoed — so it cannot appear in the screen recording; `dtlab-record`
refuses to start until the student confirms login already happened (no
passwords/OTPs on screen). The packer runs a content-redaction pass over
every packed text file (API-key patterns scrubbed; email/phone/"Deliver
to" markers counted into a `redaction_report` in the manifest) because
filename-based filtering cannot see inside transcripts. Remote installers
are pinned by SHA-256 and downloaded-then-verified, never piped to shell;
the noVNC desktop gets a per-codespace random password and the forwarded
port must stay Private.

**Research ethics:** course participation and research participation are
separable — consent covers the pseudonymized questionnaire, the
purchase-profile extract, the clickstream (with its explicit exclusions),
agent logs, AND the partner-pairing disclosure (a self-selected classmate
sees your agent narrate your purchase profile); a synthetic-persona pack provides a no-questions opt-out with no
grade impact; pseudonym↔name mapping is held separately by the instructor
and destroyed post-study; data minimization is implemented in code (the
pre-flight refuses to launch with PII-shaped files in the workspace; the
packer redacts keys and flags PII) rather than promised in prose. The
cohort sits in India: DPDP Act 2023 is the operative regime and BITSoM's
ethics process (plus the instructor's home IRB where required) precedes
the questionnaire; GDPR applies only if EU exchange students enroll.

**Account risk, stated plainly in the syllabus:** automated interaction
sits in tension with Amazon's conditions of use. Mitigations — manual
login, human-warmed sessions, human-paced actions, add-to-cart only, one
short run — reduce but do not eliminate the risk of an account being
flagged; the synthetic-persona path doubles as the zero-risk option, and
class time is never spent fighting Amazon. The mid-session flag fallback
is now specified, not improvised: the student re-runs both sessions
against the pre-built sandbox store (books.toscrape.com, the smoke-test
target) with the synthetic persona — graded identically, flagged
`sandbox`, excluded from the research dataset (see the risk table in
`COURSE_PLAN_1WEEK.md`).

## 10. Timeline: why five 3 h sessions + one overnight work

Monday (Session 6) is environment + identity: consent, accounts, and the
codespace build in class, with the questionnaire as evening homework —
the overnight works because the Form needs only a link and a pseudonym,
and the instructor's batch tool turns the response sheet into
per-student persona files in minutes, printing a completion roster for
chasing stragglers. Tuesday completes the build on the student's own key
and ends with a watched sandbox run — at ~80 per section, ~5–8 stuck
environments are a planning assumption, not a surprise, and the triage
buffer absorbs them. Wednesday commits the human baseline before any
agent runs. Thursday and Friday each fit two ~55-minute agent runs plus
structured verdict capture inside 3 h, with the partner-swap protocol
running both days and one-command packing closing Friday. Everything cut
from earlier drafts (data-export lead times, VM funnels, host checks as
a student-facing step) was cut because it could not survive this clock;
everything retained is either enforced in code or has a pre-decided
classroom fallback.

## 11. Known limitations, accepted deliberately

1. **DOM fragility** in the human-session logger (cart-click selector,
   URL parsing) — single patch points, TA-validated against live
   amazon.in shortly before the course.
2. **Hermes release drift** — docs canonical, dry run decisive.
3. **Datacenter-IP CAPTCHA friction** — measured in the dry run, with
   the fallback decision made before, not during, the week.
4. **Agent-read history is imprecise** relative to the official export —
   acceptable for preference grounding; precise path available
   post-course for a validation subsample.
5. **Layer-1 pause is self-attested** and closes the visible channel
   only — which is exactly why Layers 2–4 exist and carry the
   inferential weight.
6. **Empty-history students** produce persona-only twins — flagged, kept,
   and analyzed as a natural comparison subgroup rather than excluded.

The unifying design principle behind all of the above: **every claim the
experiment will need to defend is either enforced by code or measured as
data — never merely instructed.** Ordering, blinding, quarantine, verdict
consistency, citation traceability, and contamination are all in that
category; where enforcement is impossible (the pause, naturalistic human
shopping), the design measures instead. That principle is what makes a
classroom exercise with 161 MBA students simultaneously a publishable
paired-choice experiment.
