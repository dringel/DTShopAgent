#!/usr/bin/env python3
"""
capture_verdicts.py — `dtlab-verdict`: guided, structured, BLIND verdict
capture (replaces hand-editing the comparison memo — format errors at
N=161 were the failure mode).

BLIND ASSESSMENT: for every task the started runs' picks are presented in
a per-task randomized order labeled Run A-D — condition (persona/ablated)
and tier (economy/frontier) are never shown before a verdict is stored.
The label order derives from sha256(student|task|run|"verdictorder"), so
it is reproducible, differs across tasks, and pack_evidence.py resolves
the same mapping when parsing the memo fallback (LOCKSTEP). The
label->run mapping is revealed only in the post-capture summary and the
Overall-reflections stage (whose questions reference tiers by design and
run after all verdicts).

For every task x started run it prompts, input-validated:
  - verdict: better | identical | equivalent | inferior
    ('identical' is ASIN-checked live against your pick and the agent's,
    and re-verified by the packer)
  - the agent-pick rating (1-10); your OWN pick's rating is asked once
    per task (it does not vary by run)
  - a one-line rationale
then the per-task head-to-heads as pairwise Run-X-vs-Run-Y questions
(only for contrasts whose two runs both exist) and, once all four runs
are captured, the Overall reflection questions.

Writes (schema dtlab-verdicts-v2, research_protocol.md §6) into
~/dtlab/quarantine/verdicts/ — under the quarantine root every agent
path is barred from, so no agent can ever read stored judgments:
  verdicts.csv             student_id, task_id, condition, tier, verdict,
                           rating_self, rating_agent, rationale,
                           verdict_at_utc  (condition/tier resolved
                           post-capture from the blind labels)
  head_to_heads.csv        task_id, contrast, winner (resolved)
  overall_reflections.md   free text
  capture_meta.json        blind-capture stamp for the manifest

SINGLE SESSION (D5): all verdicts are captured ONCE, in Friday's single
blind session, after run 4 — before that the tool prints the schedule
and exits. With the tier order counterbalanced across days, the single
session is blind on BOTH factors. Stored rows are IMMUTABLE: the first
stored value of every (task, run) verdict — and its ratings and
rationale — is final; re-running displays stored rows read-only (rows
are keyed by the RESOLVED condition/tier, so a crash mid-session never
loses what was already written, and rows for runs that are no longer
readable are carried forward, never dropped).

`dtlab-verdict --amend` is the ONLY correction path: it appends to
verdicts_amendments.csv (row key, field, new value, one-line reason,
amended_at_utc) and never rewrites the original row. No TA token: the
gate used to require ~/dtlab/.ta_token, which nothing in provisioning
ever created, so the documented correction path was dead for the whole
cohort. What makes an amendment safe is that it is append-only and
carries a reason — the original verdict is still there, and the
analyzer applies amendments last-wins and reports their count, so a
corrected verdict is visible in the data rather than a silent rewrite.

`dtlab-verdict --worksheet` prints each task's blind label -> pick list
(titles + ASINs only) for the memo fallback path, without capturing.
"""

import csv
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
WS = HOME / "dtlab" / "workspace"
QUAR = HOME / "dtlab" / "quarantine"   # root the agent is barred from


def _qdir(name):
    """Quarantine path for `name`, falling back to the pre-quarantine
    location when only that exists (legacy layouts keep working)."""
    p = QUAR / name
    legacy = HOME / "dtlab" / name
    return p if (p.exists() or not legacy.exists()) else legacy


VD = QUAR / "verdicts"               # agent-quarantined verdict store
HU = _qdir("human")
HOLD = _qdir("persona_hold")
RUNSDIR = HOME / "dtlab" / "runs"
# Superseded attempts parked by a redo. Deliberately NOT under RUNSDIR:
# anything left in there would be picked up as an extra run, and a
# student who redid every condition would be asked to rate six.
HISTDIR = HOME / "dtlab" / "runs_history"
VERDICTS = ("better", "identical", "equivalent", "inferior")
VERDICT_HELP = ("better     = the agent's choice is BETTER for me than my own pick\n"
                "identical  = same product (same ASIN) as mine\n"
                "equivalent = different product, equally good fit for me\n"
                "inferior   = the agent's choice is WORSE for me")
