# Change log & the live dry-run checklist

This file serves two operational purposes: the **T-21 dry-run
checklist** (everything that can only be verified against the live
stack — work through ALL of it during the trial run and tick items off
here) and the **change log** (every kit change and every deviation from
the docs observed during the trial, dated, appended at the bottom).
Design reasoning lives in `docs/design_rationale.md`; the operative
plan is `COURSE_PLAN_1WEEK.md`.

## THE T-21 dry-run checklist (live — the one canonical copy)

1. **Hermes `/browser connect` mechanics** — verify it attaches to the
   CDP port (`DTLAB_CDP_PORT=9222`) and profile launched by
   `tools/dtlab_browser.sh`; adjust the constant if the pinned release
   expects something else.
2. **Hermes `HERMES_HOME` + config mechanics (pinned release)** —
   verify on the pinned release: `$HERMES_HOME/SOUL.md` is loaded and
   the working-directory copy ignored; the launcher-generated
   `config.yaml` (from `provisioning/hermes_config.template.yaml`)
   selects the model (adjust the template keys if the release
   differs); where transcripts land inside the run home (adjust the
   packer's collection subpath). Legacy fallback `DTLAB_HERMES_DIRS`
   remains for old layouts.
3. **Installer pins** — pin Hermes/uv URLs + SHA-256 and the Playwright
   version in both provisioners (TA_ONBOARDING.md > "Updating installer
   pins"); builds refuse to run unpinned.
4. **noVNC password rotation** — confirm the rotation in
   `.devcontainer/setup.sh` actually takes effect in a built codespace.
5. **Model IDs + verification** — pin `DTLAB_MODEL_ECONOMY` /
   `DTLAB_MODEL_FRONTIER` in `dtlab_config.env` (launch refuses
   `PIN-AT-DRYRUN`); confirm the per-run config verification catches a
   forced mismatch; spot-check a transcript for the model actually
   used.
6. **Protocol-token + forbidden-path canaries** — per SOUL variant,
   the decision log opens with the right `PROTOCOL |` token; a sandbox
   request to read `~/dtlab/quarantine/...` is refused and logged;
   the packer flags a planted quarantine reference; the bootstrap
   freeze hash trips on edit. (Procedures: TA_ONBOARDING >
   "T-21 trial-run work items".)
7. **Codespaces quotas** — reconcile the 120 vs 180 core-hours figures
   against GitHub's current docs (`CLOUD_SETUP.md`).
8. **Google Forms scale** — one `buildForm()` run creates all 115
   questions + 16 page breaks without hitting Apps Script quotas.
9. **Browser profile sharing** — Playwright (`executable_path` = system
   chromium) and the agent session tolerate the shared profile at
   `~/dtlab/browser-profile` (version skew was the risk).
10. **Breadcrumb selector** — `#wayfinding-breadcrumbs_feature_div`
    still yields categories on live amazon.in product pages (degrades to
    empty category, never an error).
11. **CAND compliance** — the agent actually follows the `CAND |` line
    format under the pinned Hermes/model; check the dry-run manifest's
    `candidates` and `warnings` fields.
12. **Token/cost benchmark across tiers** — one full single-category
    task under Haiku-class and Sonnet-class, each with and without
    extended thinking, repeated over 2–3 categories; record tokens, $,
    wall-clock, success (TA_ONBOARDING work item). Sets the per-key cap
    and validates the ~$20 spend-limit guidance.
13. **Category links** — spot-check the `amazon_url` browse-node links
    in `tasks_config.csv` still resolve to the intended categories on
    live amazon.in.
14. **Cart selectors (`dtlab-cart`)** — validate the SELECTORS dict in
    `tools/capture_cart.py` against the live amazon.in cart page (run
    a real agent-filled cart through `dtlab-cart`, check
    `cart_runN.json` items + the packer's `cart_verified` result;
    parsing failure degrades to screenshot-only by design).
15. **Checkout-guard rules** — validate the blocked patterns in
    `tools/checkout_guard_extension/rules.json` against live amazon.in:
    desktop Buy Now, cart "Proceed to Buy", one-click where offered,
    and the mobile-web layout each land on blocked.html, while cart
    add/edit/view stays untouched.
16. **Human ref= provenance mapping** — during the dry-run human
    session, spot-check that amazon's ref= slugs on product views
    (search results, a carousel, Buy Again, a category page) land in
    the right buckets via `analyze_cohort.py::bucket_ref` (unknown
    slugs fall to 'other' by design; adjust the mapping there).

## Change log

Append every kit change and every observed deviation from the docs
here, newest first, dated, with the files touched and the suites re-run.

### 2026-07-27 — Kit finalized for the T-21 trial run

The complete kit as handed to the teaching team: per-run Hermes homes
deliver each run's SOUL and pinned model configuration (fail-closed,
hashed, token-verified); tier order counterbalanced across days per
student via the counterbalance sheet; one-time questionnaire-blind
bootstrap writes the frozen purchase profile; single blind Friday
verdict session with immutable rows and TA-authorized amendments;
quarantine root for all human-side artifacts with pack-time leakage
scans; live exact cart verification; full redaction with final-archive
scanning; cluster-aware confirmatory statistics (sign-flip permutation,
Holm over H1–H3) with run-level research exports; supply-chain and
image pins with a stale-prebuild check. All four regression suites,
lint, and the doc-checker are green at this state.
