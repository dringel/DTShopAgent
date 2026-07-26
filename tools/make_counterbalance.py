#!/usr/bin/env python3
"""
make_counterbalance.py — INSTRUCTOR tool: generate the per-student
grounding-order counterbalance sheet for the four-run 2x2.

One file, two destinations: upload it to the LMS as the assignment
sheet AND place it at the repo root as counterbalance.csv before the
freeze — provisioning bakes it to ~/dtlab/counterbalance.csv, where
dtlab-start looks up each student's day order and demotes typed entry
to a confirmation. Pseudonyms only — no PII ever enters this file.

INPUT   --roster roster.csv with columns: student_id, section
        (optional: pair_id — carried through unchanged)
OUTPUT  --out counterbalance.csv with columns:
        student_id, section, pair_id, day1_order, day2_order,
        tier_day1, tier_day2

Balance: within each section, half P_FIRST / half NP_FIRST per day
(the odd student falls on the seeded coin), with day 2 re-randomized
independently of day 1 — the design's per-day counterbalancing,
stratified by section. The MODEL-TIER order (economy-first vs
frontier-first across the two days) is likewise balanced within
section and drawn INDEPENDENTLY of the grounding orders, so tier
order is orthogonal to grounding order by construction; the printed
2x2 crosstab per section makes the balance auditable. Deterministic:
the same roster and --seed always produce the same sheet.

USAGE
  python3 tools/make_counterbalance.py --roster roster.csv \
      [--out counterbalance.csv] [--seed 2026]
"""

import argparse
import csv
import hashlib
import random
import sys
from collections import Counter
from pathlib import Path


def validate(roster_path, cb_path):
    """Freeze gate (audit 8.2): full roster coverage, per-section
    balance of grounding AND tier orders, and the sheet's sha256 for
    the freeze record. Exit non-zero on any problem."""
    with open(roster_path, newline="", encoding="utf-8-sig") as f:
        roster = [r for r in csv.DictReader(f)
                  if (r.get("student_id") or "").strip()]
    with open(cb_path, newline="", encoding="utf-8-sig") as f:
        cb = [r for r in csv.DictReader(f)
              if (r.get("student_id") or "").strip()]
    r_ids = {r["student_id"].strip() for r in roster}
    c_ids = {r["student_id"].strip() for r in cb}
    problems = []
    if r_ids - c_ids:
        problems.append("roster students missing from the sheet: "
                        f"{sorted(r_ids - c_ids)[:8]}")
    if c_ids - r_ids:
        problems.append("sheet students not on the roster: "
                        f"{sorted(c_ids - r_ids)[:8]}")
    by_section = {}
    for r in cb:
        by_section.setdefault(
            (r.get("section") or "").strip() or "ALL", []).append(r)
    checks = (("day1_order", "P_FIRST", "NP_FIRST"),
              ("day2_order", "P_FIRST", "NP_FIRST"),
              ("tier_day1", "economy", "frontier"))
    for section, members in sorted(by_section.items()):
        for col, va, vb in checks:
            c = Counter((m.get(col) or "").strip() for m in members)
            if c[va] + c[vb] != len(members):
                problems.append(f"section {section}: {col} has "
                                f"non-{va}/{vb} values")
            elif abs(c[va] - c[vb]) > 1:
                problems.append(f"section {section}: {col} unbalanced "
                                f"({va} {c[va]} vs {vb} {c[vb]})")
    for r in cb:
        if {(r.get("tier_day1") or "").strip(),
                (r.get("tier_day2") or "").strip()} != {"economy",
                                                        "frontier"}:
            problems.append(f"{r['student_id']}: tier_day1/tier_day2 "
                            "are not complementary")
            break
    sha = hashlib.sha256(Path(cb_path).read_bytes()).hexdigest()
    print(f"counterbalance.csv sha256: {sha}  (record at freeze)")
    if problems:
        for pr in problems:
            print(f"INVALID: {pr}")
        sys.exit(1)
    print(f"VALID: {len(cb)} students, full roster coverage, grounding "
          "and tier orders balanced within every section.")


