#!/usr/bin/env bash
# setup.sh — container-adapted provisioning for the Codespaces route
# (PRIMARY route, see COURSE_PLAN_1WEEK.md). Mirrors provisioning/provision.sh
# but for the devcontainer: Debian base (apt chromium works here; on Ubuntu
# VMs chromium is snap-packaged), desktop-lite provides the noVNC desktop on
# display :1 / web port 6080. Safe to re-run at any time.
#
# Lifecycle split (devcontainer.json):
#   onCreateCommand:   bash .devcontainer/setup.sh onCreate
#     local layout + the heavy network installs (apt, playwright, Hermes).
#     Prebuilds execute onCreate, so with prebuilds enabled these are baked
#     into the one frozen image all 161 students share.
#   postCreateCommand: bash .devcontainer/setup.sh
#     the per-codespace bits (kit version stamp, desktop password rotation)
#     plus the same idempotent local layout, so a codespace restored from a
#     prebuild is complete without any network step.
#
# LOCAL STEPS RUN FIRST in both phases: a network failure (e.g. the Hermes
# installer gate below) still leaves a diagnosable environment with all
# dtlab-* commands in place.
#
# DTLAB_TEST=1 short-circuits every network step (used by tests/).
set -euo pipefail
trap 'echo "" >&2; echo "Setup did not finish — tell a TA. Retry with: bash .devcontainer/setup.sh" >&2' ERR
KIT="$(cd "$(dirname "$0")/.." && pwd)"   # repo root = the dt-lab kit
PHASE="${1:-postCreate}"

# ---- pinned downloads -------------------------------------------------
# Remote installers are downloaded to a file, checksum-verified, then
# executed. The Hermes URL is an immutable signed release tag, and the
# installer is additionally told which exact release commit to check out:
# hashing a script that still clones floating main would not be a real pin.
# Pins resolved and scripts inspected 2026-08-28; update only via
# TA_ONBOARDING.md > "Updating installer pins" and a fresh build.
HERMES_INSTALLER_URL="https://raw.githubusercontent.com/NousResearch/hermes-agent/v2026.8.3/scripts/install.sh"
HERMES_INSTALLER_SHA256="45f589461248c7a6ec3aecd7522a69dd49c5c8dbf4798ba1296af5c0c5e7ccd3"
HERMES_COMMIT="3c27eb6234bf91b8ceee9e9071591b31e9b148cb"
PLAYWRIGHT_PIN="==1.62.0"
ANTHROPIC_PIN="==0.122.0"

# Flags passed to the Hermes installer. These are load-bearing, not
# cosmetic — see the "Hermes Agent" step below. Keep .devcontainer/setup.sh
# and provisioning/provision.sh in lockstep.
HERMES_INSTALL_FLAGS=(--skip-setup --non-interactive
  --commit "$HERMES_COMMIT" --force-commit)
# Wall-clock ceiling for the installer. A blocked prompt must fail the
# build with a diagnosis, never hang a creation hook forever.
HERMES_INSTALL_TIMEOUT="${DTLAB_HERMES_INSTALL_TIMEOUT:-2400}"

fetch_verified() {  # url sha256 dest
  local url="$1" sha="$2" dest="$3"
  if [ "$sha" = "UNPINNED" ] && [ "${DTLAB_ALLOW_UNPINNED:-0}" != "1" ]; then
    echo "ERROR: $url has no pinned SHA-256."
    echo "Pin it first (TA_ONBOARDING.md > Updating installer pins), or"
    echo "export DTLAB_ALLOW_UNPINNED=1 for a throwaway test build."
    exit 1
  fi
  curl -fsSL "$url" -o "$dest"
  if [ "$sha" != "UNPINNED" ]; then
    echo "$sha  $dest" | sha256sum -c - || {
      echo "ERROR: checksum mismatch for $url — a new release or tampering."
      echo "Do NOT bypass; re-pin per TA_ONBOARDING.md and re-run."
      exit 1
    }
  else
    echo "WARNING: running UNPINNED installer from $url (test build only)."
  fi
}

