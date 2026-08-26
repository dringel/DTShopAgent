#!/usr/bin/env python3
"""capture_tokens.py — token + cost accounting for one agent run.

T-21 item 12 asks for a token/cost benchmark across tiers, to set the
per-student spend cap and validate the ~$20 guidance. Nothing recorded
it: the only figure from the dry run was read off the Hermes status bar
by eye (~29,000 tokens for a full Haiku session).

Reads the run's own Hermes home — the per-run directory the launcher
creates — so each run is accounted separately and the numbers can be
compared across the 2x2 without hand-transcription.

PRICING NOTE, and this one is time-sensitive: Claude Sonnet 5 is on
introductory pricing of $2/$10 per MTok until 31 August 2026, after which
it is $3/$15. The lab week starts around then, so a benchmark computed
before the cutoff understates the real cost by roughly half. Both rates
are in the table and the applicable one is chosen by date; the output
always states which was used.

Writes <run>/token_usage.json and prints a one-line summary.

Usage:
  capture_tokens.py [--home DIR] [--model ID] [--out PATH] [--at DATE]
"""

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# USD per million tokens, from the Claude models documentation.
# (input, output). Re-check at freeze — these are the pinned figures the
# budget guidance depends on.
PRICES = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-haiku-4-5":          (1.00, 5.00),
    "claude-sonnet-5":           (3.00, 15.00),   # standard
    "claude-opus-5":             (5.00, 25.00),
    "claude-fable-5":            (10.00, 50.00),
}
# Sonnet 5 introductory rate and the date it stops applying.
SONNET_INTRO = (2.00, 10.00)
SONNET_INTRO_UNTIL = date(2026, 8, 31)

# Token counts appear under several key names depending on where in the
# session file they were written; accept any of them rather than assuming
# one shape and silently reporting zero.
IN_KEYS = ("input_tokens", "prompt_tokens", "inputTokens", "input")
OUT_KEYS = ("output_tokens", "completion_tokens", "outputTokens", "output")
CACHE_KEYS = ("cache_creation_input_tokens", "cache_read_input_tokens")


def walk_usage(obj, acc):
    """Recursively sum every usage-shaped dict found anywhere in a file."""
    if isinstance(obj, dict):
        keys = set(obj)
        if keys & set(IN_KEYS) or keys & set(OUT_KEYS):
            for k in IN_KEYS:
                if isinstance(obj.get(k), int):
                    acc["input"] += obj[k]
                    break
            for k in OUT_KEYS:
                if isinstance(obj.get(k), int):
                    acc["output"] += obj[k]
                    break
            for k in CACHE_KEYS:
                if isinstance(obj.get(k), int):
                    acc["cache"] += obj[k]
            acc["records"] += 1
        for v in obj.values():
            walk_usage(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            walk_usage(v, acc)


def scan(home):
    acc = {"input": 0, "output": 0, "cache": 0, "records": 0, "files": 0}
    for f in sorted(Path(home).rglob("*")):
        if not f.is_file() or f.suffix.lower() not in (".json", ".jsonl"):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        acc["files"] += 1
        if f.suffix.lower() == ".jsonl":
            for raw in text.splitlines():
                line = raw.strip()
                if not line:
                    continue
                try:
                    walk_usage(json.loads(line), acc)
                except json.JSONDecodeError:
                    continue
        else:
            try:
                walk_usage(json.loads(text), acc)
            except json.JSONDecodeError:
                continue
    return acc


def price_for(model, when):
    if model and model.startswith("claude-sonnet-5"):
        intro = when <= SONNET_INTRO_UNTIL
        return (SONNET_INTRO if intro else PRICES["claude-sonnet-5"],
                "introductory" if intro else "standard")
    for key, val in PRICES.items():
        if model and model.startswith(key):
            return val, "standard"
    return None, "unknown model"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default=None,
                    help="Hermes home for the run (default: newest "
                         "runs/*/hermes_home)")
    ap.add_argument("--model", default=None,
                    help="model id (default: read from the run's "
                         "model_id.txt)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--at", default=None,
                    help="pricing date YYYY-MM-DD (default: today) — use "
                         "the lab week's date to price the real run")
    args = ap.parse_args()

    runs = Path.home() / "dtlab" / "runs"
    home = Path(args.home) if args.home else None
    if home is None:
        homes = sorted(runs.glob("*/hermes_home"),
                       key=lambda p: p.stat().st_mtime if p.exists() else 0)
        if not homes:
            sys.exit("capture_tokens: no runs/*/hermes_home found — run "
                     "an agent session first")
        home = homes[-1]
    if not home.is_dir():
        sys.exit(f"capture_tokens: {home} is not a directory")

    run_dir = home.parent
    model = args.model
    if not model:
        mf = run_dir / "model_id.txt"
        model = mf.read_text().strip() if mf.is_file() else None

    when = (datetime.strptime(args.at, "%Y-%m-%d").date() if args.at
            else datetime.now(timezone.utc).date())
    acc = scan(home)
    rate, basis = price_for(model, when)

    cost = None
    if rate:
        cost = round(acc["input"] / 1e6 * rate[0]
                     + acc["output"] / 1e6 * rate[1], 4)

    out = Path(args.out) if args.out else run_dir / "token_usage.json"
    payload = {
        "run": run_dir.name,
        "hermes_home": str(home),
        "model": model,
        "priced_at": when.isoformat(),
        "rate_basis": basis,
        "usd_per_mtok_in_out": rate,
        "input_tokens": acc["input"],
        "output_tokens": acc["output"],
        "cache_tokens": acc["cache"],
        "total_tokens": acc["input"] + acc["output"],
        "usd_estimate": cost,
        "usage_records_found": acc["records"],
        "files_scanned": acc["files"],
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if acc["records"] == 0:
        print(f"capture_tokens: scanned {acc['files']} file(s) under {home} "
              "but found no usage records.", file=sys.stderr)
        print("  Hermes may store usage elsewhere for this release — check "
              "the session files and pass --home explicitly.",
              file=sys.stderr)
        sys.exit(1)

    note = ""
    if model and model.startswith("claude-sonnet-5") and basis == "introductory":
        note = (f"  NOTE: introductory rate, expires "
                f"{SONNET_INTRO_UNTIL.isoformat()} — after that this run "
                f"costs ~1.5x more.")
    print(f"capture_tokens: {payload['total_tokens']:,} tokens "
          f"({acc['input']:,} in / {acc['output']:,} out) on "
          f"{model or 'unknown model'}"
          + (f" ≈ ${cost:.4f} ({basis})" if cost is not None else
             " — no price for this model"))
    if note:
        print(note)
    print(f"  written to {out}")


if __name__ == "__main__":
    main()
