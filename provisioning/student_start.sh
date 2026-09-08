#!/usr/bin/env bash
# student_start.sh — the ONLY command students need. Validates everything,
# collects the API key on first run, and walks through the session.
#
# Plan of record (COURSE_PLAN_1WEEK.md, research_protocol.md §1): with the
# questionnaire-ablation factor ON, every agent runs the task set FOUR
# times in a within-student 2x2 — grounding (persona|ablated) x model tier
# (runs 1-2 = day-1 tier, runs 3-4 = day-2 tier). BOTH the grounding order
# (per day) and the tier order (across days) come from the course
# counterbalance sheet, per student. All students are human-first.
#
# DTLAB_TEST=1     stop right before the browser/Hermes launch (used by
#                  tests/test_start_flow.sh; all state is already written).
# DTLAB_SANDBOX=1  sandbox mode: books.toscrape.com smoke test / flagged-
#                  account fallback — soft gates, sandbox SOUL, run is
#                  stamped for exclusion from the research dataset.
set -uo pipefail
WS="$HOME/dtlab/workspace"
# Shared constants (repo: dtlab_config.env, provisioned to ~/dtlab/).
# shellcheck source=/dev/null
[ -f "$HOME/dtlab/dtlab_config.env" ] && . "$HOME/dtlab/dtlab_config.env"
# Final item count of the course questionnaire (115 per
# questionnaire_instrument_source.md). Used for the completeness check only.
EXPECTED_ITEMS="${DTLAB_EXPECTED_ITEMS:-115}"
# Research-only items (PR02, PR08 — make_persona.py AGENT_HIDDEN_ITEMS):
# answered in the Form and kept in persona_survey.csv, but never rendered
# into the agent-visible persona_survey.md (they name upcoming purchases —
# direct answer leakage into the shopping tasks). The rendered count the
# gate below checks is therefore two lower than the instrument size;
# tests/test_instrument_lockstep.py enforces the lockstep.
AGENT_HIDDEN_COUNT=2
RENDERED_ITEMS=$(( EXPECTED_ITEMS - AGENT_HIDDEN_COUNT ))
# Questionnaire-ablation factor (research_protocol.md §1). 0: single agent
# run, unchanged legacy flow. 1 (plan of record): FOUR runs — the SAME
# tasks under persona vs ablated grounding on each of the two lab days;
# workspace state is ENFORCED per condition (in ablated runs the persona
# files are physically absent, and the agent gets the ablated SOUL).
PERSONA_FACTOR="${DTLAB_PERSONA_FACTOR:-0}"
# Legacy day-tier defaults: real runs resolve their tier from the
# counterbalance sheet (tier_day1/tier_day2, per student); these values
# remain only as the sandbox fallback and are parsed harmlessly for one
# release.
DAY1_TIER="${DTLAB_DAY1_TIER:-economy}"
DAY2_TIER="${DTLAB_DAY2_TIER:-frontier}"
SANDBOX="${DTLAB_SANDBOX:-0}"
RUNSDIR="$HOME/dtlab/runs"
# ---- quarantine root (D3): everything the agent must never see —
# human picks, verdicts, held persona files — lives under ONE root,
# ~/dtlab/quarantine/, which every SOUL bars by path. Migration shim:
# pre-C1 layouts moved once, silently idempotent.
QUAR="$HOME/dtlab/quarantine"
mkdir -p "$QUAR"
for _qd in human verdicts persona_hold; do
  if [ -d "$HOME/dtlab/$_qd" ] && [ ! -e "$QUAR/$_qd" ]; then
    mv "$HOME/dtlab/$_qd" "$QUAR/$_qd"
  fi
done
HOLD="$QUAR/persona_hold"
RUN=""; COND=""; TIER=""; FRESH_RUN=0; MODEL_ID=""; RUN_HOME=""
GREEN='\033[0;32m'; RED='\033[0;31m'; YEL='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  [ok]${NC} $1"; }
bad()  { echo -e "${RED}  [!!]${NC} $1"; FAIL=1; }
note() { echo -e "${YEL}  [..]${NC} $1"; }
FAIL=0

# The most likely lab-day fire: a leftover lab-browser window (usually the
# shopping session) still holds the shared profile lock, so the CDP launch
# silently no-ops into a tab of the old, CDP-less instance and Hermes
# /browser connect has nothing to attach to. Poll the CDP endpoint for ~5s
# after launching; fail LOUD with the one action that fixes it.
wait_cdp() {
  # Cold Chromium starts are SLOW. The 3 Sep dry run measured ~5.5s from
  # launch to the "DevTools listening" line on a cold cache, against the
  # fixed 5s (10 x 0.5s) budget this used to allow -- so every cold
  # Codespace lost the race by about half a second. The browser was
  # starting correctly and being abandoned just before it finished, and
  # the operator was then told to "close all browser windows" when none
  # were open. Poll up to 30s (the value proven live on 30 Aug), still
  # bounded, still fail-closed. DTLAB_CDP_WAIT_TRIES keeps the tests fast.
  local port="${DTLAB_CDP_PORT:-9222}" i
  local tries="${DTLAB_CDP_WAIT_TRIES:-60}"   # 60 x 0.5s = 30s
  for ((i = 1; i <= tries; i++)); do
    if curl -fsS "http://127.0.0.1:${port}/json/version" >/dev/null 2>&1; then
      if [ "$i" -gt 10 ]; then
        ok "browser automation port ready after ~$(( i / 2 ))s (cold start)"
      fi
      return 0
    fi
    sleep 0.5
  done
  echo ""
  echo -e "${RED}The lab browser did not come up with its automation (CDP)"
  echo -e "port within $(( tries / 2 ))s."
  echo -e "If a lab-browser window IS open, close ALL of them (including the"
  echo -e "shopping session) and re-run dtlab-start."
  echo -e "If none are open, the browser failed to start -- run this to see"
  echo -e "why:  DISPLAY=:1 bash ~/dtlab/tools/dtlab_browser.sh${NC}"
  return 1
}

# Checkout-guard canary: before any run, a scratch tab is driven to a
# checkout URL over CDP and MUST land on the guard extension's
# blocked.html. When the guard works this generates ZERO amazon.in
# traffic (declarativeNetRequest redirects the main frame before the
# network); if the guard were absent, the canary is one harmless GET —
# exactly the case that must go red before Hermes starts.
canary_checkout_guard() {
  local port="${DTLAB_CDP_PORT:-9222}"
  local canary="https://www.amazon.in/gp/buy/spc/handlers/display.html"
  local resp tid i blocked=1
  resp=$(curl -fsS -X PUT "http://127.0.0.1:${port}/json/new?${canary}" \
           2>/dev/null) \
    || resp=$(curl -fsS "http://127.0.0.1:${port}/json/new?${canary}" \
                2>/dev/null) \
    || resp=""
  tid=$(printf '%s' "$resp" | python3 -c '
import json, sys
try:
    print(json.load(sys.stdin).get("id", ""))
except Exception:
    pass' 2>/dev/null)
  [ -n "$tid" ] || return 1
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS "http://127.0.0.1:${port}/json/list" 2>/dev/null \
       | python3 -c '
import json, sys
try:
    tabs = json.load(sys.stdin)
except Exception:
    sys.exit(1)
for t in tabs:
    if t.get("id") == sys.argv[1]:
        u = t.get("url", "")
        sys.exit(0 if u.startswith("chrome-extension://")
                 and u.endswith("blocked.html") else 1)
sys.exit(1)' "$tid" 2>/dev/null; then
      blocked=0
      break
    fi
    sleep 0.5
  done
  curl -fsS "http://127.0.0.1:${port}/json/close/${tid}" >/dev/null 2>&1 \
    || true
  return $blocked
}

canary_gate() {
  if canary_checkout_guard; then
    ok "checkout guard active (canary blocked)"
    return 0
  fi
  echo ""
  echo -e "${RED}The checkout guard did NOT block the canary page — the"
  echo -e "add-to-cart-only guarantee is not enforceable right now."
  echo -e "Close ALL lab-browser windows and re-run dtlab-start; if this"
  echo -e "repeats, call a TA before any agent run.${NC}"
  return 1
}

# ---- per-run Hermes home (treatment delivery) ----
# Hermes loads SOUL.md ONLY from $HERMES_HOME/SOUL.md (never from the
# working directory) and selects its model via $HERMES_HOME/config.yaml.
# Each run therefore gets its own FRESH home carrying exactly two files:
# the condition's SOUL and a config generated from the kit template with
# the run's pinned model ID. Fresh home per run = no memory store and no
# session history crossing runs. The workspace SOUL.md copy stays for
# student inspection only; the home is the authoritative delivery.
sha256_file() {
  python3 -c 'import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"
}

resolve_model() {  # $1 = tier -> stdout: exact model id (rc 1 = unpinned)
  local m
  case "$1" in
    economy)  m="${DTLAB_MODEL_ECONOMY:-PIN-AT-DRYRUN}" ;;
    frontier) m="${DTLAB_MODEL_FRONTIER:-PIN-AT-DRYRUN}" ;;
    *)        m="PIN-AT-DRYRUN" ;;
  esac
  if [ -z "$m" ] || [ "$m" = "PIN-AT-DRYRUN" ]; then
    if [ "${DTLAB_TEST:-0}" = "1" ]; then m="test-model-$1"
    elif [ "${DTLAB_ALLOW_UNPINNED:-0}" = "1" ]; then m="UNPINNED-$1"
    else return 1; fi
  fi
  printf '%s\n' "$m"
}

