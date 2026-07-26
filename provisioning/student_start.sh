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
HOLD="$HOME/dtlab/persona_hold"
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
  local port="${DTLAB_CDP_PORT:-9222}" i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS "http://127.0.0.1:${port}/json/version" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  echo ""
  echo -e "${RED}The lab browser did not come up with its automation (CDP) port."
  echo -e "Close ALL open lab-browser windows (including the shopping session),"
  echo -e "then re-run dtlab-start.${NC}"
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
    echo -e "(TA_ONBOARDING.md > Instructor-only work items), or export"
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

# Effective-config verification, FAIL CLOSED: re-read the file Hermes
# will actually load and assert it names the assigned provider + model.
# Kept as ONE function so the dry run can extend it to the live
# /api/model read if the pinned release exposes one.
verify_hermes_config() {  # $1 = home dir, $2 = provider, $3 = model id
  grep -qF -- "$3" "$1/config.yaml" 2>/dev/null \
    && grep -qF -- "$2" "$1/config.yaml" 2>/dev/null
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
        note "could not reach the Claude API to verify the key — storing it
       anyway; if agent runs fail with auth errors, reset with
       rm ~/.dtlab_env and re-enter" ;;
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

# 2. Required workspace files
if [ -f "$WS/SOUL.md" ]; then ok "SOUL.md (agent identity) present"
else bad "SOUL.md missing from $WS"; fi
if [ -f "$WS/tasks.md" ] && ! grep -q "INSTRUCTOR_TASK" "$WS/tasks.md"; then
  ok "tasks.md present and filled"
else
  bad "tasks.md missing or still contains template placeholders"
fi
HU="$HOME/dtlab/human"
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
if [ "$PERSONA_FACTOR" = "1" ]; then
  # first run directory that does not exist yet = the next run
  for i in 1 2 3 4; do
    if [ ! -d "$RUNSDIR/run$i" ]; then RUN=$i; break; fi
  done
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
  if [ -z "$RUN" ]; then
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
  DAY=$(run_day "$RUN")
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
          home / "dtlab" / "persona_hold" / "persona_survey.csv"):
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
  ORDERFILE="$HOME/dtlab/persona_order_day$DAY.txt"
  if [ ! -f "$ORDERFILE" ]; then
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
  PORDER=$(cat "$ORDERFILE")
  # ---- model tier for this day: counterbalanced ACROSS DAYS per
  # student (tier_day1/tier_day2 on the sheet). The tier is assigned,
  # never guessed: no sheet row + no valid typed entry = fail closed.
  TIERFILE="$HOME/dtlab/tier_day$DAY.txt"
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
  COND=$(run_cond "$RUN" "$PORDER")
  # run-dir creation happens ONLY at launch (after every gate below has
  # passed) — a refused gate must never leave a phantom "started" run
  [ -d "$RUNSDIR/run$RUN" ] || FRESH_RUN=1
  mkdir -p "$HOLD"
  if [ "$FRESH_RUN" = "1" ]; then
    ok "starting agent run $RUN of 4 ($TIER tier, $COND grounding; day-$DAY order $PORDER)"
  else
    ok "resuming agent run $RUN of 4 ($TIER tier, $COND grounding)"
  fi
  if [ "$COND" = "persona" ]; then
    for f in persona_survey.md persona_survey.csv; do
      [ -f "$HOLD/$f" ] && mv "$HOLD/$f" "$WS/$f"
    done
    cp "$HOME/dtlab/soul/SOUL.md" "$WS/SOUL.md"
    ok "ablation factor: run $RUN = PERSONA run (questionnaire present; use the standard prompt)"
  else
    for f in persona_survey.md persona_survey.csv; do
      [ -f "$WS/$f" ] && mv "$WS/$f" "$HOLD/$f"
    done
    cp "$HOME/dtlab/soul/SOUL_ablated.md" "$WS/SOUL.md"
    ok "ablation factor: run $RUN = ABLATED run (questionnaire removed from the workspace; use the ABLATED prompt from tasks.md)"
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
fi
[ -f "$WS/human_picks.csv" ] \
  && bad "human_picks.csv found in the AGENT workspace — move it to ~/dtlab/human/ (the agent must not see your picks)"
# persona file may legitimately sit in the hold dir during an ablated run
PSF="$WS/persona_survey.md"
[ -f "$PSF" ] || PSF="$HOLD/persona_survey.md"
if [ -f "$PSF" ]; then
  N=$(grep -c '^\- \*\*' "$PSF" || true)
  MIN=$(( RENDERED_ITEMS * 95 / 100 ))
  if [ "$N" -ge "$MIN" ]; then
    ok "persona_survey.md present ($N/$RENDERED_ITEMS agent-visible items)"
  elif [ "$N" -gt 0 ]; then
    bad "persona_survey.md has only $N/$RENDERED_ITEMS agent-visible items — regenerate"
  else
    bad "persona_survey.md is empty or malformed — regenerate"
  fi
else
  bad "persona_survey.md missing — run make_persona.py first (see handout §6)"
fi
note "purchase profile: created BY THE AGENT from your amazon.in order
       history as its first action (no extraction needed beforehand)"

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
for p in (ws / "persona_survey.csv", dt / "persona_hold" / "persona_survey.csv"):
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
if [ -n "$RUN" ]; then
  if [ "$COND" = "persona" ]; then SOUL_SRC="$HOME/dtlab/soul/SOUL.md"
  else SOUL_SRC="$HOME/dtlab/soul/SOUL_ablated.md"; fi
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
