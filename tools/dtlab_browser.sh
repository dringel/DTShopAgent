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

# Chromium's namespace sandbox needs unprivileged user namespaces. The
# Codespaces container does not grant them, so Chromium aborts before it
# draws a window:
#   Failed to move to new namespace: ... errno = Operation not permitted
#   FATAL zygote_host_impl_linux.cc Check failed: Operation not permitted
# Probe once and degrade EXPLICITLY, rather than shipping the flag
# unconditionally.
#
# SECURITY NOTE — needs instructor sign-off. --no-sandbox removes
# Chromium's renderer sandbox. In this lab the browser is logged into a
# real amazon.in account and, during agent runs, follows links an LLM
# chose on the live web; the same container holds the student's Anthropic
# key in ~/.dtlab_env. The per-student, disposable container remains the
# isolation boundary. The flag is applied ONLY where the kernel refuses
# the namespace sandbox, so the VM route keeps its sandbox intact.
# --disable-dev-shm-usage is the companion fix for the small /dev/shm
# containers get; without it Chromium crashes on heavy pages.
#
# The probe mirrors the zygote's user+net unshare. It is a heuristic: a
# host that allows the probe but still refuses Chromium (or the reverse,
# e.g. Ubuntu 24.04's AppArmor userns restrictions on the VM route) would
# be misjudged. Erring toward --no-sandbox costs isolation; erring the
# other way costs a dead lab. Validate both routes at T-21.
SANDBOX_ARGS=()
if ! unshare --user --net true 2>/dev/null; then
  SANDBOX_ARGS=(--no-sandbox --disable-dev-shm-usage)
  echo "NOTICE: unprivileged user namespaces are unavailable in this" >&2
  echo "container, so Chromium starts WITHOUT its sandbox. Expected on" >&2
  echo "the Codespaces route; see the security note in $0." >&2
fi

mkdir -p "$PROFILE"
exec "$BIN" \
  --user-data-dir="$PROFILE" \
  "${SANDBOX_ARGS[@]}" \
  --remote-debugging-port="$PORT" \
  --load-extension="$EXTDIR" \
  --disable-extensions-except="$EXTDIR" \
  --no-first-run --no-default-browser-check \
  "$URL"