pin_gate() {  # $1 = tier -> sets MODEL_ID, or exits 1 (fail closed)
  if ! MODEL_ID=$(resolve_model "$1"); then
    echo ""
    echo -e "${RED}ERROR: no pinned model ID for the '$1' tier —"
    echo -e "dtlab_config.env still reads PIN-AT-DRYRUN."
    echo -e "Pin DTLAB_MODEL_ECONOMY / DTLAB_MODEL_FRONTIER first"
    echo -e "(TA_ONBOARDING.md > T-21 trial-run work items), or export"
    echo -e "DTLAB_ALLOW_UNPINNED=1 for a throwaway test build.${NC}"
    exit 1
  fi
}

make_hermes_home() {  # $1 = home dir, $2 = SOUL variant file, $3 = model id
  local hh="$1" soul="$2" model="$3"
  local tpl="$HOME/dtlab/hermes_config.template.yaml"
  if [ ! -f "$tpl" ]; then
    echo -e "${RED}hermes_config.template.yaml missing from ~/dtlab/ —"
    echo -e "re-run provisioning, or tell a TA.${NC}"
    return 1
  fi
  mkdir -p "$hh"
  cp "$soul" "$hh/SOUL.md"
  sed -e "s|{{PROVIDER}}|${DTLAB_PROVIDER:-anthropic}|g" \
      -e "s|{{MODEL_ID}}|$model|g" "$tpl" > "$hh/config.yaml"
}

# Effective-config verification, FAIL CLOSED.
#
# Grepping the file we just wrote proves only that we wrote it. It cannot
# detect the failure this gate exists to catch: a config whose SCHEMA the
# pinned Hermes release does not understand. That happened at the 2026-08-18
# dry run -- the old template used `model.id`, Hermes v0.20.0 wants
# `model.default`, so Hermes reported "no model configured", fell back to its
# own default, and this check still returned green. Four runs would have
# executed on one model while the manifest claimed two tiers.
#
# So: keep the cheap written-file check (it catches a broken substitution),
# then ask Hermes what it ACTUALLY loaded from this home.
verify_hermes_config() {  # $1 = home dir, $2 = provider, $3 = model id
  grep -qF -- "$3" "$1/config.yaml" 2>/dev/null || return 1
  grep -qF -- "$2" "$1/config.yaml" 2>/dev/null || return 1

  local eff
  eff="$(HERMES_HOME="$1" hermes config get model.default 2>/dev/null \
         | tr -d '[:space:]')"
  if [ -z "$eff" ]; then
    # Could not ask Hermes (older release, or the subcommand moved). The
    # file check passed, so proceed -- but say so, because this is the
    # assurance the gate is meant to provide.
    echo -e "${YEL}  [..] could not read the effective model from Hermes;" \
            "relying on the generated file only${NC}"
    return 0
  fi
  case "$eff" in
    *"$3"*) return 0 ;;
    *)
      echo -e "${RED}  [!!] Hermes loaded model '$eff' but this run is" \
              "assigned '$3'.${NC}"
      echo -e "${RED}       The config schema in" \
              "hermes_config.template.yaml does not match the pinned" \
              "Hermes release.${NC}"
      return 1 ;;
  esac
}

config_mismatch_abort() {
  echo ""
  echo -e "${RED}The model configuration generated for this run does not"
  echo -e "match your assigned tier — tell a TA. Nothing was started and"
  echo -e "no run state was written.${NC}"
  exit 1
}

echo "=============================================="
if [ "$SANDBOX" = "1" ]; then
  echo " Digital Twin Lab — SANDBOX pre-flight"
else
  echo " Digital Twin Lab — pre-flight check"
fi
echo "=============================================="

# 1. Claude API key. Stored ONLY in ~/.dtlab_env (chmod 600), sourced from
#    .bashrc via one idempotent line. Never echoed, never in shell history,
#    never typed while the screen recorder could be running.
ENVFILE="$HOME/.dtlab_env"
# shellcheck source=/dev/null
[ -f "$ENVFILE" ] && . "$ENVFILE"
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo ""
  echo "  Your Claude API key (from YOUR OWN Anthropic account, created per"
  echo "  the setup checklist). Input is HIDDEN — nothing will appear as you"
  echo "  paste. Never paste this key anywhere else; your personal monthly"
  echo "  spend limit (set in the Console per the checklist) is your cap."
  read -rsp "  Key (sk-ant-...): " KEY; echo ""
  if [[ "$KEY" == sk-ant-* ]] && [ "${#KEY}" -ge 30 ]; then
    # minimal live check BEFORE storing: a typo'd or revoked key must
    # fail here, not mid-run on lab day
    CODE=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 \
      -H "x-api-key: $KEY" -H "anthropic-version: 2023-06-01" \
      "https://api.anthropic.com/v1/models" 2>/dev/null) || CODE=""
    case "$CODE" in
      2*) ok "key verified against the Claude API." ;;
      401|403)
        echo -e "${RED}The Claude API rejected this key (HTTP $CODE)."
        echo -e "Nothing was stored. Check the key in your Anthropic Console"
        echo -e "and re-run dtlab-start. If a bad key was stored earlier,"
        echo -e "reset it with:  rm ~/.dtlab_env${NC}"
        exit 1 ;;
      *)
        # FAIL CLOSED (audit 8.5): an unverifiable key is stored only on
        # an explicit, recorded TA override — never silently
        echo ""
        echo -e "${YEL}Could not verify the key against the Claude API"
        echo -e "(HTTP '${CODE:-none}') — check the codespace's network"
        echo -e "and retry. A TA can override: type OVERRIDE to store the"
        echo -e "key unverified (the override is recorded); anything else"
        echo -e "stores nothing.${NC}"
        read -rp "> " OV
        if [ "$OV" = "OVERRIDE" ]; then
          date -u +%FT%TZ > "$HOME/dtlab/.key_override"
          note "unverified key stored on TA override (recorded in the manifest)"
        else
          echo -e "${RED}Nothing stored — re-run dtlab-start when the"
          echo -e "network is back (or with a TA for the override).${NC}"
          exit 1
        fi ;;
    esac
    umask 077
    printf 'export ANTHROPIC_API_KEY=%q\n' "$KEY" > "$ENVFILE"
    chmod 600 "$ENVFILE"
    export ANTHROPIC_API_KEY="$KEY"
    # shellcheck disable=SC2016  # deliberately unexpanded: the line is
    # sourced by future shells, not this one
    grep -qs 'dtlab_env' "$HOME/.bashrc" || \
      echo '[ -f "$HOME/.dtlab_env" ] && . "$HOME/.dtlab_env"  # dtlab_env' \
        >> "$HOME/.bashrc"
    ok "API key stored (600-permission env file; your personal spend limit applies)."
  else
    # a malformed key must stop the flow HERE — never continue into the
    # run machinery on a bad credential
    echo -e "${RED}That does not look like a Claude API key (sk-ant-...)."
    echo -e "Nothing was stored — re-run dtlab-start and paste the key from"
    echo -e "your Anthropic Console. (Stored-key reset: rm ~/.dtlab_env)${NC}"
    exit 1
  fi
else
  ok "Claude API key present."
