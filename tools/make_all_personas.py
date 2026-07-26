#!/usr/bin/env python3
"""
make_all_personas.py — INSTRUCTOR batch tool for the overnight turnaround.

Between session 1 (evening: students complete the Form) and session 2
(morning), run this once against the exported response sheet. It produces
one folder per student containing their persona_survey.md/.csv, ready to
distribute (e.g. one zip per student on the LMS, or a shared read-only
folder where each student grabs their own ID folder).

USAGE
  python3 make_all_personas.py --items questionnaire_items.csv \
      --responses responses.csv --outdir cohort_personas [--zip]

Idempotent; re-running regenerates everything. Prints a completion roster
so you can chase missing submissions before session 2 starts.
"""

import argparse
import csv
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAKE_PERSONA = HERE.parent / "questionnaire" / "make_persona.py"
if not MAKE_PERSONA.exists():                       # tools/ layout on the VM
    MAKE_PERSONA = HERE / "make_persona.py"


def _load_id_pattern():
    """Shared ID pattern from dtlab_config.env (repo root or ~/dtlab)."""
    for p in (HERE.parent / "dtlab_config.env",
              Path.home() / "dtlab" / "dtlab_config.env"):
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("DTLAB_ID_PATTERN="):
                    return line.split("=", 1)[1].strip().strip("'\"")
    return r"DT[0-9]{4}-[0-9]{3}"


ID_RE = re.compile(_load_id_pattern())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True)
    ap.add_argument("--responses", required=True)
    ap.add_argument("--outdir", default="cohort_personas")
    ap.add_argument("--zip", action="store_true",
                    help="also write one <ID>.zip per student")
    ap.add_argument("--strip-email", action="store_true",
                    help="also write <outdir>/responses_research.csv with "
                         "every email column removed (the research copy "
                         "required by research_protocol.md §2)")
    args = ap.parse_args()

    with open(args.responses, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        id_col = next((h for h in reader.fieldnames
                       if "participant id" in h.lower()
                       or "course-issued" in h.lower()), None)
        if not id_col:
            sys.exit("No participant-ID column found in responses.csv")
        ids = []
        for row in reader:
            m = ID_RE.search(row.get(id_col, ""))
            if m:
                ids.append(m.group(0))

    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        print(f"WARNING: duplicate submissions for {sorted(dupes)} — "
              f"make_persona uses the FIRST row per ID.", file=sys.stderr)

    outdir = Path(args.outdir)
    ok, fail = [], []
    for sid in sorted(set(ids)):
        d = outdir / sid
        d.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            check=False,
            args=[sys.executable, str(MAKE_PERSONA), "--items", args.items,
             "--responses", args.responses, "--student-id", sid,
             "--outdir", str(d)],
            capture_output=True, text=True)
        if r.returncode == 0:
            ok.append(sid)
            if args.zip:
                with zipfile.ZipFile(outdir / f"{sid}.zip", "w",
                                     zipfile.ZIP_DEFLATED) as z:
                    for f_ in d.iterdir():
                        z.write(f_, f_.name)
        else:
            fail.append((sid, r.stderr.strip().splitlines()[-1]
                         if r.stderr else "unknown error"))

    print(f"\nGenerated personas for {len(ok)} students -> {outdir}/")
    # sensitive-item opt-outs (D6): surfaced on the roster so the
    # exclusion is visible at distribution time, not discovered later
    optouts = []
    for sid in ok:
        meta = outdir / sid / "persona_meta.json"
        try:
            if json.loads(meta.read_text(
                    encoding="utf-8")).get("sensitive_excluded"):
                optouts.append(sid)
        except (OSError, ValueError):
            pass
    if optouts:
        print(f"Sensitive-item opt-outs ({len(optouts)}): "
              f"{', '.join(optouts)} — their agent personas exclude "
              "D04/D09/D10/D11/D12 (research CSV unchanged).")
    if fail:
        print(f"FAILED ({len(fail)}):")
        for sid, err in fail:
            print(f"  {sid}: {err}")
    print("\nRoster check: compare the ID list above against your class "
          "list to chase missing questionnaire submissions before "
          "session 2.")

    # Email hygiene (research_protocol.md §2): the raw Form export contains
    # institutional emails; the research copy must not.
    if args.strip_email:
        with open(args.responses, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader)
            keep = [i for i, h in enumerate(header)
                    if "email" not in h.lower()]
            research = outdir / "responses_research.csv"
            with open(research, "w", newline="", encoding="utf-8") as out:
                w = csv.writer(out)
                w.writerow([header[i] for i in keep])
                for row in reader:
                    w.writerow([row[i] for i in keep if i < len(row)])
        print(f"\nWrote email-stripped research copy -> {research}")
    else:
        print("\nREMINDER: responses.csv contains institutional emails. "
              "The research copy must have the email column deleted "
              "(research_protocol.md §2) — re-run with --strip-email to "
              "generate it automatically.")


if __name__ == "__main__":
    main()