echo "== [1/5] Lab layout (local, runs before anything that needs network) =="
# ---- persistent lab root -----------------------------------------------
# In Codespaces only /workspaces survives a container rebuild; everything
# under $HOME is wiped. The lab tree therefore lives at /workspaces/.dtlab
# (OUTSIDE the repo clone, so student data never sits in the git working
# tree) and ~/dtlab is a symlink to it — every existing path keeps working
# and a mid-week "Rebuild Container" no longer erases the week's evidence.
# On the VM route (no /workspaces) the root falls back to $HOME/dtlab.
# The API key file ~/.dtlab_env stays in $HOME BY DESIGN: it must not
# survive into a shared or persisted layer; re-entering the key after a
# rebuild is correct behavior.
DTLAB_ROOT="${DTLAB_ROOT:-}"
if [ -z "$DTLAB_ROOT" ]; then
  if [ -d /workspaces ] && [ -w /workspaces ]; then
    DTLAB_ROOT="/workspaces/.dtlab"
  else
    DTLAB_ROOT="$HOME/dtlab"
  fi
fi
mkdir -p "$DTLAB_ROOT"
if [ "$DTLAB_ROOT" != "$HOME/dtlab" ]; then
  if [ -e "$HOME/dtlab" ] && [ ! -L "$HOME/dtlab" ]; then
    # pre-symlink layout found: migrate its contents into the root once
    cp -a "$HOME/dtlab/." "$DTLAB_ROOT/"
    rm -rf "$HOME/dtlab"
  fi
  ln -sfn "$DTLAB_ROOT" "$HOME/dtlab"
  echo "lab root: $DTLAB_ROOT (~/dtlab is a symlink; survives rebuilds)"
fi
mkdir -p "$HOME/dtlab/workspace" "$HOME/dtlab/evidence" "$HOME/dtlab/tools"
cp -v "$KIT/agent/SOUL.md"                 "$HOME/dtlab/workspace/SOUL.md"
# kit-owned SOUL variants for the optional ablation factor (dtlab-start
# swaps the workspace SOUL.md per condition when the factor is enabled)
mkdir -p "$HOME/dtlab/soul"
cp -v "$KIT/agent/SOUL.md" "$KIT/agent/SOUL_ablated.md" \
      "$KIT/agent/SOUL_nohistory.md" \
      "$KIT/agent/SOUL_sandbox.md" "$KIT/agent/SOUL_bootstrap.md" \
      "$HOME/dtlab/soul/"
cp -v "$KIT/templates/comparison_ablation.md" \
      "$HOME/dtlab/comparison_ablation.TEMPLATE.md"
cp -v "$KIT/dtlab_config.env"              "$HOME/dtlab/dtlab_config.env"
cp -v "$KIT/tasks_config.csv"              "$HOME/dtlab/tasks_config.csv"
# per-run Hermes config template: dtlab-start generates each run's
# $HERMES_HOME/config.yaml from this (provider + pinned model per tier);
# no interactive `hermes setup` provider choice is needed — the per-run
# config is authoritative
cp -v "$KIT/provisioning/hermes_config.template.yaml" \
      "$HOME/dtlab/hermes_config.template.yaml"
# counterbalance sheet (pseudonyms only): placed at the repo root by the
# instructor before the freeze (tools/make_counterbalance.py); the
# pre-flight looks each student's day order up here
if [ -f "$KIT/counterbalance.csv" ]; then
  cp -v "$KIT/counterbalance.csv"          "$HOME/dtlab/counterbalance.csv"
elif [ "${DTLAB_ALLOW_NO_COUNTERBALANCE:-0}" = "1" ] \
     || [ "${DTLAB_TEST:-0}" = "1" ]; then
  echo "WARNING: counterbalance.csv absent (pre-freeze/test build) —"
  echo "the pre-flight cannot look up assignments until it exists."
else
  # counterbalance gate (audit 8.2): a frozen build without the sheet
  # would make every student type their own assignment — fail the build
  echo "ERROR: counterbalance.csv missing at the repo root. Generate it"
  echo "from the final roster (tools/make_counterbalance.py) and commit"
  echo "it before the freeze, or export DTLAB_ALLOW_NO_COUNTERBALANCE=1"
  echo "for a pre-freeze build."
  exit 1
