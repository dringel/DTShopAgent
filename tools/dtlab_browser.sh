#!/usr/bin/env bash
# dtlab_browser.sh — the ONE way a browser is launched in this lab.
#
# Both sessions (the student's own shopping via dtlab-shop, and the agent
# session started by dtlab-start) must use the SAME binary and the SAME
# persistent profile, so the agent inherits the human-warmed, logged-in
# session, and Hermes /browser connect can attach over CDP.
#
#   usage: dtlab_browser.sh [start-url]
#
# TODO(dry-run): verify the CDP flag/port against the Hermes version pinned
# for the course (see docs/CHANGELOG.md, instructor dry-run list).
set -euo pipefail

# shellcheck source=/dev/null
[ -f "$HOME/dtlab/dtlab_config.env" ] && . "$HOME/dtlab/dtlab_config.env"
PROFILE="$HOME/${DTLAB_BROWSER_PROFILE:-dtlab/browser-profile}"
PORT="${DTLAB_CDP_PORT:-9222}"
URL="${1:-https://www.amazon.in}"

# One binary for both sessions (log_human_session.py points Playwright at
# the same executable so profile versions never skew). The fixed-path
# ~/dtlab/bin/chromium (Playwright's bundled build, VM route) wins over
# system chromium; snap builds are never used (confinement breaks the
# shared profile and executable_path).
BIN=""
for c in "$HOME/dtlab/bin/chromium" chromium chromium-browser; do
  if command -v "$c" >/dev/null 2>&1; then BIN="$c"; break; fi
done
if [ -z "$BIN" ]; then
  echo "ERROR: no chromium/chromium-browser on PATH — provisioning incomplete." >&2
  exit 1
fi

# Checkout-guard extension: blocks every amazon.in checkout/Buy Now/
# one-click pipeline at the network layer (add-to-cart-only is enforced
# technically, not just by instruction). Lives next to this script in
# the kit tools dir on both routes; dtlab-start's canary gate proves it
# is live before any run.
EXTDIR="$(cd "$(dirname "$0")" && pwd)/checkout_guard_extension"

mkdir -p "$PROFILE"
exec "$BIN" \
  --user-data-dir="$PROFILE" \
  --remote-debugging-port="$PORT" \
  --load-extension="$EXTDIR" \
  --disable-extensions-except="$EXTDIR" \
  --no-first-run --no-default-browser-check \
  "$URL"