fi
# Spend-limit gate (audit 8.4): the README's claim is now a RECORDED
# one-time confirmation — the ack lands in the manifest at pack time.
SPENDACK="$HOME/dtlab/.spend_limit_ack"
if [ ! -f "$SPENDACK" ]; then
  read -rp "  Personal monthly spend limit (~\$20) set in your Anthropic Console? [y/N] " SL
  case "$SL" in
    [yY]*)
      date -u +%FT%TZ > "$SPENDACK"
      ok "spend-limit confirmation recorded (asked once)" ;;
    *)
      echo -e "${RED}Set it now (Anthropic Console > Billing > Limits;"
      echo -e "takes ~2 minutes — it caps what a runaway session could"
      echo -e "cost YOU), then re-run dtlab-start.${NC}"
      exit 1 ;;
  esac
fi

# ---- SANDBOX MODE: soft gates, sandbox SOUL, stamped for exclusion ----
if [ "$SANDBOX" = "1" ]; then
  if [ "$PERSONA_FACTOR" = "1" ] && [ -d "$RUNSDIR/run1" ]; then
    # mid-week flagged-account fallback: real runs already exist — stamp
    # ONLY the substituted run as sandbox so the earlier valid runs keep
    # counting at pack time (a global stamp would nuke the whole zip)
    SBRUN=""
    for i in 1 2 3 4; do
      if [ ! -d "$RUNSDIR/run$i" ]; then SBRUN=$i; break; fi
    done
    if [ -n "$SBRUN" ]; then
      # park any real-run artifacts still in the workspace before the
      # sandbox agent appends to them
      PREVR=$((SBRUN - 1))
      for f in decision_log.md agent_picks.csv; do
        if [ -f "$WS/$f" ] && [ ! -f "$RUNSDIR/run$PREVR/$f" ]; then
          mv "$WS/$f" "$RUNSDIR/run$PREVR/$f"
        fi
      done
      mkdir -p "$RUNSDIR/run$SBRUN"
      echo sandbox > "$RUNSDIR/run$SBRUN/sandbox.txt"
      note "sandbox stamped PER-RUN (run$SBRUN) — your earlier real runs stay valid research data"
    else
      echo sandbox > "$HOME/dtlab/sandbox.txt"
    fi
  else
    echo sandbox > "$HOME/dtlab/sandbox.txt"
  fi
  if [ -f "$HOME/dtlab/soul/SOUL_sandbox.md" ]; then
    cp "$HOME/dtlab/soul/SOUL_sandbox.md" "$WS/SOUL.md"
    ok "sandbox SOUL in the workspace (books.toscrape.com; Bootstrap skipped)"
  else
    bad "SOUL_sandbox.md missing from ~/dtlab/soul/ — re-run provisioning"
  fi
  if [ -f "$WS/persona_survey.md" ]; then
    note "persona present — the sandbox agent will use it (fallback mode)"
  else
    note "no persona in the workspace — fine for the smoke test"
  fi
  [ -f "$WS/tasks.md" ] \
    || note "no tasks.md — the sandbox SOUL runs its built-in smoke task"
  if [ "$FAIL" -ne 0 ]; then
    echo ""
    echo -e "${RED}Fix the [!!] items above, then re-run.${NC}"
    exit 1
  fi
  # per-run Hermes home for the sandbox session: a substituted mid-week
  # run uses its run slot's day tier; a pure practice run uses the day-1
  # (economy) tier — sandbox output is excluded from the dataset either
  # way, and the cheap tier keeps practice spend low
  if [ -n "${SBRUN:-}" ]; then
    RUN_HOME="$RUNSDIR/run$SBRUN/hermes_home"
    SBDAY=1; [ "$SBRUN" -ge 3 ] && SBDAY=2
    # substituted run: use the day's assigned tier when already resolved
    # (tier_dayN.txt); soft fallback to the legacy day default otherwise
    SBTIER="$(cat "$HOME/dtlab/tier_day$SBDAY.txt" 2>/dev/null || true)"
    case "$SBTIER" in
      economy|frontier) ;;
      *) if [ "$SBDAY" = "1" ]; then SBTIER="$DAY1_TIER"
         else SBTIER="$DAY2_TIER"; fi ;;
    esac
  else
    RUN_HOME="$RUNSDIR/sandbox_home"
    SBTIER="$DAY1_TIER"
  fi
  pin_gate "$SBTIER"
  make_hermes_home "$RUN_HOME" "$HOME/dtlab/soul/SOUL_sandbox.md" \
    "$MODEL_ID" || exit 1
  verify_hermes_config "$RUN_HOME" "${DTLAB_PROVIDER:-anthropic}" \
    "$MODEL_ID" || config_mismatch_abort
  echo ""
  echo -e "${YEL}SANDBOX RUN — practice store only (books.toscrape.com)."
  echo -e "This run is stamped for EXCLUSION from the research dataset.${NC}"
  read -rp "Press Enter to open the sandbox store and start Hermes... "
  # sandbox runs get their OWN marker: .run_started is reserved for the
  # first REAL run (pack_evidence.py keys the H_FIRST ordering check and
  # the Hermes-log collection window off it — a Tuesday practice run must
  # never predate Wednesday's human session in the manifest)
  [ -f "$HOME/dtlab/.sandbox_run_started" ] || \
    touch "$HOME/dtlab/.sandbox_run_started"
  [ "${DTLAB_TEST:-0}" = "1" ] && exit 0
  bash "$HOME/dtlab/tools/dtlab_browser.sh" "https://books.toscrape.com" \
    >/dev/null 2>&1 &
  wait_cdp || exit 1
  canary_gate || exit 1
  cd "$WS" && HERMES_HOME="$RUN_HOME" exec hermes
fi
# a stale sandbox marker must never leak into a real run's manifest
if [ -f "$HOME/dtlab/sandbox.txt" ]; then
  rm -f "$HOME/dtlab/sandbox.txt"
  # the workspace SOUL may still be the sandbox one; restore the standard
  # SOUL here — ablation runs below re-copy the per-condition SOUL anyway
  [ -f "$HOME/dtlab/soul/SOUL.md" ] && \
    cp "$HOME/dtlab/soul/SOUL.md" "$WS/SOUL.md"
  # the sandbox agent appends to decision_log.md / agent_picks.csv
  # (SOUL_sandbox protocol) — archive them so practice output never
  # contaminates real run 1's evidence
  SBA="$HOME/dtlab/sandbox_archive"
  STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  for f in decision_log.md agent_picks.csv; do
    if [ -f "$WS/$f" ]; then
      mkdir -p "$SBA"
      mv "$WS/$f" "$SBA/${STAMP}_$f"
      note "sandbox-era $f archived to ~/dtlab/sandbox_archive/"
    fi
  done
  note "stale sandbox marker removed (previous run was a sandbox run)"
fi

# Kit-commit check (audit 8.1): a frozen course pins the exact commit;
# a codespace restored from a stale prebuild must surface NOW, not as
# subtle mid-week drift.
if [ -n "${DTLAB_EXPECTED_COMMIT:-}" ]; then
  KITC=$(sed -n 's/^commit=\([0-9a-f]*\).*/\1/p' \
    "$HOME/dtlab/kit_version.txt" 2>/dev/null | head -1)
  if [ "$KITC" = "$DTLAB_EXPECTED_COMMIT" ]; then
    ok "kit commit matches the course freeze ($KITC)"
  else
    bad "this environment was built from commit '${KITC:-unknown}' but the course freeze expects '$DTLAB_EXPECTED_COMMIT' — stale prebuild; rebuild the container (tell a TA)"
  fi
else
  note "kit-commit check skipped (DTLAB_EXPECTED_COMMIT not set — pre-freeze build)"
fi

# 2. Required workspace files
if [ -f "$WS/SOUL.md" ]; then ok "SOUL.md (agent identity) present"
# Desktop password: setup leaves this marker when rotation failed, so the
# shared default is still in effect. Re-warn on EVERY run -- a one-time
# warning during a 20-minute build scrolls past and is never seen again.
if [ -f "$HOME/dtlab/.desktop_password_unrotated" ]; then
  echo -e "${YEL}  [..] desktop password was NOT rotated on this build --"
  echo -e "       the shared default is in effect. Keep port 6080 PRIVATE"
  echo -e "       and tell a TA.${NC}"
fi
else bad "SOUL.md missing from $WS"; fi
if [ -f "$WS/tasks.md" ] && ! grep -q "INSTRUCTOR_TASK" "$WS/tasks.md"; then
  ok "tasks.md present and filled"
else
  bad "tasks.md missing or still contains template placeholders"
fi
HU="$QUAR/human"
# The order-arm factor is retired: ALL students are human-first (picks
# committed Wednesday). arm.txt is still written for manifest backward
# compatibility, but there is nothing to choose.
echo "H_FIRST" > "$HOME/dtlab/arm.txt"
if [ -f "$HU/human_picks.csv" ] && [ -f "$HU/human_session.jsonl" ]; then
  ok "human-first respected: your own shopping is committed, agent goes second"
