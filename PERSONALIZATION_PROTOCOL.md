# Personalization protocol — handling Amazon's memory of the account

Amazon personalizes what both the student and the agent see: "Previously
viewed", "Buy it again", "Inspired by your browsing history", re-ranked
search results. This splits into two very different issues. One is a
feature to keep; the other is a confound to control.

## Issue A — pre-existing account personalization: KEEP IT

The account's long-run personalization (built from years of purchases and
browsing) is part of the participant's *real choice environment*. Both the
human and the agent shop inside it, and the twin's job is precisely to
choose as this person would *in this person's world*. Sterilizing the
account (fresh account, incognito) would (a) destroy ecological validity,
(b) break the purchase-history grounding, and (c) be impossible to do
symmetrically anyway. So: pre-existing personalization stays, is identical
for both shoppers at baseline, and is documented as part of the design,
not a limitation.

## Issue B — within-experiment contamination: REDUCE, BLOCK, MEASURE

The real threat: the human shops first (by design), so the agent shops in
an environment freshly perturbed by the human's session — "previously
viewed" badges on the very items the human considered, browsing-history
carousels seeded with the human's candidates, short-term re-ranking toward
them. Left alone, this biases the agent *toward* the human's picks and
inflates every agreement metric. Known direction, unknown size — so we
attack it on three layers:

### Layer 1 — REDUCE at the source: PAUSE Browsing History (required)

Amazon has a purpose-built temporary switch — use the pause, not the
permanent toggle:

**Desktop:** amazon.in → Accounts & Lists → **Browsing History** → gear
icon (Manage history) → **Pause History → 1 day** → then **Remove all
items from view** to clear the existing trail.
**App:** profile icon → Browsing history (under "Keep shopping for") →
gear icon → **Pause History → 1 day**.

