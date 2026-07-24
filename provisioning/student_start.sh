#!/usr/bin/env bash
# student_start.sh — the ONLY command students need. Validates everything,
# collects the API key on first run, and walks through the session.
#
# Plan of record (COURSE_PLAN_1WEEK.md, research_protocol.md §1): with the
# questionnaire-ablation factor ON, every agent runs the task set FOUR
# times in a within-student 2x2 — grounding (persona|ablated) x model tier
# (runs 1-2 = day-1/economy, runs 3-4 = day-2/frontier), grounding order
# counterbalanced per day. All students are human-first.
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
# Questionnaire-ablation factor (research_protocol.md §1). 0: single agent
# run, unchanged legacy flow. 1 (plan of record): FOUR runs — the SAME
# tasks under persona vs ablated grounding on each of the two lab days;
# workspace state is ENFORCED per condition (in ablated runs the persona
# files are physically absent, and the agent gets the ablated SOUL).
PERSONA_FACTOR="${DTLAB_PERSONA_FACTOR:-0}"
# Model tier by day (dtlab_config.env; overridable for reruns).
DAY1_TIER="${DTLAB_DAY1_TIER:-economy}"
DAY2_TIER="${DTLAB_DAY2_TIER:-frontier}"
SANDBOX="${DTLAB_SANDBOX:-0}"
RUNSDIR="$HOME/dtlab/runs"
HOLD="$HOME/dtlab/persona_hold"
RUN=""; COND=""; TIER=""; FRESH_RUN=0
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
    bad "That does not look like a Claude API key. Re-run dtlab-start."
  fi
else
  ok "Claude API key present."
fi

# ---- SANDBOX MODE: soft gates, sandbox SOUL, stamped for exclusion ----
if [ "$SANDBOX" = "1" ]; then
  echo sandbox > "$HOME/dtlab/sandbox.txt"
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
  cd "$WS" && exec hermes
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
  run_tier() { if [ "$1" -le 2 ]; then echo "$DAY1_TIER"; else echo "$DAY2_TIER"; fi; }
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
    t=$(cat "$d/tier.txt" 2>/dev/null || run_tier "$1")
    echo "$t, $c"
  }
  if [ -z "$RUN" ]; then
    read -rp "All four runs already started. Resume run 4 ($(prev_desc 4))? [y/N] " R4
    case "$R4" in
      [yY]*) RUN=4 ;;
      *) bad "all four agent runs are done — next steps: dtlab-verdict, then dtlab-pack"
         echo ""
         echo -e "${RED}Fix the [!!] items above, then run dtlab-start again.${NC}"
         exit 1 ;;
    esac
  elif [ "$RUN" -gt 1 ]; then
    PREV=$((RUN - 1))
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
  DAY=$(run_day "$RUN")
  TIER=$(run_tier "$RUN")
  ORDERFILE="$HOME/dtlab/persona_order_day$DAY.txt"
  if [ ! -f "$ORDERFILE" ]; then
    read -rp "Your assigned grounding order for DAY $DAY (from the LMS sheet) [P_FIRST/NP_FIRST]: " PO
    case "$PO" in
      P_FIRST|NP_FIRST) echo "$PO" > "$ORDERFILE" ;;
      *) echo -e "${RED}Enter exactly P_FIRST or NP_FIRST (check the LMS assignment sheet).${NC}"; exit 1 ;;
    esac
  fi
  PORDER=$(cat "$ORDERFILE")
  COND=$(run_cond "$RUN" "$PORDER")
  [ -d "$RUNSDIR/run$RUN" ] || FRESH_RUN=1
  mkdir -p "$RUNSDIR/run$RUN" "$HOLD"
  echo "$COND" > "$RUNSDIR/run$RUN/condition.txt"
  echo "$TIER" > "$RUNSDIR/run$RUN/tier.txt"
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
  MIN=$(( EXPECTED_ITEMS * 95 / 100 ))
  if [ "$N" -ge "$MIN" ]; then
    ok "persona_survey.md present ($N/$EXPECTED_ITEMS items)"
  elif [ "$N" -gt 0 ]; then
    bad "persona_survey.md has only $N/$EXPECTED_ITEMS items — regenerate"
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
[ -n "$RUN" ] && date -u +%FT%TZ > "$RUNSDIR/run$RUN/started_at.txt"
# per-run tier is authoritative (runs/runN/tier.txt); ~/dtlab/tier.txt is
# kept for manifest backward compatibility only
if [ -n "$TIER" ]; then
  echo "$TIER" > "$HOME/dtlab/tier.txt"
elif [ ! -f "$HOME/dtlab/tier.txt" ]; then
  echo "frontier" > "$HOME/dtlab/tier.txt"
fi
[ "${DTLAB_TEST:-0}" = "1" ] && exit 0
echo "(After the day's runs: dtlab-verdict, and on the final day dtlab-pack.)"
# Same profile + CDP port as dtlab-shop, via the one shared launcher.
bash "$HOME/dtlab/tools/dtlab_browser.sh" "https://www.amazon.in" >/dev/null 2>&1 &
wait_cdp || exit 1
cd "$WS" && exec hermes