else
  bad "your OWN shopping session must happen first — run  dtlab-shop  before any agent run"
fi

# ---- ablation factor: which of the four runs is this? ----
BOOTSTRAP_RUN=0
if [ "$PERSONA_FACTOR" = "1" ]; then
  # ---- Phase 0 (D4): the purchase profile is written ONCE, before run
  # 1, by a dedicated questionnaire-blind bootstrap session, then
  # frozen. Two dtlab-start invocations by design: the first launches
  # the bootstrap agent; the second detects the written profile,
  # freezes it, and proceeds to run 1.
  if [ ! -f "$HOME/dtlab/.bootstrap_done" ]; then
    if [ -s "$WS/purchase_profile.md" ]; then
      # ---- PII scrub BEFORE the freeze/archive (instructor decision,
      # 18 Aug call): the bootstrap agent can pull real account-holder
      # details into both the profile and its decision log. Instructions
      # caused the leak; a deterministic filter removes it. Names are
      # prompted, passed to the scrubber on stdin, used in memory, and
      # never written or exposed in a process command line. Runs before
      # chmod 444 + hash and before the log is archived. Fail-closed: a
      # bootstrap artifact that cannot be scrubbed is never frozen.
      chmod 644 "$WS/purchase_profile.md" "$WS/decision_log.md" \
        2>/dev/null || true
      if [ -t 0 ]; then
        echo ""
        echo "PII scrub before the freeze: enter every name on this Amazon"
        echo "account (yours + anyone on saved addresses), comma-separated."
        echo "Used only to strip them from bootstrap outputs — never stored."
        read -rp "  Name(s): " SCRUB_NAMES
      elif [ "${DTLAB_TEST:-0}" = "1" ]; then
        # State-machine tests supply a synthetic name as the next line
        # of scripted stdin. Real noninteractive launches fail closed.
        IFS= read -r SCRUB_NAMES || SCRUB_NAMES=""
      else
        echo -e "${RED}PII scrub needs an interactive name list and this"
        echo -e "terminal has no input TTY. The profile was NOT frozen."
        echo -e "Re-run dtlab-start interactively or tell a TA.${NC}"
        exit 1
      fi
      if [[ ! "$SCRUB_NAMES" =~ [[:alnum:]] ]]; then
        echo -e "${RED}No account-holder name was supplied, so bootstrap"
        echo -e "artifacts cannot be checked safely. The profile was"
        echo -e "NOT frozen. Re-run dtlab-start and enter the names.${NC}"
        unset SCRUB_NAMES
        exit 1
      fi
      # pseudonym from the persona files (workspace, or quarantine hold —
      # during bootstrap the persona is held there by design); the main
      # SID resolution happens later in this script, too late for us
      SCRUB_SID=$(python3 - <<'PY'
import csv, sys
from pathlib import Path
home = Path.home()
for p in (home / "dtlab" / "workspace" / "persona_survey.csv",
          home / "dtlab" / "quarantine" / "persona_hold"
          / "persona_survey.csv"):
    try:
        with open(p, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if rows and (rows[0].get("student_id") or "").strip():
            print(rows[0]["student_id"].strip()); sys.exit(0)
    except OSError:
        pass
print("unknown")
PY
)
      if [[ ! "$SCRUB_SID" =~ ^DT[0-9]{4}-[0-9]{3}$ ]]; then
        echo -e "${RED}A valid participant pseudonym was not found in the"
        echo -e "persona CSV, so the profile cannot be attributed safely."
        echo -e "The profile was NOT frozen. Tell a TA.${NC}"
        unset SCRUB_NAMES SCRUB_SID
        exit 1
      fi
      # scrubber location: provisioned copy first, then the kit copy
      # relative to this script (covers a launcher run straight from the
      # repo before provisioning has staged ~/dtlab/tools)
      SCRUB_TOOL=""
      for c in "$HOME/dtlab/tools/scrub_profile.py" \
               "$(dirname "$0")/../tools/scrub_profile.py" \
               "$(dirname "$0")/scrub_profile.py"; do
        [ -f "$c" ] && SCRUB_TOOL="$c" && break
      done
      if [ -z "$SCRUB_TOOL" ]; then
        echo -e "${RED}scrub_profile.py not found — provisioning is"
        echo -e "incomplete and the profile cannot be PII-scrubbed."
        echo -e "The profile was NOT frozen. Tell a TA.${NC}"
        unset SCRUB_NAMES SCRUB_SID
        exit 1
      fi
      if ! printf '%s\n' "$SCRUB_NAMES" | python3 "$SCRUB_TOOL" \
             --profile "$WS/purchase_profile.md" \
             --text-file "$WS/decision_log.md" \
             --student-id "$SCRUB_SID" \
             --names-stdin; then
        echo -e "${RED}PII scrub failed — bootstrap outputs were NOT frozen."
        echo -e "Fix the profile (or re-run the bootstrap) and try"
        echo -e "dtlab-start again.${NC}"
        unset SCRUB_NAMES SCRUB_SID
        exit 1
      fi
      unset SCRUB_NAMES SCRUB_SID

      # ---- claim validation against the real order list ----
      # The SOUL requires every claim in the profile to be traceable to
      # an order the agent actually saw. When captured ground truth is
      # available, any validator failure is a hard freeze gate: writing
      # the hash or .bootstrap_done after a failed reconciliation would
      # make a known-bad profile immutable and feed it into every run.
      ORDERS_JSON="$QUAR/human/purchase_orders.json"
      VALIDATOR=""
      for c in "$HOME/dtlab/tools/validate_profile.py" \
               "$(dirname "$0")/../tools/validate_profile.py"; do
        [ -f "$c" ] && VALIDATOR="$c" && break
      done
      if [ -n "$VALIDATOR" ] && [ -f "$ORDERS_JSON" ]; then
        if ! python3 "$VALIDATOR" --profile "$WS/purchase_profile.md" \
               --orders "$ORDERS_JSON"; then
          echo -e "${RED}Profile validation failed — the profile was NOT"
          echo -e "frozen. Fix it or re-run the bootstrap, then try"
          echo -e "dtlab-start again.${NC}"
          exit 1
        fi
      elif [ -n "$VALIDATOR" ]; then
        echo -e "${YEL}  [..] no order ground truth at $ORDERS_JSON —"
        echo -e "       run  python3 ~/dtlab/tools/capture_orders.py"
        echo -e "       (lab browser open) to enable claim checking.${NC}"
      fi

      chmod 444 "$WS/purchase_profile.md" 2>/dev/null || true
      sha256_file "$WS/purchase_profile.md" \
        > "$HOME/dtlab/purchase_profile.sha256"
      touch "$HOME/dtlab/.bootstrap_done"
      # park the bootstrap session's log so run 1 starts clean (the
      # packer validates its PROTOCOL token from here)
      mkdir -p "$RUNSDIR/bootstrap"
      [ -f "$WS/decision_log.md" ] && \
        mv "$WS/decision_log.md" "$RUNSDIR/bootstrap/decision_log.md"
      ok "purchase profile frozen (read-only; hash recorded) — proceeding to run 1"
    else
      BOOTSTRAP_RUN=1
    fi
  fi
  # first run directory that does not exist yet = the next run
  if [ "$BOOTSTRAP_RUN" = "0" ]; then
    for i in 1 2 3 4; do
      if [ ! -d "$RUNSDIR/run$i" ]; then RUN=$i; break; fi
    done
  fi
  run_day()  { if [ "$1" -le 2 ]; then echo 1; else echo 2; fi; }
  # condition of run N under a given day order (first run of the day
  # follows the order; the second run of the day is the other condition)
  run_cond() {  # $1=run index, $2=P_FIRST|NP_FIRST
    local first=persona second=ablated
    if [ "$2" = "NP_FIRST" ]; then first=ablated; second=persona; fi
    case "$1" in 1|3) echo "$first" ;; *) echo "$second" ;; esac
  }
  prev_desc() {  # "economy, persona" from an existing run dir
    local d="$RUNSDIR/run$1" c t
    c=$(cat "$d/condition.txt" 2>/dev/null || echo "?")
    t=$(cat "$d/tier.txt" 2>/dev/null || echo "?")
    echo "$t, $c"
  }
  # a run dir WITHOUT started_at.txt was set up but never launched (a
  # gate was refused mid-flight) — resume it silently; asking "fully
  # finished? [y/N]" about it invites a wrong "y" that would record an
  # empty run forever
  never_started() {
    [ -d "$RUNSDIR/run$1" ] && [ ! -f "$RUNSDIR/run$1/started_at.txt" ]
  }
  archive_prev_of() {  # park the LAST STARTED run's workspace artifacts
    local prev=$(($1 - 1))
    [ "$prev" -ge 1 ] || return 0
    for f in decision_log.md agent_picks.csv; do
      if [ -f "$WS/$f" ] && [ ! -f "$RUNSDIR/run$prev/$f" ]; then
        mv "$WS/$f" "$RUNSDIR/run$prev/$f"
      fi
    done
  }
  if [ "$BOOTSTRAP_RUN" = "1" ]; then
    :   # Phase 0: no run to resume — the bootstrap session has no runN
  elif [ -z "$RUN" ]; then
    if never_started 4; then
      RUN=4
      note "run 4 was set up but never started — resuming it"
      archive_prev_of 4
    else
      read -rp "All four runs already started. Resume run 4 ($(prev_desc 4))? [y/N] " R4
      case "$R4" in
        [yY]*) RUN=4 ;;
        *) bad "all four agent runs are done — next steps: dtlab-verdict, then dtlab-pack"
           echo ""
           echo -e "${RED}Fix the [!!] items above, then run dtlab-start again.${NC}"
           exit 1 ;;
      esac
    fi
  elif [ "$RUN" -gt 1 ]; then
    PREV=$((RUN - 1))
    if never_started "$PREV"; then
      RUN=$PREV
      note "run $PREV was set up but never started — resuming it"
      archive_prev_of "$PREV"
    else
      read -rp "Agent run $PREV ($(prev_desc "$PREV")) fully finished (all tasks in the log + picks file)? [y/N] " PDONE
      case "$PDONE" in
        [yY]*)
          # archive the finished run so the next one starts with a clean
          # log — an ablated agent must never be able to read a
          # persona-citing decision log (and vice versa across tiers)
          for f in decision_log.md agent_picks.csv; do
            [ -f "$WS/$f" ] && mv "$WS/$f" "$RUNSDIR/run$PREV/$f"
          done ;;
        *) RUN=$PREV ;;   # crash-resume the previous run
      esac
    fi
  fi
  if [ "$BOOTSTRAP_RUN" = "1" ]; then
    DAY=1     # the bootstrap session runs on day 1's assigned tier
  else
    DAY=$(run_day "$RUN")
  fi
  # the kit-baked counterbalance sheet (same file as the LMS artifact,
  # pseudonyms only) is the authority for BOTH assignments — grounding
  # order per day and tier order across days; typed entry is the
  # fallback and is demoted to confirmation when the sheet has this
  # student. Pseudonym resolved once, used by both lookups.
  SID=$(python3 - <<'PY'
import csv
from pathlib import Path
home = Path.home()
for p in (home / "dtlab" / "workspace" / "persona_survey.csv",
          home / "dtlab" / "quarantine" / "persona_hold"
          / "persona_survey.csv"):
    try:
        with open(p, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if rows and (rows[0].get("student_id") or "").strip():
            print(rows[0]["student_id"].strip())
            break
    except OSError:
        pass
PY
)
  CBFILE="$HOME/dtlab/counterbalance.csv"
  cb_lookup() {  # $1 = column name -> this student's value, or ""
    [ -n "$SID" ] && [ -f "$CBFILE" ] || return 0
    python3 - "$CBFILE" "$SID" "$1" <<'PY'
import csv
import sys
with open(sys.argv[1], newline="", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if (r.get("student_id") or "").strip() == sys.argv[2]:
            print((r.get(sys.argv[3]) or "").strip())
            break
PY
  }
  # Manual grounding switch (dtlab-persona), announced live in class
  # before each run. When set, it REPLACES the counterbalance-sheet
  # order entirely -- including the prompt below, which would otherwise
  # ask a student for a P_FIRST/NP_FIRST value that no longer exists for
  # them. Tier is NEVER touched by this switch, only grounding.
  SWITCHFILE="$HOME/dtlab/persona_switch.txt"
  SWITCH_ACTIVE=0
  if [ "$BOOTSTRAP_RUN" = "0" ] && [ -f "$SWITCHFILE" ]; then
    SWITCH_ACTIVE=1
    PORDER=$(cat "$SWITCHFILE")
    case "$PORDER" in
      persona|ablated) ;;
      *) bad "dtlab/persona_switch.txt has an invalid value ('$PORDER') — expected persona or ablated. Fix it or run: dtlab-persona clear"; exit 1 ;;
    esac
  fi
  ORDERFILE="$HOME/dtlab/persona_order_day$DAY.txt"
  if [ "$SWITCH_ACTIVE" = "0" ] && [ ! -f "$ORDERFILE" ] && [ "$BOOTSTRAP_RUN" = "0" ]; then
    ASSIGNED=$(cb_lookup "day${DAY}_order")
    if [ "$ASSIGNED" = "P_FIRST" ] || [ "$ASSIGNED" = "NP_FIRST" ]; then
      echo "  Your assigned DAY-$DAY grounding order (course counterbalance sheet): $ASSIGNED"
      read -rp "  Confirm [Y/n] " CONF
      case "$CONF" in
        [nN]*) echo -e "${RED}The sheet and the LMS carry the SAME assignment — tell a TA before overriding.${NC}"; exit 1 ;;
        *) echo "$ASSIGNED" > "$ORDERFILE" ;;
      esac
    else
      read -rp "Your assigned grounding order for DAY $DAY (from the LMS sheet) [P_FIRST/NP_FIRST]: " PO
      case "$PO" in
        P_FIRST|NP_FIRST) echo "$PO" > "$ORDERFILE" ;;
        *) echo -e "${RED}Enter exactly P_FIRST or NP_FIRST (check the LMS assignment sheet).${NC}"; exit 1 ;;
      esac
    fi
  fi
  [ "$SWITCH_ACTIVE" = "0" ] && [ "$BOOTSTRAP_RUN" = "0" ] && PORDER=$(cat "$ORDERFILE")
  # ---- model tier for this day: counterbalanced ACROSS DAYS per
  # student (tier_day1/tier_day2 on the sheet). The tier is assigned,
  # never guessed: no sheet row + no valid typed entry = fail closed.
  TIERFILE="$HOME/dtlab/tier_day$DAY.txt"
  # Manual tier switch (dtlab-tier), same mechanism and same reason as
  # the grounding switch above: announced live in class, overrides the
  # counterbalance sheet entirely for students who don't have a row yet.
  TIER_SWITCHFILE="$HOME/dtlab/tier_switch.txt"
  if [ ! -f "$TIERFILE" ] && [ -f "$TIER_SWITCHFILE" ]; then
    SW_TIER=$(cat "$TIER_SWITCHFILE")
    case "$SW_TIER" in
      economy|frontier) echo "$SW_TIER" > "$TIERFILE"
        note "tier switch active ($SW_TIER) — overriding the counterbalance order for this run" ;;
      *) bad "dtlab/tier_switch.txt has an invalid value ('$SW_TIER') — expected economy or frontier. Fix it or run: dtlab-tier clear"; exit 1 ;;
    esac
  fi
  if [ ! -f "$TIERFILE" ]; then
    ASSIGNED_TIER=$(cb_lookup "tier_day$DAY")
    if [ "$ASSIGNED_TIER" = "economy" ] || [ "$ASSIGNED_TIER" = "frontier" ]; then
      echo "  Your assigned DAY-$DAY model tier (course counterbalance sheet): $ASSIGNED_TIER"
      read -rp "  Confirm [Y/n] " TCONF
      case "$TCONF" in
        [nN]*) echo -e "${RED}The sheet and the LMS carry the SAME assignment — tell a TA before overriding.${NC}"; exit 1 ;;
        *) echo "$ASSIGNED_TIER" > "$TIERFILE" ;;
      esac
    else
      read -rp "Your assigned model tier for DAY $DAY (from the LMS sheet) [economy/frontier]: " TT
      case "$TT" in
        economy|frontier) echo "$TT" > "$TIERFILE" ;;
        *) echo -e "${RED}Enter exactly economy or frontier (check the LMS assignment sheet) — the tier is assigned per student, not guessable.${NC}"; exit 1 ;;
      esac
    fi
  fi
  TIER=$(cat "$TIERFILE")
  # model pinning gate: fail closed BEFORE any run state while the
  # tier's model ID is unpinned (sets MODEL_ID for the run's home)
  pin_gate "$TIER"
  mkdir -p "$HOLD"
  if [ "$BOOTSTRAP_RUN" = "1" ]; then
    # Phase 0 workspace: persona files held in quarantine REGARDLESS of
    # the grounding order — the profile is written questionnaire-blind
    for f in persona_survey.md persona_survey.csv persona_meta.json; do
      [ -f "$WS/$f" ] && mv "$WS/$f" "$HOLD/$f"
    done
    if [ -f "$HOME/dtlab/soul/SOUL_bootstrap.md" ]; then
      cp "$HOME/dtlab/soul/SOUL_bootstrap.md" "$WS/SOUL.md"
    else
      bad "SOUL_bootstrap.md missing from ~/dtlab/soul/ — re-run provisioning"
    fi
    echo ""
    echo -e "${YEL}BOOTSTRAP PHASE (one-time, before run 1): this session's"
    echo -e "agent reads your amazon.in order history and writes"
    echo -e "purchase_profile.md — questionnaire-blind (your persona files"
    echo -e "are held in quarantine), no shopping. The flow:"
    echo -e "  1. Hermes starts; the agent writes purchase_profile.md,"
    echo -e "     says it is done, and stops — then exit Hermes."
    echo -e "  2. Run dtlab-start AGAIN: pre-flight freezes the profile"
    echo -e "     (read-only, hash-recorded) and starts run 1.${NC}"
    ok "bootstrap session prepared ($TIER tier writes the profile; tier recorded)"
  else
  if [ "$SWITCH_ACTIVE" = "1" ]; then
    COND="$PORDER"   # already validated as persona|ablated above
    note "grounding switch active ($COND) — overriding the counterbalance order for this run"
  else
    COND=$(run_cond "$RUN" "$PORDER")
  fi
  # run-dir creation happens ONLY at launch (after every gate below has
  # passed) — a refused gate must never leave a phantom "started" run
  [ -d "$RUNSDIR/run$RUN" ] || FRESH_RUN=1
  if [ "$FRESH_RUN" = "1" ]; then
    if [ "$SWITCH_ACTIVE" = "1" ]; then
      ok "starting agent run $RUN of 4 ($TIER tier, $COND grounding; manual switch, not the counterbalance sheet)"
    else
      ok "starting agent run $RUN of 4 ($TIER tier, $COND grounding; day-$DAY order $PORDER)"
    fi
  else
    ok "resuming agent run $RUN of 4 ($TIER tier, $COND grounding)"
  fi
  # ---- purchase-history factor (dtlab-history), announced live in class
  # like the grounding switch. Default ON: no switch file means the
  # profile is present, which is the pre-existing behaviour.
  HIST=on
  HISTFILE="$HOME/dtlab/history_switch.txt"
  if [ -f "$HISTFILE" ]; then
    HIST=$(cat "$HISTFILE")
    case "$HIST" in
      on|off) ;;
      *) bad "dtlab/history_switch.txt has an invalid value ('$HIST') — expected on or off. Fix it or run: dtlab-history clear"; exit 1 ;;
    esac
  fi
  if [ "$HIST" = "off" ] && [ "$COND" != "persona" ]; then
    echo ""
    echo -e "${RED}Both grounding sources are off (questionnaire ablated AND"
    echo -e "history off) — that leaves nothing to model this person from"
    echo -e "and is not one of the lab's conditions. Turn one back on:"
    echo -e "  dtlab-persona on   or   dtlab-history on${NC}"
    exit 1
  fi
  # a previous no-history run parks the frozen profile in quarantine —
  # restore it BEFORE the hash check, so verification sees the real file
  [ -f "$HOLD/purchase_profile.md" ] && \
    mv "$HOLD/purchase_profile.md" "$WS/purchase_profile.md"
  # frozen-profile verification, EVERY run (fail closed): the profile
  # all four runs read must be byte-identical to the frozen bootstrap
  # output
  FROZEN_SHA="$(cat "$HOME/dtlab/purchase_profile.sha256" 2>/dev/null || echo none)"
  CUR_SHA="$([ -f "$WS/purchase_profile.md" ] \
             && sha256_file "$WS/purchase_profile.md" || echo missing)"
  if [ "$CUR_SHA" != "$FROZEN_SHA" ]; then
    echo ""
    echo -e "${RED}The purchase profile changed after the freeze (or the"
    echo -e "freeze record is missing) — tell a TA. No run was started.${NC}"
    exit 1
  fi
  ok "purchase profile verified against the freeze record"
  if [ "$COND" = "persona" ]; then
    for f in persona_survey.md persona_survey.csv persona_meta.json; do
      [ -f "$HOLD/$f" ] && mv "$HOLD/$f" "$WS/$f"
    done
  else
    for f in persona_survey.md persona_survey.csv persona_meta.json; do
      [ -f "$WS/$f" ] && mv "$WS/$f" "$HOLD/$f"
    done
  fi
  # Grounding = the two factors together. A history-off run REMOVES the
  # frozen profile from the workspace, exactly as an ablated run removes
  # the questionnaire: the SOUL variant alone is an instruction, not a
  # boundary — the file has to be gone.
  if [ "$HIST" = "off" ]; then
    mv "$WS/purchase_profile.md" "$HOLD/purchase_profile.md"
    COND="nohistory"
    cp "$HOME/dtlab/soul/SOUL_nohistory.md" "$WS/SOUL.md"
    ok "grounding: run $RUN = NO-HISTORY run (questionnaire present; purchase profile removed from the workspace)"
  elif [ "$COND" = "persona" ]; then
    cp "$HOME/dtlab/soul/SOUL.md" "$WS/SOUL.md"
    ok "grounding: run $RUN = PERSONA run (questionnaire + purchase profile; use the standard prompt)"
  else
    cp "$HOME/dtlab/soul/SOUL_ablated.md" "$WS/SOUL.md"
    ok "grounding: run $RUN = ABLATED run (questionnaire removed from the workspace; use the ABLATED prompt from tasks.md)"
  fi
  # swap in the ablation comparison template while the standard one is
  # still unfilled (never clobber student writing; .bak just in case).
  # comparison.md is the FALLBACK memo — dtlab-verdict is the primary
  # verdict capture.
  if [ -f "$HOME/dtlab/comparison_ablation.TEMPLATE.md" ] \
     && ! grep -q "(Run A)" "$WS/comparison.md" 2>/dev/null \
     && grep -q "{better|" "$WS/comparison.md" 2>/dev/null; then
    cp "$WS/comparison.md" "$WS/comparison.md.bak"
    cp "$HOME/dtlab/comparison_ablation.TEMPLATE.md" "$WS/comparison.md"
    note "comparison.md swapped to the ablation template (old file kept as comparison.md.bak)"
  fi
  fi   # end of the non-bootstrap (numbered-run) branch