fi
mkdir -p "$HOME/dtlab/assets"
cp -v "$KIT/assets/ringelai.png"           "$HOME/dtlab/assets/" 2>/dev/null || true
cp -v "$KIT/tools/log_human_session.py"    "$HOME/dtlab/tools/"
cp -v "$KIT/tools/capture_cart.py"         "$HOME/dtlab/tools/"
cp -v "$KIT/tools/scrub_profile.py"        "$HOME/dtlab/tools/"
cp -v "$KIT/tools/capture_orders.py"       "$HOME/dtlab/tools/"
cp -v "$KIT/tools/validate_profile.py"     "$HOME/dtlab/tools/"
cp -v "$KIT/tools/capture_tokens.py"       "$HOME/dtlab/tools/"
cp -v "$KIT/tools/capture_verdicts.py"     "$HOME/dtlab/tools/"
cp -v "$KIT/tools/dtlab_browser.sh"        "$HOME/dtlab/tools/"
# checkout-guard extension: kit code (never packed as evidence); the
# launcher loads it from here and dtlab-start's canary proves it's live
rm -rf "$HOME/dtlab/tools/checkout_guard_extension"
cp -rv "$KIT/tools/checkout_guard_extension" "$HOME/dtlab/tools/"
cp -v "$KIT/data-pipeline/"*.py            "$HOME/dtlab/tools/"
cp -v "$KIT/questionnaire/make_persona.py" "$HOME/dtlab/tools/"
cp -v "$KIT/tools/pack_evidence.py"        "$HOME/dtlab/tools/"
cp -v "$KIT/provisioning/student_start.sh" "$HOME/dtlab/tools/"
# Templates land in the workspace ONCE; students fill them in place, so a
# container rebuild must never clobber them.
[ -f "$HOME/dtlab/workspace/tasks.md" ] || \
  cp -v "$KIT/templates/tasks.md"          "$HOME/dtlab/workspace/tasks.md"
[ -f "$HOME/dtlab/workspace/comparison.md" ] || \
  cp -v "$KIT/templates/comparison.md"     "$HOME/dtlab/workspace/comparison.md"
# quarantine root: human picks, verdicts, held persona files — the one
# tree every agent path is barred from (SOUL boundary + leakage scan)
mkdir -p "$HOME/dtlab/quarantine/human"
cp -v "$KIT/templates/human_picks.csv" \
      "$HOME/dtlab/quarantine/human/human_picks.TEMPLATE.csv"
find "$HOME/dtlab/tools" -name '*.sh' -exec chmod +x {} +

echo "== [2/5] Commands (local) =="
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/dtlab-start" <<'EOF'
#!/usr/bin/env bash
exec bash "$HOME/dtlab/tools/student_start.sh"
EOF
cat > "$HOME/.local/bin/dtlab-record" <<'EOF'
#!/usr/bin/env bash
echo "=============================================================="
echo " RECORDING HYGIENE: log into amazon.in BEFORE starting this"
echo " recording. NEVER type passwords, OTPs, or API keys while the"
echo " recorder runs — everything on screen ends up in the video."
echo "=============================================================="
read -rp "Logged in already, nothing sensitive on screen? [y/N] " OKGO
case "$OKGO" in [yY]*) ;; *) echo "Aborted — log in first."; exit 1 ;; esac
OUT="$HOME/dtlab/evidence/run_$(date +%Y%m%d_%H%M%S).mkv"
echo "Recording desktop :1 to $OUT — Ctrl+C here to stop."
ffmpeg -f x11grab -framerate 12 -i "${DISPLAY:-:1}" -c:v libx264 \
       -preset veryfast -pix_fmt yuv420p "$OUT"
EOF
cat > "$HOME/.local/bin/dtlab-pack" <<'EOF'
#!/usr/bin/env bash
exec python3 "$HOME/dtlab/tools/pack_evidence.py" "$@"
EOF
cat > "$HOME/.local/bin/dtlab-shop" <<'EOF'
#!/usr/bin/env bash
exec python3 "$HOME/dtlab/tools/log_human_session.py" "$@"
EOF
cat > "$HOME/.local/bin/dtlab-cart" <<'EOF'
#!/usr/bin/env bash
# Run by the PARTNER after each agent run: cart screenshot + parsed cart
# contents (cross-checked against the agent's picks at pack time).
exec python3 "$HOME/dtlab/tools/capture_cart.py" "$@"
EOF
cat > "$HOME/.local/bin/dtlab-tokens" <<'EOF'
#!/usr/bin/env bash
# Token + cost accounting for a run (T-21 item 12). Run it after each
# agent session, alongside dtlab-cart. Defaults to the newest run.
exec python3 "$HOME/dtlab/tools/capture_tokens.py" "$@"
EOF
cat > "$HOME/.local/bin/dtlab-verdict" <<'EOF'
#!/usr/bin/env bash
# Guided verdict/rating/rationale capture after each day's runs.
exec python3 "$HOME/dtlab/tools/capture_verdicts.py" "$@"
EOF
cat > "$HOME/.local/bin/dtlab-results" <<'EOF'
#!/usr/bin/env bash
# Show the student where every file from every run actually lives, and
# put ~/dtlab in the VS Code file explorer.
#
# ~/dtlab sits OUTSIDE the repo folder on purpose, which is also why it
# never appears in the explorer by default. Adding it as a second
# workspace root is an EDITOR setting only: it copies nothing, moves
# nothing, and creates no new path. The agent's quarantine boundary is
# enforced by filesystem path in every SOUL and re-checked at pack time,
# so what the student can see here has no effect on what the agent can
# read.
set -euo pipefail
D="$HOME/dtlab"
SID=$(sed -n 's/^participant_id,//p' "$D/workspace/persona_survey.csv" 2>/dev/null | head -1)
SID=${SID:-DT2026-XXX}

