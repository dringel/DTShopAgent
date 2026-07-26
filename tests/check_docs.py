#!/usr/bin/env python3
"""
check_docs.py — dumb, fast CI doc-checker (D12; audit 9/10).

Three checks over the repo's markdown, no dependencies:
  (a) every intra-repo markdown link resolves to an existing file;
  (b) forbidden stale terms appear nowhere outside docs/archive/ and
      the changelog (a historical record), except the allowlisted
      legacy-ingestion / retired-design mentions below;
  (c) questionnaire_instrument_source.md is always referenced WITH its
      questionnaire/ directory.

The allowlist lives HERE, in the script — keep it short and literal.
Run from repo root:  python3 tests/check_docs.py
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# stale terms that must not reappear in current docs (audit 9.x)
FORBIDDEN = ("H_FIRST arm", "A_FIRST", "three tasks", "3 tasks",
             "TASK_CATEGORIES_10", "bit-identical")

# (relative path, term): deliberately retained mentions — legacy-pack
# ingestion notes and the retired-design rationale
ALLOWLIST = {
    ("research_protocol.md", "A_FIRST"),
    ("TA_ONBOARDING.md", "A_FIRST"),
    ("docs/design_rationale.md", "A_FIRST"),
    ("docs/design_rationale.md", "H_FIRST arm"),
    ("docs/design_rationale.md", "three tasks"),
}

# never scanned: the archive keeps retired documents verbatim, the
# changelog is a historical record, and handover files are gitignored
SKIP = ("docs/archive/", "docs/CHANGELOG.md", "CLAUDE_CODE_HANDOVER")

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")

problems = []


def md_files():
    for p in sorted(REPO.rglob("*.md")):
        rel = p.relative_to(REPO).as_posix()
        if any(part in rel for part in (".git/",)) or \
                any(rel.startswith(s) or s in rel for s in SKIP):
            continue
        yield p, rel


def check_links(p, rel, text):
    for target in LINK_RE.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path_part = target.split("#")[0]
        if not path_part:
            continue
        resolved = (p.parent / path_part).resolve()
        if not resolved.exists():
            problems.append(f"{rel}: broken link -> {target}")


def check_terms(rel, text):
    for term in FORBIDDEN:
        if term in text and (rel, term) not in ALLOWLIST:
            line = next(i + 1 for i, ln in enumerate(text.splitlines())
                        if term in ln)
            problems.append(f"{rel}:{line}: forbidden stale term "
                            f"'{term}'")


def check_instrument_ref(rel, text):
    # same-directory references inside questionnaire/ are unambiguous,
    # and contents-tree diagram lines carry the directory structurally
    if rel.startswith("questionnaire/"):
        return
    for i, ln in enumerate(text.splitlines()):
        if "├──" in ln or "└──" in ln:
            continue
        for m in re.finditer(r"questionnaire_instrument_source\.md", ln):
            before = ln[:m.start()]
            if not before.endswith("questionnaire/"):
                problems.append(
                    f"{rel}:{i + 1}: questionnaire_instrument_source.md "
                    "referenced without its questionnaire/ directory")


def main():
    n = 0
    for p, rel in md_files():
        n += 1
        text = p.read_text(encoding="utf-8", errors="replace")
        check_links(p, rel, text)
        check_terms(rel, text)
        if rel != "questionnaire/questionnaire_instrument_source.md":
            check_instrument_ref(rel, text)
    if problems:
        for pr in problems:
            print(f"FAIL: {pr}")
        print(f"\n{len(problems)} problem(s) across {n} markdown files.")
        return 1
    print(f"check_docs: {n} markdown files clean (links resolve, no "
          "stale terms, instrument source referenced with its "
          "directory).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
