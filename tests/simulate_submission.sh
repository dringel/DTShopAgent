#!/usr/bin/env bash
# Regression harness: fabricates a complete student environment and runs
# pack_evidence.py through the happy path + violation paths.
#
# SAFETY: the ENTIRE harness runs inside a throwaway sandbox HOME under
# mktemp (pack_evidence.py resolves everything via Path.home()). The real
# home directory is never touched, and every rm -rf is guarded to refuse
# any path outside the sandbox.
#
# Run from repo root:  bash tests/simulate_submission.sh
# shellcheck disable=SC2319  # `[ cond ]; check $?` is the
# harness's deliberate assertion idiom; $? is always the
# immediately preceding test
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PACK="$REPO/tools/pack_evidence.py"
PASS=0; FAIL=0
check(){ if [ "$1" = "$2" ]; then echo "  PASS: $3"; PASS=$((PASS+1));
         else echo "  FAIL: $3 (got $1, want $2)"; FAIL=$((FAIL+1)); fi; }

SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/dtlab-harness.XXXXXX")"
export HOME="$SANDBOX"
guard(){  # abort unless $HOME is still inside the sandbox before any rm -rf
  case "$HOME" in
    "$SANDBOX"*) ;;
    *) echo "FATAL: HOME escaped the sandbox ($HOME) — refusing to delete."
       exit 99 ;;
  esac
}

# portable in-place replace (BSD/macOS sed -i differs from GNU)
replace(){ python3 - "$1" "$2" "$3" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]).expanduser()
p.write_text(p.read_text().replace(sys.argv[2], sys.argv[3]))
PY
}

mkenv(){
guard
rm -rf "$HOME/dtlab" "$HOME/.hermes"
mkdir -p "$HOME/dtlab/workspace" "$HOME/dtlab/evidence" "$HOME/dtlab/human" \
         "$HOME/.hermes/sessions"
cp "$REPO/dtlab_config.env" "$HOME/dtlab/dtlab_config.env"
# fixtures use their OWN compact 3-task config: the validation chain is
# config-driven (check 15 proves counts follow the config), so the
# harness stays stable when the teaching team changes the shipped
# 5-category set in the repo's tasks_config.csv
printf 'task_id,frame,short_name,product_type,category_class,budget_min_inr,budget_max_inr\n1,Self-purchase,CatA,item A,utilitarian,0,600\n2,Self-purchase,CatB,item B,utilitarian,1000,3000\n3,Self-purchase,CatC,item C,hedonic,0,1500\n' > "$HOME/dtlab/tasks_config.csv"
cd "$HOME/dtlab/workspace" || exit 1
printf "student_id,item_code,construct,question,answer,constraint\nDT2026-999,D01,Demo,Age?,26-35,0\n" > persona_survey.csv
echo "# p" > persona_survey.md
printf "# Purchase profile (agent-extracted)\n- top categories: x\n" > purchase_profile.md
printf "# t\n## Task 1\nfilled\n\n---\nStandardized agent prompt (paste into Hermes after /browser connect):\n\nRead persona_survey.md and purchase_profile.md again before starting.\n" > tasks.md
printf "# soul stub for hashing\n" > SOUL.md
printf "log citing D01 and PP; candidates search#1..4\n" > decision_log.md
printf "task_id,title,asin,price_inr,sponsored\n1,A,B07GYLZ1ZN,299,0\n2,B,B08YRWN3RD,1299,1\n3,C,B00R9QLRRO,1450,0\n" > agent_picks.csv
printf "# c\n## Task 1\nVerdict: identical\nMy pick rating (1-10): 7\nAgent pick rating (1-10): 9\nt\n## Task 2\nVerdict: inferior\nt\n## Task 3\nVerdict: better\nt\n## Overall\nall answered\n" > comparison.md
printf '{"type":"product_view","asin":"B07GYLZ1ZN"}\n{"type":"product_view","asin":"B09YLFGBLL"}\n{"type":"product_view","asin":"B07D75V2GH"}\n' > "$HOME/dtlab/human/human_session.jsonl"
printf "task_id,title,asin,url,price_inr,reasoning\n1,A,B07GYLZ1ZN,u,299,r\n2,S,B09YLFGBLL,u,1490,r\n3,K,B07D75V2GH,u,780,r\n" > "$HOME/dtlab/human/human_picks.csv"
echo H_FIRST > "$HOME/dtlab/arm.txt"
sleep 0.2; touch "$HOME/dtlab/.run_started"; sleep 0.1
echo '{"t":1}' > "$HOME/.hermes/sessions/s.jsonl"
python3 - <<'PY'
import zlib,struct,os
def c(t,d): return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d))
raw=b''.join(b'\x00'+b'\xf0'*600 for _ in range(100))
png=b'\x89PNG\r\n\x1a\n'+c(b'IHDR',struct.pack('>IIBBBBB',200,100,8,2,0,0,0))+c(b'IDAT',zlib.compress(raw))+c(b'IEND',b'')
open(os.path.expanduser('~/dtlab/evidence/cart.png'),'wb').write(png)
PY
}

