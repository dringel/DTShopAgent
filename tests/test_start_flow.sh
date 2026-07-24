#!/usr/bin/env bash
# State-machine test for provisioning/student_start.sh: drives the
# interactive pre-flight with scripted answers inside a throwaway sandbox
# HOME and asserts the resulting workspace/hold/runs state after each
# transition (W2; four-run 2x2 per docs/WORK_ORDER_4RUN.md). DTLAB_TEST=1
# stops the script right before it would launch the browser/Hermes.
#
# Run from repo root:  bash tests/test_start_flow.sh
# shellcheck disable=SC2319  # `[ cond ]; check $?` is the
# harness's deliberate assertion idiom; $? is always the
# immediately preceding test
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
START="$REPO/provisioning/student_start.sh"
PASS=0; FAIL=0
check(){ if [ "$1" = "$2" ]; then echo "  PASS: $3"; PASS=$((PASS+1));
         else echo "  FAIL: $3 (got $1, want $2)"; FAIL=$((FAIL+1)); fi; }

SANDBOX_HOME="$(mktemp -d "${TMPDIR:-/tmp}/dtlab-startflow.XXXXXX")"
export HOME="$SANDBOX_HOME"
guard(){ case "$HOME" in "$SANDBOX_HOME"*) ;; *)
  echo "FATAL: HOME escaped sandbox"; exit 99 ;; esac; }

mkenv(){  # persona_factor(0/1) as $1
guard
rm -rf "$HOME/dtlab" "$HOME/.dtlab_env" "$HOME/.bashrc"
mkdir -p "$HOME/dtlab/workspace" "$HOME/dtlab/soul" "$HOME/dtlab/human" \
         "$HOME/dtlab/evidence"
sed "s/DTLAB_PERSONA_FACTOR='1'/DTLAB_PERSONA_FACTOR='$1'/" \
    "$REPO/dtlab_config.env" > "$HOME/dtlab/dtlab_config.env"
cp "$REPO/tasks_config.csv" "$HOME/dtlab/"
printf '# MARK-STANDARD\n' >  "$HOME/dtlab/soul/SOUL.md"
printf '# MARK-ABLATED\n'  >  "$HOME/dtlab/soul/SOUL_ablated.md"
printf '# MARK-SANDBOX\n'  >  "$HOME/dtlab/soul/SOUL_sandbox.md"
cp "$HOME/dtlab/soul/SOUL.md" "$HOME/dtlab/workspace/SOUL.md"
cp "$REPO/templates/comparison_ablation.md" \
   "$HOME/dtlab/comparison_ablation.TEMPLATE.md"
cp "$REPO/templates/comparison.md" "$HOME/dtlab/workspace/comparison.md"
printf '## Task 1\nfilled, no placeholders here\n' \
  > "$HOME/dtlab/workspace/tasks.md"
# 113 = 115-item instrument minus the 2 agent-hidden items (PR02/PR08)
for i in $(seq 1 113); do echo "- **X$i** q"; done \
  > "$HOME/dtlab/workspace/persona_survey.md"
echo "student_id,answer" > "$HOME/dtlab/workspace/persona_survey.csv"
touch "$HOME/dtlab/human/human_picks.csv" \
      "$HOME/dtlab/human/human_session.jsonl"
printf 'export ANTHROPIC_API_KEY=sk-ant-test0000000000000000000000\n' \
  > "$HOME/.dtlab_env"
chmod 600 "$HOME/.dtlab_env"
}

run(){  # $1=piped answers, rest = env assignments
  local answers="$1"; shift
  printf '%b' "$answers" | env "$@" DTLAB_TEST=1 bash "$START" \
    > "$HOME/last_out.txt" 2>&1
  echo $?
}

finish_run(){  # fabricate a finished run's workspace artifacts
  printf 'log\n'   > "$HOME/dtlab/workspace/decision_log.md"
  printf 'picks\n' > "$HOME/dtlab/workspace/agent_picks.csv"
}

