#!/usr/bin/env python3
"""
make_task_docs.py — INSTRUCTOR tool: regenerate the task-dependent student
documents from tasks_config.csv, so a custom task set (e.g. the 6-task
utilitarian/hedonic design in tasks_config_6task_example.csv) never drifts
from what the packer validates.

USAGE (from repo root)
  python3 tools/make_task_docs.py [--config tasks_config.csv]
                                  [--outdir templates]

Writes: templates/tasks.md, templates/comparison.md,
templates/comparison_ablation.md. Run it AFTER editing the config, commit
the result, and re-run the test harness. The shipped 3-task templates ARE
this generator's output for tasks_config.csv — the harness round-trip
check keeps them byte-identical; the packer validates submissions against
the config either way.
"""

import argparse
import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load(path):
    """Active rows only: task_ids starting with '#' are inactive catalog
    entries (see docs/TASK_CATEGORIES_10.md for the activation workflow)."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f)
                if r.get("task_id", "").strip()
                and not r["task_id"].strip().startswith("#")]
    if not rows:
        sys.exit(f"no active tasks in {path} (rows starting with '#' are "
                 "inactive — remove the '#' to activate)")
    ids = [r["task_id"].strip() for r in rows]
    if len(ids) != len(set(ids)):
        sys.exit("duplicate task_id in config")
    return rows


def budget_text(r):
    lo, hi = int(r["budget_min_inr"]), int(r["budget_max_inr"])
    return f"Rs.{lo}-{hi}" if lo else f"budget ceiling: Rs.{hi}"


def gen_tasks(tasks):
    has_gift = any("gift" in r["product_type"].lower() for r in tasks)
    L = ["# The shopping tasks — participant {STUDENT_ID}", "",
         "<!-- GENERATED from tasks_config.csv by tools/make_task_docs.py —",
         "     edit the CONFIG, not this file."]
    if has_gift:
        L += ["     STUDENT: fill only the {...} fields in the gift task,",
              "     nothing else."]
    else:
        L += ["     STUDENT: edit NOTHING in this file."]
    L += ["     dtlab-start re-orders the task sections into YOUR assigned",
          "     (randomized) order at pre-flight — never re-sort by hand.",
          "     This exact file is (a) pasted to the agent on lab day and",
          "     (b) packed as a deliverable, so keep it verbatim. -->", ""]
    for r in tasks:
        name = (r.get("short_name") or "").strip() or r["frame"]
        L += [f"## Task {r['task_id']} — {name} ({budget_text(r)})"]
        if "gift" in r["product_type"].lower():
            L += ["Add to cart a birthday gift for my {RELATIONSHIP — e.g. "
                  "\"younger sister\"}.",
                  "About them: {TWO_SENTENCE_DESCRIPTION}.", ""]
        else:
            L += [f"Add to cart {r['product_type']}. Category class "
                  f"({r['category_class']}) is for the analysis, not for "
                  "you — shop normally.", ""]
    n = len(tasks)
    L += ["---",
          "dtlab-start announces before every run which of the two "
          "prompts below",
          "to paste — standard for persona runs, ABLATED for ablated "
          "runs.", "",
          "Standardized agent prompt (paste into Hermes after "
          "/browser connect):", "",
          "Read persona_survey.md and purchase_profile.md again before "
          "starting.",
          f"You have {n} tasks on amazon.in, listed in tasks.md in this "
          "workspace.",
          "Work through them IN THE ORDER they appear in tasks.md.",
          "For each: search, evaluate candidates, and ADD TO CART exactly "
          "one item.",
          "Follow the decision-log and agent_picks.csv protocol in your "
          "SOUL for", "every task. Do not check out.", "",
          "---",
          "Standardized agent prompt — ABLATED run (only if the "
          "questionnaire-",
          "ablation factor is enabled; dtlab-start tells you which run "
          "this is):", "",
          "Read purchase_profile.md again before starting. You have "
          f"{n} tasks on",
          "amazon.in, listed in tasks.md in this workspace. Work through "
          "them IN",
          "THE ORDER they appear in tasks.md. For each: search, evaluate",
          "candidates, and ADD TO CART exactly one item. Follow the "
          "decision-log",
          "and agent_picks.csv protocol in your SOUL for every task. Do "
          "not check", "out."]
    return "\n".join(L) + "\n"


BLOCK = """Verdict: {better|identical|equivalent|inferior}
My pick: {title} | Agent pick: {title}
My pick rating (1-10): {N}
Agent pick rating (1-10): {N}
Attribution — which evidence did the decision log cite, and was it real
or confabulated?
{...}
Mechanism — where we diverged, why?
{...}
"""

OVERALL = """## Overall (answer all four)
1. Stated vs revealed: when my survey answers and purchase history
   conflicted, which did the agent follow — and which SHOULD it have?
{...}
2. Platform power: roughly what share of the agent's candidate sets came
   from first-page / sponsored results?
{...}
3. Delegation: would I give this twin real spending authority with a cap?
   For which categories?
{...}
4. The one change that would most improve my twin:
{...}
"""

HEAD = """# Comparison & assessment — participant {STUDENT_ID}

