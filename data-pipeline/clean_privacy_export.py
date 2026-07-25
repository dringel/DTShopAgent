#!/usr/bin/env python3
"""
clean_privacy_export.py — Convert Amazon's official "Request Your Data" export
into the lab's schema (dtlab-orders-v1). The official export is the only
capture path: authoritative unit prices and quantities, no site automation.

Point it at the Retail.OrderHistory*.csv inside the unzipped export.
Column names vary across export versions, so matching is fuzzy/case-insensitive.

USAGE
  python3 clean_privacy_export.py --student-id DT2026-042 \
      --in "Your Orders/Retail.OrderHistory.1.csv" --out purchase_history.csv

Privacy minimization: only date, title, ASIN, unit price, quantity survive.
Addresses, order IDs, payment instruments, and carrier data are dropped here,
before the file ever reaches the agent workspace or the research dataset.
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "dtlab-orders-v1"
FIELDNAMES = ["student_id", "order_date", "brand_guess", "product_title",
              "asin", "unit_price_inr", "quantity", "capture_method"]

# fuzzy header aliases (lowercased, stripped of non-alnum)
ALIASES = {
    "order_date": ["orderdate", "date"],
    "product_title": ["productname", "title", "itemname"],
    "asin": ["asin", "asinisbn"],
    "unit_price_inr": ["unitprice", "purchasepriceperunit", "itemprice",
                       "listpriceperunit"],
    "quantity": ["quantity", "qty"],
}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def map_headers(headers):
    normed = {norm(h): h for h in headers}
    mapping = {}
    for field, cands in ALIASES.items():
        for c in cands:
            if c in normed:
                mapping[field] = normed[c]
                break
    missing = [f for f in ("order_date", "product_title", "asin") 
               if f not in mapping]
    if missing:
        sys.exit(f"Could not find columns for {missing} in export. "
                 f"Headers present: {headers}\n"
                 f"-> Add an alias in ALIASES and re-run.")
    return mapping


def parse_date(s):
    # amazon.in exports write day-first dates: %d/%m/%Y must win over
    # %m/%d/%Y or 04/07/2026 silently becomes April 7th
    s = (s or "").strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y",
                "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s.split("T")[0] if "T" in s else s,
                                     fmt.split("T")[0] if "T" in fmt else fmt
                                     ).date().isoformat()
        except ValueError:
            continue
    return s


def parse_price(s):
    m = re.search(r"[\d,]+(?:\.\d+)?", s or "")
    return float(m.group(0).replace(",", "")) if m else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--student-id", required=True)
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", default="purchase_history.csv")
    args = ap.parse_args()

    rows_out = []
    with open(args.inp, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        mapping = map_headers(reader.fieldnames)
        for r in reader:
            title = (r.get(mapping["product_title"]) or "").strip()
            asin = (r.get(mapping["asin"]) or "").strip()
            if not title or not asin:
                continue
            qty_raw = r.get(mapping.get("quantity", ""), "1")
            try:
                qty = int(float(qty_raw))
            except (ValueError, TypeError):
                qty = 1
            rows_out.append({
                "student_id": args.student_id,
                "order_date": parse_date(r.get(mapping["order_date"], "")),
                "brand_guess": title.split()[0] if title else "",
                "product_title": title,
                "asin": asin,
                "unit_price_inr": parse_price(
                    r.get(mapping.get("unit_price_inr", ""), "")),
                "quantity": qty,
                "capture_method": "privacy_export",
            })

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(rows_out)

    Path(Path(args.out).stem + "_provenance.json").write_text(json.dumps({
        "schema_version": SCHEMA_VERSION,
        "tool": "clean_privacy_export 1.0 (2026-07)",
        "student_id": args.student_id,
        "capture_method": "privacy_export",
        "source_file": Path(args.inp).name,
        "items_captured": len(rows_out),
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "marketplace": "amazon.in",
    }, indent=2))

    print(f"Done: {len(rows_out)} items -> {args.out} (+ provenance sidecar)")


if __name__ == "__main__":
    main()