mkenv_ablation(){
mkenv
mkdir -p "$HOME/dtlab/runs/run1" "$HOME/dtlab/runs/run2" "$HOME/dtlab/persona_hold"
echo P_FIRST > "$HOME/dtlab/persona_order.txt"
echo persona > "$HOME/dtlab/runs/run1/condition.txt"
echo ablated > "$HOME/dtlab/runs/run2/condition.txt"
# run1 = persona run: adopt mkenv's default (item-citing) artifacts
mv "$HOME/dtlab/workspace/decision_log.md" "$HOME/dtlab/runs/run1/"
mv "$HOME/dtlab/workspace/agent_picks.csv" "$HOME/dtlab/runs/run1/"
# run2 = ablated run, artifacts still in the workspace (packer adopts them)
printf "log citing PP only; candidates search#1..4\n" > "$HOME/dtlab/workspace/decision_log.md"
printf "task_id,title,asin,price_inr,sponsored\n1,A,B07GYLZ1ZN,299,0\n2,X,B0AAAA1111,1200,0\n3,Y,B0BBBB2222,1400,0\n" > "$HOME/dtlab/workspace/agent_picks.csv"
# P_FIRST ends on the ablated run -> persona files sit in the hold dir
mv "$HOME/dtlab/workspace/persona_survey.csv" "$HOME/dtlab/persona_hold/"
mv "$HOME/dtlab/workspace/persona_survey.md"  "$HOME/dtlab/persona_hold/"
cat > "$HOME/dtlab/workspace/comparison.md" <<'EOF'
# c
## Task 1 (persona run)
Verdict: identical
t
## Task 1 (ablated run)
Verdict: identical
t
## Task 2 (persona run)
Verdict: inferior
t
## Task 2 (ablated run)
Verdict: equivalent
t
## Task 3 (persona run)
Verdict: better
t
## Task 3 (ablated run)
Verdict: inferior
t
## Head-to-head
Task 1 winner: tie
Task 2 winner: ablated
Task 3 winner: persona
same-product notes
## Overall
all answered
EOF
}

mkenv_4run(){
mkenv
mkdir -p "$HOME/dtlab/runs/run1" "$HOME/dtlab/runs/run2" \
         "$HOME/dtlab/runs/run3" "$HOME/dtlab/runs/run4" \
         "$HOME/dtlab/persona_hold"
echo P_FIRST  > "$HOME/dtlab/persona_order_day1.txt"
echo NP_FIRST > "$HOME/dtlab/persona_order_day2.txt"
# day 1 (economy): run1 persona, run2 ablated; day 2 (frontier, NP_FIRST):
# run3 ablated, run4 persona (artifacts left in the workspace -> adopted)
for i in 1 2 3 4; do
  case $i in 1|2) t=economy ;; *) t=frontier ;; esac
  case $i in 1|4) c=persona ;; *) c=ablated ;; esac
  echo "$c" > "$HOME/dtlab/runs/run$i/condition.txt"
  echo "$t" > "$HOME/dtlab/runs/run$i/tier.txt"
  date -u +%FT%TZ > "$HOME/dtlab/runs/run$i/started_at.txt"
done
rm -f "$HOME/dtlab/workspace/decision_log.md" \
      "$HOME/dtlab/workspace/agent_picks.csv"
printf "log citing D01 and PP; candidates search#1..4\n" > "$HOME/dtlab/runs/run1/decision_log.md"
printf "task_id,title,asin,price_inr,sponsored\n1,A,B07GYLZ1ZN,299,0\n2,B,B08YRWN3RD,1299,1\n3,C,B00R9QLRRO,1450,0\n" > "$HOME/dtlab/runs/run1/agent_picks.csv"
printf "log citing PP only\n" > "$HOME/dtlab/runs/run2/decision_log.md"
printf "task_id,title,asin,price_inr,sponsored\n1,A,B07GYLZ1ZN,299,0\n2,X,B0AAAA1111,1200,0\n3,Y,B0BBBB2222,1400,0\n" > "$HOME/dtlab/runs/run2/agent_picks.csv"
printf "log citing PP only, frontier\n" > "$HOME/dtlab/runs/run3/decision_log.md"
printf "task_id,title,asin,price_inr,sponsored\n1,Q,B0CCCC3333,310,0\n2,X,B0AAAA1111,1200,0\n3,Y,B0BBBB2222,1400,0\n" > "$HOME/dtlab/runs/run3/agent_picks.csv"
# run4 = final run: artifacts still in the workspace, packer adopts them
printf "log citing D01 and PP, frontier\n" > "$HOME/dtlab/workspace/decision_log.md"
printf "task_id,title,asin,price_inr,sponsored\n1,A,B07GYLZ1ZN,299,0\n2,B,B08YRWN3RD,1299,0\n3,Z,B0DDDD4444,1350,0\n" > "$HOME/dtlab/workspace/agent_picks.csv"
# four cart screenshots + parsed carts for run1 (match) and run2 (mismatch)
for i in 1 2 3 4; do
  cp "$HOME/dtlab/evidence/cart.png" "$HOME/dtlab/evidence/cart_run$i.png"