echo "[1] legacy single-run flow (factor off) reaches the launch point"
mkenv 0
rc=$(run 'y\ny\n\n')
check "$rc" 0 "exit 0"
check "$(cat "$HOME/dtlab/arm.txt")" "H_FIRST" "arm auto-recorded (no prompt)"
check "$(cat "$HOME/dtlab/tier.txt")" "frontier" "tier defaulted silently"
[ -f "$HOME/dtlab/.run_started" ]; check $? 0 "run marker touched"

echo "[2] human-first is a hard gate (no dtlab-shop -> refuse)"
mkenv 1
rm -f "$HOME/dtlab/human/human_picks.csv"
rc=$(run 'P_FIRST\ny\ny\n\n')
check "$rc" 1 "exit 1"
grep -q "dtlab-shop" "$HOME/last_out.txt"
check $? 0 "points at dtlab-shop"

echo "[3] run 1 (day-1 order P_FIRST) = persona, economy"
mkenv 1
rc=$(run 'P_FIRST\ny\ny\n\n')
check "$rc" 0 "exit 0"
check "$(cat "$HOME/dtlab/persona_order_day1.txt")" "P_FIRST" "day-1 order stored"
check "$(cat "$HOME/dtlab/runs/run1/condition.txt")" "persona" "run1 = persona"
check "$(cat "$HOME/dtlab/runs/run1/tier.txt")" "economy" "run1 = economy tier"
check "$(cat "$HOME/dtlab/tier.txt")" "economy" "legacy tier.txt mirrors the day tier"
grep -q 'MARK-STANDARD' "$HOME/dtlab/workspace/SOUL.md"
check $? 0 "standard SOUL in workspace"
[ -f "$HOME/dtlab/workspace/persona_survey.md" ]
check $? 0 "persona stays in workspace for the persona run"
grep -q '(Run A)' "$HOME/dtlab/workspace/comparison.md"
check $? 0 "comparison swapped to the ablation template (blind labels)"
[ -f "$HOME/dtlab/workspace/comparison.md.bak" ]
check $? 0 ".bak of the original comparison kept"
[ -f "$HOME/dtlab/runs/run1/started_at.txt" ]
check $? 0 "run1 start time recorded"

echo "[4] crash-resume: answering N stays on run 1, archives nothing"
printf 'log\n' > "$HOME/dtlab/workspace/decision_log.md"
rc=$(run 'n\ny\ny\n\n')
check "$rc" 0 "exit 0"
grep -q "resuming agent run 1 of 4 (economy tier, persona grounding)" \
  "$HOME/last_out.txt"
check $? 0 "resume prompt names run, tier, and condition"
[ ! -d "$HOME/dtlab/runs/run2" ]; check $? 0 "run2 not created on resume"
[ -f "$HOME/dtlab/workspace/decision_log.md" ]
check $? 0 "run-1 artifacts NOT archived on resume"

echo "[5] run 1 finished -> run 2 archives and flips to ablated (economy)"
finish_run
rc=$(run 'y\ny\ny\n\n')
check "$rc" 0 "exit 0"
check "$(cat "$HOME/dtlab/runs/run2/condition.txt")" "ablated" "run2 = ablated"
check "$(cat "$HOME/dtlab/runs/run2/tier.txt")" "economy" "run2 still economy"
[ -f "$HOME/dtlab/runs/run1/decision_log.md" ]
check $? 0 "run-1 log archived before run 2"
[ ! -f "$HOME/dtlab/workspace/decision_log.md" ]
check $? 0 "workspace log cleared for run 2"
[ -f "$HOME/dtlab/persona_hold/persona_survey.md" ] \
  && [ ! -f "$HOME/dtlab/workspace/persona_survey.md" ]
check $? 0 "persona files physically moved to the hold dir"
grep -q 'MARK-ABLATED' "$HOME/dtlab/workspace/SOUL.md"
check $? 0 "ablated SOUL in workspace"

