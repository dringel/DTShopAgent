#!/usr/bin/env python3
"""crosscheck_ids.py — INSTRUCTOR tool: reconcile participant IDs against
the ID-confirmation form, and build the TA-only identity map.

Two forms carry the same student. The questionnaire is keyed by the
participant ID they typed (`DT2026-042`); the ID-confirmation form asks
for their real BITSoM ID, their section, and the participant ID again.
Both forms collect an email address, and email is machine-captured rather
than typed from memory — so it is the reliable join key and the typed
participant IDs are what get checked against it, not the other way round.

Why this exists: in the beta, 2 of 4 students mistyped their own
participant ID (DT2026-192 for -190, DT2027-880 for DT2026-880). At
cohort scale those become silently unattributable rows, and a duplicated
ID becomes two students' data merged into one persona.

The questionnaire's ID is treated as authoritative when the two disagree,
because the persona files are generated from — and named after — that row.

OUTPUT
  identity_map.csv   TA-ONLY. bitsom_id, dt_id, email, section, status.
                     Never distribute; never commit; this is the file the
                     pseudonyms exist to keep out of the research data.
  plus an exceptions report on stdout — the rows a human must resolve.

USAGE
  python3 tools/crosscheck_ids.py \
      --responses responses.csv --idform id_form.csv \
      [--out identity_map.csv] [--section A]
"""

import argparse
import csv
import re
import sys
from collections import defaultdict

ID_RE = re.compile(r"DT\d{4}-\d{3}")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def norm_email(v):
    return (v or "").strip().lower()


def norm_id(v):
    m = ID_RE.search((v or "").strip().upper())
    return m.group(0) if m else ""


def norm_section(raw):
    m = re.search(r"\bsection\s*([ab])\b|^\s*([ab])\s*$", (raw or "").strip(),
                  re.IGNORECASE)
    return (m.group(1) or m.group(2)).upper() if m else ""