# canonical 2x2 Overall questions — keep in lockstep with
# make_task_docs.py::OVERALL_ABLATION (same five, same order)
OVERALL_QUESTIONS = (
    "1. What did the questionnaire demonstrably add over your purchase "
    "history alone — and where did the ablated twin do just as well or "
    "better?",
    "2. Constraints: your CONSTRAINT items (allergies, exclusions) were "
    "absent in the ablated runs. Did their picks violate any? What does "
    "that imply for real deployment?",
    "3. Tier: what did the frontier model demonstrably buy over the "
    "economy model — and was it worth ~10x the token price?",
    "4. Delegation: which twin (if any) would you give real spending "
    "authority with a cap, and for which categories?",
    "5. The one change that would most improve your twin:",
)
VFIELDS = ["student_id", "task_id", "condition", "tier", "verdict",
           "rating_self", "rating_agent", "rationale", "verdict_at_utc"]


def blind_labels(student_id, task_id, run_names):
    """Blind label -> run name for one task: the runs sorted by
    sha256(student|task|run|"verdictorder"), labeled A, B, C, D.
    Reproducible, differs across tasks. LOCKSTEP with
    pack_evidence.py::blind_labels (memo-fallback resolution)."""
    ordered = sorted(run_names, key=lambda rn: hashlib.sha256(
        f"{student_id}|{task_id}|{rn}|verdictorder".encode()).hexdigest())
    return dict(zip("ABCD", ordered))


def read_csv_rows(p):
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def find_student_id():
    for p in (WS / "persona_survey.csv", HOLD / "persona_survey.csv"):
        rows = read_csv_rows(p)
        if rows and rows[0].get("student_id"):
            return rows[0]["student_id"].strip()
    return None


def load_task_ids():
    p = HOME / "dtlab" / "tasks_config.csv"
    ids = [r["task_id"].strip() for r in read_csv_rows(p)
           if (r.get("task_id") or "").strip()
           and not r["task_id"].strip().startswith("#")]
    return ids or ["1", "2", "3"]


def tier_from_sheet(student_id, run_idx):
    """This student's assigned tier for the run's day, from the
    counterbalance sheet (tier order is counterbalanced across days —
    the run index alone cannot resolve it)."""
    p = HOME / "dtlab" / "counterbalance.csv"
    if not (student_id and p.exists()):
        return None
    col = "tier_day1" if run_idx <= 2 else "tier_day2"
    for r in read_csv_rows(p):
        if (r.get("student_id") or "").strip() == student_id:
            t = (r.get(col) or "").strip()
            return t if t in ("economy", "frontier") else None
    return None


def superseded_attempts():
    """Runs a redo replaced. They are rated by nobody — only the latest
    attempt of each setup is — but a student who redid a run needs to
    be told the earlier one still exists rather than left guessing."""
    if not HISTDIR.is_dir():
        return []
    return sorted(d.name for d in HISTDIR.iterdir() if d.is_dir())


def load_runs(student_id):
    """Started runs -> [(runN, condition, tier)] in run order. A run
    without tier.txt falls back to the counterbalance sheet; without
    either the tool refuses (tier labels every stored verdict row and
    is not guessable — tier order varies across students)."""
    runs = []
    for i in (1, 2, 3, 4):
        d = RUNSDIR / f"run{i}"
        if not d.exists():
            continue
        cond = (d / "condition.txt").read_text().strip() \
            if (d / "condition.txt").exists() else ""
        tier = (d / "tier.txt").read_text().strip() \
            if (d / "tier.txt").exists() else ""
        if not tier:
            tier = tier_from_sheet(student_id, i) or ""
        if cond in ("persona", "ablated", "nohistory"):
            if not tier:
                sys.exit(f"run{i} has no tier.txt and the counterbalance "
                         "sheet cannot resolve this student's tier for "
                         "that day — the tier labels every verdict row "
                         "and cannot be guessed; tell a TA.")
            runs.append((f"run{i}", cond, tier))
    # Collapse repeats of the same (condition, tier) to the LATEST run.
    #
    # A student who re-ran a condition into a NEW slot instead of redoing
    # the old one ends up with, say, run1 and run2 both nohistory. Every
    # verdict row is keyed (task, condition, tier), so two runs sharing a
    # cell collide on that key: one silently overwrites the other, and
    # the student is asked to rate four runs that can only store three.
    # Higher run number = later attempt, so the newest wins — the same
    # rule a redo already follows.
    latest = {}
    for rn, cond, tier in runs:
        latest[(cond, tier)] = (rn, cond, tier)
    deduped = [latest[k] for k in latest]
    deduped.sort(key=lambda r: int(r[0][3:]))
    if len(deduped) < len(runs):
        dropped = [rn for rn, c, t in runs
                   if latest[(c, t)][0] != rn]
        print(f"\nNote: {', '.join(dropped)} repeated a setup you ran "
              "again later.")
        print("Rating the most recent run of each setup, so nothing is")
        print("counted twice. The earlier ones are still on file.")
    return deduped