echo ""
echo "YOUR LAB FILES  ($D)"
echo ""
found=0
for r in "$D"/runs/run[0-9]*; do
  [ -d "$r" ] || continue
  found=1
  n=$(basename "$r")
  printf '  %s  %s, history=%s, %s\n' "$n" \
    "$(cat "$r/condition.txt" 2>/dev/null || echo '?')" \
    "$(cat "$r/history.txt"   2>/dev/null || echo '?')" \
    "$(cat "$r/tier.txt"      2>/dev/null || echo '?')"
  printf '     what the agent decided   %s/decision_log.md\n' "$r"
  printf '     what it put in the cart  %s/agent_picks.csv\n' "$r"
  printf '     full terminal history    %s/hermes_home/\n' "$r"
done
[ "$found" = 1 ] || echo "  (no agent runs yet - run dtlab-start)"

if [ -f "$D/workspace/decision_log.md" ]; then
  echo ""
  echo "  Your most recent run is still in progress or not yet filed:"
  printf '     %s/workspace/decision_log.md\n' "$D"
  echo "     It moves into the run folder when you start the next run."
fi

if [ -d "$D/runs_history" ] && [ -n "$(ls -A "$D/runs_history" 2>/dev/null)" ]; then
  echo ""
  echo "  Runs you redid (kept, never deleted)"
  printf '     %s/runs_history/\n' "$D"
fi

echo ""
echo "  Your own shopping session"
printf '     your picks               %s/quarantine/human/human_picks.csv\n' "$D"
printf '     full session log         %s/quarantine/human/human_session.jsonl\n' "$D"
echo ""
echo "  Your blind ratings"
printf '     %s/quarantine/verdicts/verdicts.csv\n' "$D"
echo ""
echo "  Screenshots and recordings"
printf '     %s/evidence/\n' "$D"
echo ""
echo "  Your submission zip (after dtlab-pack)"
printf '     %s/%s_evidence.zip\n' "$D" "$SID"
echo ""
echo "Read any of them from the terminal, e.g.:"
echo "  cat ~/dtlab/runs/run1/decision_log.md"
echo ""
if command -v code >/dev/null 2>&1; then
  echo "Adding $D to the file explorer..."
  if code --add "$D" >/dev/null 2>&1; then
    echo "Done - look for a 'dtlab' folder in the explorer on the left."
  else
    echo "Could not add it automatically. In VS Code use"
    echo "File > Add Folder to Workspace... and enter:  $D"
  fi
else
  echo "To browse these in VS Code: File > Add Folder to Workspace..."
  echo "then enter:  $D"
fi
EOF
cat > "$HOME/.local/bin/dtlab-runs" <<'EOF'
#!/usr/bin/env bash
# Show every agent run on this codespace: the four live slots, plus
# every attempt that a redo superseded. Nothing here is ever deleted.
set -euo pipefail
RUNSDIR="$HOME/dtlab/runs"
HISTDIR="$HOME/dtlab/runs_history"
echo "CURRENT RUNS  ($RUNSDIR)"
found=0
for d in "$RUNSDIR"/run[0-9]*; do
  [ -d "$d" ] || continue
  found=1
  printf '  %-6s %-10s history=%-4s %-9s started %s\n' \
    "$(basename "$d")" \
    "$(cat "$d/condition.txt" 2>/dev/null || echo '?')" \
    "$(cat "$d/history.txt"   2>/dev/null || echo '?')" \
    "$(cat "$d/tier.txt"      2>/dev/null || echo '?')" \
    "$(cat "$d/started_at.txt" 2>/dev/null || echo 'not started')"
