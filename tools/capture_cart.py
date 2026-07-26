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
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    # deferred to main() so the module stays importable (unit tests
    # exercise parse_price/capture_screenshot without a browser stack)
    sync_playwright = None

HOME = Path.home()
EV = HOME / "dtlab" / "evidence"
RUNSDIR = HOME / "dtlab" / "runs"
CART_URL = "https://www.amazon.in/gp/cart/view.html"
ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")

# The ONE patch point for amazon.in cart DOM drift. Validate on live
# amazon.in at the T-21 dry run; parsing failure degrades to
# screenshot-only, never an error.
SELECTORS = {
    # scoped to the ACTIVE cart: unscoped div.sc-list-item also matches
    # "Saved for later" rows, which silently carries prior runs' items
    # into every later capture
    "item":  "#sc-active-cart div.sc-list-item[data-asin]",
    "sfl_item": "#sc-saved-cart div.sc-list-item[data-asin]",
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
    """First number in the string, commas stripped (Indian grouping
    included): 'Rs.1499' -> 1499, '₹1,499' -> 1499, '1,20,000' -> 120000.
    Character-class stripping is NOT safe here — it kept the dot of
    'Rs.' and turned Rs.1499 into 0.1499."""
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(s or ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def capture_screenshot(page, png, unsafe_png):
    """Screenshot CLIPPED to the active-cart region: the amazon.in page
    header carries account PII ("Hello, <name>", "Deliver to <name> —
    <city> <PIN>") that must never enter the evidence zip. Returns True
    when the clip succeeded and `png` was written. On failure the
    full-page capture goes to `unsafe_png` (the quarantine, NEVER the
    evidence dir — the packer refuses unclipped captures) and nothing is
    written to `png`."""
    try:
        el = page.query_selector("#sc-active-cart")
        box = el.bounding_box() if el else None
        if box and box["width"] > 1 and box["height"] > 1:
            page.screenshot(path=str(png), clip=box)
            return True
    except Exception:
        pass
    Path(unsafe_png).parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(unsafe_png), full_page=True)
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


def compare_cart(picks_rows, cart_items):
    """Multiset comparison of the run's picks vs the ACTIVE cart
    (audit 4.1): every pick present, quantities compared — two tasks
    legitimately choosing the same ASIN expect qty 2 (or two lines).
    Returns (verdict, diff): exact | extras | missing | qty | unparsed."""
    if cart_items is None or not picks_rows:
        return "unparsed", {}
    want = Counter((r.get("asin") or "").strip()
                   for r in picks_rows if (r.get("asin") or "").strip())
    have = Counter()
    for c in cart_items:
        a = (c.get("asin") or "").strip()
        if a:
            try:
                q = int(c.get("qty") or 1)
            except (TypeError, ValueError):
                q = 1
            have[a] += max(q, 1)
    missing = {a: n - have.get(a, 0) for a, n in want.items()
               if have.get(a, 0) < n}
    extras = {a: n - want.get(a, 0) for a, n in have.items()
              if n > want.get(a, 0)}
    diff = {}
    if missing:
        diff["missing"] = missing
    if extras:
        diff["extras"] = extras
    if not diff:
        return "exact", {}
    if set(want) == set(have):
        return "qty", diff     # right products, wrong quantities
    if extras and not missing:
        return "extras", diff
    return "missing", diff


def load_run_picks(run):
    """The run's agent_picks.csv — from the run dir, or adopted from the
    workspace for the just-finished (highest started) run, the same rule
    the packer uses."""
    p = RUNSDIR / f"run{run}" / "agent_picks.csv"
    if not p.exists() and run == detect_run():
        wsp = HOME / "dtlab" / "workspace" / "agent_picks.csv"
        if wsp.exists():
            p = wsp
    try:
        with open(p, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def saved_for_later_asins(page):
    """ASINs parked in the 'Saved for later' section — evidence that a
    cart was 'emptied' with Save for later instead of Delete."""
    try:
        out = []
        for el in page.query_selector_all(SELECTORS["sfl_item"]):
            a = (el.get_attribute(SELECTORS["asin"]) or "").strip()
            if ASIN_RE.fullmatch(a):
                out.append(a)
        return out
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, choices=(1, 2, 3, 4),
                    help="run number (default: auto-detect from run state)")
    args = ap.parse_args()
    if sync_playwright is None:
        sys.exit("playwright missing — run this via the dtlab-cart alias "
                 "(it uses the provisioned environment).")
    run = args.run or detect_run()
    if not run:
        sys.exit("no run detected under ~/dtlab/runs — pass --run N")

    cfg = load_config()
    port = cfg.get("DTLAB_CDP_PORT", "9222")
    EV.mkdir(parents=True, exist_ok=True)
    png = EV / f"cart_run{run}.png"
    unsafe_png = (HOME / "dtlab" / "quarantine" / "unsafe_screenshots"
                  / f"cart_run{run}_fullpage.png")
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
        clipped = capture_screenshot(page, png, unsafe_png)
        if clipped:
            print(f"  [ok] screenshot -> {png} (clipped to the active "
                  "cart)")
        items = parse_items(page)
        sfl = saved_for_later_asins(page)

    # exact cart-vs-picks comparison, ENFORCED LIVE (audit 4.1): pack
    # time is too late — the cart is emptied after this capture and is
    # gone by Sunday
    picks = load_run_picks(run)
    cart_match, diff = compare_cart(picks, items)
    if items is not None:
        out_json.write_text(json.dumps({
            "schema": "dtlab-cart-v1",
            "run": run,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "clip_succeeded": bool(clipped),
            "cart_match": cart_match,
            "cart_match_diff": diff,
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
    if cart_match == "exact":
        print("  [ok] cart matches the run's picks EXACTLY (every pick, "
              "right quantities, nothing extra)")
    elif cart_match == "unparsed":
        print("  [~] cart/picks comparison skipped (cart unparsed or "
              "picks file missing) — recorded for the packer")
    else:
        print()
        print("  [!!] CART DOES NOT MATCH THE RUN'S PICKS — fix it NOW,")
        print("       before emptying (the cart is gone by pack time):")
        for a, n in sorted(diff.get("extras", {}).items()):
            print(f"       - DELETE extra active-cart item {a} (x{n})")
        for a, n in sorted(diff.get("missing", {}).items()):
            print(f"       - MISSING pick {a} (x{n}) — was it added to "
                  "the cart?")
        print("       Then RE-RUN dtlab-cart so the corrected cart is "
              "the evidence.")

    if sfl:
        print(f"  [!!] 'Saved for later' holds {len(sfl)} item(s) "
              f"({', '.join(sfl[:5])}{'...' if len(sfl) > 5 else ''}).")
        print("       If the cart was 'emptied' by clicking Save for later,")
        print("       earlier runs' items are still parked on the account.")
        print("       Delete those saved items too before the next run.")

    if not clipped:
        # capture FAILURE (audit 3.2): a full-page screenshot shows the
        # account name and delivery address — it goes to the quarantine,
        # never to evidence/, and this capture does not count
        print()
        print("  [!!] CAPTURE FAILED: the screenshot could not be clipped "
              "to the")
        print("       active-cart region (#sc-active-cart). The full-page "
              "image was")
        print(f"       quarantined at {unsafe_png}")
        print("       and will never be packed. RECAPTURE NOW: wait for "
              "the cart")
        print("       page to settle, then re-run dtlab-cart; if it fails "
              "again, take")
        print("       a MANUAL screenshot cropped to the cart items only "
              "and save it")
        print(f"       as {png} .")
        return 1

    # intervention capture (D7): the partner records CAPTCHAs and other
    # human interventions for THIS run while memory is fresh
    def ask_count(prompt):
        while True:
            raw = input(prompt).strip()
            if re.fullmatch(r"[0-9]", raw):
                return int(raw)
            print("    a single digit 0-9")

    print()
    print("Intervention log (partner answers, for THIS run):")
    n_captcha = ask_count("  CAPTCHAs handled by a human (0-9): ")
    n_iv = ask_count("  Other human interventions (0-9): ")
    note_txt = input("  One-line note (optional, Enter to skip): ").strip()
    (EV / f"interventions_run{run}.json").write_text(json.dumps({
        "captchas": n_captcha, "interventions": n_iv, "note": note_txt,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")
    print(f"  [ok] interventions recorded -> interventions_run{run}.json")

    print()
    print("NOW EMPTY THE CART by hand — use DELETE, never 'Save for later'")
    print("(saved items stay on the account and pollute later runs). The")
    print("kit never deletes anything on the account. Do not log out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