def picks_by_task(path):
    return {str(r.get("task_id", "")).strip(): r
            for r in read_csv_rows(path)}


# The stored vocabulary is better/identical/equivalent/inferior, but the
# level is described to students as "worse" — in class, in the LMS
# announcements and in the help text right above. Someone briefed in
# those words types "worse" and gets rejected for saying exactly what
# they were told to say. Accept the synonyms; store the canonical value.
# NOT "tie" -> equivalent: "tie" is already a real answer at the
# head-to-head prompts, and quietly meaning something else at the
# verdict prompt is how you record an answer nobody gave.
SYNONYMS = {"worse": "inferior", "same": "identical"}


def ask(prompt, valid, current=None, allow_empty=False):
    """Validated input; Enter keeps `current` when one exists."""
    suffix = f" [{current}]" if current else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip().lower()
        if not raw:
            if current:
                return current
            if allow_empty:
                return ""
        if raw in valid:
            return raw
        alias = SYNONYMS.get(raw)
        if alias and alias in valid:
            print(f"    (recording that as '{alias}')")
            return alias
        print(f"    one of: {' | '.join(sorted(valid))}")


def ask_rating(prompt, current=None):
    suffix = f" [{current}]" if current else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and current:
            return current
        if re.fullmatch(r"(10|[1-9])", raw):
            return raw
        print("    whole number 1-10")


def ask_line(prompt, current=None):
    suffix = " [Enter keeps stored answer]" if current else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw or (current or "")


def ask_block(prompt, current=None):
    """Multiline free text; finish with an empty line. Immediate Enter
    keeps the stored answer."""
    suffix = " [Enter keeps stored answer]" if current else ""
    print(f"{prompt}{suffix} — finish with an empty line:")
    lines = []
    while True:
        raw = input("  ")
        if not raw.strip():
            break
        lines.append(raw.rstrip())
    return "\n".join(lines) or (current or "")


def migrate_legacy_locations():
    """Verdict artifacts written before the quarantine root lived in the
    agent workspace (oldest layout) or at ~/dtlab/verdicts/ (pre-C1.3);
    pull both into ~/dtlab/quarantine/verdicts/ once."""
    legacy_vd = HOME / "dtlab" / "verdicts"
    if legacy_vd.is_dir() and not VD.exists():
        VD.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy_vd), str(VD))
        print(f"  [..] moved ~/dtlab/verdicts -> {VD}")
    VD.mkdir(parents=True, exist_ok=True)
    for name in ("verdicts.csv", "head_to_heads.csv",
                 "overall_reflections.md"):
        src = WS / name
        if not src.exists():
            continue
        dest = VD / name if not (VD / name).exists() \
            else VD / f"workspace_{name}.bak"
        shutil.move(str(src), str(dest))
        print(f"  [..] moved {name} out of the agent workspace -> {dest}")


def contrast_families(cells):
    """The pairwise contrast families whose two cells both ran.
    Each entry: (family, cell_hi, cell_lo, tie_word) where the winner
    vocabulary is the two cells' differing dimension + tie_word."""
    fams = []
    conds_all = ("persona", "ablated", "nohistory")
    for tier in ("economy", "frontier"):
        # every grounding pair that actually ran. The persona/ablated
        # pair keeps its original family name so earlier data and the
        # cohort report still match; the pairs involving nohistory are
        # named explicitly.
        for i, a in enumerate(conds_all):
            for b in conds_all[i + 1:]:
                if {(a, tier), (b, tier)} <= cells:
                    fam = (f"grounding_{tier}"
                           if {a, b} == {"persona", "ablated"}
                           else f"grounding_{a}_vs_{b}_{tier}")
                    fams.append((fam, (a, tier), (b, tier), "tie"))
    for cond in conds_all:
        if {(cond, "economy"), (cond, "frontier")} <= cells:
            fams.append((f"tier_{cond}", (cond, "frontier"),
                         (cond, "economy"), "same"))
    return fams