done
printf '{"schema":"dtlab-cart-v1","run":1,"items":[{"asin":"B07GYLZ1ZN","title":"A","unit_price":299,"qty":1},{"asin":"B08YRWN3RD","title":"B","unit_price":1299,"qty":1},{"asin":"B00R9QLRRO","title":"C","unit_price":1450,"qty":1}]}\n' > "$HOME/dtlab/evidence/cart_run1.json"
printf '{"schema":"dtlab-cart-v1","run":2,"items":[{"asin":"B07GYLZ1ZN","title":"A","unit_price":299,"qty":1}]}\n' > "$HOME/dtlab/evidence/cart_run2.json"
# 2x2 fallback memo: 12 verdict blocks + synthesis + head-to-heads
python3 - <<'PY'
import os
human = {"1": "B07GYLZ1ZN", "2": "B09YLFGBLL", "3": "B07D75V2GH"}
picks = {
    ("persona", "economy"):  {"1": "B07GYLZ1ZN", "2": "B08YRWN3RD", "3": "B00R9QLRRO"},
    ("ablated", "economy"):  {"1": "B07GYLZ1ZN", "2": "B0AAAA1111", "3": "B0BBBB2222"},
    ("ablated", "frontier"): {"1": "B0CCCC3333", "2": "B0AAAA1111", "3": "B0BBBB2222"},
    ("persona", "frontier"): {"1": "B07GYLZ1ZN", "2": "B08YRWN3RD", "3": "B0DDDD4444"},
}
verdict = {
    ("1", "persona", "economy"): "identical",
    ("2", "persona", "economy"): "inferior",
    ("3", "persona", "economy"): "better",
    ("1", "ablated", "economy"): "identical",
    ("2", "ablated", "economy"): "equivalent",
    ("3", "ablated", "economy"): "inferior",
    ("1", "ablated", "frontier"): "equivalent",
    ("2", "ablated", "frontier"): "equivalent",
    ("3", "ablated", "frontier"): "inferior",
    ("1", "persona", "frontier"): "identical",
    ("2", "persona", "frontier"): "better",
    ("3", "persona", "frontier"): "equivalent",
}
L = ["# c"]
for t in ("1", "2", "3"):
    for tier in ("economy", "frontier"):
        for cond in ("persona", "ablated"):
            L += [f"## Task {t} ({cond} run, {tier})",
                  f"Verdict: {verdict[(t, cond, tier)]}",
                  "My pick rating (1-10): 7",
                  "Agent pick rating (1-10): 6",
                  "Attribution: real", ""]
    L += [f"## Task {t} synthesis (across the four runs)",
          "pattern explained", ""]
L += ["## Head-to-head"]
for t in ("1", "2", "3"):
    L += [f"Task {t} winner (economy): persona",
          f"Task {t} winner (frontier): tie",
          f"Task {t} better model (persona): frontier",
          f"Task {t} better model (ablated): same"]
L += ["notes", "## Overall", "all answered", ""]
open(os.path.expanduser("~/dtlab/workspace/comparison.md"), "w").write("\n".join(L))
PY
}

echo "[1] happy path (H_FIRST)"
mkenv; python3 "$PACK" >/dev/null 2>&1; check $? 0 "valid pack exits 0"

echo "[2] verdict/ASIN cross-check"
mkenv; replace "$HOME/dtlab/workspace/comparison.md" "Verdict: identical" "Verdict: equivalent"
python3 "$PACK" 2>&1 | grep -q "must be 'identical'"; check $? 0 "same-ASIN wrong verdict caught"

echo "[3] bias quarantine"
mkenv; cp "$HOME/dtlab/human/human_picks.csv" "$HOME/dtlab/workspace/"
python3 "$PACK" 2>&1 | grep -q "quarantine violated"; check $? 0 "leak into agent workspace caught"

echo "[4] A_FIRST ordering violation (backdated human session)"
mkenv; echo A_FIRST > "$HOME/dtlab/arm.txt"
python3 - <<'PY'
import os,time
t=time.time()-7200
os.utime(os.path.expanduser('~/dtlab/human/human_session.jsonl'),(t,t))
PY
python3 "$PACK" 2>&1 | grep -q "A_FIRST arm: human session predates"; check $? 0 "reverse-order violation caught"

echo "[5] verdict placeholder must not cascade across sections"
mkenv; replace "$HOME/dtlab/workspace/comparison.md" "Verdict: identical" "Verdict: {better|identical|equivalent|inferior}"
OUT="$(python3 "$PACK" 2>&1)"
echo "$OUT" | grep -q "each Task needs"; check $? 0 "missing Task-1 verdict caught"
! echo "$OUT" | grep -q "must be 'identical'"; check $? 0 "Task 2's verdict NOT mis-assigned to Task 1"

echo "[6] leftover template placeholders in a task section"
mkenv; replace "$HOME/dtlab/workspace/comparison.md" "## Task 2
Verdict: inferior
t" "## Task 2
Verdict: inferior
Attribution: {...}"
python3 "$PACK" 2>&1 | grep -q "Task 2 still contains template placeholders"; check $? 0 "brace placeholders caught per-section"

echo "[7] content redaction of packed logs"
mkenv
printf '{"msg":"key is sk-ant-api03-AAAABBBBCCCCDDDD and email test@example.com, Deliver to Priya"}\n' > "$HOME/.hermes/sessions/s2.jsonl"
python3 "$PACK" >/dev/null 2>&1; check $? 0 "redaction does not fail a valid pack"
python3 - <<'PY'; check $? 0 "key redacted from zip + redaction_report in manifest"
import json,sys,zipfile,os
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
names=[n for n in z.namelist() if 's2.jsonl' in n]
log=z.read(names[0]).decode()
man=json.loads(z.read('DT2026-999/manifest.json'))
rr=man['redaction_report']
assert 'sk-ant-' not in log and '[REDACTED-API-KEY]' in log, log
assert 'test@example.com' not in log and '[REDACTED-EMAIL]' in log, log
entry=[v for k,v in rr.items() if 's2.jsonl' in k][0]
assert entry['api_keys_redacted']>=1 and entry['pii_flags'].get('emails_redacted',0)>=1
assert entry['pii_flags'].get('deliver_to',0)>=1
assert man['model_tier']=='frontier' and 'environment' in man
assert man['ratings']['1']=={'self':7,'agent':9}
assert 'config_snapshot/dtlab_config.env' in man['file_inventory']
assert man['file_inventory']['comparison.md']['mtime_utc']
assert 'DT2026-999/SUBMISSION_INFO.txt' in z.namelist()
sys.exit(0)
PY

echo "[8] human pick with malformed ASIN"
mkenv; replace "$HOME/dtlab/human/human_picks.csv" "B09YLFGBLL" "notanasin"
python3 "$PACK" 2>&1 | grep -q "human pick task 2"; check $? 0 "bad human ASIN caught"

