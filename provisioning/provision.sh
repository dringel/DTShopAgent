#!/usr/bin/env bash
# provision.sh — Build the golden VM image for the Digital Twin lab
# (FALLBACK route; Codespaces via .devcontainer/ is primary, see
# COURSE_PLAN_1WEEK.md). Run ONCE by the instructor on a clean Ubuntu 24.04
# Desktop VM, then snapshot and export. Students never run this.
#
# After provisioning, a student only needs to:
#   1. Import the VM, log in (student / <course password>)
#   2. Paste their Claude API key when prompted by student_start.sh
#   3. Drop persona_survey.md (from make_persona.py) into ~/dtlab/workspace
#      (purchase_profile.md is written by the one-time bootstrap session
#      dtlab-start runs before run 1, then frozen)
#   4. Run: dtlab-shop, then dtlab-start
set -euo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"   # repo root = the dt-lab kit

# ---- pinned downloads -------------------------------------------------
# Every remote installer is downloaded to a file, checksum-verified, then
# executed. "UNPINNED" makes the build FAIL until the TA pins a release
# (procedure: TA_ONBOARDING.md > "Updating installer pins").
# TODO(dry-run): pin real versions + checksums at image-build time.
UV_INSTALLER_URL="https://astral.sh/uv/install.sh"
UV_INSTALLER_SHA256="UNPINNED"
HERMES_INSTALLER_URL="https://hermes-agent.nousresearch.com/install.sh"
HERMES_INSTALLER_SHA256="UNPINNED"
PLAYWRIGHT_PIN=""   # e.g. "==1.55.0"; empty = latest (pin at dry run)

# Flags passed to the Hermes installer. These are load-bearing, not
# cosmetic — see the "Hermes Agent" step below. Keep .devcontainer/setup.sh
# and provisioning/provision.sh in lockstep.
HERMES_INSTALL_FLAGS=(--skip-setup --non-interactive)
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

echo "== [1/7] System packages =="
# NO chromium-browser here: on Ubuntu 24.04 that package is a snap, and
# snap confinement can neither use the lab's --user-data-dir profile nor
# be driven via Playwright's executable_path. Both sessions (human and
# agent) use Playwright's bundled Chromium instead, exposed at the fixed
# path ~/dtlab/bin/chromium in step 2 (dtlab_browser.sh and
# log_human_session.py look there first).
sudo apt-get update
sudo apt-get install -y git curl python3 python3-pip python3-venv \
    ffmpeg jq unzip

echo "== [2/7] uv + Playwright (for the capture scripts) =="
if [ -z "$PLAYWRIGHT_PIN" ] && [ "${DTLAB_ALLOW_UNPINNED:-0}" != "1" ]; then
  echo "ERROR: PLAYWRIGHT_PIN is empty — a build must never silently"
  echo "install the latest playwright. Pin the exact version (e.g."
  echo "PLAYWRIGHT_PIN='==1.55.0'; TA_ONBOARDING.md), or export"
  echo "DTLAB_ALLOW_UNPINNED=1 for a throwaway test build."
  exit 1
fi
fetch_verified "$UV_INSTALLER_URL" "$UV_INSTALLER_SHA256" /tmp/uv-install.sh
sh /tmp/uv-install.sh && rm -f /tmp/uv-install.sh
export PATH="$HOME/.local/bin:$PATH"
uv venv --seed "$HOME/dtlab/.venv"        # --seed: venv WITH pip
"$HOME/dtlab/.venv/bin/pip" install "playwright$PLAYWRIGHT_PIN"
"$HOME/dtlab/.venv/bin/playwright" install chromium
"$HOME/dtlab/.venv/bin/playwright" install-deps chromium || true
# Fixed-path symlink to the bundled Chromium: the ONE binary both the
# human session and the agent session launch (validate on the golden
# image at the dry run).
PW_CHROME="$("$HOME/dtlab/.venv/bin/python" -c \
  'from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    print(p.chromium.executable_path)')"
mkdir -p "$HOME/dtlab/bin"
ln -sf "$PW_CHROME" "$HOME/dtlab/bin/chromium"

