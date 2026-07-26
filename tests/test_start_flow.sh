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
mkdir -p "$HOME/dtlab/workspace" "$HOME/dtlab/soul" "$HOME/dtlab/quarantine/human" \
         "$HOME/dtlab/evidence"
sed -e "s/DTLAB_PERSONA_FACTOR='1'/DTLAB_PERSONA_FACTOR='$1'/" \
    -e "s/DTLAB_MODEL_ECONOMY='PIN-AT-DRYRUN'/DTLAB_MODEL_ECONOMY='claude-eco-test-1'/" \
    -e "s/DTLAB_MODEL_FRONTIER='PIN-AT-DRYRUN'/DTLAB_MODEL_FRONTIER='claude-fro-test-1'/" \
    "$REPO/dtlab_config.env" > "$HOME/dtlab/dtlab_config.env"
cp "$REPO/tasks_config.csv" "$HOME/dtlab/"
cp "$REPO/provisioning/hermes_config.template.yaml" "$HOME/dtlab/"
printf '# MARK-STANDARD\n' >  "$HOME/dtlab/soul/SOUL.md"
printf '# MARK-ABLATED\n'  >  "$HOME/dtlab/soul/SOUL_ablated.md"
printf '# MARK-SANDBOX\n'  >  "$HOME/dtlab/soul/SOUL_sandbox.md"
printf '# MARK-BOOTSTRAP\n' >  "$HOME/dtlab/soul/SOUL_bootstrap.md"
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
touch "$HOME/dtlab/quarantine/human/human_picks.csv" \
      "$HOME/dtlab/quarantine/human/human_session.jsonl"
printf 'export ANTHROPIC_API_KEY=sk-ant-test0000000000000000000000\n' \
  > "$HOME/.dtlab_env"
chmod 600 "$HOME/.dtlab_env"
# consent acknowledgment already given (the gate has its own case [22])
date -u +%FT%TZ > "$HOME/dtlab/.consent_ack"
# bootstrap phase already done: frozen profile + matching hash on file
# (Phase 0 has its own case [27])
printf '# Purchase profile (bootstrap output)\n- top categories: x\n' \
  > "$HOME/dtlab/workspace/purchase_profile.md"
python3 -c "import hashlib,os;print(hashlib.sha256(open(os.path.expanduser('~/dtlab/workspace/purchase_profile.md'),'rb').read()).hexdigest())" \
  > "$HOME/dtlab/purchase_profile.sha256"
touch "$HOME/dtlab/.bootstrap_done"
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
rm -f "$HOME/dtlab/quarantine/human/human_picks.csv"
rc=$(run 'P_FIRST\neconomy\ny\ny\n\n')
check "$rc" 1 "exit 1"
grep -q "dtlab-shop" "$HOME/last_out.txt"
check $? 0 "points at dtlab-shop"

echo "[3] run 1 (day-1 order P_FIRST) = persona, economy"
mkenv 1
rc=$(run 'P_FIRST\neconomy\ny\ny\n\n')
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
grep -q 'MARK-STANDARD' "$HOME/dtlab/runs/run1/hermes_home/SOUL.md"
check $? 0 "run-1 hermes home carries the condition (standard) SOUL"
grep -q 'claude-eco-test-1' "$HOME/dtlab/runs/run1/hermes_home/config.yaml" \
  && grep -q 'anthropic' "$HOME/dtlab/runs/run1/hermes_home/config.yaml"
check $? 0 "run-1 generated config pins the economy model + provider"
check "$(find "$HOME/dtlab/runs/run1/hermes_home" -mindepth 1 \
           -exec basename {} \; | sort | tr '\n' ' ')" \
      "SOUL.md config.yaml " "fresh run home holds ONLY SOUL.md + config.yaml"
H1=$(python3 -c "import hashlib,os;print(hashlib.sha256(open(os.path.expanduser('~/dtlab/runs/run1/hermes_home/SOUL.md'),'rb').read()).hexdigest())")
check "$(cat "$HOME/dtlab/runs/run1/soul_sha256.txt")" "$H1" \
      "per-run SOUL hash = hash of the file Hermes actually loads"