echo "[9] model tier recorded from tier.txt"
mkenv; echo economy > "$HOME/dtlab/tier.txt"
python3 "$PACK" >/dev/null 2>&1
python3 -c "
import json,zipfile,os
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
assert json.loads(z.read('DT2026-999/manifest.json'))['model_tier']=='economy'
"; check $? 0 "tier.txt=economy lands in manifest"

echo "[10] malformed student_id never reaches file paths"
mkenv; replace "$HOME/dtlab/workspace/persona_survey.csv" "DT2026-999" "../evil"
python3 "$PACK" 2>&1 | grep -q "does not match the course pattern"; check $? 0 "path-unsafe student_id rejected"

echo "[11] ablation factor happy path (persona files in hold dir)"
mkenv_ablation; python3 "$PACK" >/dev/null 2>&1; check $? 0 "valid two-run pack exits 0"
python3 - <<'PY'; check $? 0 "ablation manifest complete (conditions, 6 verdicts, head-to-head, overlap)"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
ab=m['ablation']
assert ab['enabled'] and ab['persona_order']=='P_FIRST'
assert ab['run_conditions']=={'run1':'persona','run2':'ablated'}
assert len(m['verdicts'])==6 and m['verdicts']['2_ablated']=='equivalent'
assert ab['head_to_head']=={'1':'tie','2':'ablated','3':'persona'}
assert ab['agent_pick_overlap_tasks']==['1']
assert ab['manipulation_check_cited_codes']==[]
assert set(m['contamination_index'])=={'persona','ablated'}
assert 'run1/decision_log.md' in m['sha256'] and 'run2/agent_picks.csv' in m['sha256']
sys.exit(0)
PY

echo "[12] ablated run citing a persona item code is caught"
mkenv_ablation
printf "rejected: violates D01 — user avoids X\n" >> "$HOME/dtlab/workspace/decision_log.md"
python3 "$PACK" 2>&1 | grep -q "ablation condition was violated"; check $? 0 "manipulation check fires"

echo "[13] ablation mode rejects the single-run comparison template"
mkenv_ablation
printf "# c\n## Task 1\nVerdict: identical\nt\n## Task 2\nVerdict: inferior\nt\n## Task 3\nVerdict: better\nt\n## Overall\nall answered\n" > "$HOME/dtlab/workspace/comparison.md"
python3 "$PACK" 2>&1 | grep -q "BOTH runs"; check $? 0 "wrong template caught with a clear message"

echo "[14] machine-parsed candidate + search lines (CAND/SRCH protocol)"
mkenv
printf 'SRCH | task=1 | query=spf 50 sunscreen gel | filters=sort: avg. review\nCAND | task=1 | asin=B07GYLZ1ZN | category=Health > Sunscreen | price=289 | sponsored=0 | source=search#1\nCAND | task=1 | asin=B0ZZZZZZZ9 | category=Health > Sunscreen | price=340 | sponsored=1 | source=search#3\n' >> "$HOME/dtlab/workspace/decision_log.md"
python3 "$PACK" >/dev/null 2>&1; check $? 0 "pack with CAND+SRCH lines exits 0"
python3 - <<'PY'; check $? 0 "candidates + searches in manifest; compliant case has no warnings"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
c=m['candidates']['single']['1']
assert len(c)==2 and c[0]['asin']=='B07GYLZ1ZN'
assert c[1]['sponsored']=='1' and 'Sunscreen' in c[0]['category']
s=m['searches']['single']['1']
assert len(s)==1 and s[0]['query']=='spf 50 sunscreen gel'
assert 'review' in s[0]['filters']
assert m['warnings']==[]
sys.exit(0)
PY
mkenv
printf 'CAND | task=1 | asin=B07GYLZ1ZN | category=H | price=289 | sponsored=0 | source=search#1\n' >> "$HOME/dtlab/workspace/decision_log.md"
python3 "$PACK" >/dev/null 2>&1
python3 -c "
import json,zipfile,os
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
assert any('SRCH' in w for w in m['warnings'])
"; check $? 0 "CAND without SRCH warns about missing search lines"
mkenv; python3 "$PACK" >/dev/null 2>&1
python3 -c "
import json,zipfile,os
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
assert any('CAND' in w for w in m['warnings'])
"; check $? 0 "missing CAND lines recorded as warning, not failure"

echo "[15] 6-task config drives the validation counts"
mkenv
cp "$REPO/tasks_config_6task_example.csv" "$HOME/dtlab/tasks_config.csv"
python3 "$PACK" 2>&1 | grep -q "agent_picks.csv has 3 rows, need 6"; check $? 0 "task count comes from tasks_config.csv"

echo "[16] sandbox run packs cleanly and is stamped for exclusion"
mkenv
echo sandbox > "$HOME/dtlab/sandbox.txt"
rm -f "$HOME/dtlab/arm.txt"    # smoke-test case: no arm assigned
replace "$HOME/dtlab/workspace/agent_picks.csv" "B07GYLZ1ZN" "SBX0001000"
replace "$HOME/dtlab/human/human_picks.csv"     "B07GYLZ1ZN" "SBX0001000"
replace "$HOME/dtlab/human/human_session.jsonl" "B07GYLZ1ZN" "SBX0001000"
python3 "$PACK" >/dev/null 2>&1; check $? 0 "sandbox pack exits 0 without an arm"
python3 - <<'PY'; check $? 0 "manifest stamped sandbox + report banner present"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
assert m['sandbox'] is True and m['arm']=='SANDBOX'
assert 'SANDBOX RUN' in z.read('DT2026-999/report.html').decode()
info=z.read('DT2026-999/SUBMISSION_INFO.txt').decode()
assert 'EXCLUDED from the research dataset' in info
sys.exit(0)
PY

