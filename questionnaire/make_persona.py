#!/usr/bin/env python3
"""
make_persona.py — Turn one student's row of the Google Form response sheet
into the Hermes-ready persona files.

INPUTS
  --items      questionnaire_items.csv (the instrument; defines codes/constructs)
  --responses  responses.csv (File > Download > CSV from the linked response
               Sheet — the instructor distributes this, or each student
               downloads it and the script picks out only their own row)
  --student-id the pseudonym to extract (e.g. DT2026-042)

OUTPUTS (drop both into the Hermes workspace)
  persona_survey.md   — human/agent-readable, grouped by construct,
                        each answer tagged with its item code so the agent's
                        decision log can cite "PS16" verbatim
  persona_survey.csv  — flat machine-readable copy (item_code, construct,
                        question, answer) for the research dataset

USAGE
  python3 make_persona.py --items questionnaire_items.csv \
      --responses responses.csv --student-id DT2026-042
"""

import argparse
import csv
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

# Matches any code of 1-4 letters + 1-3 digits at the start of a Form header,
# e.g. "D01.", "PS16.", "RISK07." — see AUTHORING_GUIDE.md column contract.
CODE_RE = re.compile(r"^([A-Z]{1,4}\d{1,3})\.")

# Research-only items: answered in the Form and kept in the research CSV,
# but NEVER rendered into the agent-visible persona_survey.md. PR02 (next
# planned online purchase) and PR08 (item currently in cart/wishlist) name
# upcoming purchases — leaving them in the persona would hand the agent
# the answers to the shopping tasks (same confound and remedy as the PR09
# gift-task story, docs/design_rationale.md §8). The ONE authoritative
# exclusion set: student_start.sh's rendered-count gate and
# tests/test_instrument_lockstep.py reference it.
AGENT_HIDDEN_ITEMS = {"PR02", "PR08"}

# Sensitive demographic items (D6): rendered into the agent persona BY
# DEFAULT; the Form's administrative SENSITIVE_OPTOUT checkbox removes
# exactly these five from persona_survey.md (never from the research
# CSV). Exclusion is recorded in persona_meta.json and surfaces in the
# manifest and the cohort report.
SENSITIVE_ITEMS = {"D04", "D09", "D10", "D11", "D12"}
OPTOUT_PREFIX = "SENSITIVE_OPTOUT"


def load_items(path):
    items = OrderedDict()
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("item_code"):
                items[r["item_code"]] = r
    return items


def find_student_row(path, student_id):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        id_col = next((h for h in reader.fieldnames
                       if "participant id" in h.lower()
                       or "DT2026" in h or "course-issued" in h.lower()), None)
        if not id_col:
            sys.exit("Could not find the participant-ID column in responses.csv")
        for row in reader:
            if row.get(id_col, "").strip() == student_id:
                return row, reader.fieldnames
    sys.exit(f"No response row found for {student_id}. "
             f"Check the ID and that the form was submitted.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="questionnaire_items.csv")
    ap.add_argument("--responses", required=True)
    ap.add_argument("--student-id", required=True)
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args()

    items = load_items(args.items)
    if any(c.startswith("EX0") for c in items):
        sys.exit("questionnaire_items.csv still contains EX0x example rows — "
                 "replace them with the course's real items "
                 "(see AUTHORING_GUIDE.md).")
    row, headers = find_student_row(args.responses, args.student_id)

    # Form question headers look like "PS16. 'Only 2 left in stock'..."
    answers = OrderedDict()
    for h in headers:
        m = CODE_RE.match(h.strip())
        if m and m.group(1) in items:
            val = (row.get(h) or "").strip()
            # strip Likert prefix "4 - Agree" -> keep both number and label
            answers[m.group(1)] = val

    # administrative sensitive-item opt-out (D6): checkbox checked =
    # non-empty answer in the SENSITIVE_OPTOUT. column; absent column or
    # unchecked box = default (items rendered)
    optout_col = next((h for h in headers
                       if h.strip().startswith(OPTOUT_PREFIX)), None)
    sensitive_excluded = bool(optout_col
                              and (row.get(optout_col) or "").strip())
    hidden = set(AGENT_HIDDEN_ITEMS) | (
        SENSITIVE_ITEMS if sensitive_excluded else set())

    missing = [c for c in items if c not in answers]
    if missing:
        print(f"WARNING: {len(missing)} items missing from responses "
              f"(first few: {missing[:5]}). Continuing.", file=sys.stderr)

    outdir = Path(args.outdir)

    # ---- persona_survey.csv (research copy) ----
    with open(outdir / "persona_survey.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["student_id", "item_code", "construct",
                    "question", "answer", "constraint"])
        for code, item in items.items():
            w.writerow([args.student_id, code, item["construct"],
                        item["question"], answers.get(code, ""),
                        item.get("constraint", "0") or "0"])

    # ---- persona_survey.md (agent copy) ----
    lines = [
        f"# Consumer profile — participant {args.student_id}",
        "",
        f"Source: {len(items)}-item Digital Twin questionnaire "
        "(dtlab-persona-v1).",
        "Cite item codes verbatim when using these facts in the decision log.",
        "Likert answers: 1=Disagree strongly ... 5=Agree strongly.",
        "Items marked [CONSTRAINT] are inviolable rules, never preferences.",
    ]
    if sensitive_excluded:
        lines.append(
            f"{len(SENSITIVE_ITEMS)} sensitive demographic items excluded "
            "at the participant's request.")
    lines.append("")
    current = None
    n_rendered = 0
    for code, item in items.items():
        if code in hidden:
            continue      # research-only or opted-out: CSV yes, agent no
        if item["construct"] != current:
            current = item["construct"]
            lines += [f"## {current}", ""]
        ans = answers.get(code, "(no answer)")
        flag = " **[CONSTRAINT]**" if str(
            item.get("constraint", "0")).strip() == "1" else ""
        lines.append(f"- **{code}**{flag} {item['question']}  \n  → {ans}")
        n_rendered += 1
    (outdir / "persona_survey.md").write_text("\n".join(lines) + "\n",
                                              encoding="utf-8")

    # ---- persona_meta.json: what the agent copy hides (the pre-flight
    # rendered-count gate and the packer read this) ----
    (outdir / "persona_meta.json").write_text(json.dumps({
        "agent_hidden": sorted(hidden),
        "sensitive_excluded": sensitive_excluded,
        "rendered_items": n_rendered,
    }, indent=2), encoding="utf-8")

    print(f"Wrote persona_survey.md ({n_rendered} agent-visible items"
          + (", sensitive demographics excluded on request"
             if sensitive_excluded else "")
          + f"), persona_survey.csv (all {len(items)}), and "
          f"persona_meta.json for {args.student_id} "
          f"({len(answers)}/{len(items)} items answered).")


if __name__ == "__main__":
    main()