fi
[ -f "$WS/human_picks.csv" ] \
  && bad "human_picks.csv found in the AGENT workspace — move it to ~/dtlab/quarantine/human/ (the agent must not see your picks)"
# persona file may legitimately sit in the hold dir during an ablated run
PSF="$WS/persona_survey.md"
[ -f "$PSF" ] || PSF="$HOLD/persona_survey.md"
# persona_meta.json (make_persona.py) records the exact agent-visible
# item count — the authority when present (sensitive-item opt-outs
# render 5 fewer items); the 113-based heuristic is the fallback and
# accepts both the default and the opt-out count
PMETA=""
for _pm in "$WS/persona_meta.json" "$HOLD/persona_meta.json"; do
  [ -f "$_pm" ] && PMETA="$_pm" && break
done
if [ -n "$PMETA" ]; then
  META_N=$(python3 -c 'import json,sys
print(json.load(open(sys.argv[1])).get("rendered_items", ""))' "$PMETA" \
    2>/dev/null || echo "")
else
  META_N=""
fi
if [ -f "$PSF" ]; then
  N=$(grep -c '^\- \*\*' "$PSF" || true)
  if [ -n "$META_N" ]; then
    if [ "$N" = "$META_N" ]; then
      ok "persona_survey.md present ($N agent-visible items, matches persona_meta.json)"
    else
      bad "persona_survey.md has $N agent-visible items but persona_meta.json says $META_N — regenerate"
    fi
  else
    MIN=$(( (RENDERED_ITEMS - 5) * 95 / 100 ))
    if [ "$N" -ge "$MIN" ]; then
      ok "persona_survey.md present ($N/$RENDERED_ITEMS agent-visible items)"
    elif [ "$N" -gt 0 ]; then
      bad "persona_survey.md has only $N/$RENDERED_ITEMS agent-visible items — regenerate"
    else
      bad "persona_survey.md is empty or malformed — regenerate"
    fi
  fi
else
  bad "persona_survey.md missing — run make_persona.py first (see handout §6)"
fi
note "purchase profile: written ONCE by the bootstrap session before
       run 1, then frozen read-only and hash-verified at every run"

# ---- per-student task order: randomized ACROSS students, held constant
# WITHIN a student (human session + all four agent runs), derived
# deterministically from the pseudonym. Re-orders the task sections of
# tasks.md in place (idempotent; skipped while the workspace is not yet
# complete). Ranking is in LOCKSTEP with pack_evidence.py and
# log_human_session.py.
ORDER=$(python3 - "$WS" <<'PY'
import csv, hashlib, re, sys
from pathlib import Path
ws = Path(sys.argv[1])
dt = ws.parent
sid = ""
for p in (ws / "persona_survey.csv",
          dt / "quarantine" / "persona_hold" / "persona_survey.csv"):
    try:
        with open(p, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if rows and (rows[0].get("student_id") or "").strip():
            sid = rows[0]["student_id"].strip()
            break
    except OSError:
        pass
ids = []
try:
    with open(dt / "tasks_config.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            t = (r.get("task_id") or "").strip()
            if t and not t.startswith("#"):
                ids.append(t)
except OSError:
    pass
tmd = ws / "tasks.md"
if not (sid and ids and tmd.exists()):
    sys.exit(0)
order = sorted(ids, key=lambda t: hashlib.sha256(
    f"{sid}|{t}".encode()).hexdigest())
text = tmd.read_text(encoding="utf-8")
parts = re.split(r"(?m)^(?=## Task \d)", text)
head, secs, tail = parts[0], {}, ""
for p in parts[1:]:
    m = re.match(r"## Task (\d+)", p)
    tm = re.search(r"(?m)^---\s*$", p)
    if tm:                      # the standardized-prompt block begins
        tail = p[tm.start():]
        p = p[:tm.start()]
    if m:
        secs[m.group(1)] = p
if set(secs) != set(ids):
    sys.exit(0)                 # stub/partial tasks.md: leave untouched
new = head + "".join(secs[t] for t in order) + tail
if new != text:
    tmd.write_text(new, encoding="utf-8")
(dt / "task_order.txt").write_text(",".join(order) + "\n",
                                   encoding="utf-8")
print(",".join(order))
PY
)
if [ -n "$ORDER" ]; then
  ok "your task order: $ORDER (randomized across students; identical for your own session and all agent runs — tasks.md is ordered accordingly)"
fi

# 3. Forbidden files (privacy check — these must NOT be in the workspace)
for f in "$WS"/*address* "$WS"/*payment* "$WS"/Retail.OrderHistory*; do
  [ -e "$f" ] && bad "Remove raw/PII file from workspace: $f"
done

if [ "$FAIL" -ne 0 ]; then
  echo ""
  echo -e "${RED}Fix the [!!] items above, then run dtlab-start again.${NC}"
  exit 1
fi

echo ""
echo "All checks passed. Session order (LOGIN BEFORE RECORDING — passwords"
echo "and OTPs must never be on screen while the recorder runs):"
echo "  1. Chromium opens next -> log into amazon.in MANUALLY, empty the cart."
echo "  2. Only AFTER login: in ANOTHER terminal run  dtlab-record  (optional)."
echo "  3. Hermes CLI starts    -> run: /browser connect"
echo "     If garbled text like ']11;rgb:...' appears in the input box the"
echo "     moment Hermes starts, that is harmless terminal noise (Hermes"
echo "     asking the terminal its background color) — clear the line"
echo "     (Ctrl+U or select-and-delete) before typing anything, so it is"
echo "     not sent to the agent as your first message."
echo "  4. Paste the standardized task prompt from tasks.md (dtlab-start"
echo "     announced above which one — standard or ABLATED)."
echo "  5. PARTNER watches (owner swaps seats). Intervene ONLY for CAPTCHAs"
echo "     (note every intervention). If the agent asks a question, do NOT"
echo "     answer it — its SOUL requires deciding alone; tell it to decide"
echo "     itself and note the exchange as an intervention."
echo "  6. Afterwards: partner runs  dtlab-cart  (screenshot + parsed cart),"
echo "     then EMPTIES the cart before the next run — with DELETE, never"
echo "     'Save for later' (saved items stay parked on the account)."
echo "  7. Evidence auto-collects from ~/dtlab/workspace + evidence folder."
echo ""
echo -e "${YEL}Codespaces users: NEVER set the forwarded desktop port (6080) to"
echo -e "Public — a public port hands your desktop (and your logged-in Amazon"
echo -e "session) to anyone with the URL. Leave it Private.${NC}"
echo ""
# One-time consent acknowledgment (docs/CONSENT_AND_DATA_USE.md; the
# capture is layered per research_protocol.md §3: Form checkboxes, THIS
# typed acknowledgment, the LMS release). The understanding is confirmed
# at the moment it becomes real — right before the first real agent run;
# recorded once under the persistent lab root and written into the
# manifest by dtlab-pack.
ACKFILE="$HOME/dtlab/.consent_ack"
if [ ! -f "$ACKFILE" ]; then
  echo -e "${YEL}One-time acknowledgment (consent sheet:"
  echo -e "docs/CONSENT_AND_DATA_USE.md, on the LMS): your agent is about"
  echo -e "to browse and act — add-to-cart only — on your own logged-in"
  echo -e "amazon.in account. Its logs, picks, and your verdicts are"
  echo -e "collected under your pseudonym and leave this environment"
  echo -e "exactly once, as the zip you upload to the LMS.${NC}"
  read -rp "Type AGREE to confirm and continue: " ACK
  if [ "$ACK" = "AGREE" ]; then
    date -u +%FT%TZ > "$ACKFILE"
    ok "acknowledgment recorded — you will not be asked again"
    echo ""
  else
    echo -e "${RED}Not confirmed — nothing was started. Read the consent"
    echo -e "sheet on the LMS, then re-run dtlab-start. Questions, or the"
    echo -e "opt-out path (synthetic persona, no grade impact): talk to a"
    echo -e "TA.${NC}"
    exit 1
  fi
fi
# Friday gate: the 1-day browsing-history pause set on day 1 has LAPSED
# by day 2 — require a fresh self-attest before the first frontier run.
if [ -n "$RUN" ] && [ "$RUN" -ge 3 ]; then
  echo -e "${YEL}DAY-2 GATE: the 1-day Browsing History pause from day 1 has"
  echo -e "LAPSED by now — it must be re-paused before any day-2 run.${NC}"
  read -rp "Browsing History RE-PAUSED today (Browsing History > gear icon > Pause History) and existing items removed from view? [y/N] " BH
else
  read -rp "Amazon Browsing History PAUSED for 1 day (Browsing History > gear icon > Pause History) and existing items removed from view? [y/N] " BH
fi
case "$BH" in
  [yY]*) ok "browsing history paused — browsing-driven carry-over channel closed for both sessions" ;;
  *) echo -e "${RED}Do that now (takes 30 seconds; exact steps in PERSONALIZATION_PROTOCOL.md), then re-run dtlab-start.${NC}"; exit 1 ;;
esac
read -rp "Saved payment methods REMOVED (or never present) in this lab browser profile, and no card autofill? [y/N] " PM
case "$PM" in
  [yY]*) ok "no saved payment methods in the lab browser profile" ;;
  *) echo -e "${RED}Remove them now (amazon.in > Your Account > Payment options; also check the browser's own autofill), then re-run dtlab-start. The agent never touches checkout, but a clean profile is the belt to that suspender.${NC}"; exit 1 ;;
esac
# Calendar guard: runs 3-4 are DAY-2 runs; burning all four on day 1
# breaks the tier-by-day design. Soft gate — a TA-approved early run
# passes with a typed EARLY (remembered for the rest of the day pair).
if [ -n "$RUN" ] && [ "$RUN" -ge 3 ] \
   && [ ! -f "$HOME/dtlab/.day2_early_ok" ]; then
  TODAY_IST="$(TZ=Asia/Kolkata date +%F)"
  D1DATE="$(cat "$RUNSDIR/run1/ist_date.txt" 2>/dev/null || true)"
  if [ -n "$D1DATE" ] && [ "$TODAY_IST" = "$D1DATE" ]; then
    echo -e "${YEL}Runs 3-4 are DAY-2 (frontier) runs, but today is still"
    echo -e "day 1's calendar date in IST ($D1DATE). All four runs on one"
    echo -e "day would break the tier-by-day design. Type EARLY only if a"
    echo -e "TA approved running day-2 early; anything else aborts.${NC}"
    read -rp "> " OK3
    if [ "$OK3" = "EARLY" ]; then
      echo EARLY > "$HOME/dtlab/.day2_early_ok"
      note "TA-approved early day-2 start recorded"
    else
      echo -e "${RED}Come back on lab day 2 for runs 3-4.${NC}"
      exit 1
    fi
  fi
fi
if [ -n "$COND" ]; then
  echo ""
  echo -e "${YEL}2x2 DESIGN ACTIVE — this is agent run $RUN of 4 ($TIER tier, $COND grounding).${NC}"
  echo "After THIS run: the partner runs  dtlab-cart  (saves cart_run$RUN.png"
  echo "+ parsed cart contents into ~/dtlab/evidence/), then EMPTIES the"
  echo "cart before the next run (DELETE each item — never 'Save for later')."
fi
read -rp "Press Enter to open the browser and start Hermes... "
# marker = FIRST REAL agent-run start (log collection and the ordering
# check key off the earliest start, so never re-touch it; sandbox runs
# stamp .sandbox_run_started instead and never touch this one)
[ -f "$HOME/dtlab/.run_started" ] || touch "$HOME/dtlab/.run_started"
# Hermes transcript-dir probe (LEGACY packs only): with per-run homes,
# transcripts land inside $HERMES_HOME and dtlab-pack collects them from
# each run's home directly. Global dirs are still recorded when present
# so pre-per-run-home evidence remains collectable.
HD_FOUND=""
for d in $(echo "${DTLAB_HERMES_DIRS:-}" | tr ':' ' ') \
         "$HOME/.hermes" "$HOME/.config/hermes"; do
  [ -d "$d" ] && HD_FOUND="${HD_FOUND:+$HD_FOUND:}$d"
done
[ -n "$HD_FOUND" ] && echo "$HD_FOUND" > "$HOME/dtlab/.hermes_dirs"
# ---- launch order (audit 4.4): browser -> CDP liveness -> checkout-
# guard canary -> effective-config verification -> ONLY THEN run state.
# A dead CDP port or an unproven guard must leave NO runs/runN dir for
# a fresh run; a resume of an already-started run is unaffected.
# DTLAB_TEST=1 skips the browser stack and exits after the state write,
# so tests observe the final state.
if [ "${DTLAB_TEST:-0}" != "1" ]; then
  # Same profile + CDP port as dtlab-shop, via the one shared launcher.
  bash "$HOME/dtlab/tools/dtlab_browser.sh" "https://www.amazon.in" \
    >/dev/null 2>&1 &
  wait_cdp || exit 1
  canary_gate || exit 1
fi
# ---- per-run Hermes home: generated and VERIFIED before any run state
# is written — a config mismatch must never leave a phantom "started"
# run ----
if [ "$BOOTSTRAP_RUN" = "1" ]; then
  RUN_HOME="$RUNSDIR/bootstrap/hermes_home"
  make_hermes_home "$RUN_HOME" "$HOME/dtlab/soul/SOUL_bootstrap.md" \
    "$MODEL_ID" || exit 1
  verify_hermes_config "$RUN_HOME" "${DTLAB_PROVIDER:-anthropic}" \
    "$MODEL_ID" || config_mismatch_abort
elif [ -n "$RUN" ]; then
  case "$COND" in
    persona)   SOUL_SRC="$HOME/dtlab/soul/SOUL.md" ;;
    nohistory) SOUL_SRC="$HOME/dtlab/soul/SOUL_nohistory.md" ;;
    *)         SOUL_SRC="$HOME/dtlab/soul/SOUL_ablated.md" ;;
  esac
  RUN_HOME="$RUNSDIR/run$RUN/hermes_home"
  if [ -d "$RUN_HOME" ]; then
    # crash-resume: refresh SOUL + config in place, keep the transcripts
    make_hermes_home "$RUN_HOME" "$SOUL_SRC" "$MODEL_ID" || exit 1
    verify_hermes_config "$RUN_HOME" "${DTLAB_PROVIDER:-anthropic}" \
      "$MODEL_ID" || config_mismatch_abort
  else
    HH_STAGE="$RUNSDIR/.pending_hermes_home"
    rm -rf "$HH_STAGE"
    make_hermes_home "$HH_STAGE" "$SOUL_SRC" "$MODEL_ID" || exit 1
    verify_hermes_config "$HH_STAGE" "${DTLAB_PROVIDER:-anthropic}" \
      "$MODEL_ID" || { rm -rf "$HH_STAGE"; config_mismatch_abort; }
    mkdir -p "$RUNSDIR/run$RUN"
    mv "$HH_STAGE" "$RUN_HOME"
  fi
else
  # legacy single-run flow (factor off): one home under runs/single/
  LEGACY_TIER="$(cat "$HOME/dtlab/tier.txt" 2>/dev/null || echo frontier)"
  case "$LEGACY_TIER" in economy|frontier) ;; *) LEGACY_TIER=frontier ;; esac
  pin_gate "$LEGACY_TIER"
  RUN_HOME="$RUNSDIR/single/hermes_home"
  SOUL_SRC="$HOME/dtlab/soul/SOUL.md"
  [ -f "$SOUL_SRC" ] || SOUL_SRC="$WS/SOUL.md"
  make_hermes_home "$RUN_HOME" "$SOUL_SRC" "$MODEL_ID" || exit 1
  verify_hermes_config "$RUN_HOME" "${DTLAB_PROVIDER:-anthropic}" \
    "$MODEL_ID" || config_mismatch_abort
fi
# run state is written HERE — every gate above has passed, so a refused
# gate can never leave a phantom run; started_at/ist_date are guarded so
# a crash-resume never overwrites the true first start
if [ -n "$RUN" ]; then
  mkdir -p "$RUNSDIR/run$RUN"
  echo "$COND" > "$RUNSDIR/run$RUN/condition.txt"
  echo "${HIST:-on}" > "$RUNSDIR/run$RUN/history.txt"
  echo "$TIER" > "$RUNSDIR/run$RUN/tier.txt"
  [ -f "$RUNSDIR/run$RUN/started_at.txt" ] || \
    date -u +%FT%TZ > "$RUNSDIR/run$RUN/started_at.txt"
  [ -f "$RUNSDIR/run$RUN/ist_date.txt" ] || \
    TZ=Asia/Kolkata date +%F > "$RUNSDIR/run$RUN/ist_date.txt"
  # context/config hashes + model id: the audit record of exactly which
  # SOUL and model config THIS run's Hermes loaded
  sha256_file "$RUN_HOME/SOUL.md" > "$RUNSDIR/run$RUN/soul_sha256.txt"
  sha256_file "$RUN_HOME/config.yaml" \
    > "$RUNSDIR/run$RUN/config_sha256.txt"
  echo "$MODEL_ID" > "$RUNSDIR/run$RUN/model_id.txt"
  # per-run snapshot of the frozen profile: proves what THIS run saw
  [ -f "$RUNSDIR/run$RUN/purchase_profile.md" ] || \
    { [ -f "$WS/purchase_profile.md" ] && \
      cp "$WS/purchase_profile.md" "$RUNSDIR/run$RUN/purchase_profile.md"; }
elif [ "$BOOTSTRAP_RUN" = "1" ]; then
  # the profile writer's identity is part of the research record
  echo "$TIER" > "$RUNSDIR/bootstrap/tier.txt"
  echo "$MODEL_ID" > "$RUNSDIR/bootstrap/model_id.txt"
  [ -f "$RUNSDIR/bootstrap/started_at.txt" ] || \
    date -u +%FT%TZ > "$RUNSDIR/bootstrap/started_at.txt"
fi
# per-run tier is authoritative (runs/runN/tier.txt); ~/dtlab/tier.txt is
# kept for manifest backward compatibility only
if [ -n "$TIER" ]; then
  echo "$TIER" > "$HOME/dtlab/tier.txt"
elif [ ! -f "$HOME/dtlab/tier.txt" ]; then
  echo "frontier" > "$HOME/dtlab/tier.txt"
fi
[ "${DTLAB_TEST:-0}" = "1" ] && exit 0
echo "(After the day's runs: dtlab-verdict, and on the final day dtlab-pack.)"
# HERMES_HOME is the treatment delivery: Hermes loads $HERMES_HOME/SOUL.md
# and $HERMES_HOME/config.yaml (per-run condition SOUL + pinned model)
cd "$WS" && HERMES_HOME="$RUN_HOME" exec hermes
