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
import sqlite3
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

# Cache multipliers on the BASE INPUT rate. Cache was previously counted
# but never priced, which understated a real bootstrap session roughly
# 8x: the 3 Sep run billed 72 raw input tokens against ~572k cache reads
# and ~71k cache writes, and only the 72 were charged. T-21 item 12 sets
# the per-key cap and validates the ~$20 spend guidance off this number,
# so the understatement mattered.
# Read 0.1x; write 1.25x at the 5-minute TTL (2x at 1-hour). Hermes does
# not tell us which TTL it used, so the cheaper write is assumed and the
# payload records the assumption.
CACHE_READ_MULT = 0.10
CACHE_WRITE_MULT = 1.25
CACHE_WRITE_TTL_ASSUMED = "5-minute (1.25x); a 1-hour TTL would be 2x"

# Token counts appear under several key names depending on where in the
# session file they were written; accept any of them rather than assuming
# one shape and silently reporting zero. Reads and writes are kept APART
# because they are priced differently.
IN_KEYS = ("input_tokens", "prompt_tokens", "inputTokens", "input")
OUT_KEYS = ("output_tokens", "completion_tokens", "outputTokens", "output")
CACHE_READ_KEYS = ("cache_read_input_tokens", "cache_read_tokens")
CACHE_WRITE_KEYS = ("cache_creation_input_tokens", "cache_write_tokens")
REASONING_KEYS = ("reasoning_tokens", "thinking_tokens")


def new_acc():
    return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
            "reasoning": 0, "records": 0, "files": 0}