The pause lasts ONE day, so it is repeated on EVERY lab-day morning —
Wednesday (human session), Thursday (economy runs), and Friday (frontier
runs; `dtlab-start`'s day-2 gate re-confirms it). It self-reverses — no
cleanup step, nothing left permanently changed on 161 personal accounts.
`dtlab-start` gates on a self-attested confirmation each day.
Two notes for the handout: (a) users have reported the permanent on/off
toggle occasionally flipping back on by itself — the pause appears more
reliable, but students should verify the Browsing History page shows
paused/empty before proceeding; (b) even paused, this closes the
BROWSING-driven surfaces (the contamination channel); purchase-driven
surfaces like "Buy it again" remain, which is the baseline personalization
we deliberately keep (Issue A).

Each lab-day morning, before that day's first session:
1. amazon.in → Browsing History → gear icon (**Manage history**) →
   **Pause History → 1 day** → **Remove all items from view**.
2. Verify the Browsing History page shows paused/empty.

With browsing history paused on every lab day, the "previously viewed" /
"inspired by browsing" surfaces never populate from the human's session
(or from earlier agent runs), and all shoppers face symmetric
conditions. (Purchase-history-driven
surfaces like "Buy it again" remain — that's Issue A, wanted.)
(Gate implemented in `dtlab-start` as described above.) Note: Amazon may still use short-term session signals
for ranking internally; the toggle removes the visible and strongest
channel, not necessarily every trace — hence Layers 2 and 3.

### Layer 2 — TARGETED BLOCK + measured provenance (SOUL rule)

The human shops naturalistically; the agent shops the whole site the
same way — anything less would make the human–agent process comparison
an artifact of an imposed rule, and would forbid the agent from ever
encountering the platform choice architecture (carousels, badges,
sponsored placements) the study wants to observe it navigating. The
distinction that matters is *which* surfaces can carry the human
session's trace:

- **Allowed (item-based or purchase-based — no browsing-session
  leakage):** keyword search, category pages, product-page links,
  "Customers who viewed this also viewed", "Frequently bought
  together", bestseller lists, badges, sponsored results, and "Buy it
  again" (purchase-driven — the baseline personalization deliberately
  kept under Issue A).
- **Banned (browsing-derived — the contamination channel):** "Previously
  viewed", "Inspired by your browsing history", "Keep shopping for",
  "Related to items you've viewed". With Layer 1's pause working these
  modules are empty anyway; the ban is the failsafe for the accounts
  where the pause silently fails. The agent also ignores search-box
  autosuggest (which can reflect the account's recent searches) and
  types queries in full.
- **Everything is provenance-logged:** each CAND line records where the
  candidate came from (`search#rank`, `carousel:<name>`, `buy_again`,
  `product_page_link`, `category_page`), so the agent's reliance on
  each surface type is a measured variable in the cohort analysis, and
  any contamination that does slip through arrives with its origin
  attached.

This closes the browsing-derived pathway structurally while making the
rest of the choice architecture observable instead of forbidden.

### Layer 3 — MEASURE what remains (contamination index)

We already log everything needed to quantify residual contamination
instead of hand-waving it:
- Human side: the set of ASINs viewed in `human_session.jsonl`.
- Agent side: the candidates and picks in `decision_log.md` /
  `agent_picks.csv`.

`dtlab-pack` computes and writes into the manifest a **contamination
index** per run: the share of the run's CANDIDATE set (machine-parsed
CAND lines) that the human had viewed, with pick-level overlap kept as
a secondary field and tasks with missing verdicts listed explicitly.
The raw index has no natural zero — two shoppers working the same five
categories overlap on the same first page even with zero contamination
— so the analyzer reads it against a **cross-student permutation
baseline** (student i's candidate sets scored against student j≠i's
viewed sets, same tasks) and reports the excess. The index is used
descriptively and as a robustness subgroup (the grounding and tier
contrasts recomputed excluding the top-quartile-index runs), never as a
regression covariate: it measures only the human→agent channel, and
covariate adjustment on a post-treatment measurement would bias the
within-student contrasts it is meant to protect.

### Residual timing guidance

Prefer a gap of a few hours between `dtlab-shop` and the agent run
(e.g. human session in the morning, agent run in the afternoon lab)
— long enough for session-level ranking signals to decay, short enough
to keep the login warm for CAPTCHA purposes. Same day is fine; same
minute is not ideal.

## What to write in the methods section (pre-drafted)

"Both shoppers operated within the participant's authentic, long-run
personalized account environment (ecological validity). Within-experiment
carry-over from the human session to the agent sessions was (i) attenuated
by pausing and clearing Amazon browsing history on every lab day,
(ii) structurally blocked on the agent side by prohibiting only the
browsing-history-derived surfaces (all item- and purchase-based surfaces
remained available, with every candidate's provenance logged), and
(iii) quantified per participant and per run as the share of each run's
candidate set the participant had viewed, reported against a
cross-student permutation baseline and used in robustness subgroup
analyses. The
primary estimands — the questionnaire effect and the model-tier effect —
are within-participant contrasts across agent runs facing the same
human-perturbed account, so carry-over common to all runs cancels in
these comparisons."


## Layer 4 — ORDER DESIGN & ASSESSMENT BLINDING (2026-07 design)

**All students shop human-first** (Wednesday), committing their picks
before any agent run; the four agent runs (2×2: persona/ablated ×
economy/frontier) follow on Thursday and Friday. In every session —
human and agent — checkout is technically blocked at the network layer
(checkout-guard extension, canary-verified by `dtlab-start`); attempts
are logged and flagged at pack time. The order-arm
counterbalance of earlier drafts is retired: with the primary estimands
now *within-student contrasts across agent runs* — questionnaire effect
and model-tier effect — carry-over from the human session is common to
all four runs and cancels in those contrasts. The absolute human–agent
agreement level keeps its three safeguards (Layer 1 pause, Layer 2
targeted block, Layer 3 per-run index vs its permutation baseline) and is reported with
that framing.

### Assessment blinding: no one watches their own agent or judges a labeled run

Watching your own agent reason its way to a pick anchors the later
verdicts and satisfaction ratings — sympathy for a visible process is
not a property of the pick. Protocol, ALL runs, both days: students work
in self-selected pairs and **swap seats for every agent run**. The
partner babysits the neighbor's run (CAPTCHA handling needs no account
knowledge; login happens before the swap), runs `dtlab-cart` after the
run (automatic cart screenshot + parsed cart contents), and empties the
cart between runs. Owners first encounter
their agent's choices as artifacts — picks, logs, screenshots — in
`dtlab-verdict`'s structured capture (the comparison memo is the
fallback), exactly the evidence a reader of the study would have.

Blinding covers **condition knowledge at judgment time**, not just run
execution: `dtlab-verdict` presents each task's picks in a per-task
randomized order labeled Run A–D and never names condition or tier
before a verdict is stored — a student cannot favor "the persona run"
or "the frontier run" because nothing on screen says which one that is.
Condition and tier are resolved into `verdicts.csv` post-hoc, the
manifest records `verdicts_captured_blind`, and the label→run mapping is
revealed only after capture (the Overall reflections reference tiers by
design and run last). The pairing doubles as the CAPTCHA-resolution staffing
and is named in the consent sheet (a classmate sees your purchase
profile and picks during the runs; pairs are self-selected).

### Cross-run carry-over (agent → agent)

Run N+1 shops an account perturbed by run N. Handled the same way:

1. Layer 1 is repeated EVERY lab-day morning (the pause lasts one day —
   the Friday re-pause is a pre-flight gate, not a suggestion).
2. Layer 2's browsing-derived ban applies to all runs symmetrically;
   item-based surfaces do not carry session traces.
3. **Grounding order is counterbalanced within each day**
   (P_FIRST/NP_FIRST re-randomized per day on the LMS list), so the
   persona-vs-ablated contrast is orthogonal to run position.
4. The model tier is deliberately confounded with day (economy Thursday,
   frontier Friday — the course's narrative arc). State this in one
   sentence in the methods; the within-day run-order estimate from the
   counterbalanced grounding order bounds the plausible size of
   day-order effects.
5. The contamination index is computed per run and measures the
   human→agent channel only (run N→N+1 carry-over is handled by items
   1–3 above); it is reported against the cross-student permutation
   baseline and used as a robustness subgroup, never as a covariate.
