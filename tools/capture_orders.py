#!/usr/bin/env python3
"""capture_orders.py — deterministic ground truth for the purchase history.

Two jobs, both asked for on the 18 Aug instructor call:

  1. VALIDATION. The bootstrap agent's profile is prose it wrote from
     looking at a page. On the dry run it invented an appliance, renamed a
     brand, and recorded three sidebar ADVERTS as purchases. Nothing
     downstream could tell. This gives validate_profile.py something
     deterministic to check every claim against.

  2. RESEARCH DATA. "That's why we need to get the purchase histories
     captured well in the beginning… the unit ID, plus the price point
     they bought." Later analysis regresses agent/human match quality on
     purchase-history characteristics — length, diversity, category
     overlap, brand consistency — none of which survive as prose.

Reads the order list from the ALREADY-RUNNING lab browser over CDP, so it
inherits the logged-in session rather than asking for credentials.

Extraction is text-and-structure based, not class-name based: Amazon's
markup churns, but order ids, ISO-ish dates, rupee totals and /dp/<ASIN>
links are stable. Every field is optional except the ASIN — a partial
record is better than a dropped order, and validate_profile.py reports
what it could not verify rather than silently passing it.

Writes ~/dtlab/quarantine/human/purchase_orders.json (quarantined: it is
raw account data, not agent-visible).

Usage:
  capture_orders.py [--cdp-port 9222] [--out PATH] [--max-orders 60]
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ORDER_ID_RE = re.compile(r"\b(\d{3}-\d{7}-\d{7})\b")
ASIN_RE = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})")
RUPEE_RE = re.compile(r"₹\s*([\d,]+(?:\.\d{2})?)")
DATE_RE = re.compile(
    r"\b(\d{1,2}\s+"
    r"(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{4})\b")

# Extracted in-page, order first: locate each order-id text node, then walk
# upward to the smallest ancestor that contains product links and exactly
# one distinct order id. Starting from product links is unsafe: on the live
# amazon.in DOM, shallow recommendation cards reach the page-wide orders
# container before genuine product links reach their own order header.
#
# Once the order boundary is known, collect every text/image-alt candidate
# for each ASIN. parse_card() chooses the useful title deterministically;
# the first link is commonly an image link with no innerText.
PAGE_JS = r"""
() => {
  const ONE_ORDER_ID = /\b\d{3}-\d{7}-\d{7}\b/;
  const ALL_ORDER_IDS = /\b\d{3}-\d{7}-\d{7}\b/g;
  const ASIN = /\/(?:dp|gp\/product)\/([A-Z0-9]{10})/;
  const PRODUCT_LINKS = 'a[href*="/dp/"],a[href*="/gp/product/"]';
  const out = [];
  const seenOrders = new Set();
  if (!document.body) return out;

  // Text nodes avoid repeatedly scanning innerText for every element on
  // the page, and give us the exact element that renders the order id.
  const walker = document.createTreeWalker(
    document.body, NodeFilter.SHOW_TEXT);
  const orderIdNodes = [];
  let node;
  while ((node = walker.nextNode())) {
    const ids = (node.nodeValue || '').match(ALL_ORDER_IDS) || [];
    ids.forEach(orderId => orderIdNodes.push({
      orderId: orderId,
      element: node.parentElement
    }));
  }

  orderIdNodes.forEach(({orderId, element}) => {
    if (!element || seenOrders.has(orderId)) return;

    let el = element, card = null;
    for (let i = 0; i < 20 && el; i++, el = el.parentElement) {
      const text = el.innerText || '';
      const distinctIds = new Set(text.match(ALL_ORDER_IDS) || []);
      if (distinctIds.size > 1) break;       // crossed into all-orders UI
      if (distinctIds.size === 1 &&
          el.querySelectorAll(PRODUCT_LINKS).length) {
        card = el;
        break;
      }
    }
    if (!card) return;
    seenOrders.add(orderId);

    const text = card.innerText || '';
    // Defensive invariant: a selected card must never span two orders.
    const cardIds = new Set(text.match(ALL_ORDER_IDS) || []);
    if (cardIds.size !== 1 || !cardIds.has(orderId)) return;

    const byAsin = new Map();
    card.querySelectorAll(PRODUCT_LINKS).forEach(a => {
      const m = (a.getAttribute('href') || '').match(ASIN);
      if (!m) return;
      const asin = m[1];
      if (!byAsin.has(asin)) byAsin.set(asin, new Set());
      const candidates = byAsin.get(asin);
      const linkText = (a.innerText || '').replace(/\s+/g, ' ').trim();
      if (linkText) candidates.add(linkText);
      a.querySelectorAll('img[alt]').forEach(img => {
        const alt = (img.alt || '').replace(/\s+/g, ' ').trim();
        if (alt) candidates.add(alt);
      });
    });

    byAsin.forEach((titleCandidates, asin) => out.push({
      asin: asin,
      title_candidates: [...titleCandidates],
      card_text: text.replace(/\s+/g, ' ').trim().slice(0, 2400)
    }));
  });
  return out;
}
"""

TITLE_NOISE = {
    "buy it again",
    "get product support",
    "return items",
    "see all buying options",
    "view order details",
    "write a product review",
}


def select_title(rec):
    """Choose a product title over image links, prices, and action links."""
    raw = []
    if rec.get("title"):
        raw.append(rec["title"])
    raw.extend(rec.get("title_candidates", []))

    candidates = []
    for value in raw:
        value = re.sub(r"\s+", " ", str(value)).strip()
        if value and value not in candidates:
            candidates.append(value)

    def useful(value):
        lowered = value.casefold()
        if lowered in TITLE_NOISE:
            return False
        if re.fullmatch(r"-?\d+%", value):
            return False
        if re.fullmatch(
                r"(?:₹\s*[\d,]+(?:\.\d{1,2})?)+", value):
            return False
        return True

    useful_candidates = [value for value in candidates if useful(value)]
    choices = useful_candidates or candidates
    return (max(choices, key=len) if choices else "")[:300]


def parse_card(rec):
    t = rec.get("card_text", "")
    order_ids = list(dict.fromkeys(ORDER_ID_RE.findall(t)))
    if len(order_ids) > 1:
        raise ValueError("candidate order card spans multiple order ids")
    date = DATE_RE.search(t)
    amounts = [a.replace(",", "") for a in RUPEE_RE.findall(t)]
    return {
        "asin": rec["asin"],
        "title": select_title(rec),
        "order_id": order_ids[0] if order_ids else None,
        "order_date": date.group(1) if date else None,
        # first rupee figure on an order card is the order total; keep
        # them all so a multi-item order can still be reconciled
        "order_total": float(amounts[0]) if amounts else None,
        "amounts_seen": [float(a) for a in amounts],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cdp-port", default="9222")
    ap.add_argument("--out", default=str(
        Path.home() / "dtlab" / "quarantine" / "human"
        / "purchase_orders.json"))
    ap.add_argument("--max-orders", type=int, default=60)
    ap.add_argument("--url", default=(
        "https://www.amazon.in/gp/css/order-history"
        "?orderFilter=year-{year}"))
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("capture_orders: playwright not installed in this "
                 "environment")

    year = datetime.now(timezone.utc).year
    records = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(
                f"http://127.0.0.1:{args.cdp_port}")
        except Exception as exc:
            sys.exit(f"capture_orders: could not attach to the lab browser "
                     f"on CDP {args.cdp_port} ({type(exc).__name__}). Start "
                     "it first: DISPLAY=:1 bash ~/dtlab/tools/"
                     "dtlab_browser.sh &")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        # this year and last, so a ~12-month window is covered without
        # touching the date dropdown (which the agent could not operate)
        for y in (year, year - 1):
            page.goto(args.url.format(year=y), wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            try:
                records += page.evaluate(PAGE_JS)
            except Exception as exc:
                print(f"capture_orders: extraction failed on {y}: "
                      f"{type(exc).__name__}", file=sys.stderr)
        page.close()

    parsed, seen = [], set()
    for r in records:
        try:
            rec = parse_card(r)
        except ValueError as exc:
            print(f"capture_orders: rejected contaminated card: {exc}",
                  file=sys.stderr)
            continue
        key = (rec["asin"], rec["order_id"])
        if key in seen:
            continue
        seen.add(key)
        parsed.append(rec)
        if len(parsed) >= args.max_orders:
            break

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": "amazon.in order history via CDP",
        "n_items": len(parsed),
        "items": parsed,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    n_id = sum(1 for r in parsed if r["order_id"])
    n_amt = sum(1 for r in parsed if r["order_total"] is not None)
    print(f"capture_orders: {len(parsed)} item(s) written to {out}")
    print(f"  with order id: {n_id}   with a rupee total: {n_amt}")
    if not parsed:
        print("  WARNING: nothing captured. Either the account has no "
              "orders in the window, or you are not logged in in the lab "
              "browser.", file=sys.stderr)


if __name__ == "__main__":
    main()