[ -s "$HOME/dtlab/runs/run1/config_sha256.txt" ]
check $? 0 "per-run config hash recorded"
check "$(cat "$HOME/dtlab/runs/run1/model_id.txt")" "claude-eco-test-1" \
      "run-1 model id recorded"

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
[ -f "$HOME/dtlab/quarantine/persona_hold/persona_survey.md" ] \
  && [ ! -f "$HOME/dtlab/workspace/persona_survey.md" ]
check $? 0 "persona files physically moved to the hold dir"
grep -q 'MARK-ABLATED' "$HOME/dtlab/workspace/SOUL.md"
check $? 0 "ablated SOUL in workspace"
grep -q 'MARK-ABLATED' "$HOME/dtlab/runs/run2/hermes_home/SOUL.md"
check $? 0 "run-2 hermes home carries the ABLATED SOUL"
grep -q 'claude-eco-test-1' "$HOME/dtlab/runs/run2/hermes_home/config.yaml"
check $? 0 "run-2 config still pins the economy model"

echo "[6] run 3 needs the day-2 order and the Friday re-pause gate"
finish_run
rc=$(run 'y\nNP_FIRST\nfrontier\nn\n')
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
grep -q 'claude-fro-test-1' "$HOME/dtlab/runs/run3/hermes_home/config.yaml"
check $? 0 "run-3 config pins the frontier model"
check "$(cat "$HOME/dtlab/runs/run3/model_id.txt")" "claude-fro-test-1" \
      "run-3 model id recorded"
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
grep -q 'MARK-STANDARD' "$HOME/dtlab/runs/run4/hermes_home/SOUL.md" \
  && grep -q 'claude-fro-test-1' "$HOME/dtlab/runs/run4/hermes_home/config.yaml"
check $? 0 "run-4 hermes home: standard SOUL + frontier model"

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
      "$HOME/dtlab/quarantine/human/human_picks.csv"
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
grep -q 'MARK-SANDBOX' "$HOME/dtlab/runs/sandbox_home/SOUL.md"
check $? 0 "sandbox hermes home carries the sandbox SOUL"
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
rc=$(run 'P_FIRST\neconomy\ny\ny\n\n')
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
# CDP alive AND the checkout-guard canary lands on blocked.html
cat > "$HOME/bin/curl" <<'EOF'
#!/usr/bin/env bash
for a in "$@"; do
  case "$a" in
    *json/new*)   printf '{"id":"CANARY1","url":"about:blank"}'; exit 0 ;;
    *json/list*)  printf '[{"id":"CANARY1","url":"chrome-extension://abcdefghijklmnop/blocked.html"}]'; exit 0 ;;
    *json/close*) printf 'ok'; exit 0 ;;
  esac
done
exit 0
EOF
chmod +x "$HOME/bin/curl"
printf 'y\ny\n\n' | env PATH="$HOME/bin:$PATH" bash "$START" \
  > "$HOME/last_out.txt" 2>&1
rc=$?
check "$rc" 0 "live CDP port + blocked canary proceeds to Hermes"
grep -q "checkout guard active (canary blocked)" "$HOME/last_out.txt"
check $? 0 "canary gate reports the guard live"
[ -f "$HOME/hermes_ran" ]
check $? 0 "Hermes started once the port answered"
guard; rm -rf "${HOME:?}/bin" "$HOME/hermes_ran"

echo "[15] B16.1: refused gate leaves no phantom run; never-started dirs resume"
mkenv 1
rc=$(run 'P_FIRST\neconomy\ny\nn\n')     # payment gate refused
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
# C1.2: tier order balanced within section, day-2 tier complementary
a = [r["tier_day1"] for r in rows if r["section"] == "A"]
assert a.count("economy") == 2 and a.count("frontier") == 2, a
b = [r["tier_day1"] for r in rows if r["section"] == "B"]
assert sorted(b) == ["economy", "frontier"], b
for r in rows:
    assert {r["tier_day1"], r["tier_day2"]} == {"economy", "frontier"}, r