echo "== [3/7] Hermes Agent =="
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
# TODO(freeze): pin an exact anthropic version alongside the other
# installer pins; ">=0.39.0" is only Hermes' own stated floor.
HERMES_PY="$(sed -n 's|^exec "\([^"]*python\)".*|\1|p' \
             "$HOME/.local/bin/hermes" 2>/dev/null | head -1)"
HERMES_UV="$HOME/.hermes/bin/uv"
[ -x "$HERMES_UV" ] || HERMES_UV="$(command -v uv || true)"
if [ -n "$HERMES_PY" ] && [ -x "$HERMES_PY" ] && [ -n "$HERMES_UV" ]; then
  "$HERMES_UV" pip install --python "$HERMES_PY" "anthropic>=0.39.0"
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

echo "== [4/7] Lab directory layout =="
mkdir -p "$HOME/dtlab/workspace" "$HOME/dtlab/evidence" "$HOME/dtlab/tools"
cp -v "$KIT/agent/SOUL.md"                 "$HOME/dtlab/workspace/SOUL.md"
# kit-owned SOUL variants for the optional ablation factor (dtlab-start
# swaps the workspace SOUL.md per condition when the factor is enabled)
mkdir -p "$HOME/dtlab/soul"
cp -v "$KIT/agent/SOUL.md" "$KIT/agent/SOUL_ablated.md" \
      "$KIT/agent/SOUL_sandbox.md" "$KIT/agent/SOUL_bootstrap.md" \
      "$HOME/dtlab/soul/"
cp -v "$KIT/templates/comparison_ablation.md" \
      "$HOME/dtlab/comparison_ablation.TEMPLATE.md"
cp -v "$KIT/dtlab_config.env"              "$HOME/dtlab/dtlab_config.env"
cp -v "$KIT/tasks_config.csv"              "$HOME/dtlab/tasks_config.csv"
# per-run Hermes config template: dtlab-start generates each run's
# $HERMES_HOME/config.yaml from this (provider + pinned model per tier)
cp -v "$KIT/provisioning/hermes_config.template.yaml" \
      "$HOME/dtlab/hermes_config.template.yaml"
# counterbalance sheet (pseudonyms only): placed at the repo root by the
# instructor before the freeze (tools/make_counterbalance.py)
if [ -f "$KIT/counterbalance.csv" ]; then
  cp -v "$KIT/counterbalance.csv"          "$HOME/dtlab/counterbalance.csv"
elif [ "${DTLAB_ALLOW_NO_COUNTERBALANCE:-0}" = "1" ]; then
  echo "WARNING: counterbalance.csv absent (pre-freeze build)."
else
  echo "ERROR: counterbalance.csv missing at the repo root. Generate it"
  echo "from the final roster (tools/make_counterbalance.py) before the"
  echo "freeze, or export DTLAB_ALLOW_NO_COUNTERBALANCE=1."
  exit 1
fi
mkdir -p "$HOME/dtlab/assets"
cp -v "$KIT/assets/ringelai.png"           "$HOME/dtlab/assets/" 2>/dev/null || true
cp -v "$KIT/data-pipeline/"*.py            "$HOME/dtlab/tools/"
cp -v "$KIT/questionnaire/make_persona.py" "$HOME/dtlab/tools/"
cp -v "$KIT/provisioning/student_start.sh" "$HOME/dtlab/tools/"
cp -v "$KIT/tools/pack_evidence.py"        "$HOME/dtlab/tools/"
cp -v "$KIT/tools/log_human_session.py"    "$HOME/dtlab/tools/"
cp -v "$KIT/tools/capture_cart.py"         "$HOME/dtlab/tools/"
cp -v "$KIT/tools/capture_verdicts.py"     "$HOME/dtlab/tools/"
cp -v "$KIT/tools/dtlab_browser.sh"        "$HOME/dtlab/tools/"
# checkout-guard extension: kit code (never packed as evidence); the
# launcher loads it from here and dtlab-start's canary proves it's live
rm -rf "$HOME/dtlab/tools/checkout_guard_extension"
cp -rv "$KIT/tools/checkout_guard_extension" "$HOME/dtlab/tools/"
# Templates land in the workspace ONCE; students fill them in place, so a
# re-run must never clobber them.
[ -f "$HOME/dtlab/workspace/tasks.md" ] || \
  cp -v "$KIT/templates/tasks.md"          "$HOME/dtlab/workspace/tasks.md"
[ -f "$HOME/dtlab/workspace/comparison.md" ] || \
  cp -v "$KIT/templates/comparison.md"     "$HOME/dtlab/workspace/comparison.md"
# quarantine root: human picks, verdicts, held persona files — the one
# tree every agent path is barred from (SOUL boundary + leakage scan)
mkdir -p "$HOME/dtlab/quarantine/human"
cp -v "$KIT/templates/human_picks.csv" \
      "$HOME/dtlab/quarantine/human/human_picks.TEMPLATE.csv"  # manual fallback only
find "$HOME/dtlab/tools" -name '*.sh' -exec chmod +x {} +

echo "== [5/7] Kit version stamp (reproducibility metadata) =="
printf 'commit=%s built=%s route=vm\n' \
  "$(git -C "$KIT" rev-parse --short HEAD 2>/dev/null || echo unknown)" \
  "$(date -u +%Y-%m-%dT%H:%MZ)" > "$HOME/dtlab/kit_version.txt"

echo "== [6/7] Convenience commands =="
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/dtlab-start" <<'EOF'
#!/usr/bin/env bash
exec bash "$HOME/dtlab/tools/student_start.sh"
EOF
cat > "$HOME/.local/bin/dtlab-record" <<'EOF'
#!/usr/bin/env bash
# Screen-record the full desktop until Ctrl+C; saves to evidence folder.
echo "=============================================================="
echo " RECORDING HYGIENE: log into amazon.in BEFORE starting this"
echo " recording. NEVER type passwords, OTPs, or API keys while the"
echo " recorder runs — everything on screen ends up in the video."
echo "=============================================================="
read -rp "Logged in already, nothing sensitive on screen? [y/N] " OKGO
case "$OKGO" in [yY]*) ;; *) echo "Aborted — log in first."; exit 1 ;; esac
OUT="$HOME/dtlab/evidence/run_$(date +%Y%m%d_%H%M%S).mkv"
echo "Recording to $OUT — press Ctrl+C in this terminal to stop."
ffmpeg -f x11grab -framerate 12 -i "$DISPLAY" -c:v libx264 -preset veryfast \
       -pix_fmt yuv420p "$OUT"
