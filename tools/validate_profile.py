#!/usr/bin/env python3
"""validate_profile.py — check purchase_profile.md against real orders.

The bootstrap SOUL says: "Every claim in purchase_profile.md must be
traceable to an order you actually saw — never invent orders." Nothing
enforced it. On the 18 Aug dry run the agent produced a structurally
perfect profile that named a 2000W immersion heater never bought (the
real order was a power bank), substituted a brand, priced three items
wrong, and listed Yale smart locks, Wipro devices and an air purifier as
purchases — all of which were adverts in the page sidebar. A reviewer
working from a checklist would have passed it.

This turns that from a trust problem into a test. Three checks against
the ground truth from capture_orders.py:

  ASINs   — every ASIN cited must exist in a real order.
  Prices  — every rupee figure must match a real order total or item
            amount. Derived statistics (averages, ranges) are exempt when
            the line names them, since those are computed, not observed.
  Brands  — every capitalised brand-like token must appear in some real
            product title.

Brand checking is the fuzzy one and is deliberately advisory-by-default:
prose legitimately contains capitalised words that are not brands. It is
still worth running, because "Nykaa" and "Yale" are exactly what it
catches, and the report names each unmatched token so a human can judge
in seconds.

Exit codes:  0 clean · 1 unverifiable claims found · 2 could not run

Usage:
  validate_profile.py --profile PATH --orders PATH [--strict-brands]
"""

import argparse
import json
import re
import sys
from pathlib import Path

ASIN_RE = re.compile(r"\b([A-Z0-9]{10})\b")
RUPEE_RE = re.compile(r"₹\s*([\d,]+(?:\.\d{1,2})?)")
# Capitalised tokens that are prose, not brands. Kept deliberately short:
# a false positive costs one glance, a false negative costs the paper.
STOPWORDS = {
    "Purchase", "Profile", "Review", "Period", "Top", "Categories",
    "Category", "Frequency", "Notable", "Brands", "Typical", "Price",
    "Range", "Type", "Product", "Products", "Types", "Pattern", "Order",
    "Orders", "Value", "Average", "Most", "Common", "Point", "Points",
    "Summary", "Distribution", "Observed", "Notable", "Observations",
    "Conspicuously", "Absent", "Sensitivity", "Spending", "Patterns",
    "Decision", "Making", "Inferences", "Representative", "Date",
    "Subcategory", "Brand", "Qty", "Amount", "Last", "Months", "Actual",
    "Visible", "From", "The", "This", "That", "These", "Those", "And",
    "For", "With", "Mix", "Clear", "Separation", "Majority", "Item",
    "Items", "Snacks", "Grocery", "Beauty", "Personal", "Care", "Home",
    "Kitchen", "Appliances", "Smart", "Electronics", "Audio", "Fashion",
    "Clothing", "Books", "Kindle", "Toys", "Games", "Furniture",
    "Automotive", "Jewelry", "Streaming", "Healthy", "Foods", "Consumer",
    "Accessories", "Wellness", "Delivered", "Aug", "August", "Indicator",
    "Repurchased", "Repurchase", "Bundle", "Pack", "Variety", "Balance",
    "Habit", "Driven", "Tech", "Practical", "Life", "Phase", "Qty",
    "Participant", "REDACTED", "NAME", "CITY", "PIN", "PHONE", "EMAIL",
}
GENERIC_WORDS = {
    "with", "pack", "the", "and", "for", "from", "your", "this", "that",
    "aug", "august", "grocery", "beauty", "audio", "home", "kitchen",
    "electronics", "snacks", "care", "personal", "wired", "black",
    "white", "blue", "size", "colour", "color", "qty", "each", "item",
    "items", "order", "orders", "value", "price", "point", "total",
}
DERIVED_HINTS = ("average", "avg", "mean", "range", "typical", "between",
                 "distribution", "per order", "price point")


