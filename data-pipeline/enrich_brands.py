#!/usr/bin/env python3
"""
enrich_brands.py — Replace the brand_guess heuristic with authoritative brand
names by visiting each unique ASIN's product page (byline / product overview).

Reuses the same logged-in persistent browser profile as scrape_orders.py, so
no extra login is needed. Rate-limited and resumable: already-enriched rows
(brand_source == 'page') are skipped on re-run.

USAGE
  python3 enrich_brands.py --in purchase_history.csv
  # writes purchase_history_enriched.csv

Research note: this adds a 'brand' + 'brand_source' column pair; brand_guess
is retained so you can later quantify heuristic accuracy across the cohort
(a nice methods footnote).
"""

import argparse
import csv
import random
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://www.amazon.in"
BYLINE_RE = re.compile(
    r"^(?:Visit the (.+?) Store|Brand:\s*(.+))$", re.IGNORECASE)


def browser_profile_dir():
    """The ONE shared lab browser profile (dtlab_config.env is the
    authority; same resolution as tools/log_human_session.py)."""
    rel = "dtlab/browser-profile"
    cfg = Path.home() / "dtlab" / "dtlab_config.env"
    if cfg.exists():
        for line in cfg.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DTLAB_BROWSER_PROFILE="):
                rel = line.split("=", 1)[1].strip().strip("'\"")
    return Path.home() / rel


def polite_sleep(lo=2.5, hi=5.0):
    time.sleep(random.uniform(lo, hi))


def get_brand(page, asin):
    page.goto(f"{BASE}/dp/{asin}", wait_until="domcontentloaded",
              timeout=45000)
    polite_sleep()
    el = page.query_selector("#bylineInfo")
    if el:
        m = BYLINE_RE.match(" ".join(el.inner_text().split()))
        if m:
            return (m.group(1) or m.group(2)).strip()
    # fallback: product overview table row "Brand"
    for row in page.query_selector_all(
            "#productOverview_feature_div tr, table.a-normal tr"):
        cells = row.query_selector_all("td, th")
        if len(cells) >= 2 and "brand" in cells[0].inner_text().lower():
            return " ".join(cells[1].inner_text().split())
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="purchase_history.csv")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.inp, newline="", encoding="utf-8")))
    for r in rows:
        r.setdefault("brand", r.get("brand", ""))
        r.setdefault("brand_source", r.get("brand_source", ""))

    todo_asins = {r["asin"] for r in rows
                  if r.get("brand_source") != "page" and r.get("asin")}
    if args.limit:
        todo_asins = set(list(todo_asins)[:args.limit])
    print(f"{len(todo_asins)} unique ASINs to enrich "
          f"(~{len(todo_asins) * 4 // 60} min at polite pace)")

    resolved = {}
    profile_dir = browser_profile_dir()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile_dir), headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for i, asin in enumerate(sorted(todo_asins), 1):
            try:
                b = get_brand(page, asin)
                if b:
                    resolved[asin] = b
                print(f"[{i}/{len(todo_asins)}] {asin} -> {b or '??'}")
            except Exception as e:
                print(f"[{i}/{len(todo_asins)}] {asin} FAILED: {e}")
        ctx.close()

    for r in rows:
        if r["asin"] in resolved:
            r["brand"], r["brand_source"] = resolved[r["asin"]], "page"
        elif not r.get("brand"):
            r["brand"], r["brand_source"] = r.get("brand_guess", ""), "heuristic"

    out = Path(args.inp).stem + "_enriched.csv"
    fieldnames = list(rows[0].keys())
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {out}. Unresolved ASINs keep brand_source='heuristic'.")


if __name__ == "__main__":
    main()
