#!/usr/bin/env python3
"""
scrape_orders.py — Capture amazon.in purchase history for the Digital Twin lab.

WORKFLOW
  1. Script opens a real (headed) Chromium window via Playwright.
  2. STUDENT logs into amazon.in manually (script waits — no credentials touched).
  3. Script paginates "Your Orders" for the requested years, opens each order's
     detail page, and extracts per-item: date, title, ASIN, unit price, quantity.
  4. Output: purchase_history.csv (schema v1) + provenance.json sidecar.

RESEARCH NOTES
  - Output schema is versioned and identical to clean_privacy_export.py output,
    so both capture paths merge into one cohort dataset.
  - Brand is filled heuristically (first token of title); run enrich_brands.py
    afterwards for authoritative brand from product pages.
  - No order IDs, addresses, or payment data are written to the output file.
    (Order IDs are used transiently in-session for navigation only.)

USAGE
  python3 scrape_orders.py --student-id DT2026-042 --years 2025 2026
  python3 scrape_orders.py --student-id DT2026-042 --years 2026 --limit 5   # dry run

CAVEAT (read me, instructor)
  Amazon's DOM changes without notice. Selectors below worked at authoring time
  (July 2026) and are written defensively, but validate on YOUR dry run three
  weeks before the lab and patch SELECTORS as needed. Failures are logged per
  order to scrape_errors.log; a partial CSV is still valid output.
"""

import argparse
import csv
import hashlib
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

SCHEMA_VERSION = "dtlab-orders-v1"
TOOL_VERSION = "scrape_orders 1.0 (2026-07)"
BASE = "https://www.amazon.in"


def log_ref(url):
    """Loggable reference for an order-detail URL. The docstring promise
    is that order IDs are transient — and they live in the URL query —
    so the persistent error log gets only the query-stripped path plus a
    short hash for correlation within one session."""
    h = hashlib.sha256((url or "").encode()).hexdigest()[:12]
    return f"{urlparse(url or '').path}#{h}"


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

# ---- selectors: single place to patch when Amazon's DOM drifts ---------------
SELECTORS = {
    "order_card": "div.order-card, div.js-order-card, div.order",
    "order_date": ".order-header .a-color-secondary .a-size-base, "
                  ".order-info .a-color-secondary.value, "
                  "span.order-date-invoice-item",
    "details_link": "a[href*='order-details'], a[href*='orderID=']",
    "item_row": "div.yohtmlc-item, div.a-fixed-left-grid",
    "item_title_link": "a[href*='/dp/'], a[href*='/gp/product/']",
    "item_price": ".a-color-price, .yohtmlc-item .a-color-price",
    "item_qty": ".item-view-qty, span.product-image__qty, "
                "span:has-text('Qty:')",
}
ASIN_RE = re.compile(r"(?:/dp/|/gp/product/)([A-Z0-9]{10})")
PRICE_RE = re.compile(r"[\d,]+(?:\.\d+)?")
QTY_RE = re.compile(r"(\d+)")

FIELDNAMES = ["student_id", "order_date", "brand_guess", "product_title",
              "asin", "unit_price_inr", "quantity", "capture_method"]


def polite_sleep(lo=2.0, hi=4.5):
    time.sleep(random.uniform(lo, hi))


def parse_price(text):
    m = PRICE_RE.search(text or "")
    return float(m.group(0).replace(",", "")) if m else None


