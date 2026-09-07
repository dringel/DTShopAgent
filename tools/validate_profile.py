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

This turns that from a trust problem into a test. Four checks against
the ground truth from capture_orders.py:

  ASINs   — every ASIN cited must exist in a real order.
  Prices  — every rupee figure must match a real order total or item
            amount. Derived statistics (averages, ranges) are exempt when
            the line names them, since those are computed, not observed.
  Brands  — every capitalised brand-like token must appear in some real
            product title.
  Stats   — the required Summary Stats block (completed orders, purchased
            line items, total spend, average order value) must match
            what capture_orders.py's ground truth actually contains,
            exactly on the integer counts and the total, within ₹1 on
            the average (prose rounds to whole rupees).

Brand checking is the fuzzy one and is deliberately advisory-by-default:
prose legitimately contains capitalised words that are not brands. It is
still worth running, because "Nykaa" and "Yale" are exactly what it
catches, and the report names each unmatched token so a human can judge
in seconds.

Stats checking is what closes the P0.2 gap the brand/ASIN/price checks
never covered: none of them look at aggregate claims at all, so a
profile could state a wildly wrong average order value, or conflate
order count with line-item count, and pass clean. The Summary Stats
block is mandatory (agent/SOUL_bootstrap.md) precisely so the four
numbers in it can be reconciled exactly rather than pattern-matched out
of free prose that can be rephrased any given run. Category percentages
have no ground truth to check against (capture_orders.py extracts no
category field), so they get an internal-consistency check only:
stated percentages must sum to approximately 100%.

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
    # Summary Stats block headers/fields (P0.2): structural, appear on
    # every profile, not brand candidates
    "Stats", "Completed", "Purchased", "Total",
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

# A rupee RANGE ("₹350-₹1,500", "₹350-400") is a summary statistic by
# construction: its endpoints are rounded bracket values, not amounts any
# single order carries. The SOUL asks for exactly this ("typical price
# points per category"). On 3 Sep the agent supplied it and was hard-
# failed anyway, because DERIVED_HINTS is matched per LINE and the profile
# put the "Typical Price Points" label on a header line with the ranges on
# the bullets under it -- so the exemption never reached them. Detect the
# SHAPE of a range rather than depending on a keyword landing on the same
# line. A single amount has no trailing "- <number>" and stays checked.
RANGE_RE = re.compile(
    r"₹\s*[\d,]+(?:\.\d{1,2})?\s*(?:[-\u2013\u2014]|to)\s*"
    r"₹?\s*[\d,]+(?:\.\d{1,2})?")


def is_derived(line):
    """True when a line states a COMPUTED figure rather than an observed
    amount. Both price checks call this, so the rule cannot drift between
    them (it previously existed only as an inline expression in each)."""
    return bool(RANGE_RE.search(line)) or any(
        h in line.lower() for h in DERIVED_HINTS)

# agent/SOUL_bootstrap.md #3 scopes traceability explicitly: "Every claim
# in the Observations section... must be traceable". Inferences is the
# one section the SOUL deliberately exempts -- "an inference is your
# reading of a pattern, not something to cite an order for" -- and its
# free prose routinely contains capitalised words (a category rollup
# like "TVs", a restated date, its own "Inference:" label) that are not
# claims about any order at all. Caught live, 7 Sept: a clean, PASSING
# profile still printed ten "brand? not found" lines, all traceable to
# this section, none to anything the agent actually claimed happened.
INFERENCES_RE = re.compile(r"(?m)^##\s*Inferences\b")


def traceable_scope(profile_text):
    """The prefix of the profile the SOUL actually requires to trace to a
    real order -- everything up to (not including) '## Inferences'. Falls
    back to the whole text if that heading is missing/misspelled, since a
    malformed profile should fail LOUDER, not have half its content
    silently exempted from checking."""
    m = INFERENCES_RE.search(profile_text)
    return profile_text[:m.start()] if m else profile_text

# Summary Stats block (agent/SOUL_bootstrap.md, P0.2): four required
# lines, in prose the agent writes, so match loosely on wording/spacing
# but strictly on which four fields exist — a MISSING field is itself a
# reportable problem, not silently skipped.
# (field key, display label, regex) — the label is what a TA sees, kept
# separate from the key so "n_orders" does not have to read as a message
STATS_FIELDS = [
    ("n_orders", "Completed orders", re.compile(
        r"(?im)^\s*completed orders\s*:\s*(\d+)\s*$")),
    ("n_line_items", "Purchased line items", re.compile(
        r"(?im)^\s*purchased line items\s*:\s*(\d+)\s*$")),
    ("total_spend", "Total spend", re.compile(
        r"(?im)^\s*total spend\s*:\s*₹\s*([\d,]+(?:\.\d{1,2})?)\s*$")),
    ("avg_order_value", "Average order value", re.compile(
        r"(?im)^\s*average order value\s*:\s*₹\s*([\d,]+(?:\.\d{1,2})?)\s*$")),
]
STATS_FIELD_RES = {key: pat for key, _label, pat in STATS_FIELDS}
# "Top categories" lines carry a trailing percentage: "Grocery — 40%".
# Internal-consistency only (P0.2 decision): capture_orders.py extracts
# no category field, so there is no ground truth to reconcile a SPLIT
# against — only that the stated shares add up.
CATEGORY_PCT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")


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


