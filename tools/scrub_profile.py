#!/usr/bin/env python3
"""scrub_profile.py — post-extraction PII filter for bootstrap text.

Why this exists (dry run, 18 Aug 2026): the bootstrap agent titled the
profile with the REAL NAME on the Amazon account ("Purchase Profile:
<account holder>"), pulled from a saved address — despite the SOUL never
asking for it and the participant being pseudonymous (DT####-###). The
instructor's chosen fix is a deterministic filter AFTER extraction, not
another instruction to the model: instructions produced the leak;
filters remove it.

Policy (per the 18 Aug instructor call):
  * STRIP  — person names on the account/addresses, street addresses,
             city+PIN lines, phone numbers, emails, Amazon customer IDs.
  * KEEP   — age and every demographic the questionnaire already covers.
  * The profile must end up attributed to the PSEUDONYM, never a name.

The names to strip cannot be hard-coded and are NOT stored: the launcher
passes them on stdin, the scrubber uses them in memory, and then discards
them. They never appear in the process command line. Only counts are
reported.

Fail-closed: every requested file is read and scrubbed in memory first.
No file is rewritten if a target is missing/empty or a supplied name (or
one of its scrub-worthy tokens) survives in any output.

Usage:
  printf '%s\n' "Name One,Name Two" | scrub_profile.py \
    --profile PATH --text-file PATH --student-id DT####-### --names-stdin
"""

import argparse
import re
import sys
from pathlib import Path

# Generic Amazon-page PII that needs no name list.
GENERIC_PATTERNS = [
    # "Hello, Vinir" / "Deliver to Vinita" / "Ship to X" page furniture
    (re.compile(r"(?im)^(.*\b(?:hello|deliver(?:ing)? to|ship to)[,:]?\s+)"
                r"[A-Z][a-zA-Z .'-]{1,40}$"), r"\1[REDACTED-NAME]"),
    # Labelled address lines. The full value is private even when it does
    # not include a PIN code or a supplied account-holder name.
    (re.compile(r"(?im)^(\s*(?:[-*+]\s*)?(?:delivery|shipping)?\s*address\s*:)"
                r"(?!\s*\[REDACTED-ADDRESS\]\s*$)\s*.+$"),
     r"\1 [REDACTED-ADDRESS]"),
    # Indian PIN codes in address-like context: "Kota 324005"
    (re.compile(r"\b([A-Z][a-z]{2,20})[ ,-]{1,3}(\d{6})\b"),
     "[REDACTED-CITY-PIN]"),
    # phone numbers (10+ digits, allowing separators)
    (re.compile(r"(?<!\d)(?:\+?91[ -]?)?\d{5}[ -]?\d{5}(?!\d)"),
     "[REDACTED-PHONE]"),
    # emails
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[REDACTED-EMAIL]"),
    # Amazon customer/account ids
    (re.compile(r"\bamzn1\.[\w.-]+\b", re.IGNORECASE), "[REDACTED-AMZN-ID]"),
]


def name_variants(raw_names):
    """Full names plus individual tokens (len>=3) with word boundaries.
    Token-level matching catches 'Purchase Profile: Vinita Gupta Rai'
    even if only part of the name was provided, at the cost of rare
    false positives — acceptable: this file is a behavioural summary,
    not prose about people."""
    pats = []
    for raw in raw_names:
        name = raw.strip()
        if not name:
            continue
        pats.append(re.compile(re.escape(name), re.IGNORECASE))
        for tok in name.split():
            if len(tok) >= 3:
                pats.append(re.compile(rf"\b{re.escape(tok)}\b", re.IGNORECASE))
    return pats


def _scrub_text(text, pats):
    n = 0
    for pat in pats:
        text, k = pat.subn("[REDACTED-NAME]", text)
        n += k
    for pat, repl in GENERIC_PATTERNS:
        text, k = pat.subn(repl, text)
        n += k
    return text, n


def scrub_text(text, pats):
    """Scrub a non-profile bootstrap text artifact."""
    return _scrub_text(text, pats)


def scrub(text, student_id, pats):
    n = 0
    # profile must be attributed to the pseudonym, never a name.
    # (idempotent: a header already reading "participant <id>" is not a
    # redaction — otherwise check-only mode reports a phantom leak on a
    # clean file and the launcher refuses to freeze it)
    hdr = re.compile(r"(?im)^(#\s*Purchase Profile:?\s*)(.*)$")
    m = hdr.search(text)
    if m and m.group(2).strip() != f"participant {student_id}":
        text = hdr.sub(rf"\1participant {student_id}", text, count=1)
        n += 1
    text, k = _scrub_text(text, pats)
    return text, n + k


def _surviving_name(text, pats):
    """Return true if any supplied full-name/token pattern survives."""
    without_marker = text.replace("[REDACTED-NAME]", "")
    return any(pat.search(without_marker) for pat in pats)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--text-file", action="append", default=[],
                    help="additional bootstrap text artifact to scrub; "
                         "repeatable")
    ap.add_argument("--student-id", required=True)
    ap.add_argument("--names-stdin", action="store_true",
                    help="read comma/newline-separated account-holder "
                         "names from stdin")
    ap.add_argument("--check-only", action="store_true",
                    help="report leaks without rewriting")
    args = ap.parse_args()

    if not re.fullmatch(r"DT\d{4}-\d{3}", args.student_id):
        sys.exit("scrub_profile: invalid participant pseudonym; tell a TA")

    names_text = sys.stdin.read() if args.names_stdin else ""
    raw = [s.strip() for s in re.split(r"[,\n]", names_text) if s.strip()]
    pats = name_variants(raw)

    targets = []
    seen = set()
    for value, is_profile in [(args.profile, True)] + [
            (value, False) for value in args.text_file]:
        p = Path(value)
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        if not p.is_file() or p.stat().st_size == 0:
            sys.exit(f"scrub_profile: {p} missing or empty")
        targets.append((p, is_profile, p.read_text(encoding="utf-8")))

    transformed = []
    total = 0
    for p, is_profile, text in targets:
        if is_profile:
            out, n = scrub(text, args.student_id, pats)
        else:
            out, n = scrub_text(text, pats)
        if _surviving_name(out, pats):
            sys.exit("scrub_profile: supplied name data still present "
                     "after scrubbing — refusing; tell a TA")
        transformed.append((p, out, n))
        total += n

    if args.check_only:
        print(f"scrub_profile: {total} PII match(es) would be redacted "
              f"across {len(targets)} file(s)")
        sys.exit(1 if total else 0)

    # Write only after every target has passed the fail-closed checks.
    for p, out, n in transformed:
        if n:
            p.write_text(out, encoding="utf-8")
    print(f"scrub_profile: {total} PII match(es) redacted across "
          f"{len(targets)} file(s); profile attributed to "
          f"{args.student_id}")


if __name__ == "__main__":
    main()