echo "[6] run 3 needs the day-2 order and the Friday re-pause gate"
finish_run
rc=$(run 'y\nNP_FIRST\nn\n')
check "$rc" 1 "refusing the re-pause gate exits 1"
grep -q "LAPSED" "$HOME/last_out.txt"
check $? 0 "gate names the lapsed 1-day pause"
check "$(cat "$HOME/dtlab/persona_order_day2.txt")" "NP_FIRST" "day-2 order stored"
[ ! -f "$HOME/dtlab/runs/run3/started_at.txt" ]
check $? 0 "refused run 3 never started"

echo "[7] run 3: same-IST-day calendar gate, then EARLY override passes"
# runs 1-2 were created today, so the day-2 calendar guard fires first
rc=$(run 'y\ny\ny\nnope\n')
check "$rc" 1 "run 3 on day-1's IST date without EARLY exits 1"
grep -q "EARLY" "$HOME/last_out.txt"
check $? 0 "gate asks for the TA-approved EARLY override"
[ ! -d "$HOME/dtlab/runs/run3" ]
check $? 0 "refused calendar gate leaves no phantom run-3 dir"
rc=$(run 'y\ny\ny\nEARLY\n\n')
check "$rc" 0 "exit 0 with typed EARLY"
check "$(cat "$HOME/dtlab/runs/run3/condition.txt")" "ablated" "run3 = ablated (day-2 NP_FIRST)"
check "$(cat "$HOME/dtlab/runs/run3/tier.txt")" "frontier" "run3 = frontier tier"
check "$(cat "$HOME/dtlab/tier.txt")" "frontier" "legacy tier.txt now frontier"
[ -f "$HOME/dtlab/runs/run2/decision_log.md" ]
check $? 0 "run-2 log archived before run 3"
grep -q 'MARK-ABLATED' "$HOME/dtlab/workspace/SOUL.md"
check $? 0 "ablated SOUL for run 3"

echo "[8] run 4 = persona, frontier; persona files restored; EARLY remembered"
finish_run
rc=$(run 'y\ny\ny\n\n')
check "$rc" 0 "exit 0 (no second EARLY prompt on the same approved day)"
check "$(cat "$HOME/dtlab/runs/run4/condition.txt")" "persona" "run4 = persona"
check "$(cat "$HOME/dtlab/runs/run4/tier.txt")" "frontier" "run4 = frontier tier"
[ -f "$HOME/dtlab/workspace/persona_survey.md" ]
check $? 0 "persona files restored to the workspace"
grep -q 'MARK-STANDARD' "$HOME/dtlab/workspace/SOUL.md"
check $? 0 "standard SOUL for run 4"

echo "[9] all four runs done: refusing resume points at the next steps"
finish_run
rc=$(run 'n\n')
check "$rc" 1 "exit 1"
grep -q "dtlab-verdict" "$HOME/last_out.txt" \
  && grep -q "dtlab-pack" "$HOME/last_out.txt"
check $? 0 "clear next-step message (dtlab-verdict, dtlab-pack)"

echo "[10] sandbox mode: soft gates, sandbox SOUL, marker hygiene"
mkenv 0
rm -f "$HOME/dtlab/workspace/persona_survey.md" \
      "$HOME/dtlab/workspace/tasks.md" \
      "$HOME/dtlab/human/human_picks.csv"