def parse_date(text):
    text = (text or "").replace("Ordered on", "").strip()
    for fmt in ("%d %B %Y", "%B %d, %Y", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text  # keep raw; clean later rather than lose data


def brand_guess(title):
    """First token heuristic; enrich_brands.py replaces this with ground truth."""
    t = (title or "").strip()
    return t.split()[0] if t else ""


def extract_order_items(page, order_url, log):
    """Open an order-details page and pull per-item rows."""
    items = []
    page.goto(order_url, wait_until="domcontentloaded", timeout=45000)
    polite_sleep()
    date_el = page.query_selector(SELECTORS["order_date"])
    order_date = parse_date(date_el.inner_text() if date_el else "")

    for row in page.query_selector_all(SELECTORS["item_row"]):
        link = row.query_selector(SELECTORS["item_title_link"])
        if not link:
            continue
        href = link.get_attribute("href") or ""
        m = ASIN_RE.search(href)
        if not m:
            continue
        title = " ".join(link.inner_text().split())
        price_el = row.query_selector(SELECTORS["item_price"])
        price = parse_price(price_el.inner_text() if price_el else "")
        qty = 1
        qty_el = row.query_selector(SELECTORS["item_qty"])
        if qty_el:
            qm = QTY_RE.search(qty_el.inner_text())
            if qm:
                qty = int(qm.group(1))
        items.append({
            "order_date": order_date,
            "brand_guess": brand_guess(title),
            "product_title": title,
            "asin": m.group(1),
            "unit_price_inr": price if price is not None else "",
            "quantity": qty,
            "capture_method": "scrape",
        })
    if not items:
        log.write(f"NO_ITEMS {log_ref(order_url)}\n")
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--student-id", required=True,
                    help="Course-issued pseudonym, e.g. DT2026-042")
    ap.add_argument("--years", nargs="+", required=True,
                    help="e.g. --years 2025 2026")
    ap.add_argument("--limit", type=int, default=0,
                    help="Stop after N orders (testing)")
    ap.add_argument("--out", default="purchase_history.csv")
    args = ap.parse_args()

    profile_dir = browser_profile_dir()
    out_path = Path(args.out)
    log = open("scrape_errors.log", "a", encoding="utf-8")
    all_rows, n_orders = [], 0

    with sync_playwright() as p:
        try:
            ctx = p.chromium.launch_persistent_context(
                str(profile_dir), headless=False,
                viewport={"width": 1280, "height": 900},
            )
        except Exception:
            sys.exit("Could not open the shared lab browser profile — "
                     "another window is holding its lock.\n"
                     "Close ALL open lab-browser windows (including the "
                     "shopping session), then re-run this script.")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(f"{BASE}/your-orders/orders", wait_until="domcontentloaded")

        print("\n>>> Log into amazon.in in the browser window.")
        print(">>> When you can see the 'Your Orders' list, return here and")
        input(">>> press Enter to start capture... ")

        for year in args.years:
            start = 0
            while True:
                url = (f"{BASE}/your-orders/orders?"
                       f"timeFilter=year-{year}&startIndex={start}")
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                polite_sleep()
                cards = page.query_selector_all(SELECTORS["order_card"])
                if not cards:
                    break
                detail_urls = []
                for c in cards:
                    a = c.query_selector(SELECTORS["details_link"])
                    if a and a.get_attribute("href"):
                        href = a.get_attribute("href")
                        detail_urls.append(
                            href if href.startswith("http") else BASE + href)
                for du in detail_urls:
                    try:
                        all_rows += extract_order_items(page, du, log)
                    except PWTimeout:
                        log.write(f"TIMEOUT {log_ref(du)}\n")
                    except Exception as e:  # keep going; partial data is data
                        log.write(f"ERROR {log_ref(du)} :: {e}\n")
                    n_orders += 1
                    if args.limit and n_orders >= args.limit:
                        break
                if (args.limit and n_orders >= args.limit) or len(cards) < 10:
                    break
                start += 10
            if args.limit and n_orders >= args.limit:
                break
        ctx.close()

    for r in all_rows:
        r["student_id"] = args.student_id
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(all_rows)

    provenance = {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_VERSION,
        "student_id": args.student_id,
        "capture_method": "scrape",
        "years_requested": args.years,
        "orders_visited": n_orders,
        "items_captured": len(all_rows),
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "marketplace": "amazon.in",
        "notes": "brand_guess is heuristic until enrich_brands.py is run",
    }
    Path(out_path.stem + "_provenance.json").write_text(
        json.dumps(provenance, indent=2))

    print(f"\nDone: {len(all_rows)} items from {n_orders} orders "
          f"-> {out_path} (+ provenance sidecar)")
    if Path("scrape_errors.log").stat().st_size:
        print("Some orders failed — see scrape_errors.log (partial CSV is OK).")
    log.close()


if __name__ == "__main__":
    sys.exit(main())
