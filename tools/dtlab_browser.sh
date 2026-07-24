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

# One binary for both sessions: prefer system chromium (log_human_session.py
# points Playwright at the same executable so profile versions never skew).
BIN=""
for c in chromium chromium-browser; do
  if command -v "$c" >/dev/null 2>&1; then BIN="$c"; break; fi
done
if [ -z "$BIN" ]; then
  echo "ERROR: no chromium/chromium-browser on PATH — provisioning incomplete." >&2
  exit 1
fi

mkdir -p "$PROFILE"
exec "$BIN" \
  --user-data-dir="$PROFILE" \
  --remote-debugging-port="$PORT" \
  --no-first-run --no-default-browser-check \
  "$URL"