rc=$(run '\n' DTLAB_SANDBOX=1)
check "$rc" 0 "smoke test passes without persona/tasks/human files"
[ -f "$HOME/dtlab/sandbox.txt" ]; check $? 0 "sandbox marker written"
[ ! -f "$HOME/dtlab/arm.txt" ]; check $? 0 "no arm file in sandbox mode"
grep -q 'MARK-SANDBOX' "$HOME/dtlab/workspace/SOUL.md"
check $? 0 "sandbox SOUL in workspace"
[ -f "$HOME/dtlab/.sandbox_run_started" ]
check $? 0 "sandbox stamps its OWN marker (.sandbox_run_started)"
[ ! -f "$HOME/dtlab/.run_started" ]
check $? 0 "sandbox NEVER touches .run_started (real-run marker)"
mkenv 0
echo sandbox > "$HOME/dtlab/sandbox.txt"     # stale marker from earlier
cp "$HOME/dtlab/soul/SOUL_sandbox.md" "$HOME/dtlab/workspace/SOUL.md"
# sandbox-era agent output left in the workspace (SOUL_sandbox appends)
printf 'CAND | sandbox practice\n' > "$HOME/dtlab/workspace/decision_log.md"
printf 'task_id,asin\nsbx,SBX0001000\n' > "$HOME/dtlab/workspace/agent_picks.csv"
rc=$(run 'y\ny\n\n')
check "$rc" 0 "normal run after sandbox exits 0"
[ ! -f "$HOME/dtlab/sandbox.txt" ]
check $? 0 "stale sandbox marker removed by a normal run"
grep -q 'MARK-STANDARD' "$HOME/dtlab/workspace/SOUL.md"
check $? 0 "standard SOUL restored after a sandbox run"
[ ! -f "$HOME/dtlab/workspace/decision_log.md" ] \
  && [ ! -f "$HOME/dtlab/workspace/agent_picks.csv" ]
check $? 0 "sandbox-era workspace artifacts cleared before the real run"
ls "$HOME/dtlab/sandbox_archive/"*decision_log.md >/dev/null 2>&1 \
  && ls "$HOME/dtlab/sandbox_archive/"*agent_picks.csv >/dev/null 2>&1
check $? 0 "sandbox-era artifacts archived to ~/dtlab/sandbox_archive/"
[ -f "$HOME/dtlab/.run_started" ]
check $? 0 "real run touches .run_started"

echo "[11] pre-flight re-orders tasks.md into the student's randomized order"
mkenv 0
printf 'student_id,item_code\nDT2026-999,D01\n' \
  > "$HOME/dtlab/workspace/persona_survey.csv"
python3 - <<'PY'   # full 5-section tasks.md in config (1..5) order
import os
secs = "".join(f"## Task {t}\nfilled section {t}\n\n" for t in "12345")
open(os.path.expanduser("~/dtlab/workspace/tasks.md"), "w").write(
    "# t\n\n" + secs + "---\nStandardized agent prompt: filled\n")
