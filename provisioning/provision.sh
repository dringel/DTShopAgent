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
#      (purchase_profile.md is written by the agent itself at Bootstrap)
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
bash /tmp/hermes-install.sh && rm -f /tmp/hermes-install.sh

echo "== [4/7] Lab directory layout =="
mkdir -p "$HOME/dtlab/workspace" "$HOME/dtlab/evidence" "$HOME/dtlab/tools"
cp -v "$KIT/agent/SOUL.md"                 "$HOME/dtlab/workspace/SOUL.md"
# kit-owned SOUL variants for the optional ablation factor (dtlab-start
# swaps the workspace SOUL.md per condition when the factor is enabled)
mkdir -p "$HOME/dtlab/soul"
cp -v "$KIT/agent/SOUL.md" "$KIT/agent/SOUL_ablated.md" \
      "$KIT/agent/SOUL_sandbox.md" "$HOME/dtlab/soul/"
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
echo "a minimal one at the dry run (TA_ONBOARDING.md > Instructor-only work"
echo "items #1). Enable browser automation in LOCAL browser mode. Leave the"
echo "API key BLANK everywhere — students insert their own via dtlab-start."
echo "Then: clear shell history, remove any test keys, snapshot, export .ova."
