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
import shutil
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
                    help="also write one <ID>.zip per student "
                         "(exact allowlist: persona_survey.md, "
                         "persona_survey.csv, persona_meta.json)")
    ap.add_argument("--latest-wins", action="store_true",
                    help="resolve duplicate submissions by keeping the "
                         "latest Form timestamp per ID (decision logged "
                         "to the roster); without it duplicates are a "
                         "blocking error")
    ap.add_argument("--keep-email", action="store_true",
                    help="INSTRUCTOR integrity check only: keep the "
                         "email column in the research copy — never for "
                         "distribution (email stripping is the default)")
    ap.add_argument("--strip-email", action="store_true",
                    help="(deprecated no-op: stripping is the default)")
    args = ap.parse_args()

    with open(args.responses, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        id_col = next((h for h in headers
                       if "participant id" in h.lower()
                       or "course-issued" in h.lower()), None)
        if not id_col:
            sys.exit("No participant-ID column found in responses.csv")
        ts_col = next((h for h in headers
                       if h.strip().lower() == "timestamp"), None)
        all_rows = list(reader)

    # duplicate submissions: BLOCKING unless --latest-wins (audit 5.8)
    by_id = {}
    dup_log = []
    for row in all_rows:
        m = ID_RE.search(row.get(id_col, ""))
        if not m:
            continue
        sid = m.group(0)
        prev = by_id.get(sid)
        if prev is None:
            by_id[sid] = row
            continue
        if not args.latest_wins:
            by_id[sid] = "DUP"
            continue
        newer = (row.get(ts_col) or "") > (prev.get(ts_col) or "") \
            if ts_col else False
        kept, dropped = (row, prev) if newer else (prev, row)
        dup_log.append(f"{sid}: kept the row stamped "
                       f"{kept.get(ts_col)} over {dropped.get(ts_col)}"
                       if ts_col else f"{sid}: kept the first row")
        by_id[sid] = kept
    dupes = sorted(s for s, r in by_id.items() if r == "DUP")
    if dupes:
        sys.exit(f"duplicate submissions for {dupes} — resolve them in "
                 "the response sheet, or pass --latest-wins to keep the "
                 "latest Form timestamp per ID (the decision is logged "
                 "to the roster output).")

    # generation source: the deduplicated sheet (make_persona takes the
    # first matching row, so the dedup must happen HERE)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    import tempfile
    dedup_path = None
    responses_for_gen = args.responses
    if dup_log:
        fd = tempfile.NamedTemporaryFile(
            "w", newline="", encoding="utf-8", suffix=".csv",
            delete=False)
        with fd as fh:
            w = csv.DictWriter(fh, fieldnames=headers)
            w.writeheader()
            w.writerows(by_id[s] for s in sorted(by_id))
        dedup_path = fd.name
        responses_for_gen = dedup_path

    ALLOWLIST = ("persona_survey.md", "persona_survey.csv",
                 "persona_meta.json")
    ok, fail, skipped = [], [], []
    for sid in sorted(by_id):
        with tempfile.TemporaryDirectory() as tdir:
            r = subprocess.run(
                check=False,
                args=[sys.executable, str(MAKE_PERSONA),
                      "--items", args.items,
                      "--responses", responses_for_gen,
                      "--student-id", sid, "--outdir", tdir],
                capture_output=True, text=True)
            if r.returncode != 0:
                err = (r.stderr.strip().splitlines()[-1]
                       if r.stderr else "unknown error")
                if "no consent on file" in err:
                    skipped.append((sid, "no consent on file — resolve "
                                    "before generating this persona"))
                else:
                    fail.append((sid, err))
                continue
            # exact allowlist, staged in a fresh temp dir, atomically
            # replacing the per-student output (audit 5.8) — the full
            # response sheet never enters a per-student artifact
            stage = outdir / f".{sid}.tmp"
            if stage.exists():
                shutil.rmtree(stage)
            stage.mkdir(parents=True)
            for name in ALLOWLIST:
                src = Path(tdir) / name
                if src.exists():
                    shutil.copy2(src, stage / name)
            final = outdir / sid
            if final.exists():
                shutil.rmtree(final)
            stage.rename(final)
            ok.append(sid)
            if args.zip:
                ztmp = outdir / f"{sid}.zip.tmp"
                with zipfile.ZipFile(ztmp, "w",
                                     zipfile.ZIP_DEFLATED) as z:
                    for name in ALLOWLIST:
                        if (final / name).exists():
                            z.write(final / name, name)
                ztmp.replace(outdir / f"{sid}.zip")
    if dedup_path:
        Path(dedup_path).unlink(missing_ok=True)

    print(f"\nGenerated personas for {len(ok)} students -> {outdir}/")
    for line in dup_log:
        print(f"  duplicate resolved (--latest-wins): {line}")
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
    if skipped:
        print(f"SKIPPED, consent unresolved ({len(skipped)}):")
        for sid, why in skipped:
            print(f"  {sid}: {why}")
    if fail:
        print(f"FAILED ({len(fail)}):")
        for sid, err in fail:
            print(f"  {sid}: {err}")
    print("\nRoster check: compare the ID list above against your class "
          "list to chase missing questionnaire submissions before "
          "session 2.")

    # Email hygiene (research_protocol.md §2): the raw Form export
    # contains institutional emails; the research copy is written
    # email-stripped BY DEFAULT (--keep-email is the instructor's
    # integrity check, never for distribution).
    with open(args.responses, newline="", encoding="utf-8-sig") as f:
        reader2 = csv.reader(f)
        header2 = next(reader2)
        keep = [i for i, h in enumerate(header2)
                if args.keep_email or "email" not in h.lower()]
        research = outdir / "responses_research.csv"
        with open(research, "w", newline="", encoding="utf-8") as out:
            w = csv.writer(out)
            w.writerow([header2[i] for i in keep])
            for row in reader2:
                w.writerow([row[i] for i in keep if i < len(row)])
    print(f"\nWrote research copy -> {research} "
          + ("(EMAILS KEPT — integrity check only, never distribute)"
             if args.keep_email else "(email columns stripped)"))
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