PY
rc=$(run 'y\ny\n\n')
check "$rc" 0 "exit 0"
DERIVED=$(python3 -c "
import hashlib
print(','.join(sorted('12345', key=lambda t: hashlib.sha256(f'DT2026-999|{t}'.encode()).hexdigest())))")
check "$(cat "$HOME/dtlab/task_order.txt")" "$DERIVED" "task_order.txt = derived order"
FIRST=$(grep -m1 '^## Task' "$HOME/dtlab/workspace/tasks.md" | grep -o '[0-9]')
check "$FIRST" "${DERIVED%%,*}" "tasks.md re-ordered (first section = first of derived order)"
grep -q "your task order: $DERIVED" "$HOME/last_out.txt"
check $? 0 "order announced to the student"
rc=$(run 'y\ny\n\n')   # idempotent second run
check "$rc" 0 "re-run exits 0 (re-ordering is idempotent)"
check "$(grep -m1 '^## Task' "$HOME/dtlab/workspace/tasks.md" | grep -o '[0-9]')" \
      "${DERIVED%%,*}" "order unchanged on re-run"

echo "[12] B4: lab tree behind ~/dtlab symlink (persistent /workspaces root)"
mkenv 1
mkdir -p "$HOME/ws"
mv "$HOME/dtlab" "$HOME/ws/.dtlab"
ln -s "$HOME/ws/.dtlab" "$HOME/dtlab"
rc=$(run 'P_FIRST\ny\ny\n\n')
check "$rc" 0 "pre-flight exits 0 through the symlink"
check "$(cat "$HOME/ws/.dtlab/runs/run1/condition.txt" 2>/dev/null)" \
      "persona" "run state lands under the persistent root"
# rebuild simulation: $HOME is wiped (symlink gone), the root survives;
# setup.sh re-links on the next build and the week continues
guard; rm -f "$HOME/dtlab"
ln -s "$HOME/ws/.dtlab" "$HOME/dtlab"
printf 'log\n'   > "$HOME/dtlab/workspace/decision_log.md"
printf 'picks\n' > "$HOME/dtlab/workspace/agent_picks.csv"
rc=$(run 'y\ny\ny\n\n')
check "$rc" 0 "after a rebuild (fresh symlink) the next run continues"
check "$(cat "$HOME/ws/.dtlab/runs/run2/condition.txt" 2>/dev/null)" \
      "ablated" "run-2 state recorded under the root"
[ -f "$HOME/ws/.dtlab/runs/run1/decision_log.md" ]
check $? 0 "run-1 artifacts archived under the root across the rebuild"

echo "[13] B5: setup.sh — local steps precede network; DTLAB_TEST short-circuits"
SETUP="$REPO/.devcontainer/setup.sh"
WRAP_LINE=$(grep -n 'local/bin/dtlab-start' "$SETUP" | head -1 | cut -d: -f1)
FETCH_LINE=$(grep -n 'fetch_verified "' "$SETUP" | head -1 | cut -d: -f1)
[ -n "$WRAP_LINE" ] && [ -n "$FETCH_LINE" ] && [ "$WRAP_LINE" -lt "$FETCH_LINE" ]
check $? 0 "wrapper creation precedes any fetch_verified call in the script"
grep -q '"onCreateCommand": "bash .devcontainer/setup.sh onCreate"' \
  "$REPO/.devcontainer/devcontainer.json"
check $? 0 "heavy installs wired to onCreateCommand (prebuilds bake them)"
guard; rm -rf "$HOME/dtlab" "$HOME/wsroot" "$HOME/.local" "$HOME/.bashrc"
DTLAB_TEST=1 DTLAB_ROOT="$HOME/wsroot/.dtlab" bash "$SETUP" onCreate \
  > "$HOME/setup_out.txt" 2>&1
check $? 0 "onCreate phase exits 0 with DTLAB_TEST=1 (no network)"
grep -q "skipping network install steps" "$HOME/setup_out.txt"
check $? 0 "network steps short-circuited"
[ -L "$HOME/dtlab" ] && [ -d "$HOME/wsroot/.dtlab/workspace" ]
check $? 0 "DTLAB_ROOT override honored; ~/dtlab is a symlink to it"
[ -x "$HOME/.local/bin/dtlab-start" ] && [ -x "$HOME/.local/bin/dtlab-pack" ]
check $? 0 "dtlab-* wrappers created by the local phase"
DTLAB_TEST=1 DTLAB_ROOT="$HOME/wsroot/.dtlab" bash "$SETUP" \
  > "$HOME/setup_out2.txt" 2>&1
check $? 0 "postCreate phase exits 0 with DTLAB_TEST=1"
[ -f "$HOME/wsroot/.dtlab/kit_version.txt" ]
check $? 0 "kit stamp written per codespace (postCreate)"
guard; rm -rf "$HOME/dtlab" "$HOME/wsroot"

echo "[14] B7: CDP liveness check fails loud before Hermes ever starts"
mkenv 0
mkdir -p "$HOME/bin" "$HOME/dtlab/tools"
printf '#!/usr/bin/env bash\nexit 7\n' > "$HOME/bin/curl"       # CDP dead
# shellcheck disable=SC2016  # $HOME must expand when the stub RUNS
printf '#!/usr/bin/env bash\ntouch "$HOME/hermes_ran"\n' > "$HOME/bin/hermes"
printf '#!/usr/bin/env bash\nexit 0\n' > "$HOME/dtlab/tools/dtlab_browser.sh"
chmod +x "$HOME/bin/curl" "$HOME/bin/hermes" \
         "$HOME/dtlab/tools/dtlab_browser.sh"
printf 'y\ny\n\n' | env PATH="$HOME/bin:$PATH" bash "$START" \
  > "$HOME/last_out.txt" 2>&1
rc=$?
check "$rc" 1 "exit nonzero when the CDP port never comes up"
grep -q "Close ALL open lab-browser windows" "$HOME/last_out.txt"
check $? 0 "prints the one action that fixes the profile lock"
[ ! -f "$HOME/hermes_ran" ]
check $? 0 "Hermes never started on a dead CDP port"
printf '#!/usr/bin/env bash\nexit 0\n' > "$HOME/bin/curl"       # CDP alive
printf 'y\ny\n\n' | env PATH="$HOME/bin:$PATH" bash "$START" \
  > "$HOME/last_out.txt" 2>&1
rc=$?
check "$rc" 0 "live CDP port proceeds to Hermes"
[ -f "$HOME/hermes_ran" ]
check $? 0 "Hermes started once the port answered"
guard; rm -rf "${HOME:?}/bin" "$HOME/hermes_ran"

echo "[15] B16.1: refused gate leaves no phantom run; never-started dirs resume"
mkenv 1
rc=$(run 'P_FIRST\ny\nn\n')             # payment gate refused
check "$rc" 1 "payment-gate refusal exits 1"
[ ! -d "$HOME/dtlab/runs/run1" ]
check $? 0 "no phantom run-1 dir after a refused gate"
rc=$(run 'y\ny\n\n')                    # order stored; gates pass
check "$rc" 0 "next start launches run 1 without a 'finished?' prompt"
check "$(cat "$HOME/dtlab/runs/run1/condition.txt")" "persona" \
      "run-1 state written only at launch"
[ -f "$HOME/dtlab/runs/run1/ist_date.txt" ]
check $? 0 "actual IST date recorded per run"
finish_run
mkdir -p "$HOME/dtlab/runs/run2"        # set up but never started
rc=$(run 'y\ny\n\n')
check "$rc" 0 "never-started run-2 dir resumes without a y/N prompt"
grep -q "set up but never started" "$HOME/last_out.txt"
check $? 0 "silent-resume note printed (no wrong-'y' trap)"
check "$(cat "$HOME/dtlab/runs/run2/condition.txt")" "ablated" \
      "resumed run 2 gets its real condition at launch"
[ -f "$HOME/dtlab/runs/run1/decision_log.md" ]
check $? 0 "run-1 artifacts still archived on the silent-resume path"

echo "[16] B16.2: counterbalance sheet — generator + lookup/confirmation"
cat > "$HOME/roster.csv" <<'EOF'
student_id,section,pair_id
DT2026-999,A,P01
DT2026-001,A,P01
DT2026-002,A,P02
DT2026-003,A,P02
DT2026-004,B,P03
DT2026-005,B,P03
EOF
python3 "$REPO/tools/make_counterbalance.py" --roster "$HOME/roster.csv" \
  --out "$HOME/cb1.csv" --seed 7 >/dev/null
python3 "$REPO/tools/make_counterbalance.py" --roster "$HOME/roster.csv" \
  --out "$HOME/cb2.csv" --seed 7 >/dev/null
cmp -s "$HOME/cb1.csv" "$HOME/cb2.csv"
check $? 0 "generator is deterministic for the same roster + seed"
python3 - "$HOME/cb1.csv" <<'PY'
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
assert len(rows) == 6
for day in ("day1_order", "day2_order"):
    a = [r[day] for r in rows if r["section"] == "A"]
    assert a.count("P_FIRST") == 2 and a.count("NP_FIRST") == 2, (day, a)
    b = [r[day] for r in rows if r["section"] == "B"]
    assert sorted(b) == ["NP_FIRST", "P_FIRST"], (day, b)
assert rows[0]["pair_id"] == "P01"
PY
check $? 0 "balanced P/NP within each section per day; pair carried"
mkenv 1
cp "$HOME/cb1.csv" "$HOME/dtlab/counterbalance.csv"
printf 'student_id,item_code\nDT2026-999,D01\n' \
  > "$HOME/dtlab/workspace/persona_survey.csv"
rc=$(run '\ny\ny\n\n')                  # Enter = confirm assigned order
check "$rc" 0 "sheet lookup + confirmation path exits 0"
grep -q "counterbalance sheet" "$HOME/last_out.txt"
check $? 0 "assigned order announced from the sheet"
EXPECTED=$(python3 - "$HOME/cb1.csv" <<'PY'
import csv, sys
for r in csv.DictReader(open(sys.argv[1])):
    if r["student_id"] == "DT2026-999":
        print("persona" if r["day1_order"] == "P_FIRST" else "ablated")
PY
)
check "$(cat "$HOME/dtlab/runs/run1/condition.txt")" "$EXPECTED" \
      "run-1 condition matches the SHEET assignment, not typed input"

echo "[17] B16.3: API key — malformed exits at once; live check gates storage"
mkenv 0
rm -f "$HOME/.dtlab_env"
mkdir -p "$HOME/bin"
printf '#!/usr/bin/env bash\nprintf 200\n' > "$HOME/bin/curl"
chmod +x "$HOME/bin/curl"
rc=$(run 'garbage-key\n' PATH="$HOME/bin:$PATH")
check "$rc" 1 "malformed key exits 1 immediately (never reaches the run flow)"
grep -q "does not look like" "$HOME/last_out.txt"
check $? 0 "clear malformed-key message"
[ ! -f "$HOME/.dtlab_env" ]; check $? 0 "nothing stored on malformed input"
printf '#!/usr/bin/env bash\nprintf 401\n' > "$HOME/bin/curl"
rc=$(run 'sk-ant-api03-XXXXXXXXXXXXXXXXXXXXXXXX\n' PATH="$HOME/bin:$PATH")
check "$rc" 1 "API-rejected key exits 1"
grep -q "rm ~/.dtlab_env" "$HOME/last_out.txt"
check $? 0 "reset path printed"
[ ! -f "$HOME/.dtlab_env" ]; check $? 0 "rejected key never stored"
printf '#!/usr/bin/env bash\nprintf 200\n' > "$HOME/bin/curl"
rc=$(run 'sk-ant-api03-XXXXXXXXXXXXXXXXXXXXXXXX\ny\ny\n\n' PATH="$HOME/bin:$PATH")
check "$rc" 0 "verified key stores and the flow continues"
grep -q "key verified" "$HOME/last_out.txt"
check $? 0 "verification reported"
grep -q "sk-ant-api03" "$HOME/.dtlab_env"
check $? 0 "key stored after verification"
guard; rm -rf "${HOME:?}/bin"

echo "[18] B16.4: mid-week sandbox fallback stamps PER-RUN, not the whole zip"
mkenv 1
rc=$(run 'P_FIRST\ny\ny\n\n')           # real run 1
check "$rc" 0 "real run 1 launches"
finish_run
rc=$(run '\n' DTLAB_SANDBOX=1)          # flagged-account fallback
check "$rc" 0 "sandbox fallback exits 0"
[ -f "$HOME/dtlab/runs/run2/sandbox.txt" ]
check $? 0 "sandbox stamped on run2 only"
[ ! -f "$HOME/dtlab/sandbox.txt" ]
check $? 0 "no GLOBAL sandbox marker when real runs exist"
[ -f "$HOME/dtlab/runs/run1/decision_log.md" ]
check $? 0 "real run-1 artifacts parked into run1 before the sandbox agent"

guard
rm -rf "$SANDBOX_HOME"
echo ""; echo "Results: $PASS passed, $FAIL failed"
exit $FAIL