PY
check $? 0 "balanced P/NP within each section per day; pair carried; tier order balanced + complementary"
python3 "$REPO/tools/make_counterbalance.py" --roster "$HOME/roster.csv" \
  --out "$HOME/cb3.csv" --seed 7 | grep -q "2x2 crosstab"
check $? 0 "tier-order x grounding crosstab printed (orthogonality auditable)"
mkenv 1
cp "$HOME/cb1.csv" "$HOME/dtlab/counterbalance.csv"
printf 'student_id,item_code\nDT2026-999,D01\n' \
  > "$HOME/dtlab/workspace/persona_survey.csv"
rc=$(run '\n\ny\ny\n\n')               # Enter x2 = confirm order + tier
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
EXPTIER=$(python3 - "$HOME/cb1.csv" <<'PY'
import csv, sys
for r in csv.DictReader(open(sys.argv[1])):
    if r["student_id"] == "DT2026-999":
        print(r["tier_day1"])
PY
)
check "$(cat "$HOME/dtlab/runs/run1/tier.txt")" "$EXPTIER" \
      "run-1 tier matches the SHEET tier_day1, not a day default"
grep -q "assigned DAY-1 model tier" "$HOME/last_out.txt"
check $? 0 "assigned tier announced from the sheet"
# C1.2: tier is NOT guessable — no sheet row and no valid typed entry
# must fail closed before any run state
mkenv 1
rc=$(run 'P_FIRST\nwhatever\n')
check "$rc" 1 "garbage typed tier exits 1 (tier is assigned, not guessed)"
grep -q "economy or frontier" "$HOME/last_out.txt"
check $? 0 "fail-closed message names the valid entries and the sheet"
[ ! -d "$HOME/dtlab/runs/run1" ]
check $? 0 "no run state written on the tier fail-close"

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
rc=$(run 'P_FIRST\neconomy\ny\ny\n\n') # real run 1
check "$rc" 0 "real run 1 launches"
finish_run
rc=$(run '\n' DTLAB_SANDBOX=1)          # flagged-account fallback
check "$rc" 0 "sandbox fallback exits 0"
[ -f "$HOME/dtlab/runs/run2/sandbox.txt" ]
check $? 0 "sandbox stamped on run2 only"
grep -q 'MARK-SANDBOX' "$HOME/dtlab/runs/run2/hermes_home/SOUL.md"
check $? 0 "substituted run gets a per-run home with the sandbox SOUL"
[ ! -f "$HOME/dtlab/sandbox.txt" ]
check $? 0 "no GLOBAL sandbox marker when real runs exist"
[ -f "$HOME/dtlab/runs/run1/decision_log.md" ]
check $? 0 "real run-1 artifacts parked into run1 before the sandbox agent"

echo "[19] B18: dtlab-start records the probed Hermes transcript dirs"
mkenv 1
mkdir -p "$HOME/.hermes/sessions"
rc=$(run 'P_FIRST\neconomy\ny\ny\n\n')
check "$rc" 0 "exit 0"
[ -f "$HOME/dtlab/.hermes_dirs" ] && \
  grep -q ".hermes" "$HOME/dtlab/.hermes_dirs"
check $? 0 ".hermes_dirs records the transcript dir dtlab-pack will read"

echo "[20] B22: canary NOT blocked -> pre-flight fails before Hermes"
mkenv 0
mkdir -p "$HOME/bin" "$HOME/dtlab/tools"
# shellcheck disable=SC2016  # $HOME must expand when the stub RUNS
printf '#!/usr/bin/env bash\ntouch "$HOME/hermes_ran"\n' > "$HOME/bin/hermes"
printf '#!/usr/bin/env bash\nexit 0\n' > "$HOME/dtlab/tools/dtlab_browser.sh"
cat > "$HOME/bin/curl" <<'EOF'
#!/usr/bin/env bash
for a in "$@"; do
  case "$a" in
    *json/new*)   printf '{"id":"CANARY1","url":"about:blank"}'; exit 0 ;;
    *json/list*)  printf '[{"id":"CANARY1","url":"https://www.amazon.in/ap/signin"}]'; exit 0 ;;
    *json/close*) printf 'ok'; exit 0 ;;
  esac
