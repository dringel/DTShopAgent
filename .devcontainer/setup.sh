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
# executed. "UNPINNED" FAILS the build until the TA pins a release
# (procedure: TA_ONBOARDING.md > "Updating installer pins") — with
# Codespaces prebuilds enabled, all 161 students then share one frozen,
# pre-tested image. TODO(dry-run): pin real version + checksum.
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
      "$KIT/agent/SOUL_sandbox.md" "$HOME/dtlab/soul/"
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
fi
mkdir -p "$HOME/dtlab/assets"
cp -v "$KIT/assets/ringelai.png"           "$HOME/dtlab/assets/" 2>/dev/null || true
cp -v "$KIT/tools/log_human_session.py"    "$HOME/dtlab/tools/"
cp -v "$KIT/tools/capture_cart.py"         "$HOME/dtlab/tools/"
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
cat > "$HOME/.local/bin/dtlab-verdict" <<'EOF'
#!/usr/bin/env bash
# Guided verdict/rating/rationale capture after each day's runs.
exec python3 "$HOME/dtlab/tools/capture_verdicts.py" "$@"
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
    bash /tmp/hermes-install.sh && rm -f /tmp/hermes-install.sh
  fi
  echo "onCreate phase done (layout + installs). Per-codespace steps run"
  echo "at creation via postCreateCommand."
  exit 0
fi

echo "== [3/5] Kit version stamp (per-codespace reproducibility metadata) =="
printf 'commit=%s built=%s route=codespaces image=%s\n' \
  "$(git -C "$KIT" rev-parse --short HEAD 2>/dev/null || echo unknown)" \
  "$(date -u +%Y-%m-%dT%H:%MZ)" \
  "mcr.microsoft.com/devcontainers/python:1-3.12-bookworm" \
  > "$HOME/dtlab/kit_version.txt"

echo "== [4/5] Desktop password (per-codespace, replaces the shipped default) =="
# The desktop-lite feature bakes a fixed password at build time; rotate it
# to a per-codespace random one so a leaked/public port is not an open door.
NEWPW="$(tr -dc 'a-z0-9' < /dev/urandom | head -c 10 || true)"
ROTATED=0
if [ -n "$NEWPW" ] && [ "${DTLAB_TEST:-0}" != "1" ]; then
  for f in /usr/local/share/desktop-init.sh /usr/local/etc/desktop-init.sh; do
    if [ -f "$f" ] && sudo grep -q 'dtlab' "$f"; then
      sudo sed -i "/passw/s/dtlab/$NEWPW/g" "$f"
      # verify the edit actually landed before announcing the password
      # as fact (TODO(dry-run): confirm x11vnc restarts pick it up)
      if sudo grep -q "$NEWPW" "$f"; then
        ROTATED=1
      fi
    fi
  done
fi
if [ "$ROTATED" = "1" ]; then
  sudo pkill x11vnc 2>/dev/null || true   # supervisor restarts it with the new password
  echo "*** Your personal Lab Desktop password (write it down): $NEWPW ***"
else
  # TODO(dry-run): locate the desktop-lite password store in the built image
  # and make the rotation stick; until verified, the default applies.
  echo "WARNING: could not rotate the desktop password automatically —"
  echo "the shipped default 'dtlab' is in effect."
fi
echo ""
echo "*** NEVER set the forwarded port 6080 to Public. A public port gives"
echo "*** anyone with the URL a desktop logged into YOUR Amazon account."

echo "== [5/5] Done =="
echo ""
echo "Setup complete. Open the 'Lab Desktop' forwarded port (6080) in your"
echo "browser — password printed above (or 'dtlab' if rotation failed)."
echo "KEEP THE PORT PRIVATE. Then use the VS Code terminal for:"
echo "  dtlab-shop | dtlab-start | dtlab-cart | dtlab-verdict |"
echo "  dtlab-record (optional) | dtlab-pack"