<!-- GENERATED from tasks_config.csv by tools/make_task_docs.py.
     Verdict values: better | identical | equivalent | inferior (your
     agent's pick relative to YOUR OWN pick; 'identical' is
     ASIN-verified). Ratings: how satisfied would you be OWNING each
     pick, 1-10, whole numbers. Machine-parsed — do not rephrase. -->
"""


def gen_comparison(tasks):
    out = [HEAD]
    for r in tasks:
        out.append(f"## Task {r['task_id']}\n{BLOCK}")
    out.append(OVERALL)
    return "\n".join(out)


# compact per-run block for the four-run 2x2 (verdict + two ratings +
# one Attribution line; the prose analysis happens ONCE per task in the
# synthesis section, not per block)
BLOCK_2X2 = """Verdict: {better|identical|equivalent|inferior}
My pick rating (1-10): {N}
Agent pick rating (1-10): {N}
Attribution — evidence the decision log cited, real or confabulated: {...}
"""

# keep in lockstep with tools/capture_verdicts.py::OVERALL_QUESTIONS
OVERALL_ABLATION = """## Overall (answer all five)
1. What did the questionnaire demonstrably add over your purchase history
   alone — and where did the ablated twin do just as well or better?
{...}
2. Constraints: your CONSTRAINT items (allergies, exclusions) were absent
   in the ablated runs. Did their picks violate any? What does that imply
   for real deployment?
{...}
3. Tier: what did the frontier model demonstrably buy over the economy
   model — and was it worth ~10x the token price?
{...}
4. Delegation: which twin (if any) would you give real spending authority
   with a cap, and for which categories?
{...}
5. The one change that would most improve your twin:
{...}
"""


BLIND_NOTE = """<!-- BLIND ASSESSMENT: each task's four runs appear below only as
     Run A-D, in a per-task randomized order (the same order dtlab-verdict
     uses). Run `dtlab-verdict --worksheet` for the per-task list of which
     PICK is Run A/B/C/D — titles and ASINs only; which run was persona or
     ablated, economy or frontier stays hidden until after your verdicts.
     Fill every verdict block before the Head-to-head section. -->
"""


def gen_comparison_ablation(tasks):
    """Four-run 2x2 fallback memo (dtlab-verdict is the primary capture):
    per task, four compact BLIND blocks (Run A-D; pack_evidence.py
    resolves the labels), then ONE prose synthesis, then the
    machine-parsed head-to-head lines (filled after the reveal)."""
    out = [HEAD.replace("— participant",
                        "(four-run 2x2 design) — participant"), BLIND_NOTE]
    for r in tasks:
        t = r["task_id"]
        for run_label in ("A", "B", "C", "D"):
            out.append(f"## Task {t} (Run {run_label})\n{BLOCK_2X2}")
        out.append(f"## Task {t} synthesis (across the four runs)\n"
                   "One short paragraph: what explains the pattern across "
                   "the four runs\n(grounding effect, tier effect, both, "
                   "neither)?\n{...}\n")
    hh = ["## Head-to-head",
          "<!-- Compare the runs' picks per task DIRECTLY. Fill this",
          "     section AFTER all verdict blocks: it names conditions,",
          "     and dtlab-verdict (or a TA) reveals which run was which",
          "     once verdicts are on file. Machine-parsed: keep each",
          "     line's format exactly. -->"]
    for r in tasks:
        t = r["task_id"]
        hh += [f"Task {t} winner (economy): {{persona|ablated|tie}}",
               f"Task {t} winner (frontier): {{persona|ablated|tie}}",
               f"Task {t} better model (persona): {{frontier|economy|same}}",
               f"Task {t} better model (ablated): {{frontier|economy|same}}"]
    hh += ["Where two runs picked the SAME product, what does that say "
           "about what", "the varied factor added (or didn't)?", "{...}", ""]
    out.append("\n".join(hh))
    out.append(OVERALL_ABLATION)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(REPO / "tasks_config.csv"))
    ap.add_argument("--outdir", default=str(REPO / "templates"))
    args = ap.parse_args()
    tasks = load(args.config)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "tasks.md").write_text(gen_tasks(tasks), encoding="utf-8")
    (outdir / "comparison.md").write_text(gen_comparison(tasks),
                                          encoding="utf-8")
    (outdir / "comparison_ablation.md").write_text(
        gen_comparison_ablation(tasks), encoding="utf-8")
    print(f"Wrote tasks.md, comparison.md, comparison_ablation.md for "
          f"{len(tasks)} tasks -> {outdir}/")
    print("Re-run: bash tests/simulate_submission.sh (and re-freeze the "
          "task set before lab day).")


if __name__ == "__main__":
    main()