done
exit 0
EOF
chmod +x "$HOME/bin/curl" "$HOME/bin/hermes" \
         "$HOME/dtlab/tools/dtlab_browser.sh"
printf 'y\ny\n\n' | env PATH="$HOME/bin:$PATH" bash "$START" \
  > "$HOME/last_out.txt" 2>&1
rc=$?
check "$rc" 1 "unblocked canary exits 1"
grep -q "checkout guard did NOT block" "$HOME/last_out.txt"
check $? 0 "red canary names the failed guarantee"
grep -q "call a TA" "$HOME/last_out.txt"
check $? 0 "red canary escalates to a TA on repeat"
[ ! -f "$HOME/hermes_ran" ]
check $? 0 "Hermes never started with the guard unproven"
guard; rm -rf "${HOME:?}/bin" "$HOME/hermes_ran"

echo "[21] B22: checkout-guard extension files are sane"
python3 - "$REPO" <<'PY'
import json, sys
from pathlib import Path
ext = Path(sys.argv[1]) / "tools" / "checkout_guard_extension"
rules = json.loads((ext / "rules.json").read_text(encoding="utf-8"))
assert isinstance(rules, list)
required = {"||amazon.in/gp/buy/", "||amazon.in/checkout/",
            "||amazon.in/gp/product/one-click/",
            "||amazon.in/hz/mobile/checkout", "||amazon.in/gp/aw/buy"}
pats = {r["condition"]["urlFilter"] for r in rules}
assert pats == required, pats ^ required
assert not any("/gp/cart" in p for p in pats), "cart must stay untouched"
assert all(p.startswith("||amazon.in/") for p in pats)
for p in required:
    mains = [r for r in rules if r["condition"]["urlFilter"] == p
             and r["condition"]["resourceTypes"] == ["main_frame"]]
    assert len(mains) == 1 and mains[0]["action"]["type"] == "redirect" \
        and mains[0]["action"]["redirect"]["extensionPath"] \
        == "/blocked.html", p
    others = [r for r in rules if r["condition"]["urlFilter"] == p
              and r not in mains]
    assert len(others) == 1 and others[0]["action"]["type"] == "block", p
    assert set(others[0]["condition"]["resourceTypes"]) == \
        {"sub_frame", "xmlhttprequest", "other"}, p
ids = [r["id"] for r in rules]
assert len(ids) == len(set(ids)), "duplicate rule ids"
man = json.loads((ext / "manifest.json").read_text(encoding="utf-8"))
assert man["manifest_version"] == 3
assert man["permissions"] == ["declarativeNetRequest"]
assert man["host_permissions"] == ["*://*.amazon.in/*"]
assert man["declarative_net_request"]["rule_resources"][0]["path"] \
    == "rules.json"
assert "background" not in man and "content_scripts" not in man, \
    "the extension must stay logic-free (auditable in one screen)"
blocked = (ext / "blocked.html").read_text(encoding="utf-8")
assert "add items to the cart only" in blocked
assert "http://" not in blocked and "https://" not in blocked, \
    "blocked.html must load no external resources"
PY
check $? 0 "rules cover the five pipelines, spare the cart; manifest minimal; blocked.html self-contained"

echo "[22] consent acknowledgment: one-time typed AGREE before the first run"
mkenv 1
rm -f "$HOME/dtlab/.consent_ack"
rc=$(run 'P_FIRST\neconomy\nnope\n')
check "$rc" 1 "refusing the acknowledgment exits 1"
grep -q "CONSENT_AND_DATA_USE" "$HOME/last_out.txt"
check $? 0 "gate names the consent sheet"
grep -q "opt-out path" "$HOME/last_out.txt"
check $? 0 "refusal points at the opt-out path and a TA"
[ ! -d "$HOME/dtlab/runs/run1" ] && [ ! -f "$HOME/dtlab/.consent_ack" ]
check $? 0 "nothing started, nothing recorded on refusal"
rc=$(run 'AGREE\ny\ny\n\n')
check "$rc" 0 "typed AGREE proceeds to the run"
[ -f "$HOME/dtlab/.consent_ack" ]
check $? 0 "acknowledgment recorded once under the lab root"
check "$(cat "$HOME/dtlab/runs/run1/condition.txt")" "persona" \
      "run 1 launches only after the acknowledgment"