EOF
cat > "$HOME/.local/bin/dtlab-pack" <<'EOF2'
#!/usr/bin/env bash
exec python3 "$HOME/dtlab/tools/pack_evidence.py" "$@"
EOF2
cat > "$HOME/.local/bin/dtlab-shop" <<'EOF2'
#!/usr/bin/env bash
# Step that comes FIRST (all students are human-first): your own logged
# shopping session.
exec "$HOME/dtlab/.venv/bin/python" "$HOME/dtlab/tools/log_human_session.py" "$@"
EOF2
cat > "$HOME/.local/bin/dtlab-cart" <<'EOF2'
#!/usr/bin/env bash
# Run by the PARTNER after each agent run: cart screenshot + parsed cart
# contents (cross-checked against the agent's picks at pack time).
exec "$HOME/dtlab/.venv/bin/python" "$HOME/dtlab/tools/capture_cart.py" "$@"
EOF2
cat > "$HOME/.local/bin/dtlab-verdict" <<'EOF2'
#!/usr/bin/env bash
# Guided verdict/rating/rationale capture after each day's runs.
exec python3 "$HOME/dtlab/tools/capture_verdicts.py" "$@"
EOF2
chmod +x "$HOME/.local/bin/dtlab-start" "$HOME/.local/bin/dtlab-record" \
         "$HOME/.local/bin/dtlab-pack" "$HOME/.local/bin/dtlab-shop" \
         "$HOME/.local/bin/dtlab-cart" "$HOME/.local/bin/dtlab-verdict"

echo "== [7/7] Done =="
echo "Provider + model selection is PER-RUN: dtlab-start writes each run's"
echo "\$HERMES_HOME (condition SOUL + config.yaml with the pinned model) —"
echo "no interactive 'hermes setup' provider choice is needed. If the pinned"
echo "Hermes release requires a global ~/.hermes/config.yaml to exist, create"
echo "a minimal one at the dry run (TA_ONBOARDING.md > T-21 trial-run work"
echo "items #1). Enable browser automation in LOCAL browser mode. Leave the"
echo "API key BLANK everywhere — students insert their own via dtlab-start."
echo "Then: clear shell history, remove any test keys, snapshot, export .ova."