def scan_state_db(home):
    """Read Hermes v0.20.0's SQLite session store, if present.

    Hermes stopped writing JSONL session files. v0.20.0 keeps sessions in
    <HERMES_HOME>/state.db, so the JSON/JSONL scan below finds nothing and
    every run reported zero usage -- discovered live on 3 Sep 2026, after
    which no token or cost figure existed for ANY run. The `sessions`
    table already carries the exact counters this tool was reconstructing
    by hand, including reasoning_tokens, which is what T-21 item 12's
    with/without-extended-thinking split needs.

    Returns (acc, per_model) or (None, None) when there is no usable DB,
    so the caller can fall back to the legacy scan for older layouts.
    """
    db = Path(home) / "state.db"
    if not db.is_file():
        return None, None
    acc = new_acc()
    per_model = []
    try:
        # read-only: never let a reporting tool mutate a run's evidence
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error:
        return None, None
    try:
        rows = con.execute(
            "select coalesce(model,''), coalesce(input_tokens,0), "
            "coalesce(output_tokens,0), coalesce(cache_read_tokens,0), "
            "coalesce(cache_write_tokens,0), coalesce(reasoning_tokens,0) "
            "from sessions").fetchall()
        for model, tin, tout, cr, cw, reas in rows:
            acc["input"] += tin
            acc["output"] += tout
            acc["cache_read"] += cr
            acc["cache_write"] += cw
            acc["reasoning"] += reas
            acc["records"] += 1
        # Per-model/per-task rows prove the auxiliary models (vision,
        # web_extract, compression) actually ran on the run's assigned
        # tier -- the config pins them deliberately, and a side model on
        # another tier would contaminate the tier manipulation directly.
        try:
            per_model = [
                {"model": m, "task": t, "input_tokens": tin,
                 "output_tokens": tout, "cache_read_tokens": cr,
                 "cache_write_tokens": cw, "reasoning_tokens": reas}
                for m, t, tin, tout, cr, cw, reas in con.execute(
                    "select coalesce(model,''), coalesce(task,''), "
                    "coalesce(input_tokens,0), coalesce(output_tokens,0), "
                    "coalesce(cache_read_tokens,0), "
                    "coalesce(cache_write_tokens,0), "
                    "coalesce(reasoning_tokens,0) from session_model_usage")]
        except sqlite3.Error:
            per_model = []      # table absent on another release: not fatal
    except sqlite3.Error:
        return None, None
    finally:
        con.close()
    if acc["records"] == 0:
        return None, None
    acc["files"] = 1
    return acc, per_model


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
            for k in CACHE_READ_KEYS:
                if isinstance(obj.get(k), int):
                    acc["cache_read"] += obj[k]
            for k in CACHE_WRITE_KEYS:
                if isinstance(obj.get(k), int):
                    acc["cache_write"] += obj[k]
            for k in REASONING_KEYS:
                if isinstance(obj.get(k), int):
                    acc["reasoning"] += obj[k]
                    break
            acc["records"] += 1
        for v in obj.values():
            walk_usage(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            walk_usage(v, acc)


def scan(home):
    acc = new_acc()
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


def compute_cost(acc, rate):
    """(usd, per-component breakdown) for one accumulator.

    Cache is priced off the BASE INPUT rate rather than skipped. It used
    to be counted and then dropped from the total, which understated the
    first real session measured by ~8x -- its raw input was 72 tokens
    against ~572k cache reads. Reasoning tokens are deliberately NOT
    added: whether Hermes counts them inside output_tokens or alongside
    is unconfirmed, and the only measured session had none, so a
    double-count could not be ruled out.
    """
    if not rate:
        return None, None
    parts = {
        "input": round(acc["input"] / 1e6 * rate[0], 6),
        "output": round(acc["output"] / 1e6 * rate[1], 6),
        "cache_read": round(
            acc["cache_read"] / 1e6 * rate[0] * CACHE_READ_MULT, 6),
        "cache_write": round(
            acc["cache_write"] / 1e6 * rate[0] * CACHE_WRITE_MULT, 6),
    }
    return round(sum(parts.values()), 4), parts


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
    # Hermes v0.20.0 keeps sessions in SQLite; older layouts wrote JSON.
    # Prefer the DB and fall back, so a mixed estate still reports.
    acc, per_model = scan_state_db(home)
    source = "state.db"
    if acc is None:
        acc, per_model, source = scan(home), [], "json-scan"
    rate, basis = price_for(model, when)

    cost, cost_parts = compute_cost(acc, rate)

    out = Path(args.out) if args.out else run_dir / "token_usage.json"
    payload = {
        "run": run_dir.name,
        "hermes_home": str(home),
        "model": model,
        "priced_at": when.isoformat(),
        "rate_basis": basis,
        "usd_per_mtok_in_out": rate,
        "usage_source": source,
        "input_tokens": acc["input"],
        "output_tokens": acc["output"],
        "cache_read_tokens": acc["cache_read"],
        "cache_write_tokens": acc["cache_write"],
        "cache_tokens": acc["cache_read"] + acc["cache_write"],
        # T-21 item 12 needs the with/without-extended-thinking split, and
        # this is the only field that settles it empirically rather than
        # by inference from the config. 0 means the model did not think.
        # NOT added to the cost: whether Hermes counts these inside
        # output_tokens or alongside them is unconfirmed, and the one
        # measured session had 0, so double-counting could not be ruled
        # out. Re-check against the first session that reports non-zero.
        "reasoning_tokens": acc["reasoning"],
        "total_tokens": acc["input"] + acc["output"],
        "billable_tokens": (acc["input"] + acc["output"]
                            + acc["cache_read"] + acc["cache_write"]),
        "usd_estimate": cost,
        "usd_breakdown": cost_parts,
        "cache_write_ttl_assumed": CACHE_WRITE_TTL_ASSUMED,
        "per_model_usage": per_model,
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
    print(f"capture_tokens: {payload['billable_tokens']:,} billable tokens "
          f"({acc['input']:,} in / {acc['output']:,} out / "
          f"{acc['cache_read']:,} cache-read / "
          f"{acc['cache_write']:,} cache-write / "
          f"{acc['reasoning']:,} reasoning) on "
          f"{model or 'unknown model'} [{source}]"
          + (f" ≈ ${cost:.4f} ({basis})" if cost is not None else
             " — no price for this model"))
    if note:
        print(note)
    print(f"  written to {out}")


if __name__ == "__main__":
    main()