finish_run
rc=$(run 'y\ny\ny\n\n')
check "$rc" 0 "run 2 proceeds"
! grep -q "One-time acknowledgment" "$HOME/last_out.txt"
check $? 0 "never asked again once recorded"

echo "[23] C1.1: unpinned model IDs fail closed before any prompt or state"
mkenv 1
# restore the shipped fail-closed placeholders (mkenv pins test dummies);
# run WITHOUT DTLAB_TEST so the gate is exercised as shipped
sed "s/DTLAB_MODEL_ECONOMY='claude-eco-test-1'/DTLAB_MODEL_ECONOMY='PIN-AT-DRYRUN'/" \
    "$HOME/dtlab/dtlab_config.env" > "$HOME/dtlab/cfg.tmp" \
  && mv "$HOME/dtlab/cfg.tmp" "$HOME/dtlab/dtlab_config.env"
printf 'P_FIRST\neconomy\n' | bash "$START" > "$HOME/last_out.txt" 2>&1
rc=$?
check "$rc" 1 "PIN-AT-DRYRUN model id exits 1"
grep -q "PIN-AT-DRYRUN" "$HOME/last_out.txt"
check $? 0 "gate names the placeholder and the pin procedure"
grep -q "DTLAB_ALLOW_UNPINNED" "$HOME/last_out.txt"
check $? 0 "gate names the throwaway-test escape"
[ ! -d "$HOME/dtlab/runs/run1" ]
check $? 0 "no run state written on the pin gate"
rc=$(run 'y\ny\n\n')             # order/tier stored; dummy ids in test mode
check "$rc" 0 "test mode proceeds on dummy model ids"
check "$(cat "$HOME/dtlab/runs/run1/model_id.txt")" "test-model-economy" \
      "dummy id recorded in test mode"

echo "[24] C1.1: generated-config mismatch fails closed, leaves no run state"
mkenv 1
# tampered template: hardcoded model instead of the {{MODEL_ID}} slot
printf 'model:\n  provider: "anthropic"\n  id: "some-other-model"\n' \
  > "$HOME/dtlab/hermes_config.template.yaml"
rc=$(run 'P_FIRST\neconomy\ny\ny\n\n')
check "$rc" 1 "config that does not name the assigned model exits 1"
grep -q "does not" "$HOME/last_out.txt" \
  && grep -q "tell a TA" "$HOME/last_out.txt"
check $? 0 "student-legible mismatch message"
[ ! -d "$HOME/dtlab/runs/run1" ]
check $? 0 "no phantom run state after a config mismatch"
rm -rf "$HOME/dtlab/runs"          # missing template also fails closed
rm -f "$HOME/dtlab/hermes_config.template.yaml"
rc=$(run 'y\ny\n\n')
check "$rc" 1 "missing template exits 1"
grep -q "re-run provisioning" "$HOME/last_out.txt"
check $? 0 "missing template points at provisioning"

echo "[25] C1.7: run state written only after the CDP + canary gates"
mkenv 1
mkdir -p "$HOME/bin" "$HOME/dtlab/tools"
printf '#!/usr/bin/env bash\nexit 7\n' > "$HOME/bin/curl"       # CDP dead
# shellcheck disable=SC2016  # $HOME must expand when the stub RUNS
printf '#!/usr/bin/env bash\ntouch "$HOME/hermes_ran"\n' > "$HOME/bin/hermes"
printf '#!/usr/bin/env bash\nexit 0\n' > "$HOME/dtlab/tools/dtlab_browser.sh"
chmod +x "$HOME/bin/curl" "$HOME/bin/hermes" \
         "$HOME/dtlab/tools/dtlab_browser.sh"
printf 'P_FIRST\neconomy\ny\ny\n\n' | env PATH="$HOME/bin:$PATH" \
  bash "$START" > "$HOME/last_out.txt" 2>&1