def pick(headers, *needles, sample=None):
    """Find a column by what it contains. Forms exports use the full
    question text as the header, so position is never reliable."""
    for h in headers:
        low = h.lower()
        if any(n in low for n in needles):
            return h
    if sample:                       # fall back to matching cell content
        for h in headers:
            if ID_RE.search(str(sample.get(h, "") or "")):
                return h
    return None


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit(f"{path} has no rows")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--responses", required=True,
                    help="questionnaire response export")
    ap.add_argument("--idform", required=True,
                    help="ID-confirmation form export")
    ap.add_argument("--out", default="identity_map.csv")
    ap.add_argument("--section", default=None, metavar="A|B",
                    help="restrict the report to one section")
    args = ap.parse_args()

    qrows, irows = read_rows(args.responses), read_rows(args.idform)

    q_id = pick(qrows[0].keys(), "participant id", "course-issued",
                sample=qrows[0])
    q_mail = pick(qrows[0].keys(), "email")
    if not q_id or not q_mail:
        sys.exit(f"could not find ID/email columns in {args.responses}")

    # the ID form has TWO id-ish columns: the real BITSoM one and the
    # participant one. Distinguish by the DT pattern, not by position.
    i_mail = pick(irows[0].keys(), "email")
    i_sect = pick(irows[0].keys(), "section")
    i_dt = next((h for h in irows[0].keys()
                 if any(ID_RE.search(str(r.get(h) or "")) for r in irows)),
                None)
    i_bits = next((h for h in irows[0].keys()
                   if h not in (i_dt, i_mail, i_sect)
                   and any(re.fullmatch(r"\d{4,12}", str(r.get(h) or "").strip())
                           for r in irows)), None)
    if not i_mail or not i_dt:
        sys.exit(f"could not find email/participant-ID columns in "
                 f"{args.idform}")

    # questionnaire: email -> dt_id, and dt_id -> email
    q_by_mail, q_by_id, dupes = {}, {}, []
    for r in qrows:
        e, d = norm_email(r.get(q_mail)), norm_id(r.get(q_id))
        if not d:
            continue
        if e:
            q_by_mail[e] = d
        if d in q_by_id and q_by_id[d] != e:
            dupes.append(f"questionnaire: {d} submitted by two emails "
                         f"({q_by_id[d]} and {e})")
        q_by_id[d] = e

    out_rows, problems = [], list(dupes)
    seen_dt, seen_bits = defaultdict(list), defaultdict(list)

    for n, r in enumerate(irows, start=2):
        email = norm_email(r.get(i_mail))
        claimed = norm_id(r.get(i_dt))
        bits = (r.get(i_bits) or "").strip() if i_bits else ""
        section = norm_section(r.get(i_sect)) if i_sect else ""

        if not EMAIL_RE.match(email):
            problems.append(f"ID form row {n}: unusable email {email!r}")
            continue

        if email in q_by_mail:                       # matched on email
            actual = q_by_mail[email]
            status = "ok" if actual == claimed else "id_mismatch"
            if status == "id_mismatch":
                problems.append(
                    f"ID form row {n} ({bits or 'no BITSoM id'}): claims "
                    f"{claimed or 'nothing'} but their questionnaire was "
                    f"submitted as {actual} — using {actual}, which is what "
                    "their persona is named after")
        elif claimed and claimed in q_by_id:         # matched on the ID
            actual, status = claimed, "email_mismatch"
            problems.append(
                f"ID form row {n} ({bits or 'no BITSoM id'}): the email "
                f"{email} does not appear on the questionnaire, but "
                f"{claimed} does — they used two different addresses; "
                "verify before trusting this row")
        else:
            actual, status = claimed, "no_questionnaire"
            problems.append(
                f"ID form row {n} ({bits or 'no BITSoM id'}, {email}): no "
                "questionnaire response found by email or by ID — they "
                "have not done it, or used a third address")

        if actual:
            seen_dt[actual].append(bits or email)
        if bits:
            seen_bits[bits].append(actual or email)
        out_rows.append({"bitsom_id": bits, "dt_id": actual, "email": email,
                         "section": section, "status": status})

    # collisions: the failure the pseudonym scheme cannot survive
    blocking = []
    for did, who in seen_dt.items():
        if len({w for w in who}) > 1:
            blocking.append(f"COLLISION: {did} claimed by {len(set(who))} "
                            f"different students ({', '.join(sorted(set(who)))})"
                            " — their data is unattributable until resolved")
    for bid, who in seen_bits.items():
        if len({w for w in who}) > 1:
            blocking.append(f"DUPLICATE: BITSoM id {bid} submitted twice with "
                            f"different participant IDs ({', '.join(sorted(set(who)))})")

    # students who did the questionnaire but never confirmed their ID
    confirmed = {r["dt_id"] for r in out_rows if r["dt_id"]}
    missing = sorted(set(q_by_id) - confirmed)

    if args.section:
        want = args.section.strip().upper()
        out_rows = [r for r in out_rows if r["section"] == want]

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["bitsom_id", "dt_id", "email",
                                          "section", "status"])
        w.writeheader()
        w.writerows(sorted(out_rows, key=lambda r: r["dt_id"]))

    ok = sum(1 for r in out_rows if r["status"] == "ok")
    print(f"Wrote {args.out}: {len(out_rows)} mapped, {ok} clean.")
    print("  TA-ONLY — this file links real identities to pseudonyms. "
          "Do not distribute or commit it.\n")

    if blocking:
        print("BLOCKING — resolve before generating or mailing personas:")
        for b in blocking:
            print(f"  {b}")
        print()
    if problems:
        print("Needs a human:")
        for p in problems:
            print(f"  {p}")
        print()
    if missing:
        print(f"Questionnaire done but ID form not submitted ({len(missing)}) "
              "— chase these:")
        for d in missing:
            print(f"  {d}  ({q_by_id[d] or 'no email'})")
        print()
    if not (blocking or problems or missing):
        print("No exceptions. Every ID-form row matches a questionnaire "
              "response, and every participant ID is unique.")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