done
[ "$found" = 1 ] || echo "  (none yet — run dtlab-start)"
echo ""
echo "SUPERSEDED RUNS  ($HISTDIR)"
if [ -d "$HISTDIR" ] && [ -n "$(ls -A "$HISTDIR" 2>/dev/null)" ]; then
  for d in "$HISTDIR"/run*_attempt*; do
    [ -d "$d" ] || continue
    printf '  %-34s %-10s history=%-4s %s\n' \
      "$(basename "$d")" \
      "$(cat "$d/condition.txt" 2>/dev/null || echo '?')" \
      "$(cat "$d/history.txt"   2>/dev/null || echo '?')" \
      "$(cat "$d/tier.txt"      2>/dev/null || echo '?')"
  done
  echo ""
  echo "  Full table: $HISTDIR/HISTORY.md"
else
  echo "  (none — you have not redone a run yet)"
fi
EOF
cat > "$HOME/.local/bin/dtlab-persona" <<'EOF'
#!/usr/bin/env bash
# Manual grounding switch, announced live in class before each run —
# NOT the counterbalanced order file. When set, dtlab-start uses this
# switch directly as the run's condition instead of computing one from
# the counterbalance sheet. The model tier (economy/frontier) is
# UNAFFECTED — this only ever touches grounding.
set -euo pipefail
SW="$HOME/dtlab/persona_switch.txt"
case "${1:-status}" in
  on)  echo persona > "$SW"; echo "Grounding switch: ON (persona) — next run uses your persona." ;;
  off) echo ablated > "$SW"; echo "Grounding switch: OFF (ablated) — next run has no persona." ;;
  clear) rm -f "$SW"; echo "Switch cleared — dtlab-start falls back to the counterbalance sheet." ;;
  status)
    if [ -f "$SW" ]; then echo "Grounding switch: $(cat "$SW") (set — overrides the counterbalance sheet)"
    else echo "Grounding switch: not set (dtlab-start uses the counterbalance sheet as normal)"
    fi ;;
  *) echo "usage: dtlab-persona on|off|clear|status" >&2; exit 1 ;;