rc=$?
check "$rc" 1 "dead CDP port exits 1"
[ ! -d "$HOME/dtlab/runs/run1" ]
check $? 0 "CDP failure leaves NO run-1 state (fresh run)"
[ ! -f "$HOME/hermes_ran" ]
check $? 0 "Hermes never started on a dead CDP port"
cat > "$HOME/bin/curl" <<'EOF'
#!/usr/bin/env bash
for a in "$@"; do
  case "$a" in
    *json/new*)   printf '{"id":"C1","url":"about:blank"}'; exit 0 ;;
    *json/list*)  printf '[{"id":"C1","url":"https://www.amazon.in/ap/signin"}]'; exit 0 ;;
    *json/close*) printf 'ok'; exit 0 ;;
  esac
done
exit 0
EOF
chmod +x "$HOME/bin/curl"
printf 'y\ny\n\n' | env PATH="$HOME/bin:$PATH" bash "$START" \
  > "$HOME/last_out.txt" 2>&1
rc=$?
check "$rc" 1 "unblocked canary exits 1"
[ ! -d "$HOME/dtlab/runs/run1" ]
check $? 0 "canary failure leaves NO run-1 state (fresh run)"
cat > "$HOME/bin/curl" <<'EOF'
#!/usr/bin/env bash
for a in "$@"; do
  case "$a" in
    *json/new*)   printf '{"id":"C1","url":"about:blank"}'; exit 0 ;;
    *json/list*)  printf '[{"id":"C1","url":"chrome-extension://abcdefghijklmnop/blocked.html"}]'; exit 0 ;;
    *json/close*) printf 'ok'; exit 0 ;;
  esac
done
exit 0
EOF
chmod +x "$HOME/bin/curl"
printf 'y\ny\n\n' | env PATH="$HOME/bin:$PATH" bash "$START" \
  > "$HOME/last_out.txt" 2>&1
rc=$?
check "$rc" 0 "all gates green -> exit 0 through the hermes stub"
check "$(cat "$HOME/dtlab/runs/run1/condition.txt")" "persona" \
      "run-1 state written only AFTER the gates, before exec"
[ -f "$HOME/hermes_ran" ]
check $? 0 "Hermes started after the state write"
guard; rm -rf "${HOME:?}/bin" "$HOME/hermes_ran"

echo "[26] C1.3: quarantine migration shim + workspace human_picks refusal"
mkenv 1
# fabricate the PRE-quarantine layout: human/, verdicts/, persona_hold/
# directly under ~/dtlab
rm -rf "$HOME/dtlab/quarantine"
mkdir -p "$HOME/dtlab/human" "$HOME/dtlab/persona_hold" \
         "$HOME/dtlab/verdicts"
printf 'task_id\n' > "$HOME/dtlab/human/human_picks.csv"
touch "$HOME/dtlab/human/human_session.jsonl"
printf 'v\n' > "$HOME/dtlab/verdicts/verdicts.csv"
printf 'p\n' > "$HOME/dtlab/persona_hold/old_persona.md"
rc=$(run 'P_FIRST\neconomy\ny\ny\n\n')
check "$rc" 0 "pre-quarantine layout run exits 0 (shim migrates)"
[ -f "$HOME/dtlab/quarantine/human/human_picks.csv" ] \
  && [ -f "$HOME/dtlab/quarantine/verdicts/verdicts.csv" ] \
  && [ -f "$HOME/dtlab/quarantine/persona_hold/old_persona.md" ]
check $? 0 "human, verdicts, and persona_hold migrated under quarantine/"
[ ! -d "$HOME/dtlab/human" ] && [ ! -d "$HOME/dtlab/verdicts" ] \
  && [ ! -d "$HOME/dtlab/persona_hold" ]
check $? 0 "old locations gone after the shim"
mkenv 1
cp "$HOME/dtlab/quarantine/human/human_picks.csv" "$HOME/dtlab/workspace/"
rc=$(run 'P_FIRST\neconomy\ny\ny\n\n')
check "$rc" 1 "human_picks.csv inside the AGENT workspace refuses to launch"
grep -q "quarantine/human" "$HOME/last_out.txt"
check $? 0 "refusal names the quarantine location"

