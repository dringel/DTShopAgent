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
date -u +%FT%TZ > "$HOME/dtlab/.consent_ack"
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

add_hermes_homes(){  # per-run HERMES_HOME layout on top of mkenv_4run
python3 - <<'PY'
import hashlib, os
home = os.path.expanduser("~")
for i in (1, 2, 3, 4):
    d = f"{home}/dtlab/runs/run{i}"
    hh = f"{d}/hermes_home"
    os.makedirs(f"{hh}/sessions", exist_ok=True)
    model = "claude-eco-test-1" if i <= 2 else "claude-fro-test-1"
    cond = "persona" if i in (1, 4) else "ablated"
    with open(f"{hh}/SOUL.md", "w") as f:
        f.write(f"# {cond} soul variant\n")
    with open(f"{hh}/config.yaml", "w") as f:
        f.write(f'model:\n  provider: "anthropic"\n  id: "{model}"\n')
    with open(f"{hh}/sessions/run{i}.jsonl", "w") as f:
        f.write('{"run": %d}\n' % i)
    for name, src in (("soul_sha256.txt", f"{hh}/SOUL.md"),
                      ("config_sha256.txt", f"{hh}/config.yaml")):
        h = hashlib.sha256(open(src, "rb").read()).hexdigest()
        open(f"{d}/{name}", "w").write(h + "\n")
    open(f"{d}/model_id.txt", "w").write(model + "\n")
    # PROTOCOL token: the SOUL variant's canary opens the decision log
    token = "persona-v3" if cond == "persona" else "ablated-v3"
    logp = f"{d}/decision_log.md"
    if not os.path.exists(logp):        # run-4 log still in the workspace
        logp = f"{home}/dtlab/workspace/decision_log.md"
    body = open(logp).read()
    open(logp, "w").write(f"PROTOCOL | soul={token}\n" + body)
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
assert man['consent_ack_utc'], "typed AGREE must be audited in the manifest"
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
grep -q '## Task 5 (Run D)' "$GEN/comparison_ablation.md" \
  && ! grep -q '(persona run,' "$GEN/comparison_ablation.md"
check $? 0 "2x2 verdict blocks are BLIND (Run A-D, no condition names)"
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
assert m['transcript_collection']=='legacy_pool'   # no per-run homes here
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

echo "[31] B2: blind A-D verdict capture end-to-end (resolve, no leak, pack)"
mkenv_4run
python3 - "$REPO" <<'PY'; check $? 0 "blind capture: labels differ per task; resolved cond/tier correct; no condition leak before reveal"
import csv, hashlib, os, subprocess, sys
REPO, HOME, SID = sys.argv[1], os.path.expanduser("~"), "DT2026-999"
RUNS = ["run1", "run2", "run3", "run4"]
def blind(t):
    order = sorted(RUNS, key=lambda rn: hashlib.sha256(
        f"{SID}|{t}|{rn}|verdictorder".encode()).hexdigest())
    return dict(zip("ABCD", order))
condtier, picks = {}, {}
for rn in RUNS:
    d = f"{HOME}/dtlab/runs/{rn}"
    condtier[rn] = (open(f"{d}/condition.txt").read().strip(),
                    open(f"{d}/tier.txt").read().strip())
    src = f"{d}/agent_picks.csv"
    if not os.path.exists(src):        # run-4 artifacts adopted from WS
        src = f"{HOME}/dtlab/workspace/agent_picks.csv"
    picks[rn] = {r["task_id"]: r["asin"] for r in csv.DictReader(open(src))}
human = {r["task_id"]: r["asin"]
         for r in csv.DictReader(open(f"{HOME}/dtlab/human/human_picks.csv"))}
tasks, cycle = ["1", "2", "3"], ["better", "equivalent", "inferior", "better"]
lines, expected = [], {}
for t in tasks:
    lab2run = blind(t)
    lines.append("7")                                    # rating_self, once
    for i, label in enumerate("ABCD"):
        rn = lab2run[label]
        v = "identical" if picks[rn].get(t) == human.get(t) else cycle[i]
        expected[(t,) + condtier[rn]] = v
        lines += [v, "5", "r"]
    lines += ["tie"] * 4                                 # 4 blind pairwise
lines += ["x", ""] * 5                                   # Overall Q1-Q5
p = subprocess.run([sys.executable, f"{REPO}/tools/capture_verdicts.py"],
                   input="\n".join(lines) + "\n",
                   capture_output=True, text=True)
assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
pre = p.stdout[:p.stdout.index("Reveal")]
for w in ("persona", "ablated", "economy", "frontier"):
    assert w not in pre, f"'{w}' leaked before the reveal"
assert len({tuple(sorted(blind(t).items())) for t in tasks}) > 1
vd = f"{HOME}/dtlab/verdicts"
rows = list(csv.DictReader(open(f"{vd}/verdicts.csv")))
assert len(rows) == 12
for r in rows:
    assert expected[(r["task_id"], r["condition"], r["tier"])] == r["verdict"]
    assert r["rating_self"] == "7" and r["verdict_at_utc"]
h = list(csv.DictReader(open(f"{vd}/head_to_heads.csv")))
assert len(h) == 12 and all(r["winner"] in ("tie", "same") for r in h)
assert os.path.exists(f"{vd}/overall_reflections.md")
assert not os.path.exists(f"{HOME}/dtlab/workspace/verdicts.csv")
sys.exit(0)
PY
python3 "$PACK" >/dev/null 2>&1; check $? 0 "pack from blind capture exits 0"
python3 - <<'PY'; check $? 0 "manifest: verdicts_captured_blind, 12 resolved verdicts, hth families"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
assert m['verdicts_captured_blind'] is True
assert m['verdict_source']=='verdicts_csv' and len(m['verdicts'])==12
assert set(m['ablation']['head_to_head']) == \
    {'grounding_economy','grounding_frontier','tier_persona','tier_ablated'}
assert m['ratings']['1_persona_economy']=={'self':7,'agent':5}
assert 'DT2026-999/verdicts.csv' in z.namelist()
sys.exit(0)
PY

echo "[32] B2/B17: Thursday capture resumes Friday; corrupt run never drops rows"
mkenv_4run
guard; rm -rf "$HOME/dtlab/runs/run3" "$HOME/dtlab/runs/run4"
python3 - "$REPO" <<'PY'; check $? 0 "3-phase resume: stored answers survive; corrupt condition.txt carries rows forward"
import csv, hashlib, os, shutil, subprocess, sys
REPO, HOME, SID = sys.argv[1], os.path.expanduser("~"), "DT2026-999"
WS = f"{HOME}/dtlab/workspace"
def blind(t, runs):
    order = sorted(runs, key=lambda rn: hashlib.sha256(
        f"{SID}|{t}|{rn}|verdictorder".encode()).hexdigest())
    return dict(zip("ABCD", order))
def condtier(rn):
    d = f"{HOME}/dtlab/runs/{rn}"
    return (open(f"{d}/condition.txt").read().strip(),
            open(f"{d}/tier.txt").read().strip())
def picks_of(rn, runs):
    src = f"{HOME}/dtlab/runs/{rn}/agent_picks.csv"
    if not os.path.exists(src) and rn == runs[-1]:
        src = f"{WS}/agent_picks.csv"
    return {r["task_id"]: r["asin"] for r in csv.DictReader(open(src))}
human = {r["task_id"]: r["asin"]
         for r in csv.DictReader(open(f"{HOME}/dtlab/human/human_picks.csv"))}
tasks = ["1", "2", "3"]
cap = f"{REPO}/tools/capture_verdicts.py"
def run_capture(lines):
    return subprocess.run([sys.executable, cap],
                          input="\n".join(lines) + "\n",
                          capture_output=True, text=True)
# ---- phase 1: Thursday (runs 1-2 only) ----
runs = ["run1", "run2"]
ct = {rn: condtier(rn) for rn in runs}
lines, thur = [], {}
for t in tasks:
    lab2run = blind(t, runs)
    lines.append("8")
    for i, label in enumerate("AB"):
        rn = lab2run[label]
        v = "identical" if picks_of(rn, runs).get(t) == human.get(t) \
            else ("better" if i == 0 else "equivalent")
        thur[(t,) + ct[rn]] = v
        lines += [v, "4", "thu"]
    # one family (grounding_economy): answer the PERSONA run's label
    plabel = next(lb for lb, rn in lab2run.items() if ct[rn][0] == "persona")
    lines.append(plabel.lower())
p = run_capture(lines)
assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
rows = list(csv.DictReader(open(f"{HOME}/dtlab/verdicts/verdicts.csv")))
assert len(rows) == 6
h = {(r["task_id"], r["contrast"]): r["winner"] for r in
     csv.DictReader(open(f"{HOME}/dtlab/verdicts/head_to_heads.csv"))}
assert all(h[(t, "grounding_economy")] == "persona" for t in tasks)
# ---- phase 2: Friday (runs 3-4 exist; fresh process keeps Thursday) ----
for i, cond, tier in ((3, "ablated", "frontier"), (4, "persona", "frontier")):
    d = f"{HOME}/dtlab/runs/run{i}"
    os.makedirs(d, exist_ok=True)
    open(f"{d}/condition.txt", "w").write(cond + "\n")
    open(f"{d}/tier.txt", "w").write(tier + "\n")
open(f"{HOME}/dtlab/runs/run3/agent_picks.csv", "w").write(
    "task_id,title,asin,price_inr,sponsored\n1,Q,B0CCCC3333,310,0\n"
    "2,X,B0AAAA1111,1200,0\n3,Y,B0BBBB2222,1400,0\n")
runs = ["run1", "run2", "run3", "run4"]
ct = {rn: condtier(rn) for rn in runs}
lines, fri = [], {}
for t in tasks:
    lab2run = blind(t, runs)
    lines.append("")                       # rating_self stored -> Enter
    for label in "ABCD":
        rn = lab2run[label]
        if rn in ("run1", "run2"):
            lines += ["", "", ""]          # stored -> Enter keeps
        else:
            v = "identical" if picks_of(rn, runs).get(t) == human.get(t) \
                else "inferior"
            fri[(t,) + ct[rn]] = v
            lines += [v, "6", "fri"]
    # families in fixed order: grounding_economy (stored), then
    # grounding_frontier, tier_persona, tier_ablated (new)
    lines += ["", "tie", "tie", "tie"]
lines += ["x", ""] * 5
p = run_capture(lines)
assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
rows = list(csv.DictReader(open(f"{HOME}/dtlab/verdicts/verdicts.csv")))
assert len(rows) == 12
got = {(r["task_id"], r["condition"], r["tier"]): r for r in rows}
for k, v in thur.items():
    assert got[k]["verdict"] == v and got[k]["rationale"] == "thu", k
    assert got[k]["rating_self"] == "8" and got[k]["rating_agent"] == "4"
for k, v in fri.items():
    assert got[k]["verdict"] == v and got[k]["rationale"] == "fri", k
# ---- phase 3: corrupt run3's condition -> rows carried, not dropped ----
open(f"{HOME}/dtlab/runs/run3/condition.txt", "w").write("garbage\n")
runs3 = ["run1", "run2", "run4"]
lines = []
for t in tasks:
    lines += [""] + [""] * 9 + ["", ""]    # all stored -> Enter
p = run_capture(lines)                     # 3 runs -> no Overall stage
assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
assert "carried forward" in p.stdout
rows = list(csv.DictReader(open(f"{HOME}/dtlab/verdicts/verdicts.csv")))
assert len(rows) == 12
kept = [r for r in rows if (r["condition"], r["tier"]) ==
        ("ablated", "frontier")]
assert len(kept) == 3 and all(r["rationale"] == "fri" for r in kept)
shutil.rmtree(f"{HOME}/dtlab/verdicts")    # leave later cases untouched
sys.exit(0)
PY

echo "[33] B2: blind memo fallback parses; labels resolve via shared derivation"
mkenv_4run
rm -f "$HOME/dtlab/workspace/comparison.md"
python3 - <<'PY'
import csv, hashlib, os
HOME, SID = os.path.expanduser("~"), "DT2026-999"
RUNS = ["run1", "run2", "run3", "run4"]
def blind(t):
    order = sorted(RUNS, key=lambda rn: hashlib.sha256(
        f"{SID}|{t}|{rn}|verdictorder".encode()).hexdigest())
    return dict(zip("ABCD", order))
condtier, picks = {}, {}
for rn in RUNS:
    d = f"{HOME}/dtlab/runs/{rn}"
    condtier[rn] = (open(f"{d}/condition.txt").read().strip(),
                    open(f"{d}/tier.txt").read().strip())
    src = f"{d}/agent_picks.csv"
    if not os.path.exists(src):
        src = f"{HOME}/dtlab/workspace/agent_picks.csv"
    picks[rn] = {r["task_id"]: r["asin"] for r in csv.DictReader(open(src))}
human = {r["task_id"]: r["asin"]
         for r in csv.DictReader(open(f"{HOME}/dtlab/human/human_picks.csv"))}
L = ["# c"]
for t in ("1", "2", "3"):
    lab2run = blind(t)
    for label in "ABCD":
        rn = lab2run[label]
        v = "identical" if picks[rn].get(t) == human.get(t) else "equivalent"
        L += [f"## Task {t} (Run {label})", f"Verdict: {v}",
              "My pick rating (1-10): 7", "Agent pick rating (1-10): 6",
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
open(f"{HOME}/dtlab/workspace/comparison.md", "w").write("\n".join(L))
PY
python3 "$PACK" >/dev/null 2>&1; check $? 0 "blind memo pack exits 0"
python3 - <<'PY'; check $? 0 "blind memo: 12 verdicts resolved to condition/tier keys"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
assert m['verdict_source']=='comparison_md'
assert m['verdicts_captured_blind'] is False
assert len(m['verdicts'])==12
assert m['verdicts']['1_persona_economy']=='identical'
assert m['verdicts']['3_ablated_frontier']=='equivalent'
assert m['ratings']['2_persona_frontier']=={'self':7,'agent':6}
sys.exit(0)
PY

echo "[34] B14: contamination index computed on the CAND candidate set"
mkenv
printf 'CAND | task=1 | asin=B07GYLZ1ZN | category=H | price=289 | sponsored=0 | source=search#1\nCAND | task=1 | asin=B0ZZZZZZZ9 | category=H | price=340 | sponsored=1 | source=search#3\nCAND | task=2 | asin=B09YLFGBLL | category=E | price=1290 | sponsored=0 | source=search#1\n' >> "$HOME/dtlab/workspace/decision_log.md"
python3 "$PACK" >/dev/null 2>&1; check $? 0 "pack exits 0"
python3 - <<'PY'; check $? 0 "index = mean candidate-viewed share; pick overlap + missing verdicts explicit"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
ci=m['contamination_index']
assert ci['basis']=='candidate_set'
assert ci['per_task_candidate_viewed_share']=={'1':0.5,'2':1.0}, ci
assert ci['index']==0.75, ci
assert ci['overlapping_pick_tasks']==['1'], ci   # agent pick 1 was viewed
assert ci['tasks_missing_verdict']==[], ci
sys.exit(0)
PY

echo "[35] B16.4: per-run sandbox stamp excludes THAT run, keeps the rest"
mkenv_4run
echo sandbox > "$HOME/dtlab/runs/run3/sandbox.txt"
python3 "$PACK" >/dev/null 2>&1
check $? 0 "pack exits 0 with runs 1, 2, 4 valid and run 3 sandbox-stamped"
python3 - <<'PY'; check $? 0 "run3 excluded per-run; zip NOT globally sandbox; others validate"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
assert m['sandbox'] is False and m['arm']=='H_FIRST'
assert m['sandbox_runs']==['run3']
assert any('run3 is a sandbox run' in w for w in m['warnings'])
assert set(m['ablation']['run_conditions'])=={'run1','run2','run4'}
assert not any(n.startswith('DT2026-999/run3/') for n in z.namelist())
assert 'run4/agent_picks.csv' in m['sha256']
sys.exit(0)
PY

echo "[36] B18: log cap keeps newest, warns, dedupes; .hermes_dirs honored"
mkenv
python3 - <<'PY'   # three 600KB transcripts newer than the run marker
import os, time
home = os.path.expanduser("~")
os.makedirs(f"{home}/.hermes/sessions", exist_ok=True)
os.makedirs(f"{home}/.hermes/other/sessions", exist_ok=True)
now = time.time()
for name, dt in (("old.jsonl", 10), ("mid.jsonl", 20), ("new.jsonl", 30)):
    p = f"{home}/.hermes/sessions/{name}"
    open(p, "w").write("x" * 600_000)
    os.utime(p, (now + dt, now + dt))
# same basename in a second same-named dir: dest must deduplicate
p2 = f"{home}/.hermes/other/sessions/new.jsonl"
open(p2, "w").write('{"d":1}\n')
os.utime(p2, (now + 25, now + 25))
PY
DTLAB_MAX_LOG_MB=1 python3 "$PACK" >/dev/null 2>&1
check $? 0 "capped pack exits 0"
python3 - <<'PY'; check $? 0 "newest kept, oldest dropped with a warning; dedup name present"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
logs=[n.rsplit('/',1)[1] for n in z.namelist() if '/hermes_logs/' in n]
assert 'sessions__new.jsonl' in logs, logs
assert 'sessions__new__2.jsonl' in logs, logs      # deduplicated twin
assert not any('old' in n for n in logs), logs      # oldest dropped first
assert any('MB cap' in w for w in m['warnings']), m['warnings']
sys.exit(0)
PY
mkenv
mkdir -p "$HOME/hermes_elsewhere/sessions"
echo '{"t":2}' > "$HOME/hermes_elsewhere/sessions/moved.jsonl"
guard; rm -rf "$HOME/.hermes"
printf '%s\n' "$HOME/hermes_elsewhere" > "$HOME/dtlab/.hermes_dirs"
python3 "$PACK" >/dev/null 2>&1
check $? 0 "pack collects from the dir dtlab-start recorded"
python3 -c "
import zipfile,os
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
assert any('moved.jsonl' in n for n in z.namelist())
"; check $? 0 "recorded transcript dir wins over the guesses"

echo "[37] B18: non-numeric task_id fails loudly at generation time"
printf 'task_id,frame,short_name,product_type,category_class,budget_min_inr,budget_max_inr\nA1,Self-purchase,X,item,utilitarian,0,600\n' > "$HOME/badtasks.csv"
python3 "$REPO/tools/make_task_docs.py" --config "$HOME/badtasks.csv" \
  --outdir "$HOME/gen_bad" 2>&1 | grep -q "task_id must be numeric"
check $? 0 "generator refuses a non-numeric catalog row with a clear message"

echo "[38] B19: dtlab-shop sid discipline + pack cross-check"
mkenv
printf '{"student_id":"DT2026-777","type":"session_start"}\n{"type":"product_view","asin":"B07GYLZ1ZN"}\n' \
  > "$HOME/dtlab/human/human_session.jsonl"
python3 "$PACK" 2>&1 | grep -q "logged as DT2026-777"
check $? 0 "session logged under a different sid is caught at pack time"
mkenv
printf '{"student_id":"DT2026-999","type":"session_start"}\n{"type":"product_view","asin":"B07GYLZ1ZN"}\n{"type":"product_view","asin":"B09YLFGBLL"}\n{"type":"product_view","asin":"B07D75V2GH"}\n' \
  > "$HOME/dtlab/human/human_session.jsonl"
python3 "$PACK" >/dev/null 2>&1
check $? 0 "matching sid in the session log passes"
SHOP="$REPO/tools/log_human_session.py"
mv "$HOME/dtlab/workspace/persona_survey.csv" "$HOME/persona.bak"
OUT38="$(cd "$HOME" && python3 "$SHOP" 2>&1)"; RC38=$?
[ "$RC38" -ne 0 ] && [ "$RC38" -ne 2 ] && \
  echo "$OUT38" | grep -q "cannot determine your student id"
check $? 0 "flagless dtlab-shop explains the sid, never raw argparse death"
mv "$HOME/persona.bak" "$HOME/dtlab/workspace/persona_survey.csv"
OUT38B="$(cd "$HOME" && python3 "$SHOP" --student-id BADID 2>&1)"; RC38B=$?
[ "$RC38B" -ne 0 ] && echo "$OUT38B" | grep -q "does not match the course pattern"
check $? 0 "malformed --student-id refused with the desync warning"
OUT38C="$(cd "$HOME" && python3 "$SHOP" --student-id DT2026-111 2>&1)"; RC38C=$?
[ "$RC38C" -ne 0 ] && echo "$OUT38C" | grep -q "contradicts persona_survey.csv"
check $? 0 "sid contradicting the persona refused"

echo "[39] B22: checkout-shaped URL in a log blocks; guard-fire is recorded"
mkenv_4run
printf 'navigation attempt: https://www.amazon.in/gp/buy/spc/handlers/display.html?token=SECRET123 was refused\n' \
  >> "$HOME/dtlab/runs/run2/decision_log.md"
OUT39="$(python3 "$PACK" 2>&1)"; RC39=$?
check "$([ "$RC39" -ne 0 ]; echo $?)" 0 "pack with a checkout URL exits non-zero"
echo "$OUT39" | grep -q "checkout-shaped URL in run2/decision_log.md"
check $? 0 "blocking issue names the run and demands review"
python3 - <<'PY'; check $? 0 "manifest checkout_attempts: query-stripped URL, no token"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
ca=m['checkout_attempts']
e=ca['run2/decision_log.md']
assert e['checkout_urls']==['amazon.in/gp/buy/spc/handlers/display.html'], e
assert 'SECRET123' not in json.dumps(ca)
assert e['guard_fired']==0
assert any('checkout-shaped URL' in i for i in m['validation_issues'])
sys.exit(0)
PY
mkenv_4run
printf 'blocked navigation landed on chrome-extension://abcdefghij/blocked.html — logged as obstacle, returning to task\n' \
  >> "$HOME/dtlab/runs/run1/decision_log.md"
python3 "$PACK" >/dev/null 2>&1
check $? 0 "guard-fired sighting alone never blocks the pack"
python3 - <<'PY'; check $? 0 "guard fire recorded in checkout_attempts, no issue raised"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
e=m['checkout_attempts']['run1/decision_log.md']
assert e['guard_fired']==1 and e['checkout_urls']==[], e
assert m['validation_issues']==[], m['validation_issues']
sys.exit(0)
PY

echo "[40] C1.1: per-run transcript collection + PROTOCOL token validation"
mkenv_4run; add_hermes_homes
python3 "$PACK" >/dev/null 2>&1; check $? 0 "per-run home layout packs clean"
python3 - <<'PY'; check $? 0 "per-run transcripts staged; model ids + hashes from run files; tokens recorded"
import json,zipfile,os,sys
z=zipfile.ZipFile(os.path.expanduser('~/dtlab/DT2026-999_evidence.zip'))
m=json.loads(z.read('DT2026-999/manifest.json'))
assert m['transcript_collection']=='per_run'
for i in (1,2,3,4):
    assert f'DT2026-999/run{i}/hermes_logs/sessions__run{i}.jsonl' \
        in z.namelist(), i
    assert f'run{i}/soul_sha256.txt' in m['sha256'], i
env=m['environment']
assert env['model_id_by_run']=={'run1':'claude-eco-test-1','run2':'claude-eco-test-1','run3':'claude-fro-test-1','run4':'claude-fro-test-1'}
assert set(env['context_sha256_by_run'])=={'run1','run2','run3','run4'}
assert set(env['config_sha256_by_run'])=={'run1','run2','run3','run4'}
assert m['protocol_tokens_by_run']=={'run1':'persona-v3','run2':'ablated-v3','run3':'ablated-v3','run4':'persona-v3'}
assert m['validation_issues']==[], m['validation_issues']
# the delivery files themselves are hashed, never packed as transcripts
assert not any(n.endswith('hermes_logs/hermes_home__SOUL.md')
               for n in z.namelist())
sys.exit(0)
PY
mkenv_4run; add_hermes_homes           # wrong token: ablated run claims persona
replace "$HOME/dtlab/runs/run2/decision_log.md" "soul=ablated-v3" "soul=persona-v3"
OUT40="$(python3 "$PACK" 2>&1)"; RC40=$?
check "$([ "$RC40" -ne 0 ]; echo $?)" 0 "mismatched PROTOCOL token blocks"
echo "$OUT40" | grep -q "run2: decision log PROTOCOL token"
check $? 0 "issue names the run and both tokens"
mkenv_4run; add_hermes_homes           # token absent entirely
replace "$HOME/dtlab/runs/run3/decision_log.md" "PROTOCOL | soul=ablated-v3" "no token here"
python3 "$PACK" 2>&1 | grep -q "run3: decision log PROTOCOL token is MISSING"
check $? 0 "absent PROTOCOL token blocks, naming the run"
mkenv_4run; add_hermes_homes           # completed run with zero transcripts
rm -f "$HOME/dtlab/runs/run1/hermes_home/sessions/run1.jsonl"
python3 "$PACK" 2>&1 | grep -q "run1: completed run .* ZERO collected Hermes transcripts"
check $? 0 "completed run without transcripts is a blocking issue"
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