esac
EOF
cat > "$HOME/.local/bin/dtlab-update" <<'EOF'
#!/usr/bin/env bash
# Pull course fixes into an ALREADY-RUNNING codespace.
#
# Two things have to happen and only the first is obvious. "Use this
# template" copies have NO git link back to the course repo, so an
# upstream remote is added on first use. And ~/dtlab (the SOULs, config
# and dtlab-* commands the lab actually reads) is provisioned ONCE when
# the codespace is created — so after merging we re-run setup.sh, or the
# new files sit in the repo and never reach the runtime.
#
# Your own data is untouched: runs/, quarantine/, the persona files and
# the frozen purchase profile are never rewritten by setup.sh.
set -euo pipefail
UPSTREAM="https://github.com/dringel/DTShopAgent.git"
KIT=$(ls -d /workspaces/*/.devcontainer 2>/dev/null | head -1 | xargs -r dirname)
if [ -z "$KIT" ] || [ ! -d "$KIT/.git" ]; then
  echo "Could not find the lab repo under /workspaces — tell a TA." >&2
  exit 1
fi
cd "$KIT"
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "You have uncommitted edits in $KIT."
  echo "The lab never asks you to edit repo files — if you did not do this"
  echo "deliberately, tell a TA rather than continuing."
  exit 1
fi
git remote get-url upstream >/dev/null 2>&1 || git remote add upstream "$UPSTREAM"
echo "Fetching course updates..."
git fetch --quiet upstream
if git merge --ff-only upstream/main 2>/dev/null; then
  echo "Repo updated (fast-forward)."
else
  # "Use this template" copies start from a fresh initial commit and
  # share NO history with the course repo, so a merge is impossible by
  # construction. Take upstream's files instead — the lab never asks a
  # student to edit repo files, so there is nothing of theirs to lose.
  echo "No shared history (template copy) — taking the course files."
  git checkout upstream/main -- . || {
    echo "Could not apply the course files — tell a TA." >&2; exit 1; }
  # checkout writes the files AND stages them, which would trip the
  # dirty-tree guard above on the NEXT run — the update would lock
  # itself out after succeeding once. Commit so the tree ends clean.
  git -c user.email=lab@dtlab -c user.name="DT Lab" \
      commit -qm "course update" >/dev/null 2>&1 || true
  echo "Repo files updated."
fi
echo "Re-provisioning ~/dtlab ..."
bash "$KIT/.devcontainer/setup.sh" >/dev/null
echo "Done. Your runs, personas and shopping session were not touched."
EOF
cat > "$HOME/.local/bin/dtlab-history" <<'EOF'
#!/usr/bin/env bash
# Manual purchase-history switch, announced live in class like
# dtlab-persona. OFF removes the frozen purchase_profile.md from the
# workspace for that run (the agent gets the questionnaire only). The
# questionnaire factor and the model tier are UNAFFECTED. Both factors
# off at once is refused by dtlab-start — that leaves no grounding.
set -euo pipefail
SW="$HOME/dtlab/history_switch.txt"
case "${1:-status}" in
  on)  echo on  > "$SW"; echo "History switch: ON — next run reads your purchase profile." ;;
  off) echo off > "$SW"; echo "History switch: OFF — next run has no purchase history (questionnaire only)." ;;
  clear) rm -f "$SW"; echo "Switch cleared — history defaults to ON." ;;
  status)
    if [ -f "$SW" ]; then echo "History switch: $(cat "$SW") (set)"
    else echo "History switch: not set (defaults to ON — purchase profile is read)"
    fi ;;
  *) echo "usage: dtlab-history on|off|clear|status" >&2; exit 1 ;;
esac
EOF
cat > "$HOME/.local/bin/dtlab-tier" <<'EOF'
#!/usr/bin/env bash
# Manual model-tier switch, same mechanism as dtlab-persona: announced
# live in class, overrides the counterbalance sheet for students who
# don't have a row yet. Only takes effect for a day that hasn't already
# resolved a tier (existing tier_dayN.txt always wins).
set -euo pipefail
SW="$HOME/dtlab/tier_switch.txt"
case "${1:-status}" in
  economy|frontier) echo "$1" > "$SW"; echo "Tier switch: $1 — next unresolved day uses this tier." ;;
  clear) rm -f "$SW"; echo "Switch cleared — dtlab-start falls back to the counterbalance sheet." ;;
  status)
    if [ -f "$SW" ]; then echo "Tier switch: $(cat "$SW") (set — overrides the counterbalance sheet)"
    else echo "Tier switch: not set (dtlab-start uses the counterbalance sheet as normal)"
    fi ;;
  *) echo "usage: dtlab-tier economy|frontier|clear|status" >&2; exit 1 ;;
esac
EOF
chmod +x "$HOME/.local/bin/"dtlab-*
grep -q 'dtlab PATH' "$HOME/.bashrc" || cat >> "$HOME/.bashrc" <<'EOF'
# dtlab PATH
export PATH="$HOME/.local/bin:$PATH"
export DISPLAY="${DISPLAY:-:1}"
alias chromium-browser=chromium
EOF

if [ "$PHASE" = "onCreate" ]; then
  if [ "${DTLAB_TEST:-0}" = "1" ]; then
    echo "== [3/5] DTLAB_TEST=1 — skipping network install steps (test build) =="
  else
    echo "== [3/5] Packages (network) =="
    if [ -z "$PLAYWRIGHT_PIN" ] && [ "${DTLAB_ALLOW_UNPINNED:-0}" != "1" ]; then
      echo "ERROR: PLAYWRIGHT_PIN is empty — a build must never silently"
      echo "install the latest playwright. Pin the exact version (e.g."
      echo "PLAYWRIGHT_PIN='==1.55.0'; TA_ONBOARDING.md > Updating"
      echo "installer pins), or export DTLAB_ALLOW_UNPINNED=1 for a"
      echo "throwaway test build."
      exit 1
    fi
    sudo apt-get update
    sudo apt-get install -y chromium ffmpeg jq unzip
    pip install --user "playwright$PLAYWRIGHT_PIN"
    python3 -m playwright install chromium
    # NOT `sudo python3 -m playwright ...`: root's python has no
    # playwright, so that form always failed silently. The user install
    # invokes sudo apt-get itself; apt chromium above already provides
    # the shared libraries either way.
    python3 -m playwright install-deps chromium || \
      echo "WARNING: playwright install-deps failed — the apt chromium's shared libraries cover the lab flows"

    echo "== [4/5] Hermes Agent (network) =="
    fetch_verified "$HERMES_INSTALLER_URL" "$HERMES_INSTALLER_SHA256" \
        /tmp/hermes-install.sh
    # --skip-setup and --non-interactive are REQUIRED here.
    #
    # The upstream installer finishes by running `hermes setup` — an arrow-key
    # TUI — and it reads that wizard from /dev/tty DIRECTLY, not from stdin
    # (installer: run_setup_wizard runs `... hermes_cli.main setup < /dev/tty`;
    # its six prompt_yes_no() calls fall back to /dev/tty the same way). A
    # container lifecycle hook HAS an openable /dev/tty, but nothing is
    # attached to the other end: the Codespaces creation-log panel is a log
    # stream, not a terminal. The wizard therefore renders, blocks on read,
    # and the build hangs with no way to answer it. Keystrokes typed into the
    # creation-log panel never reach the container.
    #
    # Before "simplifying" the line below, note what does NOT fix this:
    #   * `< /dev/null` — the wizard bypasses stdin entirely.
    #   * `curl ... | bash` — the installer's own `[ -t 0 ]` probe only
    #     decides WHICH terminal it reads from, never whether to prompt.
    #   * --skip-setup alone — the yes/no prompts (build tools, gateway
    #     service, WhatsApp pairing) can still block on /dev/tty.
    #
    # The wizard is redundant for this kit in any case: dtlab-start generates
    # each run's own $HERMES_HOME/config.yaml from
    # provisioning/hermes_config.template.yaml, and that per-run config is
    # authoritative for provider + model.
    hermes_rc=0
    timeout "$HERMES_INSTALL_TIMEOUT" bash /tmp/hermes-install.sh \
        "${HERMES_INSTALL_FLAGS[@]}" </dev/null || hermes_rc=$?
    if [ "$hermes_rc" -eq 0 ]; then
      rm -f /tmp/hermes-install.sh
    else
      if [ "$hermes_rc" -eq 124 ]; then
        echo "ERROR: the Hermes installer exceeded ${HERMES_INSTALL_TIMEOUT}s."
        echo "The usual cause is an interactive prompt blocking on /dev/tty in a"
        echo "non-interactive build. Confirm HERMES_INSTALL_FLAGS still match the"
        echo "pinned installer's --help output before raising the timeout."
      else
        echo "ERROR: the Hermes installer failed (exit $hermes_rc)."
      fi
      exit 1
    fi

    # The Anthropic provider SDK is NOT installed by the Hermes installer
    # when --skip-setup is passed: the interactive wizard is where a
    # provider is chosen and its package pulled in. Skipping that wizard is
    # mandatory here (it deadlocks a lifecycle hook, see above), so the
    # provider package must be installed explicitly -- otherwise Hermes
    # starts, connects, and only then dies with "Failed to initialize
    # agent: The 'anthropic' package is required for the Anthropic
    # provider." Anthropic is the only provider this course uses.
    #
    # The venv is built by uv and has neither pip nor ensurepip, so uv is
    # the only way in. Both paths are derived, not hard-coded: the launcher
    # wrapper names its own interpreter, and uv ships inside the Hermes
    # tree at ~/.hermes/bin/uv.
    # 0.122.0 is the exact SDK present for the successful 18 Aug live
    # bootstrap. Do not float across the SDK's 1.x migration at freeze.
    HERMES_PY="$(sed -n 's|^exec "\([^"]*python\)".*|\1|p' \
                 "$HOME/.local/bin/hermes" 2>/dev/null | head -1)"
    HERMES_UV="$HOME/.hermes/bin/uv"
    [ -x "$HERMES_UV" ] || HERMES_UV="$(command -v uv || true)"
    if [ -n "$HERMES_PY" ] && [ -x "$HERMES_PY" ] && [ -n "$HERMES_UV" ]; then
      "$HERMES_UV" pip install --python "$HERMES_PY" "anthropic$ANTHROPIC_PIN"
      if "$HERMES_PY" -c "import anthropic" 2>/dev/null; then
        echo "anthropic SDK present in the Hermes venv"
      else
        echo "ERROR: the Anthropic provider SDK did not install into the"
        echo "Hermes venv ($HERMES_PY). Hermes would start but fail to"
        echo "initialize the agent. Tell a TA."
        exit 1
      fi
    else
      echo "ERROR: could not locate the Hermes interpreter or uv."
      echo "  interpreter: ${HERMES_PY:-<not found>}"
      echo "  uv:          ${HERMES_UV:-<not found>}"
      echo "Hermes cannot use the Anthropic provider without its SDK."
      exit 1
    fi
  fi
  echo "onCreate phase done (layout + installs). Per-codespace steps run"
  echo "at creation via postCreateCommand."
  exit 0
fi

echo "== [3/5] Kit version stamp (per-codespace reproducibility metadata) =="
printf 'commit=%s built=%s route=codespaces image=%s\n' \
  "$(git -C "$KIT" rev-parse --short HEAD 2>/dev/null || echo unknown)" \
  "$(date -u +%Y-%m-%dT%H:%MZ)" \
  "mcr.microsoft.com/devcontainers/python@sha256:7876580d (tag 1-3.12-bookworm at pin time)" \
  > "$HOME/dtlab/kit_version.txt"

echo "== [4/5] Desktop password (per-codespace, replaces the shipped default) =="
# The desktop-lite feature bakes a fixed password at build time; rotate it
# to a per-codespace random one so a leaked port is not an open door.
#
# The previous approach sed-ed the shipped init script and assumed x11vnc
# would pick the change up. It did not: the dry run found every codespace
# still running the shipped default. The authoritative secret is whatever
# the RUNNING x11vnc reads, so detect that at runtime instead of guessing
# desktop-lite's internals, and verify before announcing anything.
NEWPW="$(tr -dc 'a-z0-9' < /dev/urandom | head -c 14 || true)"
ROTATED=0
ROTATE_NOTE=""
if [ -n "$NEWPW" ] && [ "${DTLAB_TEST:-0}" != "1" ]; then
  # 1. update the shipped init scripts too, so a container restart does
  #    not quietly revert to the default
  for f in /usr/local/share/desktop-init.sh /usr/local/etc/desktop-init.sh; do
    if [ -f "$f" ] && sudo grep -q 'dtlab' "$f"; then
      sudo sed -i "/passw/s/dtlab/$NEWPW/g" "$f"
    fi
  done

  # 2. the store that actually matters: parse it off the live process
  VNC_CMD="$(pgrep -a x11vnc 2>/dev/null | head -1 || true)"
  RFBAUTH="$(printf '%s' "$VNC_CMD" \
             | sed -n 's/.*-rfbauth[= ]\([^ ]*\).*/\1/p')"
  if [ -z "$RFBAUTH" ]; then
    RFBAUTH="$(printf '%s' "$VNC_CMD" \
               | sed -n 's/.*-passwdfile[= ]\([^ ]*\).*/\1/p')"
  fi
  if [ -n "$RFBAUTH" ] && command -v x11vnc >/dev/null 2>&1 \
     && sudo x11vnc -storepasswd "$NEWPW" "$RFBAUTH" >/dev/null 2>&1; then
    ROTATED=1
    ROTATE_NOTE="rfbauth store: $RFBAUTH"
  fi

  # 3. x11vnc may not be up yet during onCreate — try the usual stores
  if [ "$ROTATED" != "1" ] && command -v x11vnc >/dev/null 2>&1; then
    for cand in "$HOME/.vnc/passwd" /usr/local/etc/vnc_passwd \
                /root/.vnc/passwd; do
      if [ -e "$cand" ] \
         && sudo x11vnc -storepasswd "$NEWPW" "$cand" >/dev/null 2>&1; then
        ROTATED=1
        ROTATE_NOTE="rfbauth store: $cand"
        break
      fi
    done
  fi

  # 4. restart so the new secret is read
  if [ "$ROTATED" = "1" ]; then
    sudo pkill x11vnc 2>/dev/null || true
  fi
fi
rm -f "$HOME/dtlab/.desktop_password_unrotated"
if [ "$ROTATED" = "1" ]; then
  echo "*** Your personal Lab Desktop password (write it down): $NEWPW ***"
  echo "    ($ROTATE_NOTE)"
else
  # Deliberately NOT a build failure: bricking the environment for 161
  # students is worse than a shared password on a port that is private
  # by default. But it must not be forgettable either, so leave a marker
  # the pre-flight re-warns about on every single run.
  touch "$HOME/dtlab/.desktop_password_unrotated" 2>/dev/null || true
  echo ""
  echo "!!! ============================================================"
  echo "!!! DESKTOP PASSWORD NOT ROTATED — the shipped default 'dtlab'"
  echo "!!! is in effect. Every environment built this way shares it."
  echo "!!! The forwarded port is private, which is what is protecting"
  echo "!!! you; the password is NOT. Keep port 6080 private, and tell"
  echo "!!! a TA that rotation failed on this build."
  echo "!!! ============================================================"
  echo ""
fi

echo ""
echo "*** NEVER set the forwarded port 6080 to Public. A public port gives"
echo "*** anyone with the URL a desktop logged into YOUR Amazon account."

echo "== [5/5] Done =="
echo ""
echo "Setup complete. Open the 'Lab Desktop' forwarded port (6080) in your"
echo "browser — password printed above (or 'dtlab' if rotation failed)."
echo "KEEP THE PORT PRIVATE. Then use the VS Code terminal for:"
echo "  dtlab-shop | dtlab-start | dtlab-cart | dtlab-tokens |"
echo "  dtlab-verdict | dtlab-runs | dtlab-results (find your files) |"
echo "  dtlab-record (optional) | dtlab-pack"