def resolved_winner(fam, cell_a, cell_b, ans, label_a, label_b, tie_word):
    """Blind answer (label or 'tie') -> stored winner vocabulary."""
    if ans == "tie":
        return tie_word
    cell = cell_a if ans == label_a.lower() else cell_b
    return cell[0] if fam.startswith("grounding_") else cell[1]


AMEND_FIELDS = ("verdict", "rating_self", "rating_agent", "rationale")


def amend_flow(student_id):
    """TA-authorized append-only correction: the original verdict row is
    never rewritten; the analyzer applies amendments last-wins."""
    vpath = VD / "verdicts.csv"
    rows = read_csv_rows(vpath)
    if not rows:
        sys.exit("no stored verdicts to amend (verdicts.csv is empty)")
    print("Amendment (append-only; the original row stays untouched).")
    t = input("  task_id: ").strip()
    cond = input("  condition (persona/ablated): ").strip().lower()
    tier = input("  tier (economy/frontier): ").strip().lower()
    if not any((r.get("task_id") or "").strip() == t
               and (r.get("condition") or "").strip() == cond
               and (r.get("tier") or "").strip() == tier for r in rows):
        sys.exit(f"no stored verdict row for task {t} ({cond}, {tier})")
    field = input("  field (" + "/".join(AMEND_FIELDS) + "): ").strip()
    if field not in AMEND_FIELDS:
        sys.exit("field must be one of " + "/".join(AMEND_FIELDS))
    val = input("  new value: ").strip()
    if field == "verdict" and val not in VERDICTS:
        sys.exit("verdict must be better/identical/equivalent/inferior")
    if field.startswith("rating") and not re.fullmatch(r"(10|[1-9])", val):
        sys.exit("rating must be a whole number 1-10")
    reason = input("  one-line reason: ").strip()
    if not reason:
        sys.exit("a reason is required for the audit trail")
    # Confirm rather than gate. The original row is never rewritten and
    # the reason is on the record, so the audit trail is what protects
    # the data here — a token file that provisioning never created only
    # protected it by making the whole path unusable.
    print(f"  This appends a correction for task {t} ({cond}, {tier}): "
          f"{field} -> {val}")
    print("  The verdict you already recorded stays on file underneath.")
    if os.environ.get("DTLAB_AMEND_YES") != "1":
        try:
            go = input("  Append this amendment? [y/N] ").strip()
        except EOFError:
            go = ""
        if not go.lower().startswith("y"):
            sys.exit("Nothing appended — the stored verdict stays as-is.")
    apath = VD / "verdicts_amendments.csv"
    fields = ["student_id", "task_id", "condition", "tier", "field",
              "new_value", "reason", "amended_at_utc"]
    new_file = not apath.exists()
    with open(apath, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            w.writeheader()
        w.writerow({"student_id": student_id, "task_id": t,
                    "condition": cond, "tier": tier, "field": field,
                    "new_value": val, "reason": reason,
                    "amended_at_utc":
                        datetime.now(timezone.utc).isoformat()})
    print(f"Amendment appended to {apath} — the analyzer applies "
          "amendments last-wins and reports their count.")
    return 0


def print_worksheet(student_id, task_ids, runs, rundata):
    print(f"\nBlind worksheet — {student_id} ({len(runs)} runs on file).")
    print("Per task, the runs' picks in their blind order (conditions stay")
    print("hidden until after verdicts). Use these labels in the fallback")
    print("memo's 'Task N (Run X)' blocks.")
    run_names = [rn for rn, _, _ in runs]
    for t in task_ids:
        lab2run = blind_labels(student_id, t, run_names)
        print(f"\n  Task {t}:")
        for label in "ABCD"[:len(run_names)]:
            a = rundata[lab2run[label]].get(t, {})
            print(f"    Run {label}: {(a.get('title') or '?')[:60]} "
                  f"({(a.get('asin') or '?').strip()})")


def main():
    student_id = find_student_id()
    if "--student-id" in sys.argv:
        student_id = sys.argv[sys.argv.index("--student-id") + 1]
    if not student_id:
        sys.exit("cannot determine student_id (persona_survey.csv missing? "
                 "use --student-id DT2026-###)")
    task_ids = load_task_ids()
    runs = load_runs(student_id)
    if not runs:
        sys.exit("no agent runs found under ~/dtlab/runs — dtlab-verdict "
                 "runs AFTER the day's agent runs.")
    run_names = [rn for rn, _, _ in runs]
    condtier = {rn: (c, t) for rn, c, t in runs}
    cells = {(c, t) for _, c, t in runs}
    cell2run = {(c, t): rn for rn, c, t in runs}

    def picks_for_run(rn):
        # the FINAL run's artifacts still sit in the workspace until the
        # next dtlab-start archives them — adopt them into the
        # highest-numbered run, same rule as pack_evidence.py
        p = RUNSDIR / rn / "agent_picks.csv"
        if not p.exists() and rn == run_names[-1] \
                and (WS / "agent_picks.csv").exists():
            p = WS / "agent_picks.csv"
        return picks_by_task(p)

    rundata = {rn: picks_for_run(rn) for rn in run_names}
    if "--worksheet" in sys.argv:
        print_worksheet(student_id, task_ids, runs, rundata)
        return 0
    if "--amend" in sys.argv:
        migrate_legacy_locations()
        return amend_flow(student_id)
    # ---- SINGLE SESSION (D5): capture happens once, after the LAST run
    # of whichever design this student is actually running. "4" was the
    # 2x2's run count; it is not the only complete design any more, and
    # checking against it refused every three-condition student outright
    # (3 of 4, forever, since a run 4 was never coming).
    present_conds = {c for _, c, _ in runs}
    present_tiers = {t for _, _, t in runs if t}
    # No length-2 "legacy 2-run, complete" case: student_start.sh now
    # writes tier.txt unconditionally for every ablation run (it did not
    # always), which was the ONLY signal that used to distinguish a
    # genuine legacy 2-run pack from a three-condition student who has
    # only done 2 of their 3 runs so far. On today's build that legacy
    # shape cannot be produced live, and treating 2-of-3 as "complete"
    # would silently capture verdicts for a student who is not done —
    # a false positive is much worse here than a false negative.
    complete = (
        len(runs) >= 4                                     # legacy 2x2
        or (len(runs) == 3                                 # three-condition
            and present_conds == {"persona", "ablated", "nohistory"}
            and len(present_tiers) <= 1)
    )
    if not complete:
        print(f"\ndtlab-verdict — {student_id}. Runs on file: "
              f"{len(runs)} ({', '.join(sorted(present_conds)) or 'none'}).")
        print("Verdicts are captured ONCE, in one blind session after ALL")
        print("of your agent runs are done — persona, ablated AND")
        print("nohistory, on the same tier. Nothing was captured now.")
        print("(dtlab-verdict --worksheet works any time.)")
        return 0
    human = picks_by_task(HU / "human_picks.csv")

    migrate_legacy_locations()
    vpath = VD / "verdicts.csv"
    stored = {(r.get("task_id", "").strip(), r.get("condition", "").strip(),
               r.get("tier", "").strip()): r for r in read_csv_rows(vpath)}
    hpath = VD / "head_to_heads.csv"
    hstored = {(r.get("task_id", "").strip(), r.get("contrast", "").strip()):
               (r.get("winner") or "").strip()
               for r in read_csv_rows(hpath)}

    print(f"\ndtlab-verdict — {student_id}. Runs on file: " +
          ", ".join(run_names) + ".")
    print("BLIND assessment: each task shows the runs' picks in a")
    print("randomized order as Run A-D. Which run was which is revealed")
    print("AFTER your verdicts are saved.")
    print("Stored answers are FINAL (shown read-only on a re-run);")
    print("corrections go through  dtlab-verdict --amend  with a TA.")
    _old = superseded_attempts()
    if _old:
        print(f"\nYou redid at least one run: {len(_old)} earlier "
              "attempt(s) were replaced.")
        print("You are rating the LATEST attempt of each setup — that is")
        print("deliberate, and it is why you see three runs and not more.")
        print("The earlier ones were archived, not deleted:")
        print(f"  {HISTDIR}")
        print("  dtlab-runs      lists them")
        print("  dtlab-results   opens that folder in the file explorer")
    print()

    out_rows = []
    hrows = []
    new_rows_stored = False
    fams = contrast_families(cells)
    for t in task_ids:
        lab2run = blind_labels(student_id, t, run_names)
        run2lab = {rn: label for label, rn in lab2run.items()}
        h = human.get(t, {})
        h_asin = (h.get("asin") or "").strip()
        print(f"\n=== Task {t} ===")
        if h:
            print(f"    your pick : {h.get('title', '?')[:70]} ({h_asin})")
        # own-pick satisfaction: one judgment per task (it does not vary
        # by run); stored per row for schema compatibility, and FINAL
        # once stored
        cur_rs = next(((stored.get((t,) + condtier[rn], {})
                        .get("rating_self") or "").strip()
                       for rn in run_names
                       if (stored.get((t,) + condtier[rn], {})
                           .get("rating_self") or "").strip()), None)
        fresh_rows = [rn for rn in run_names
                      if not (stored.get((t,) + condtier[rn], {})
                              .get("verdict") or "").strip()]
        if cur_rs:
            rs = cur_rs
        elif fresh_rows:
            rs = ask_rating("    YOUR pick — satisfaction owning it "
                            "(1-10)")
        else:
            rs = ""
        for label in "ABCD"[:len(run_names)]:
            rn = lab2run[label]
            cond, tier = condtier[rn]
            cur = stored.get((t, cond, tier), {})
            a = rundata[rn].get(t, {})
            a_asin = (a.get("asin") or "").strip()
            print(f"\n  Run {label} pick: {(a.get('title') or '?')[:70]} "
                  f"({a_asin})")
            if (cur.get("verdict") or "").strip():
                # IMMUTABLE: the first stored value is final; display
                # read-only and keep the original row byte-for-byte
                # (verdict_at_utc included)
                print(f"    stored verdict: {cur['verdict']} (final — "
                      "corrections only via dtlab-verdict --amend)")
                out_rows.append({f: (cur.get(f) or "") for f in VFIELDS})
                continue
            if a_asin and h_asin:
                if a_asin == h_asin:
                    print("    (same ASIN as your pick — verdict must be "
                          "'identical')")
                    valid = {"identical"}
                else:
                    valid = {"better", "equivalent", "inferior"}
            else:
                valid = set(VERDICTS)
            v = ask("    verdict (better/identical/equivalent/inferior)",
                    valid)
            ra = ask_rating("    this pick — satisfaction owning it (1-10)")
            why = ask_line("    one-line rationale")
            new_rows_stored = True
            out_rows.append({
                "student_id": student_id, "task_id": t,
                "condition": cond, "tier": tier, "verdict": v,
                "rating_self": rs, "rating_agent": ra, "rationale": why,
                "verdict_at_utc":
                    datetime.now(timezone.utc).isoformat()})
        # pairwise head-to-heads for this task, still blind; stored
        # winners are final
        for fam, fam_cell_a, fam_cell_b, tie_word in fams:
            # present the pair in label order (A before D, etc.)
            (la, cell_a), (lb, cell_b) = sorted(
                [(run2lab[cell2run[fam_cell_a]], fam_cell_a),
                 (run2lab[cell2run[fam_cell_b]], fam_cell_b)])
            cur_res = hstored.get((t, fam)) or None
            if cur_res:
                print(f"  head-to-head {fam}: stored (final)")
                hrows.append({"task_id": t, "contrast": fam,
                              "winner": cur_res})
                continue
            w = ask(f"  head-to-head: Run {la} vs Run {lb} — better pick "
                    f"for you ({la.lower()}/{lb.lower()}/tie)",
                    {la.lower(), lb.lower(), "tie"})
            new_rows_stored = True
            hrows.append({"task_id": t, "contrast": fam,
                          "winner": resolved_winner(
                              fam, cell_a, cell_b, w, la, lb, tie_word)})

    # ---- carry forward stored rows for runs no longer readable (a
    #      corrupt condition.txt must never silently drop data) ----
    covered = {(r["task_id"], r["condition"], r["tier"]) for r in out_rows}
    carried = [r for k, r in stored.items() if k not in covered]
    for r in carried:
        out_rows.append({f: (r.get(f) or "") for f in VFIELDS})
    if carried:
        gone = sorted({(r.get("condition", ""), r.get("tier", ""))
                       for r in carried})
        print(f"\n  [..] carried forward {len(carried)} stored verdict "
              f"row(s) for run(s) not currently on file: "
              f"{', '.join(f'{c}/{t}' for c, t in gone)} — tell a TA if "
              "that is unexpected.")
    asked_h = {(r["task_id"], r["contrast"]) for r in hrows}
    hcarried = [{"task_id": k[0], "contrast": k[1], "winner": w}
                for k, w in hstored.items() if k not in asked_h]
    hrows += hcarried

    with open(vpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=VFIELDS)
        w.writeheader()
        w.writerows(out_rows)
    print(f"\nWrote {vpath} ({len(out_rows)} rows, schema "
          "dtlab-verdicts-v2, captured blind)")
    with open(hpath, "w", newline="", encoding="utf-8") as f:
        wcsv = csv.DictWriter(f, fieldnames=["task_id", "contrast",
                                             "winner"])
        wcsv.writeheader()
        wcsv.writerows(hrows)
    print(f"Wrote {hpath}")
    # ---- capture meta: blind is written true only when no reveal
    # preceded the last stored row; revealed_at_utc marks this
    # session's reveal (below) and survives re-runs ----
    mpath = VD / "capture_meta.json"
    prior_meta = {}
    if mpath.exists():
        try:
            prior_meta = json.loads(mpath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            prior_meta = {}
    complete = (sum(1 for r in out_rows
                    if (r.get("verdict") or "").strip())
                >= len(task_ids) * len(run_names)) \
        and len(hrows) >= len(task_ids) * len(fams)
    blind = bool(prior_meta.get("blind", True)) and not (
        prior_meta.get("revealed_at_utc") and new_rows_stored)
    now_utc = datetime.now(timezone.utc).isoformat()
    mpath.write_text(json.dumps({
        "schema": "dtlab-verdicts-v2",
        "blind": blind,
        "single_session": True,
        "written_at_utc": now_utc,
        "revealed_at_utc": prior_meta.get("revealed_at_utc")
        or (now_utc if complete else None),
    }, indent=2), encoding="utf-8")

    if not complete:
        print("\n(Reveal withheld: not every task x run verdict and "
              "head-to-head is on file yet — re-run dtlab-verdict.)")
        return 0

    # ---- reveal — only AFTER everything above is on disk ----
    print("\n=== Reveal — which run was which (hidden until now) ===")
    for rn, cond, tier in runs:
        print(f"  {rn}: {cond} grounding, {tier} tier")
    print("  Blind labels by task:")
    for t in task_ids:
        lab2run = blind_labels(student_id, t, run_names)
        print(f"    Task {t}: " + ", ".join(
            f"{label}={lab2run[label]}"
            for label in "ABCD"[:len(run_names)]))

    # ---- Overall reflections (after the full 2x2 exists) ----
    opath = VD / "overall_reflections.md"
    if len(runs) >= 4:
        print("\n=== Overall reflections (a few sentences each) ===")
        existing = opath.read_text(encoding="utf-8") if opath.exists() \
            else ""
        answers = []
        for i, q in enumerate(OVERALL_QUESTIONS, 1):
            # stored answer = text after the question's blank line
            m = re.search(rf"(?ms)^## Q{i}\n.*?\n\n(.*?)\n?(?=^## Q|\Z)",
                          existing)
            cur = (m.group(1).strip() or None) if m else None
            print(f"\n{q}")
            a = ask_block("  answer", cur)
            answers.append((q, a))
        opath.write_text(
            f"# Overall reflections — {student_id}\n\n" +
            "\n".join(f"## Q{i}\n{q}\n\n{a}\n"
                      for i, (q, a) in enumerate(answers, 1)),
            encoding="utf-8")
        print(f"\nWrote {opath}")
    else:
        print("\n(Overall reflections are asked once all four runs exist — "
              "re-run dtlab-verdict after the day-2 runs.)")

    print("\nDone. Next: after the final day's runs — dtlab-pack.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