def load_orders(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    items = d.get("items", [])
    asins = {i["asin"] for i in items if i.get("asin")}
    titles = " | ".join((i.get("title") or "") for i in items).lower()
    amounts = set()
    for i in items:
        if i.get("order_total") is not None:
            amounts.add(round(float(i["order_total"]), 2))
        for a in i.get("amounts_seen") or []:
            amounts.add(round(float(a), 2))
    return asins, titles, amounts, len(items), items


def title_tokens(text):
    """Distinctive words usable for matching a profile line to an order."""
    return {w.lower() for w in re.findall(r"[A-Za-z][\w\'-]{3,}", text)
            if w.lower() not in GENERIC_WORDS}


def price_pairing_problems(profile_text, items):
    """Amount-exists is not enough: on the dry run the agent priced boAt
    at Rs354 (really Rs304) and Pringles at Rs390 (really Rs504). Both
    amounts existed -- on OTHER orders -- so a set-membership check
    passed. Match each line to the order(s) it names, then require the
    line's amount to be one of THAT order's amounts."""
    out = []
    per_item = []
    for i in items:
        toks = title_tokens(i.get("title") or "")
        amts = {round(float(a), 2) for a in (i.get("amounts_seen") or [])}
        if i.get("order_total") is not None:
            amts.add(round(float(i["order_total"]), 2))
        if toks and amts:
            per_item.append((toks, amts, (i.get("title") or "")[:48]))

    for line in profile_text.splitlines():
        vals = [round(float(r.replace(",", "")), 2)
                for r in RUPEE_RE.findall(line)]
        if not vals or any(h in line.lower() for h in DERIVED_HINTS):
            continue
        line_toks = title_tokens(line)
        # candidates: orders sharing at least two distinctive words, or
        # one sufficiently long one (brand names like "pringles")
        cands = []
        for toks, amts, title in per_item:
            shared = line_toks & toks
            if len(shared) >= 2 or any(len(w) >= 6 for w in shared):
                cands.append((amts, title, shared))
        if not cands:
            continue                      # nothing to pair against
        if any(v in amts for amts, _, _ in cands for v in vals):
            continue                      # consistent with a named order
        amts, title, shared = cands[0]
        out.append(("PRICE", f"Rs{vals[0]:,.0f}",
                    f"line names '{title}' (matched on "
                    f"{sorted(shared)[:2]}) whose real amount is "
                    f"{sorted(amts)} -- line: {line.strip()[:60]}"))
    return out


def check(profile_text, asins, titles, amounts, items, strict_brands):
    problems = []

    for asin in set(ASIN_RE.findall(profile_text)):
        if asin in STOPWORDS or not any(c.isdigit() for c in asin):
            continue
        if asin not in asins:
            problems.append(("ASIN", asin,
                             "cited but not in any captured order"))

    for line in profile_text.splitlines():
        derived = any(h in line.lower() for h in DERIVED_HINTS)
        for raw in RUPEE_RE.findall(line):
            val = round(float(raw.replace(",", "")), 2)
            if val in amounts:
                continue
            if derived:
                continue          # computed statistic, not an observation
            problems.append(("PRICE", f"₹{raw}",
                             f"no order with this amount — line: "
                             f"{line.strip()[:70]}"))

    problems += price_pairing_problems(profile_text, items)

    brand_hits = []
    for tok in set(re.findall(r"\b([A-Z][a-zA-Z]{2,})\b", profile_text)):
        if tok in STOPWORDS:
            continue
        if tok.lower() in titles:
            continue
        brand_hits.append(tok)
    for tok in sorted(brand_hits):
        problems.append(("BRAND" if strict_brands else "brand?", tok,
                         "not found in any real product title"))

    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--orders", required=True)
    ap.add_argument("--strict-brands", action="store_true",
                    help="treat unmatched capitalised tokens as failures "
                         "rather than warnings")
    args = ap.parse_args()

    prof = Path(args.profile)
    orders = Path(args.orders)
    if not prof.is_file():
        sys.exit(2)
    if not orders.is_file():
        print(f"validate_profile: no ground truth at {orders} — run "
              "capture_orders.py first", file=sys.stderr)
        sys.exit(2)

    asins, titles, amounts, n, items = load_orders(orders)
    if n == 0:
        print("validate_profile: ground truth is empty; refusing to "
              "'pass' a profile against nothing", file=sys.stderr)
        sys.exit(2)

    problems = check(prof.read_text(encoding="utf-8"), asins, titles,
                     amounts, items, args.strict_brands)

    hard = [p for p in problems if p[0] in ("ASIN", "PRICE", "BRAND")]
    soft = [p for p in problems if p[0] == "brand?"]

    print(f"validate_profile: checked against {n} captured order item(s)")
    for kind, what, why in hard:
        print(f"  [!!] {kind:6} {what:<28} {why}")
    for kind, what, why in soft:
        print(f"  [..] {kind:6} {what:<28} {why}")

    if hard:
        print(f"\n{len(hard)} unverifiable claim(s). The SOUL requires "
              "every claim to be traceable to a real order.")
        sys.exit(1)
    if soft:
        print(f"\n{len(soft)} capitalised token(s) not found in any "
              "product title — review by eye; re-run with --strict-brands "
              "to fail on these.")
    else:
        print("  clean — every ASIN, price and brand traced to a real order")
    sys.exit(0)


if __name__ == "__main__":
    main()
