#!/usr/bin/env python3
"""mail_personas.py — INSTRUCTOR tool: email each student their own persona zip.

make_all_personas.py --zip produces one <ID>.zip per student. This walks
that folder, looks each ID's email up in the ID-confirmation form export,
and sends each student ONLY their own zip.

Nobody's zip is ever sent to anybody else: the ID in the filename is the
join key, one recipient per message, and an ID with no matching email is
reported and skipped rather than guessed at.

DRY RUN BY DEFAULT. Nothing is sent until you pass --send.

The password is read from the DTLAB_SMTP_PASSWORD environment variable —
never a flag, so it stays out of your shell history. For Gmail this is an
App Password (Google Account > Security > App passwords), not your normal
password.

USAGE
  export DTLAB_SMTP_PASSWORD='xxxx xxxx xxxx xxxx'
  python3 tools/mail_personas.py \
      --zips cohort_personas --roster id_form_responses.csv \
      --from you@bitsom.edu.in            # dry run: prints the plan
  python3 tools/mail_personas.py ... --send    # actually sends
"""

import argparse
import csv
import os
import re
import smtplib
import ssl
import sys
import time
from email.message import EmailMessage
from pathlib import Path

ID_RE = re.compile(r"DT\d{4}-\d{3}")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SUBJECT = "Digital Twin Lab — your persona files ({sid})"
BODY = """Hi,

Attached are your three persona files for the Digital Twin Lab:
persona_survey.md, persona_survey.csv and persona_meta.json.

In your codespace terminal, unzip them and move all three into
~/dtlab/workspace/ :

    unzip {sid}.zip
    mv persona_survey.md persona_survey.csv persona_meta.json ~/dtlab/workspace/

Then run your shopping session with your own participant ID:

    dtlab-shop --student-id {sid}

These files are personal to you — please don't share them.

Digital Twin Lab teaching team
"""


def norm_section(raw):
    """'Section A (Morning)' / 'A' / 'section a' -> 'A'. Returns '' when
    the answer names no recognisable section."""
    m = re.search(r"\bsection\s*([ab])\b|^\s*([ab])\s*$", (raw or "").strip(),
                  re.IGNORECASE)
    return (m.group(1) or m.group(2)).upper() if m else ""


def load_roster(path):
    """ID -> (email, section), from the ID-confirmation form export.
    Columns are matched by content, not position, since Forms exports
    carry the full question text as the header."""
    id_to_email, problems = {}, []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit(f"{path} has no rows")
    headers = rows[0].keys()
    id_col = next((h for h in headers if ID_RE.search(str(rows[0].get(h, "")))
                   or "participant id" in h.lower()
                   or "dt2026" in h.lower()), None)
    mail_col = next((h for h in headers if "email" in h.lower()), None)
    sect_col = next((h for h in headers if "section" in h.lower()), None)
    if not id_col or not mail_col:
        sys.exit(f"could not find an ID column and an email column in {path} "
                 f"(headers: {list(headers)[:6]}...)")
    for i, r in enumerate(rows, start=2):
        m = ID_RE.search((r.get(id_col) or "").strip().upper())
        email = (r.get(mail_col) or "").strip().lower()
        section = norm_section(r.get(sect_col)) if sect_col else ""
        if not m:
            problems.append(f"row {i}: no valid DT id in {id_col!r}")
            continue
        if not EMAIL_RE.match(email):
            problems.append(f"row {i}: {m.group(0)} has no usable email")
            continue
        sid = m.group(0)
        if sid in id_to_email and id_to_email[sid][0] != email:
            problems.append(f"row {i}: {sid} claimed by two emails "
                            f"({id_to_email[sid][0]}, {email}) — "
                            "resolve by hand")
            continue
        id_to_email[sid] = (email, section)
    return id_to_email, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zips", required=True,
                    help="folder of <ID>.zip from make_all_personas.py --zip")
    ap.add_argument("--roster", required=True,
                    help="CSV export of the ID-confirmation form")
    ap.add_argument("--from", dest="sender", required=True)
    ap.add_argument("--smtp", default="smtp.gmail.com")
    ap.add_argument("--port", type=int, default=465)
    ap.add_argument("--section", default=None, metavar="A|B",
                    help="only mail this section (from the ID form's section "
                         "question). Section A meets before Section B, so "
                         "you can mail A as soon as A has responded and "
                         "re-run for B later. Omit to mail everyone.")
    ap.add_argument("--send", action="store_true",
                    help="actually send (default is a dry run)")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="seconds between messages (default 1.0)")
    args = ap.parse_args()

    zips = sorted(Path(args.zips).glob("DT*.zip"))
    if not zips:
        sys.exit(f"no <ID>.zip files in {args.zips} — run "
                 "make_all_personas.py --zip first")
    id_to_email, problems = load_roster(args.roster)

    want = (args.section or "").strip().upper()
    planned, unmatched, other_section, no_section = [], [], [], []
    for z in zips:
        sid = z.stem
        entry = id_to_email.get(sid)
        if not entry:
            unmatched.append((sid, None, z))
            continue
        email, section = entry
        if want:
            if section == want:
                planned.append((sid, email, z))
            elif section:
                other_section.append(sid)
            else:
                no_section.append(sid)
        else:
            planned.append((sid, email, z))

    for p in problems:
        print(f"  [roster] {p}")
    for sid, _, _ in unmatched:
        print(f"  [skip] {sid}: no email on file — this student gets nothing")
    for sid in no_section:
        print(f"  [skip] {sid}: no section on their form row — send by hand "
              "or re-run without --section")
    matched_ids = {s for s, _, _ in planned} | set(other_section) \
        | set(no_section)
    for sid in sorted(set(id_to_email) - matched_ids):
        if want and id_to_email[sid][1] != want:
            continue          # other section's chase list, not this run's
        print(f"  [note] {sid} filled the ID form but has no persona zip")

    scope = f" in Section {want}" if want else ""
    print(f"\n{len(planned)} to send{scope}, {len(unmatched)} skipped, "
          f"{len(problems)} roster problem(s).")
    if other_section:
        print(f"{len(other_section)} held back (other section) — re-run with "
              "the other --section when they're ready.")
    if not args.send:
        for sid, email, _ in planned[:5]:
            print(f"  would send {sid}.zip -> {email}")
        if len(planned) > 5:
            print(f"  ... and {len(planned) - 5} more")
        print("\nDRY RUN — nothing sent. Re-run with --send when this looks "
              "right.")
        return 0
    if not planned:
        sys.exit("nothing to send")

    password = os.environ.get("DTLAB_SMTP_PASSWORD")
    if not password:
        sys.exit("set DTLAB_SMTP_PASSWORD first (an App Password for Gmail) "
                 "— it is deliberately not a command-line flag")

    sent, failed = 0, []
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(args.smtp, args.port, context=ctx) as s:
        s.login(args.sender, password)
        for sid, email, path in planned:
            msg = EmailMessage()
            msg["From"] = args.sender
            msg["To"] = email
            msg["Subject"] = SUBJECT.format(sid=sid)
            msg.set_content(BODY.format(sid=sid))
            msg.add_attachment(path.read_bytes(), maintype="application",
                               subtype="zip", filename=path.name)
            try:
                s.send_message(msg)
                sent += 1
                print(f"  sent {sid} -> {email}")
            except Exception as exc:                    # keep going
                failed.append((sid, email, repr(exc)))
                print(f"  FAILED {sid} -> {email}: {exc}")
            time.sleep(args.delay)

    print(f"\nSent {sent}/{len(planned)}.")
    for sid, email, err in failed:
        print(f"  retry by hand: {sid} -> {email} ({err})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