def assign_day(sids, seed, day):
    """Balanced P_FIRST/NP_FIRST assignment for one section-day."""
    rng = random.Random(f"{seed}|day{day}|{'|'.join(sorted(sids))}")
    order = sorted(sids)
    rng.shuffle(order)
    n_p = len(order) // 2 + (rng.randrange(2) if len(order) % 2 else 0)
    return {sid: ("P_FIRST" if i < n_p else "NP_FIRST")
            for i, sid in enumerate(order)}


def assign_tier_order(sids, seed):
    """Balanced economy-first/frontier-first day-1 tier for one section,
    drawn from its OWN seeded stream — independent of the grounding
    draws, so tier order is orthogonal to grounding order."""
    rng = random.Random(f"{seed}|tierorder|{'|'.join(sorted(sids))}")
    order = sorted(sids)
    rng.shuffle(order)
    n_e = len(order) // 2 + (rng.randrange(2) if len(order) % 2 else 0)
    return {sid: ("economy" if i < n_e else "frontier")
            for i, sid in enumerate(order)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roster",
                    help="CSV with student_id, section (optional pair_id)")
    ap.add_argument("--out", default="counterbalance.csv")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--validate", nargs=2,
                    metavar=("roster.csv", "counterbalance.csv"),
                    help="freeze gate: assert full roster coverage and "
                         "per-section balance of grounding + tier "
                         "orders; prints the sheet's sha256 for the "
                         "freeze record")
    args = ap.parse_args()
    if args.validate:
        return validate(*args.validate)
    if not args.roster:
        ap.error("--roster is required (or use --validate)")

    with open(args.roster, newline="", encoding="utf-8-sig") as f:
        roster = [r for r in csv.DictReader(f)
                  if (r.get("student_id") or "").strip()]
    if not roster:
        sys.exit("roster has no student_id rows")
    sids = [r["student_id"].strip() for r in roster]
    if len(sids) != len(set(sids)):
        dupes = [s for s, n in Counter(sids).items() if n > 1]
        sys.exit(f"duplicate student_id(s) in the roster: {dupes[:5]}")

    by_section = {}
    for r in roster:
        by_section.setdefault((r.get("section") or "").strip() or "ALL",
                              []).append(r["student_id"].strip())
    day1, day2, tier1 = {}, {}, {}
    for section, members in by_section.items():
        day1.update(assign_day(members, f"{args.seed}|{section}", 1))
        day2.update(assign_day(members, f"{args.seed}|{section}", 2))
        tier1.update(assign_tier_order(members, f"{args.seed}|{section}"))

    out = Path(args.out)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["student_id", "section",
                                          "pair_id", "day1_order",
                                          "day2_order", "tier_day1",
                                          "tier_day2"])
        w.writeheader()
        for r in roster:
            sid = r["student_id"].strip()
            w.writerow({"student_id": sid,
                        "section": (r.get("section") or "").strip(),
                        "pair_id": (r.get("pair_id") or "").strip(),
                        "day1_order": day1[sid],
                        "day2_order": day2[sid],
                        "tier_day1": tier1[sid],
                        "tier_day2": ("frontier"
                                      if tier1[sid] == "economy"
                                      else "economy")})

    for day, amap in (("day 1", day1), ("day 2", day2)):
        for section, members in sorted(by_section.items()):
            c = Counter(amap[s] for s in members)
            print(f"{day} section {section}: P_FIRST {c['P_FIRST']} / "
                  f"NP_FIRST {c['NP_FIRST']}")
    for section, members in sorted(by_section.items()):
        c = Counter(tier1[s] for s in members)
        print(f"tier order section {section}: economy-first "
              f"{c['economy']} / frontier-first {c['frontier']}")
        ct = Counter((tier1[s], day1[s]) for s in members)
        print("  2x2 crosstab (tier-order x day1-grounding): " +
              ", ".join(f"{t}-first/{g}={ct.get((t, g), 0)}"
                        for t in ("economy", "frontier")
                        for g in ("P_FIRST", "NP_FIRST")))
    print(f"Wrote {out} ({len(roster)} students, seed {args.seed}). "
          "Upload to the LMS AND place at the repo root as "
          "counterbalance.csv before the freeze.")


if __name__ == "__main__":
    main()