echo "[27] C1.5: bootstrap phase — one questionnaire-blind frozen profile"
mkenv 1
rm -f "$HOME/dtlab/.bootstrap_done" "$HOME/dtlab/purchase_profile.sha256" \
      "$HOME/dtlab/workspace/purchase_profile.md"
rc=$(run 'economy\ny\ny\n\n')
check "$rc" 0 "bootstrap session launches (no grounding-order prompt)"
grep -q "BOOTSTRAP PHASE" "$HOME/last_out.txt"
check $? 0 "phase-0 banner prints the two-invocation flow"
[ ! -d "$HOME/dtlab/runs/run1" ]
check $? 0 "no run-1 state during the bootstrap session"
grep -q 'MARK-BOOTSTRAP' "$HOME/dtlab/runs/bootstrap/hermes_home/SOUL.md"
check $? 0 "bootstrap hermes home carries SOUL_bootstrap"
check "$(cat "$HOME/dtlab/runs/bootstrap/tier.txt")" "economy" \
      "profile writer's tier recorded"
check "$(cat "$HOME/dtlab/runs/bootstrap/model_id.txt")" "claude-eco-test-1" \
      "profile writer's model recorded"
[ -f "$HOME/dtlab/quarantine/persona_hold/persona_survey.md" ] \
  && [ ! -f "$HOME/dtlab/workspace/persona_survey.md" ]
check $? 0 "persona held in quarantine during bootstrap (questionnaire-blind)"
# the bootstrap agent writes the profile + its PROTOCOL-opened log
printf 'PROTOCOL | soul=bootstrap-v1\nprofile written\n' \
  > "$HOME/dtlab/workspace/decision_log.md"
printf '# Purchase profile\n- top categories: y\n' \
  > "$HOME/dtlab/workspace/purchase_profile.md"
rc=$(run 'P_FIRST\ny\ny\n\n')
check "$rc" 0 "second dtlab-start freezes the profile and starts run 1"
grep -q "purchase profile frozen" "$HOME/last_out.txt"
check $? 0 "freeze announced"
[ -f "$HOME/dtlab/.bootstrap_done" ] \
  && [ -s "$HOME/dtlab/purchase_profile.sha256" ]
check $? 0 "freeze marker + hash recorded"
[ ! -w "$HOME/dtlab/workspace/purchase_profile.md" ]
check $? 0 "profile is read-only after the freeze"
check "$(cat "$HOME/dtlab/runs/run1/condition.txt")" "persona" \
      "run 1 started after the freeze"
[ -f "$HOME/dtlab/runs/bootstrap/decision_log.md" ] \
  && [ ! -f "$HOME/dtlab/workspace/decision_log.md" ]
check $? 0 "bootstrap log parked under runs/bootstrap/ (run 1 starts clean)"
[ -f "$HOME/dtlab/runs/run1/purchase_profile.md" ]
check $? 0 "per-run profile snapshot recorded at launch"
finish_run
chmod +w "$HOME/dtlab/workspace/purchase_profile.md"
echo tampered >> "$HOME/dtlab/workspace/purchase_profile.md"
rc=$(run 'y\ny\ny\n\n')
check "$rc" 1 "tampered profile fails every later run closed"
grep -q "changed after the freeze" "$HOME/last_out.txt"
check $? 0 "tamper message names the freeze"
[ ! -d "$HOME/dtlab/runs/run2" ]
check $? 0 "no run-2 state after the tamper refusal"
mkenv 1
rm -f "$HOME/dtlab/.bootstrap_done" "$HOME/dtlab/purchase_profile.sha256" \
      "$HOME/dtlab/workspace/purchase_profile.md"
rc=$(run '\n' DTLAB_SANDBOX=1)
check "$rc" 0 "sandbox run skips phase 0"
[ ! -d "$HOME/dtlab/runs/bootstrap" ]
check $? 0 "no bootstrap state in sandbox mode"

guard
rm -rf "$SANDBOX_HOME"
echo ""; echo "Results: $PASS passed, $FAIL failed"
exit $FAIL