echo "[17] task-doc generator round-trip (no brace artifacts, parseable markers)"
GEN="$HOME/gen_templates"
python3 "$REPO/tools/make_task_docs.py" --config "$REPO/tasks_config.csv" --outdir "$GEN" >/dev/null
! grep -q '{{' "$GEN"/*.md; check $? 0 "no double-brace artifacts in generated templates"
[ "$(grep -c '^## Task' "$GEN/comparison.md")" = "5" ]; check $? 0 "generated comparison has one block per task (5-category set)"
# 2x2 ablation template: 4 cell blocks + 1 synthesis section per task
[ "$(grep -c '^## Task' "$GEN/comparison_ablation.md")" = "25" ]; check $? 0 "generated ablation template has five sections per task"
grep -q 'Verdict: {better|identical|equivalent|inferior}' "$GEN/comparison.md" \
  && grep -q 'My pick rating (1-10): {N}' "$GEN/comparison.md" \
  && grep -q 'Task 5 winner (frontier): {persona|ablated|tie}' "$GEN/comparison_ablation.md" \
  && grep -q 'Task 5 better model (ablated): {frontier|economy|same}' "$GEN/comparison_ablation.md"
check $? 0 "machine-parsed markers intact in generated templates"
grep -q 'IN THE ORDER they appear' "$GEN/tasks.md"
check $? 0 "standardized prompts instruct in-order shopping"
for f in tasks.md comparison.md comparison_ablation.md; do
  cmp -s "$GEN/$f" "$REPO/templates/$f"
  check $? 0 "shipped templates/$f is byte-identical to generator output"
done

echo "[18] four-run 2x2 happy path (memo fallback; run-4 artifacts adopted)"
mkenv_4run
OUT18="$(DTLAB_MODEL_ID_DAY1=claude-haiku-x DTLAB_MODEL_ID_DAY2=claude-sonnet-y python3 "$PACK" 2>&1)"
check $? 0 "valid four-run pack exits 0"
echo "$OUT18" | grep -q "run2: agent_picks.csv items not found in the captured cart"
check $? 0 "cart cross-check mismatch warns, names the run"
python3 - <<'PY'; check $? 0 "2x2 manifest complete (12 verdicts, 4 hth families, overlap sets, per-cell contamination, cart_verified, per-run model IDs)"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
ab=m['ablation']
assert ab['enabled'] and ab['design']=='2x2'
assert ab['grounding_order']=={'day1':'P_FIRST','day2':'NP_FIRST'}
assert ab['run_conditions']=={'run1':'persona','run2':'ablated','run3':'ablated','run4':'persona'}
assert ab['run_tiers']=={'run1':'economy','run2':'economy','run3':'frontier','run4':'frontier'}
assert len(m['verdicts'])==12 and m['verdicts']['2_ablated_frontier']=='equivalent'
assert m['verdicts']['3_persona_economy']=='better'
assert m['ratings']['1_persona_economy']=={'self':7,'agent':6}
assert ab['head_to_head']['grounding_economy']=={'1':'persona','2':'persona','3':'persona'}
assert ab['head_to_head']['grounding_frontier']=={'1':'tie','2':'tie','3':'tie'}
assert ab['head_to_head']['tier_persona']=={'1':'frontier','2':'frontier','3':'frontier'}
assert ab['head_to_head']['tier_ablated']=={'1':'same','2':'same','3':'same'}
assert ab['pick_overlap']=={'within_economy':['1'],'within_frontier':[],
                            'within_persona':['1','2'],'within_ablated':['2','3']}
assert ab['manipulation_check_cited_codes']=={'run2':[],'run3':[]}
assert ab['cart_verified']=={'run1':True,'run2':False,'run3':None,'run4':None}
assert set(m['contamination_index'])=={'persona_economy','ablated_economy','ablated_frontier','persona_frontier'}
assert m['environment']['model_id_by_run']=={'run1':'claude-haiku-x','run2':'claude-haiku-x','run3':'claude-sonnet-y','run4':'claude-sonnet-y'}
assert 'run4/decision_log.md' in m['sha256'] and 'run3/agent_picks.csv' in m['sha256']
assert 'screenshots/cart_run1.json' in m['sha256']
sys.exit(0)
PY

echo "[19] missing run 4 is an issue naming the run; the pack still builds"
mkenv_4run
guard; rm -rf "$HOME/dtlab/runs/run4" "$HOME/dtlab/DT2026-999_evidence.zip"
OUT19="$(python3 "$PACK" 2>&1)"; RC19=$?
check "$([ "$RC19" -ne 0 ]; echo $?)" 0 "pack exits non-zero"
echo "$OUT19" | grep -q "run4 missing"; check $? 0 "issue names run4"
[ -f "$HOME/dtlab/DT2026-999_evidence.zip" ]; check $? 0 "zip still produced (partial packs are data)"

echo "[20] manipulation check fires on EITHER ablated log (day-2 run)"
mkenv_4run
printf "rejected: violates D01 — user avoids X\n" >> "$HOME/dtlab/runs/run3/decision_log.md"
python3 "$PACK" 2>&1 | grep -q "run3) cites persona item codes"; check $? 0 "run-3 citation caught"

echo "[21] dtlab-verdict files are the primary verdict source"
mkenv_4run
rm -f "$HOME/dtlab/workspace/comparison.md"
python3 - <<'PY'
import csv, os
verdict = {
    ("1","persona","economy"):"identical",("2","persona","economy"):"inferior",
    ("3","persona","economy"):"better",("1","ablated","economy"):"identical",
    ("2","ablated","economy"):"equivalent",("3","ablated","economy"):"inferior",
    ("1","ablated","frontier"):"equivalent",("2","ablated","frontier"):"equivalent",
    ("3","ablated","frontier"):"inferior",("1","persona","frontier"):"identical",
    ("2","persona","frontier"):"better",("3","persona","frontier"):"equivalent",
}
ws = os.path.expanduser("~/dtlab/workspace")
with open(f"{ws}/verdicts.csv","w",newline="") as f:
    w = csv.writer(f)
    w.writerow(["student_id","task_id","condition","tier","verdict",
                "rating_self","rating_agent","rationale"])
    for (t,c,ti),v in verdict.items():
        w.writerow(["DT2026-999",t,c,ti,v,"8","5","because reasons"])
with open(f"{ws}/head_to_heads.csv","w",newline="") as f:
    w = csv.writer(f)
    w.writerow(["task_id","contrast","winner"])
    for t in ("1","2","3"):
        w.writerow([t,"grounding_economy","persona"])
        w.writerow([t,"grounding_frontier","tie"])
        w.writerow([t,"tier_persona","frontier"])
        w.writerow([t,"tier_ablated","same"])
open(f"{ws}/overall_reflections.md","w").write("# Overall reflections\nanswers\n")
PY
python3 "$PACK" >/dev/null 2>&1; check $? 0 "pack from verdicts.csv exits 0 without comparison.md"
python3 - <<'PY'; check $? 0 "verdict_source=verdicts_csv; rationales passed through; hth from head_to_heads.csv"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
assert m['verdict_source']=='verdicts_csv'
assert len(m['verdicts'])==12 and m['verdicts']['2_persona_frontier']=='better'
assert m['ratings']['3_ablated_frontier']=={'self':8,'agent':5}
assert m['rationales']['1_persona_economy']=='because reasons'
assert m['ablation']['head_to_head']['tier_persona']=={'1':'frontier','2':'frontier','3':'frontier'}
assert 'DT2026-999/verdicts.csv' in z.namelist()
assert 'DT2026-999/overall_reflections.md' in z.namelist()
sys.exit(0)
PY
mkenv_4run
rm -f "$HOME/dtlab/workspace/comparison.md"
printf "student_id,task_id,condition,tier,verdict,rating_self,rating_agent,rationale\nDT2026-999,1,persona,economy,identical,11,5,r\n" > "$HOME/dtlab/workspace/verdicts.csv"
python3 "$PACK" 2>&1 | grep -q "rating '11' out of range"; check $? 0 "verdicts.csv rating range validated"

echo "[22] CAND source strings normalize into provenance buckets"
mkenv
printf 'CAND | task=1 | asin=B07GYLZ1ZN | category=H | price=289 | sponsored=0 | source=carousel:Frequently bought together\nCAND | task=2 | asin=B08YRWN3RD | category=E | price=1299 | sponsored=0 | source=buy_again\nCAND | task=3 | asin=B00R9QLRRO | category=G | price=1450 | sponsored=0 | source=weird-new-surface\n' >> "$HOME/dtlab/workspace/decision_log.md"
python3 "$PACK" >/dev/null 2>&1
python3 - <<'PY'; check $? 0 "raw source kept + bucket stored (carousel/buy_again/other)"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
c=m['candidates']['single']
assert c['1'][0]['source_bucket']=='carousel' and c['1'][0]['source'].startswith('carousel:')
assert c['2'][0]['source_bucket']=='buy_again'
assert c['3'][0]['source_bucket']=='other'
sys.exit(0)
PY

echo "[24] randomized task order: recorded when respected, warned when re-sorted"
mkenv
DERIVED=$(python3 -c "
import hashlib
print(','.join(sorted(['1','2','3'], key=lambda t: hashlib.sha256(f'DT2026-999|{t}'.encode()).hexdigest())))")
REVERSED=$(python3 -c "print(','.join(reversed('$DERIVED'.split(','))))")
write_tasks_md(){  # $1 = comma-separated task order
  python3 - "$1" <<'PY'
import os, sys
order = sys.argv[1].split(",")
secs = "".join(f"## Task {t}\nfilled section {t}\n\n" for t in order)
open(os.path.expanduser("~/dtlab/workspace/tasks.md"), "w").write(
    "# t\n\n" + secs +
    "---\nStandardized agent prompt (paste into Hermes after /browser connect):\n\nRead persona_survey.md and purchase_profile.md again before starting.\n")
PY
}
write_tasks_md "$REVERSED"
python3 "$PACK" 2>&1 | grep -q "re-sorted by hand"; check $? 0 "hand-re-sorted tasks.md draws a warning"
write_tasks_md "$DERIVED"
OUT24="$(python3 "$PACK" 2>&1)"
! echo "$OUT24" | grep -q "re-sorted by hand"; check $? 0 "assigned order passes without warning"
python3 - <<'PY'; check $? 0 "manifest records task_order == task_order_expected"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
assert m['task_order'] is not None and m['task_order']==m['task_order_expected']
assert sorted(m['task_order'])==['1','2','3']
sys.exit(0)
PY

echo "[25] shopping-process length: human timing + per-run durations"
mkenv_4run
python3 - <<'PY'   # ts'd clickstream: one cart_add per task
import json, os, hashlib
order = sorted(["1","2","3"], key=lambda t: hashlib.sha256(
    f"DT2026-999|{t}".encode()).hexdigest())
ev = [{"ts": "2026-09-25T10:00:00+00:00", "type": "session_start"},
      {"ts": "2026-09-25T10:01:00+00:00", "type": "search", "query": "q"},
      {"ts": "2026-09-25T10:02:00+00:00", "type": "product_view",
       "asin": "B07GYLZ1ZN"},
      {"ts": "2026-09-25T10:03:00+00:00", "type": "filter_sort",
       "url": "/s?rh=x"},
      {"ts": "2026-09-25T10:08:00+00:00", "type": "cart_add",
       "asin": "B07GYLZ1ZN"},
      {"ts": "2026-09-25T10:10:00+00:00", "type": "product_view",
       "asin": "B09YLFGBLL"},
      {"ts": "2026-09-25T10:20:00+00:00", "type": "cart_add",
       "asin": "B09YLFGBLL"},
      {"ts": "2026-09-25T10:22:00+00:00", "type": "product_view",
       "asin": "B07D75V2GH"},
      {"ts": "2026-09-25T10:26:00+00:00", "type": "cart_add",
       "asin": "B07D75V2GH"},
      {"ts": "2026-09-25T10:27:00+00:00", "type": "session_end"}]
with open(os.path.expanduser("~/dtlab/human/human_session.jsonl"), "w") as f:
    for e in ev:
        f.write(json.dumps(e) + "\n")
PY
python3 "$PACK" >/dev/null 2>&1
python3 - <<'PY'; check $? 0 "cart-add fallback: per-task minutes/searches/views/filters + per-run durations"
import json,zipfile,os,sys,hashlib
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
p=m['process']
assert p['human']['duration_min']==27.0
assert p['human']['filter_sorts']==1 and p['human']['cart_adds']==3
assert p['human']['attribution']=='cart_add_segments'
order = sorted(["1","2","3"], key=lambda t: hashlib.sha256(
    f"DT2026-999|{t}".encode()).hexdigest())
pt=p['human']['per_task']
assert pt[order[0]]=={'minutes':8.0,'searches':1,'product_views':1,'filter_sorts':1}
assert pt[order[1]]=={'minutes':12.0,'searches':0,'product_views':1,'filter_sorts':0}
assert pt[order[2]]['minutes']==6.0
assert all(p['runs'][rn]['duration_min'] is not None
           for rn in ('run1','run2','run3','run4'))
sys.exit(0)
PY
python3 - <<'PY'   # guided-session log: explicit task_start/task_end markers
import json, os, hashlib
order = sorted(["1","2","3"], key=lambda t: hashlib.sha256(
    f"DT2026-999|{t}".encode()).hexdigest())
T = "2026-09-25T10:%02d:00+00:00"
ev = [{"ts": T % 0, "type": "task_start", "task_id": order[0]},
      {"ts": T % 1, "type": "search", "query": "q"},
      {"ts": T % 2, "type": "product_view", "asin": "B07GYLZ1ZN"},
      {"ts": T % 3, "type": "filter_sort", "url": "/s?rh=x"},
      {"ts": T % 8, "type": "task_end", "task_id": order[0]},
      {"ts": T % 9, "type": "task_start", "task_id": order[1]},
      {"ts": T % 10, "type": "product_view", "asin": "B09YLFGBLL"},
      {"ts": T % 20, "type": "task_end", "task_id": order[1]},
      {"ts": T % 21, "type": "task_start", "task_id": order[2]},
      {"ts": T % 22, "type": "product_view", "asin": "B07D75V2GH"},
      {"ts": T % 26, "type": "task_end", "task_id": order[2]}]
with open(os.path.expanduser("~/dtlab/human/human_session.jsonl"), "w") as f:
    for e in ev:
        f.write(json.dumps(e) + "\n")
PY
python3 "$PACK" >/dev/null 2>&1
python3 - <<'PY'; check $? 0 "guided session: exact task_start/task_end attribution wins"
import json,zipfile,os,sys,hashlib
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
p=m['process']['human']
assert p['attribution']=='task_markers'
order = sorted(["1","2","3"], key=lambda t: hashlib.sha256(
    f"DT2026-999|{t}".encode()).hexdigest())
assert p['per_task'][order[0]]=={'minutes':8.0,'searches':1,'product_views':1,'filter_sorts':1}
assert p['per_task'][order[1]]=={'minutes':11.0,'searches':0,'product_views':1,'filter_sorts':0}
assert p['per_task'][order[2]]['minutes']==5.0
sys.exit(0)
PY

echo "[27] B3: email/phone redacted from staged text; key in config .env caught"
mkenv
cat >> "$HOME/dtlab/workspace/purchase_profile.md" <<'EOF'
- order confirmation went to priya.sharma@example.in
- delivery contact +91 9876543210 and alt 9123456789
EOF
printf '\nANTHROPIC_API_KEY=sk-ant-api03-STUDENTPASTEDTHIS0000\n' \
  >> "$HOME/dtlab/dtlab_config.env"
python3 "$PACK" >/dev/null 2>&1; check $? 0 "pack with seeded PII exits 0"
python3 - <<'PY'; check $? 0 "email/phone/key absent from EVERY text file in the zip; counts in manifest"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
blob=b""
for n in z.namelist():
    if n.rsplit('.',1)[-1] in ('md','txt','log','json','jsonl','csv','html','env'):
        blob += z.read(n)
text=blob.decode('utf-8','replace')
assert 'priya.sharma@example.in' not in text
assert '9876543210' not in text and '9123456789' not in text
assert 'sk-ant-api03-STUDENTPASTEDTHIS0000' not in text
assert '[REDACTED-EMAIL]' in text and '[REDACTED-PHONE]' in text
m=json.loads(z.read('DT2026-999/manifest.json'))
pp=m['redaction_report']['purchase_profile.md']['pii_flags']
assert pp['emails_redacted']==1 and pp['phones_redacted']==2, pp
env_entry=m['redaction_report']['config_snapshot/dtlab_config.env']
assert env_entry['api_keys_redacted']>=1, env_entry
sys.exit(0)
PY

echo "[28] B3: cart screenshot is clipped to the active-cart region"
if python3 - >/dev/null 2>&1 <<'PY'
import os, sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    sys.exit(0 if os.path.exists(p.chromium.executable_path) else 1)
PY
then
python3 - "$REPO/tools/capture_cart.py" <<'PY'; check $? 0 "clip fixture: #sc-active-cart clipped; header excluded; fallback full-page when absent"
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("capture_cart", sys.argv[1])
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)
from playwright.sync_api import sync_playwright
FIXTURE = """<html><body style="margin:0">
<div id="hdr" style="height:120px">Hello, Priya — Deliver to Priya, Mumbai 400001</div>
<div id="sc-active-cart" style="height:300px;width:600px">cart items</div>
</body></html>"""
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 800, "height": 700})
    page.set_content(FIXTURE)
    assert cc.capture_screenshot(page, os.path.expanduser("~/clip.png")) is True
    page.set_content("<html><body><p>no cart node</p></body></html>")
    assert cc.capture_screenshot(page, os.path.expanduser("~/full.png")) is False
    b.close()
import struct
def png_h(path):
    d = open(path, "rb").read()
    i = d.index(b"IHDR")
    return struct.unpack(">II", d[i+4:i+12])[1]
assert png_h(os.path.expanduser("~/clip.png")) <= 310, "clip must exclude the 120px header"
sys.exit(0)
PY
else
  echo "  PASS: clip fixture skipped here (playwright not installed; runs where the browser stack exists)"
  PASS=$((PASS+1))
fi

echo "[26] B1: Tuesday sandbox practice never poisons the real week's pack"
# realistic multi-day spread (NOT same-second like the other cases):
# sandbox marker + sandbox transcript T-2 days, human session T-1 day,
# real .run_started + real transcripts today
mkenv_4run
python3 - <<'PY'
import os, time
home = os.path.expanduser("~")
t2, t1 = time.time() - 2 * 86400, time.time() - 1 * 86400
p = f"{home}/dtlab/.sandbox_run_started"        # Tuesday practice marker
open(p, "w").close(); os.utime(p, (t2, t2))
s = f"{home}/.hermes/sessions/sandbox_practice.jsonl"
open(s, "w").write('{"sandbox": 1}\n'); os.utime(s, (t2, t2))
hs = f"{home}/dtlab/human/human_session.jsonl"  # Wednesday human session
os.utime(hs, (t1, t1))
PY
python3 "$PACK" >/dev/null 2>&1; RC26=$?
check "$RC26" 0 "practiced student's pack exits 0 (H_FIRST not violated)"
python3 - <<'PY'; check $? 0 "no validation_issues; marker = real run; sandbox transcript excluded"
import json,zipfile,os,sys,time
from datetime import datetime
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
assert m['validation_issues']==[], m['validation_issues']
assert m['sandbox'] is False and m['arm']=='H_FIRST'
started=datetime.fromisoformat(m['first_agent_run_started_utc'])
assert time.time()-started.timestamp() < 3600, \
    "first_agent_run_started_utc must be the REAL run (today), not the sandbox"
logs=[n for n in z.namelist() if 'hermes_logs/' in n]
assert not any('sandbox_practice' in n for n in logs), logs
assert any('s.jsonl' in n for n in logs), logs
sys.exit(0)
PY

echo "[29] B4: pack through the ~/dtlab symlink + rebuild simulation"
mkenv_4run
mkdir -p "$HOME/ws"
mv "$HOME/dtlab" "$HOME/ws/.dtlab"
ln -s "$HOME/ws/.dtlab" "$HOME/dtlab"
python3 "$PACK" >/dev/null 2>&1; check $? 0 "pack exits 0 through the symlink"
[ -f "$HOME/ws/.dtlab/DT2026-999_evidence.zip" ]
check $? 0 "zip lands under the persistent root"
# rebuild simulation: $HOME wiped (symlink lost), lab root survives;
# setup.sh re-creates the symlink on the next container build
guard; rm -f "$HOME/dtlab" "$HOME/ws/.dtlab/DT2026-999_evidence.zip"
ln -s "$HOME/ws/.dtlab" "$HOME/dtlab"
python3 "$PACK" >/dev/null 2>&1; check $? 0 "re-pack after rebuild exits 0"
[ -f "$HOME/ws/.dtlab/DT2026-999_evidence.zip" ]
check $? 0 "evidence survives the rebuild (zip rebuilt from the root)"
guard; rm -rf "$HOME/dtlab" "$HOME/ws"    # leave no symlink for later cases

echo "[30] B6: low product-view count warns but never fails the pack"
mkenv
printf '{"type":"product_view","asin":"B07GYLZ1ZN"}\n{"type":"cart_add","asin":"B09YLFGBLL"}\n' \
  > "$HOME/dtlab/human/human_session.jsonl"
python3 "$PACK" >/dev/null 2>&1
check $? 0 "pack with 1 view for 3 tasks exits 0 (grid shopping is legitimate)"
python3 - <<'PY'; check $? 0 "warning recorded in manifest; no validation issue"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
assert any('product views' in w for w in m['warnings']), m['warnings']
assert not any('product views' in i for i in m['validation_issues'])
sys.exit(0)
PY

echo "[23] legacy two-run pack still validates (backward compatibility)"
mkenv_ablation; python3 "$PACK" >/dev/null 2>&1; check $? 0 "legacy 2-run pack exits 0"
python3 - <<'PY'; check $? 0 "legacy manifest keeps the 2run shape"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
ab=m['ablation']
assert ab['design']=='2run' and ab['persona_order']=='P_FIRST'
assert len(m['verdicts'])==6 and ab['agent_pick_overlap_tasks']==['1']
assert ab['manipulation_check_cited_codes']==[]
sys.exit(0)
PY

guard
rm -rf "$SANDBOX"
echo ""; echo "Results: $PASS passed, $FAIL failed"
exit $FAIL
