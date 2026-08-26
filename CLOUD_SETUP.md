# Cloud route — identical free environments via GitHub Codespaces

> **STATUS: PRIMARY route.** `COURSE_PLAN_1WEEK.md` is the single authority
> on the infrastructure decision: Codespaces on free personal accounts is
> primary, subject to confirmation by the instructor dry run (T-21); local
> VMs (`provisioning/VM_DISTRIBUTION.md`) are the fallback for students
> whose accounts get flagged or in case the dry run fails. The
> datacenter-IP CAPTCHA cost is real and is mitigated by the human-first
> protocol (dtlab-shop before the agent hands over a human-warmed session).

## Can this be done on a free cloud VM? Yes — with one known cost.

**Recommended free path: GitHub Codespaces.** Every
student gets the same frozen container environment defined in
`.devcontainer/` (at the repo root) — same OS, same Hermes version, same browser, same tools —
launched from a browser link with zero local installation, on Windows,
Intel Mac, Apple Silicon, or a library computer alike. This dissolves the
two-architecture VM problem entirely.

Why it's free — **quota figures reconciled against GitHub's docs on
2026-08-26 (T-21 item 7). Re-check at term start; GitHub has shifted
these repeatedly.**
- **Free personal accounts: 120 core-hours + 15 GB storage per month.**
  Core-hours are runtime x the machine multiplier, so 120 core-hours is
  ~60 h on the 2-core machine this config requests. The lab needs ~8-10 h.
  Comfortable headroom on compute.
- **GitHub Pro: 180 core-hours + 20 GB storage.** The Student Developer
  Pack grants Pro, which is where the 180 figure comes from — so the two
  numbers were never in conflict, they are simply different plans. The
  Pack adds a verification wait the one-week format can't absorb; treat
  it as headroom, not a dependency.
- **Free Codespaces usage is personal-account only** — it is explicitly
  not included in organization or enterprise accounts. Each student
  therefore spends their own allowance, which is the intended design, but
  it also means the TA's testing burns the TA's personal quota.
- ⚠️ **Storage is the tighter constraint, not compute.** This config
  requests `"storage": "32gb"` in `hostRequirements`, against a 15 GB
  free monthly allowance (20 GB on Pro). Storage is billed per GB-month
  across all live codespaces and prebuilds, so a student who leaves one
  codespace alive through the lab week can plausibly exceed the free
  allowance even though compute is nowhere near the limit. **Verify how
  GitHub meters this against the actual machine type before the week**,
  and tell students to delete their codespace when the lab ends rather
  than leaving it stopped-but-present.
- Machine size matters twice over: a 4-core machine halves the available
  runtime (multiplier 4 rather than 2). Use 2-core for students.
- GitHub Classroom (billing to a classroom org) exists as an alternative,
  but the plan deliberately avoids the organizational dependency.

How it works for the student:
1. Open the codespace link from the LMS handout
   (`https://codespaces.new/dringel/DTShopAgent?quickstart=1` — live
   once the repo is public at design freeze) → "Create codespace".
2. Wait ~4 min for first build (the setup script installs everything;
   with prebuilds enabled on the template repo, much less).
3. Click the auto-forwarded **Lab Desktop** port → a Linux desktop opens
   in a browser tab (noVNC; the per-codespace password is printed in the
   setup log / terminal). **Never set this port to Public** — a public
   port hands a desktop logged into your Amazon account to anyone with
   the URL. Chromium runs there.
4. Use the VS Code terminal for the six commands, same as the VM route:
   `dtlab-shop`, `dtlab-start`, `dtlab-cart` (partner, after every run),
   `dtlab-verdict`, `dtlab-record` (optional), `dtlab-pack`.
5. The packed evidence zip is downloaded via the VS Code file explorer
   (right-click → Download) and uploaded to the LMS.
6. **Stop the codespace when done** (it also auto-suspends after 30 min
   idle) — core-hours only burn while running. The flip side of that
   auto-suspend: **set the idle timeout to 240 min at
   github.com/settings/codespaces before Thursday**, and keep the VS
   Code tab active during agent runs — the noVNC Lab-Desktop tab alone
   does not count as activity, so a codespace can suspend under a
   running agent.

Instructor setup (once): make this kit a **template repo**
(`.devcontainer/` is at the repo root already), pin the installer
checksums (TA_ONBOARDING.md > "Updating installer pins"), and enable
**Codespaces prebuilds** on the template so all 161 students get one
frozen, pre-tested image (and skip most of the 4–6 min build). Do one
full dry run yourself — including a real amazon.in session — before
committing the cohort to this route.

## The known cost: datacenter IPs

Codespaces egress from Microsoft Azure datacenter IP ranges. Amazon's
anti-bot systems treat datacenter traffic with more suspicion than the
residential IPs a local VM inherits from the student's home connection.
Expect: more frequent login verification (OTP emails/SMS), more CAPTCHAs
mid-session, and a small but real chance of an account being temporarily
flagged. The design already mitigates the worst of it — the student logs
in manually, the agent's SOUL stops at every CAPTCHA for human handling,
and actions run at human pace — but the friction is genuinely higher than
on a local VM.

**Decision rule:** dry-run the full lab from a codespace yourself. If your
amazon.in session behaves (one OTP at login, occasional CAPTCHA), adopt
Codespaces as the primary route and keep local VMs as the fallback for any
student whose account gets cranky. If Amazon fights you throughout the dry
run, invert it: local VMs primary (VM_DISTRIBUTION.md), Codespaces as the
fallback for students whose laptops can't run a VM.

## Rejected free alternatives (so you don't re-litigate them)

- **Oracle Cloud "Always Free"** (4 Arm cores / 24 GB — the most generous
  true free tier): requires each student to open their own cloud account
  with a credit card, signups are frequently rejected, and free-tier
  capacity is often unavailable in popular regions. Not classroom-reliable.
- **AWS/GCP/Azure free tiers**: the always-free instance sizes (~1 GB RAM)
  cannot run a desktop + Chromium + agent.
- **Google Cloud Shell**: free but ephemeral and storage-limited; sessions
  reset. No.
- **Instructor-provisioned cloud fleet on education credits** (one script
  spins up N identical VMs with web desktops; students get a URL): the most
  controlled option and effectively free via university cloud-credit
  programs, but it makes the instructor the fleet's sysadmin for the week
  and shares the same datacenter-IP cost. Keep as plan C.