def order_stats(items):
    """Ground-truth aggregates capture_orders.py's schema makes derivable:
    one row per (asin, order_id) — a purchased LINE ITEM, not an order.
    "Completed orders" is the count of distinct order ids; a multi-item
    order must count once, not once per line item. order_total is
    per-order (capture_orders.py records the FIRST rupee figure on the
    card as the order total), so summing it per distinct order id — not
    per line item — is what avoids double-counting a multi-item order's
    total once for every item on it.

    An item with no order_id is still a purchased line item (counted),
    but cannot be attributed to a specific order for the total/average
    (matching capture_orders.py's own "every field is optional except
    the ASIN" partial-record policy)."""
    n_line_items = len(items)
    order_totals = {}
    for i in items:
        oid = i.get("order_id")
        if oid is None or i.get("order_total") is None:
            continue
        order_totals[oid] = round(float(i["order_total"]), 2)
    n_orders = len(order_totals)
    total_spend = round(sum(order_totals.values()), 2)
    avg_order_value = round(total_spend / n_orders, 2) if n_orders else None
    return {"n_orders": n_orders, "n_line_items": n_line_items,
            "total_spend": total_spend, "avg_order_value": avg_order_value}


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
        if not vals or is_derived(line):
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


def stats_problems(profile_text, items):
    """Reconcile the mandatory Summary Stats block against ground truth
    the agent could not have seen wrong (P0.2): capture_orders.py already
    excludes cancelled cards, so a wrong completed-order count here is
    either a miscount or a double-counted cancelled duplicate the agent
    is not supposed to have counted at all. A missing field is reported
    the same as a wrong one — the block is mandatory, not optional."""
    truth = order_stats(items)
    out = []
    found = {}
    for field, label, pat in STATS_FIELDS:
        m = pat.search(profile_text)
        if not m:
            out.append(("STATS", label,
                        "Summary Stats block is missing this required "
                        "line"))
            continue
        found[field] = round(float(m.group(1).replace(",", "")), 2)

    if "n_orders" in found and found["n_orders"] != truth["n_orders"]:
        out.append(("STATS", "Completed orders",
                    f"profile says {found['n_orders']:g}, ground truth "
                    f"has {truth['n_orders']} distinct order(s)"))
    if ("n_line_items" in found
            and found["n_line_items"] != truth["n_line_items"]):
        out.append(("STATS", "Purchased line items",
                    f"profile says {found['n_line_items']:g}, ground "
                    f"truth has {truth['n_line_items']} item(s)"))
    if "total_spend" in found and abs(
            found["total_spend"] - truth["total_spend"]) > 0.01:
        out.append(("STATS", "Total spend",
                    f"profile says ₹{found['total_spend']:,.2f}, "
                    f"ground truth totals ₹{truth['total_spend']:,.2f} "
                    "across completed orders with a known total"))
    if "avg_order_value" in found and truth["avg_order_value"] is not None:
        # ₹1 tolerance: prose rounds to the nearest rupee (P0.2 decision)
        if abs(found["avg_order_value"]
               - truth["avg_order_value"]) > 1.0:
            out.append(("STATS", "Average order value",
                        f"profile says ₹{found['avg_order_value']:,.2f}, "
                        "ground truth computes "
                        f"₹{truth['avg_order_value']:,.2f} (total spend "
                        "÷ completed orders)"))
    return out


def category_share_problems(profile_text):
    """Internal-consistency check only (P0.2 decision): capture_orders.py
    extracts no category field, so a stated split cannot be reconciled
    against ground truth — only that the numbers the agent chose to
    write down are not self-contradictory. Scoped to the Observations
    section: the Summary Stats block's own rupee/count lines must never
    be swept in by a stray '%' elsewhere in the profile.

    A "top categories" line may list every share on one line
    ("Grocery 40%, Beauty 30%, Home 30%") or one per line — both are
    valid prose, so every '%' on a categor*-labelled line counts, not
    just one per line."""
    m = re.search(r"(?im)^##\s*observations\s*$", profile_text)
    if not m:
        return []
    end = re.search(r"(?im)^##\s*inferences\s*$", profile_text[m.end():])
    section = (profile_text[m.end():m.end() + end.start()]
               if end else profile_text[m.end():])
    pcts = []
    for ln in section.splitlines():
        if "categor" not in ln.lower():
            continue
        pcts.extend(float(v) for v in CATEGORY_PCT_RE.findall(ln))
    if len(pcts) < 2:
        return []          # nothing to sum (single share, or none stated)
    total = sum(pcts)
    if abs(total - 100.0) > 5.0:   # generous: "approximately 100%"
        return [("STATS", "Category percentages",
                 f"{len(pcts)} category share(s) sum to {total:g}%, "
                 "not ~100%")]
    return []


def check(profile_text, asins, titles, amounts, items, strict_brands):
    problems = []

    for asin in set(ASIN_RE.findall(profile_text)):
        if asin in STOPWORDS or not any(c.isdigit() for c in asin):
            continue
        if asin not in asins:
            problems.append(("ASIN", asin,
                             "cited but not in any captured order"))

    # Price and brand checks enforce SOUL #3's traceability requirement,
    # which is scoped to Observations (and the representative-order
    # lines within it) by the SOUL's own text — Inferences is explicitly
    # exempt, so it must not be scanned for either check. Everything else
    # (ASINs, Stats, category shares) keeps scanning the full document.
    traceable_text = traceable_scope(profile_text)

    for line in traceable_text.splitlines():
        # the Summary Stats block's own rupee lines are reconciled
        # exactly by stats_problems() below — Total spend is a SUM
        # across orders and would otherwise spuriously fail the
        # single-order amount check every time
        if any(pat.match(line) for pat in STATS_FIELD_RES.values()):
            continue
        derived = is_derived(line)
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
    problems += stats_problems(profile_text, items)
    problems += category_share_problems(profile_text)

    brand_hits = []
    for tok in set(re.findall(r"\b([A-Z][a-zA-Z]{2,})\b", traceable_text)):
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

    hard = [p for p in problems if p[0] in ("ASIN", "PRICE", "BRAND",
                                              "STATS")]
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
