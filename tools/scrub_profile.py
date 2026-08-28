#!/usr/bin/env python3
"""scrub_profile.py — post-extraction PII filter for purchase_profile.md.

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

The names to strip cannot be hard-coded and are NOT stored: they are
passed on the command line (the launcher prompts for them), used in
memory, and discarded. Only the count of redactions is reported.

Fail-closed: exits non-zero if a provided name survives scrubbing, so
the launcher refuses to freeze a leaking profile.

Usage:
  scrub_profile.py --profile PATH --student-id DT####-###
                   --names "Name One,Name Two" [--check-only]
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
    for pat in pats:
        text, k = pat.subn("[REDACTED-NAME]", text)
        n += k
    for pat, repl in GENERIC_PATTERNS:
        text, k = pat.subn(repl, text)
        n += k
    return text, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--student-id", required=True)
    ap.add_argument("--names", default="",
                    help="comma-separated account-holder names; used in "
                         "memory only, never stored")
    ap.add_argument("--check-only", action="store_true",
                    help="report leaks without rewriting")
    args = ap.parse_args()

    p = Path(args.profile)
    if not p.is_file() or p.stat().st_size == 0:
        sys.exit(f"scrub_profile: {p} missing or empty")
    text = p.read_text(encoding="utf-8")

    raw = [s for s in args.names.split(",") if s.strip()]
    pats = name_variants(raw)
    out, n = scrub(text, args.student_id, pats)

    # fail closed: no provided name may survive
    for name in raw:
        if re.search(re.escape(name.strip()), out, re.IGNORECASE):
            sys.exit(f"scrub_profile: '{name.strip()}' still present "
                     "after scrubbing — refusing; tell a TA")

    if args.check_only:
        print(f"scrub_profile: {n} PII match(es) would be redacted")
        sys.exit(1 if n else 0)

    if n:
        p.write_text(out, encoding="utf-8")
    print(f"scrub_profile: {n} PII match(es) redacted; profile "
          f"attributed to {args.student_id}")


if __name__ == "__main__":
    main()
