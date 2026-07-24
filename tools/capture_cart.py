#!/usr/bin/env python3
"""
capture_cart.py — `dtlab-cart`: automated cart evidence after each agent
run (run by the PARTNER; replaces the manual cart screenshot).

Connects over CDP to the ALREADY-RUNNING lab browser (the one launched by
dtlab-start / dtlab-shop via tools/dtlab_browser.sh — same profile, same
`DTLAB_CDP_PORT`), opens the amazon.in cart page, and saves BOTH:

  ~/dtlab/evidence/cart_run<N>.png    full-page screenshot (always)
  ~/dtlab/evidence/cart_run<N>.json   parsed line items: asin, title,
                                      unit price, qty (best-effort)

The packer prefers the JSON and cross-checks agent_picks.csv against the
actual cart contents (`cart_verified` per run in the manifest); the
screenshot is embedded in report.html either way. If parsing fails, the
tool degrades to screenshot-only with a warning — a manual screenshot
remains a valid fallback.

The run number is auto-detected from ~/dtlab/runs (highest started run);
override with  --run N.

Cart EMPTYING stays a HUMAN action: this kit performs no destructive
actions on the student's account. The tool ends by reminding the partner
to empty the cart before the next run.

USAGE (inside the lab environment, while the agent's browser is open):
  dtlab-cart            # alias for: <venv-python> capture_cart.py
  dtlab-cart --run 2    # explicit run number
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("playwright missing — run this via the dtlab-cart alias "
             "(it uses the provisioned environment).")

HOME = Path.home()
EV = HOME / "dtlab" / "evidence"
RUNSDIR = HOME / "dtlab" / "runs"
CART_URL = "https://www.amazon.in/gp/cart/view.html"
ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")

# The ONE patch point for amazon.in cart DOM drift (like scrape_orders.py's
# SELECTORS). TODO(dry-run): validate on live amazon.in during the T-21
# dry run; parsing failure degrades to screenshot-only, never an error.
SELECTORS = {
    "item":  "div.sc-list-item[data-asin]",       # one cart line item
    "asin":  "data-asin",                          # attribute on the item
    "title": ".sc-product-title, .a-truncate-full",
    "price": ".sc-product-price, .sc-badge-price-to-pay .a-price-whole",
    "qty":   "[data-a-selector='value'], .quantity, "
             "select[name='quantity'] option[selected]",
}


def load_config():
    cfg = {}
    p = HOME / "dtlab" / "dtlab_config.env"
    if p.exists():
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip().strip("'\"")
    return cfg


def detect_run():
    """Highest-numbered started run (runs/runN present) — dtlab-cart runs
    right after that run finished."""
    n = 0
    for i in (1, 2, 3, 4):
        if (RUNSDIR / f"run{i}").exists():
            n = i
    return n


def parse_price(s):
    d = re.sub(r"[^\d.]", "", s or "")
    try:
        return float(d) if d else None
    except ValueError:
        return None


def capture_screenshot(page, png):
    """Screenshot CLIPPED to the active-cart region: the amazon.in page
    header carries account PII ("Hello, <name>", "Deliver to <name> —
    <city> <PIN>") that must never enter the evidence zip. Returns True
    when the clip succeeded; on any failure falls back to a full-page
    capture (the caller shows a blocking warning)."""
    try:
        el = page.query_selector("#sc-active-cart")
        box = el.bounding_box() if el else None
        if box and box["width"] > 1 and box["height"] > 1:
            page.screenshot(path=str(png), clip=box)
            return True
    except Exception:
        pass
    page.screenshot(path=str(png), full_page=True)
    return False


def parse_items(page):
    """Best-effort cart line items via the SELECTORS dict. Any failure
    returns None (caller degrades to screenshot-only)."""
    try:
        items = []
        for el in page.query_selector_all(SELECTORS["item"]):
            asin = (el.get_attribute(SELECTORS["asin"]) or "").strip()
            if not ASIN_RE.fullmatch(asin):
                continue
            t = el.query_selector(SELECTORS["title"])
            title = (t.inner_text().strip() if t else "")[:200]
            p = el.query_selector(SELECTORS["price"])
            price = parse_price(p.inner_text() if p else "")
            q = el.query_selector(SELECTORS["qty"])
            qty_txt = (q.inner_text().strip() if q else "") or "1"
            qty = int(re.sub(r"[^\d]", "", qty_txt) or 1)
            items.append({"asin": asin, "title": title,
                          "unit_price": price, "qty": qty})
        return items
    except Exception as e:                       # DOM drift, timeouts, ...
        print(f"  [~] cart parsing failed ({type(e).__name__}: {e}) — "
              "screenshot-only capture (SELECTORS dict is the patch point)")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, choices=(1, 2, 3, 4),
                    help="run number (default: auto-detect from run state)")
    args = ap.parse_args()
    run = args.run or detect_run()
    if not run:
        sys.exit("no run detected under ~/dtlab/runs — pass --run N")

    cfg = load_config()
    port = cfg.get("DTLAB_CDP_PORT", "9222")
    EV.mkdir(parents=True, exist_ok=True)
    png = EV / f"cart_run{run}.png"
    out_json = EV / f"cart_run{run}.json"

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(
                f"http://127.0.0.1:{port}")
        except Exception:
            sys.exit(f"cannot attach to the lab browser on CDP port {port}.\n"
                     "Close ALL open lab-browser windows (including the "
                     "shopping session), then re-run dtlab-start — the "
                     "agent's browser must still be open when dtlab-cart "
                     "runs.")
        ctx = browser.contexts[0] if browser.contexts else \
            browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(CART_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)              # let cart rows render
        clipped = capture_screenshot(page, png)
        print(f"  [ok] screenshot -> {png}"
              + ("" if clipped else " (FULL PAGE — clip failed)"))
        items = parse_items(page)

    if not clipped:
        print("  [!!] could not clip the screenshot to the cart region "
              "(#sc-active-cart)")
        print("       — the FULL page was captured instead, and the "
              "amazon.in header")
        print("       shows the account name and delivery city. Tell a TA "
              "before packing;")
        print("       the evidence still counts.")
        if sys.stdin.isatty():
            input("  Press Enter to acknowledge... ")

    if items is not None:
        out_json.write_text(json.dumps({
            "schema": "dtlab-cart-v1",
            "run": run,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "items": items,
        }, indent=2), encoding="utf-8")
        print(f"  [ok] parsed {len(items)} cart item(s) -> {out_json}")
        if not items:
            print("  [~] cart parsed EMPTY — if the agent did add items, "
                  "the selectors may have drifted; the screenshot still "
                  "counts, and a TA can re-check.")
    else:
        print("  [~] no cart JSON written — the packer will note that the "
              "picks/cart cross-check was skipped for this run.")

    print()
    print("NOW EMPTY THE CART by hand (the kit never deletes anything on")
    print("the account) so the next run starts clean. Do not log out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
