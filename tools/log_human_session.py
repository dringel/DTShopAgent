#!/usr/bin/env python3
"""
log_human_session.py — instrument the STUDENT'S OWN shopping session.

Runs BEFORE the agent ever starts. Opens the same persistent browser profile
(and, where available, the same system Chromium binary) the agent will later
use — this is deliberate: a session warmed by genuine human shopping is the
best anti-bot mitigation available — and passively logs the student's
shopping process while they complete the task set themselves — in their
assigned randomized task order — exactly as they normally would.

CAPTURED (to ~/dtlab/human/human_session.jsonl, schema dtlab-humanlog-v1):
  search        — query text, results page number
  product_view  — ASIN, page title, dwell start
  cart_add      — click on Add-to-Cart / Buy-Now (injected listener)
  filter_sort   — sort/filter changes visible in the URL
  nav           — any other amazon.in navigation (fallback)

NOT captured: keystrokes, non-amazon sites, passwords, payment pages
(the /gp/buy and /checkout paths are explicitly dropped). All events are
emitted by an injected page script through a binding that drops anything
whose URL is not an amazon.in page, so a stray non-Amazon tab can never be
logged.

At the end the script walks the student through confirming their final pick
per task (offering the products they viewed) and writes human_picks.csv.

EVERYTHING is written to ~/dtlab/quarantine/human/ — under the quarantine
root the agent is barred from reading (SOUL hard boundary + pre-flight
check + pack-time leakage scan), so the agent's run cannot be
contaminated by the human's choices.

USAGE
  python3 log_human_session.py --student-id DT2026-042
  ...the terminal walks you through the tasks ONE AT A TIME in your
  assigned order (press Enter after each cart-add); empty the cart at
  the end, then confirm your picks...
"""

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    # deferred to main(): id validation must work (and fail clearly)
    # even where the browser stack is absent
    sync_playwright = None

# quarantine root: the agent is barred from ~/dtlab/quarantine/ by SOUL
# boundary + pre-flight check + pack-time leakage scan
HUMAN_DIR = Path.home() / "dtlab" / "quarantine" / "human"
_legacy_human = Path.home() / "dtlab" / "human"
if _legacy_human.is_dir() and not HUMAN_DIR.exists():
    # pre-quarantine layout: migrate once (dtlab-shop can run before
    # dtlab-start's shim ever fires)
    HUMAN_DIR.parent.mkdir(parents=True, exist_ok=True)
    _legacy_human.rename(HUMAN_DIR)
ASIN_RE = re.compile(r"(?:/dp/|/gp/product/)([A-Z0-9]{10})")
ASIN_FULL_RE = re.compile(r"[A-Z0-9]{10}")
BLOCK_PATHS = ("/gp/buy", "/checkout", "/payments", "/ap/")  # never log these
# v1.1 added `category`; v1.2 adds `ref` (the amazon ref= slug of the
# product view — which surface the click came from); v1.3 adds
# task_start/task_end boundary events (the logger walks the student
# through the tasks ONE AT A TIME in their assigned order, so every
# event — search, view, filter, time — is attributable to its task
# exactly); v1.4 also captures listing-page Add-to-Cart clicks (results
# grid), carrying the ASIN from the nearest data-asin ancestor; v1.5
# adds `attempt_id` on every event (audit 5.9: the session is ONE
# committed attempt; TA-token resets archive and re-number). All
# additive.
SCHEMA = "dtlab-humanlog-v1.5"
REF_RE = re.compile(r"/ref=([^/?#]+)")


def load_config():
    cfg = {}
    p = Path.home() / "dtlab" / "dtlab_config.env"
    if p.exists():
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip().strip("'\"")
    return cfg


CFG = load_config()
# same profile the agent uses (see tools/dtlab_browser.sh); lives under
# the persistent lab root so the logged-in session survives rebuilds
PROFILE = Path.home() / CFG.get("DTLAB_BROWSER_PROFILE",
                                "dtlab/browser-profile")

# All events flow through this injected script -> dtlabEvent binding.
# Main frame only; page_load also covers pushState/popstate SPA navigation.
# No Playwright sync-API call ever happens inside an event handler (the sync
# API forbids that), and titles arrive from the page itself.
PAGE_JS = """
(() => {
  if (window !== window.top) return;
  const cat = () => {
    const el = document.querySelector('#wayfinding-breadcrumbs_feature_div');
    return el ? el.innerText.replace(/\\s*\\n\\s*/g, ' ')
                  .replace(/\\s+/g, ' ').trim().slice(0, 200) : '';
  };
  const emit = (type, extra) => {
    if (!window.dtlabEvent) return;
    try {
      window.dtlabEvent(JSON.stringify(Object.assign(
        {type: type, url: location.href, title: document.title,
         category: cat()},
        extra || {})));
    } catch (e) {}
  };
  document.addEventListener('click', (e) => {
    // product-page ATC variants PLUS the results-grid (listing) variants
    // — a pick added straight from the search grid must still log.
    // TODO(dry-run): validate the listing selectors on live amazon.in
    // alongside capture_cart.py's SELECTORS.
    const el = e.target.closest(
      '#add-to-cart-button, #buy-now-button,' +
      ' input[name="submit.add-to-cart"],' +
      ' input[name="submit.addToCart"],' +
      ' [data-action="add-to-cart"], #add-to-cart-button-ubb,' +
      ' [id^="a-autoid"] .a-button-input');
    if (el) {
      const holder = el.closest('[data-asin]');
      const asin = holder ? (holder.getAttribute('data-asin') || '') : '';
      emit('cart_add', asin ? {asin: asin} : {});
    }
  }, true);
  window.addEventListener('load', () => emit('page_load'));
  const wrap = (fn) => function () {
    const r = fn.apply(this, arguments);
    setTimeout(() => emit('page_load'), 80);
    return r;
  };
  history.pushState = wrap(history.pushState);
  history.replaceState = wrap(history.replaceState);
  window.addEventListener('popstate',
                          () => setTimeout(() => emit('page_load'), 80));
})();
"""


def clean_title(title):
    return re.sub(r"\s*[-|].*?Amazon\.in.*$", "", title or "").strip()


def amazon_host(url):
    host = urlparse(url).netloc.lower().split(":")[0]
    return host == "amazon.in" or host.endswith(".amazon.in")


class Logger:
    def __init__(self, out_path, student_id, attempt_id=1):
        self.f = open(out_path, "a", encoding="utf-8")
        self.lock = threading.Lock()
        self.student_id = student_id
        self.attempt_id = attempt_id
        self.viewed = {}   # asin -> latest title (for pick confirmation)
        self.counts = {}   # type -> count (live end-of-session summary)
        self._last = ("", 0.0)   # (url, monotonic) — dedupe double page_load

    def emit(self, type_, **kw):
        rec = {"ts": datetime.now(timezone.utc).isoformat(),
               "student_id": self.student_id,
               "attempt_id": self.attempt_id, "type": type_, **kw}
        with self.lock:
            self.counts[type_] = self.counts.get(type_, 0) + 1
            self.f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self.f.flush()

    def on_nav(self, url, title="", category=""):
        if not amazon_host(url):
            return                       # never log non-amazon browsing
        u = urlparse(url)
        if any(u.path.startswith(b) for b in BLOCK_PATHS):
            return                       # never log checkout/payment/auth
        now = time.monotonic()
        if url == self._last[0] and now - self._last[1] < 2.0:
            return                       # load + pushState double-fire
        self._last = (url, now)
        q = parse_qs(u.query)
        m = ASIN_RE.search(u.path)
        if m:
            asin = m.group(1)
            t = clean_title(title)
            self.viewed[asin] = t or self.viewed.get(asin, "")
            # provenance: amazon's ref= slug names the surface the click
            # came from (search rank, carousel, Buy Again, ...) — the
            # human-side counterpart of the agent's CAND source= field
            rm = REF_RE.search(u.path)
            ref = rm.group(1) if rm else \
                (q.get("ref_") or q.get("ref") or [""])[0]
            self.emit("product_view", asin=asin, title=t, url=u.path,
                      category=category, ref=ref[:80])
        elif u.path == "/s" and "k" in q:
            self.emit("search", query=q["k"][0],
                      page=q.get("page", ["1"])[0],
                      sort=q.get("s", [""])[0])
        elif "rh" in q or "s" in q:
            self.emit("filter_sort", url=u.path + "?" + u.query[:200])
        else:
            self.emit("nav", url=u.path)

    def on_binding(self, source, payload):
        try:
            d = json.loads(payload)
        except json.JSONDecodeError:
            return
        url = d.get("url", "")
        if not amazon_host(url):
            return                       # stray non-Amazon tab: drop
        if d.get("type") == "page_load":
            self.on_nav(url, d.get("title", ""), d.get("category", ""))
        elif d.get("type") == "cart_add":
            # product pages carry the ASIN in the URL; listing-grid clicks
            # carry it from the nearest data-asin ancestor instead
            asin = (d.get("asin") or "").strip().upper()
            if not ASIN_FULL_RE.fullmatch(asin):
                m = ASIN_RE.search(url)
                asin = m.group(1) if m else ""
            self.emit("cart_add", asin=asin,
                      title=clean_title(d.get("title", "")))


def load_task_ids():
    """Task list from ~/dtlab/tasks_config.csv as (id, product_type,
    budget-string); falls back to a generic three tasks so the tool
    still works standalone. Rows whose task_id starts with '#' are
    inactive catalog entries."""
    p = Path.home() / "dtlab" / "tasks_config.csv"
    tasks = []
    if p.exists():
        with open(p, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                tid = (r.get("task_id") or "").strip()
                if not tid or tid.startswith("#"):
                    continue
                try:
                    lo = int(r.get("budget_min_inr") or 0)
                    hi = int(r.get("budget_max_inr") or 0)
                    budget = (f"Rs.{lo}-{hi}" if lo
                              else f"up to Rs.{hi}") if hi else ""
                except ValueError:
                    budget = ""
                tasks.append((tid,
                              (r.get("product_type") or "").strip(),
                              budget))
    return tasks or [("1", "", ""), ("2", "", ""), ("3", "", "")]


def ordered_tasks(tasks, student_id):
    """The student's randomized task order — deterministic from the
    pseudonym, so the human session and all four agent runs share it.
    Ranking is in LOCKSTEP with student_start.sh and pack_evidence.py."""
    import hashlib
    return sorted(tasks, key=lambda tp: hashlib.sha256(
        f"{student_id}|{tp[0]}".encode()).hexdigest())


def confirm_picks(log: Logger, student_id):
    """Interactive confirmation of the final pick per task -> human_picks.csv."""
    recent = list(log.viewed.items())[-15:]
    print("\nProducts you viewed this session:")
    for i, (asin, title) in enumerate(recent, 1):
        print(f"  [{i:2d}] {asin}  {title[:70]}")
    rows = []
    for task, ptype, _budget in ordered_tasks(load_task_ids(), student_id):
        label = f" ({ptype[:50]})" if ptype else ""
        print(f"\n--- Task {task}{label}: your final pick ---")
        while True:
            sel = input("Number from the list above, or paste an ASIN: "
                        ).strip()
            if sel.isdigit() and 1 <= int(sel) <= len(recent):
                asin, title = recent[int(sel) - 1]
                break
            cand = sel.upper()
            if ASIN_FULL_RE.fullmatch(cand):
                asin = cand
                title = log.viewed.get(cand, "")
                if not title:
                    title = input("  Product title: ").strip()
                break
            print("  That is not a valid ASIN (10 characters A-Z/0-9, from "
                  "the product URL after /dp/). Try again.")
        while True:
            price = input("  Price in Rs. (number only): ").strip()
            if re.fullmatch(r"\d[\d,]*(?:\.\d{1,2})?", price):
                break
            print("  Digits (and commas) only, e.g. 1499 — no currency "
                  "symbols or text.")
        why = input("  Why this one (2-3 sentences): ").strip()
        rows.append({"task_id": task, "title": title, "asin": asin,
                     "url": f"https://www.amazon.in/dp/{asin}",
                     "price_inr": price, "reasoning": why})
    out = HUMAN_DIR / "human_picks.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["task_id", "title", "asin", "url",
                                          "price_inr", "reasoning"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {out}")


def find_student_id():
    """The pseudonym from the persona files — the same source every
    other tool resolves it from."""
    for p in (Path.home() / "dtlab" / "workspace" / "persona_survey.csv",
              Path.home() / "dtlab" / "persona_hold" /
              "persona_survey.csv"):
        try:
            with open(p, newline="", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            if rows and (rows[0].get("student_id") or "").strip():
                return rows[0]["student_id"].strip()
        except OSError:
            pass
    return None


def committed_attempts():
    return sorted(HUMAN_DIR.glob(".attempt_*_committed"))


def reset_records():
    p = HUMAN_DIR / ".attempt_resets"
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            out.append(ln)
    return out


def reset_attempt(sid):
    """TA-authorized reset (audit 5.9): archives the committed attempt's
    files into attempt_N/ (append-only, never overwritten) and records
    the reset; the next dtlab-shop run becomes attempt N+1."""
    n_committed = len(committed_attempts())
    if n_committed <= len(reset_records()):
        sys.exit("no committed attempt to reset — just run dtlab-shop")
    tokfile = Path.home() / "dtlab" / ".ta_token"
    expected = tokfile.read_text(encoding="utf-8").strip() \
        if tokfile.exists() else None
    supplied = os.environ.get("DTLAB_TA_TOKEN") \
        or input("TA token: ").strip()
    if not expected or supplied != expected:
        sys.exit("TA token missing or wrong — attempt resets require a "
                 "TA (~/dtlab/.ta_token, installed at setup); the "
                 "committed session stays as-is.")
    reason = input("One-line reason for the reset: ").strip()
    if not reason:
        sys.exit("a reason is required for the audit trail")
    arch = HUMAN_DIR / f"attempt_{n_committed}"
    arch.mkdir(parents=True, exist_ok=True)
    for name in ("human_session.jsonl", "human_picks.csv"):
        src = HUMAN_DIR / name
        if src.exists():
            shutil.move(str(src), str(arch / name))
    with open(HUMAN_DIR / ".attempt_resets", "a",
              encoding="utf-8") as f:
        f.write(json.dumps({
            "reset_at_utc": datetime.now(timezone.utc).isoformat(),
            "student_id": sid, "reason": reason,
            "from_attempt": n_committed}) + "\n")
    print(f"Attempt {n_committed} archived to {arch} (append-only). "
          f"Re-run dtlab-shop for attempt {n_committed + 1}.")
    return 0


def resolve_student_id(arg_sid):
    """Default from persona_survey.csv; validate the pattern; refuse a
    typed id that contradicts the persona — a silent typo here would
    desynchronize the human task order from all four agent runs."""
    persona_sid = find_student_id()
    sid = (arg_sid or "").strip() or persona_sid
    if not sid:
        sys.exit("cannot determine your student id — generate the "
                 "persona first (persona_survey.csv in the workspace) "
                 "or pass --student-id DT2026-###")
    id_re = re.compile(CFG.get("DTLAB_ID_PATTERN", r"DT[0-9]{4}-[0-9]{3}"))
    if not id_re.fullmatch(sid):
        sys.exit(f"student id '{sid}' does not match the course pattern "
                 "— check your pseudonym (a typo would silently "
                 "desynchronize your task order from every agent run)")
    if persona_sid and sid != persona_sid:
        sys.exit(f"--student-id {sid} contradicts persona_survey.csv "
                 f"({persona_sid}) — the SAME pseudonym must drive the "
                 "task order everywhere; drop the flag or fix the "
                 "persona")
    return sid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--student-id", default=None,
                    help="course pseudonym; defaults to the one in "
                         "persona_survey.csv")
    ap.add_argument("--reset-attempt", action="store_true",
                    help="TA-ONLY: archive the committed session "
                         "(append-only) and allow a re-run; requires the "
                         "TA token and a one-line reason")
    args = ap.parse_args()
    sid = resolve_student_id(args.student_id)
    args.student_id = sid
    HUMAN_DIR.mkdir(parents=True, exist_ok=True)
    if args.reset_attempt:
        return reset_attempt(sid)
    # ONE committed attempt (audit 5.9): the session is un-redoable
    # evidence — a second run without a recorded TA reset never starts
    n_committed = len(committed_attempts())
    if n_committed > len(reset_records()):
        sys.exit("Your own shopping session is already committed "
                 f"(attempt {n_committed}) — it happens ONCE. If a "
                 "re-run is genuinely needed, a TA can authorize it: "
                 "dtlab-shop --reset-attempt (TA token required; the "
                 "committed attempt is archived, never overwritten).")
    attempt_id = n_committed + 1
    if sync_playwright is None:
        sys.exit("playwright missing — run this via the dtlab-shop alias "
                 "(it uses the provisioned environment).")
    log = Logger(HUMAN_DIR / "human_session.jsonl", args.student_id,
                 attempt_id)
    log.emit("session_start", schema=SCHEMA)

    # Same binary the agent session uses, so the shared profile never sees
    # version skew (see tools/dtlab_browser.sh — same search order): the
    # fixed-path bundled Chromium (VM route) first, then system chromium.
    fixed = Path.home() / "dtlab" / "bin" / "chromium"
    exe = (str(fixed) if fixed.exists() else None) \
        or shutil.which("chromium") or shutil.which("chromium-browser")
    if not exe:
        print("WARNING: no system chromium found — using Playwright's "
              "bundled Chromium. Profile version skew with the agent "
              "session is possible; flag this to a TA.", file=sys.stderr)

    # checkout-guard extension: the Wednesday human session is
    # add-to-cart-only by protocol, so checkout is network-blocked here
    # exactly like in the agent session (same dir dtlab_browser.sh loads)
    ext_dir = Path(__file__).resolve().parent / "checkout_guard_extension"

    # Same sandbox probe as tools/dtlab_browser.sh — see the security note
    # there. Containers that refuse unprivileged user namespaces kill
    # Chromium before it opens; the VM route keeps its sandbox.
    sandbox_args = []
    try:
        userns_ok = subprocess.run(["unshare", "--user", "true"],
                                   capture_output=True).returncode == 0
    except OSError:
        userns_ok = False
    if not userns_ok:
        sandbox_args = ["--no-sandbox", "--disable-dev-shm-usage"]
        print("NOTICE: unprivileged user namespaces are unavailable in "
              "this container, so Chromium starts WITHOUT its sandbox "
              "(expected on the Codespaces route).", file=sys.stderr)

    with sync_playwright() as p:
        try:
            ctx = p.chromium.launch_persistent_context(
                str(PROFILE), headless=False,
                executable_path=exe or None,
                args=[f"--load-extension={ext_dir}",
                      f"--disable-extensions-except={ext_dir}"]
                     + sandbox_args,
                viewport={"width": 1280, "height": 900})
        except Exception as exc:
            # Do NOT assume a profile lock: a sandbox/namespace abort
            # lands here too, and telling a student to close windows they
            # never opened costs a lab session.
            sys.exit("Could not open the shared lab browser profile.\n"
                     f"  {type(exc).__name__}: {exc}\n"
                     "If that names a namespace or sandbox failure, the "
                     "container refused Chromium's sandbox — tell a TA.\n"
                     "Otherwise another lab-browser window holds the "
                     "profile lock: close ALL of them (including the "
                     "shopping session) and re-run dtlab-shop.")
        ctx.expose_binding("dtlabEvent", log.on_binding)
        ctx.add_init_script(PAGE_JS)

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.amazon.in")
        seq = ordered_tasks(load_task_ids(), args.student_id)
        print(f"\n>>> You will shop your {len(seq)} tasks ONE AT A TIME,")
        print(">>> in YOUR assigned order (same order as in tasks.md).")
        print(">>> Log into amazon.in first if needed. Finish each task")
        print(">>> (add your pick to the cart) BEFORE moving on — the")
        print(">>> walkthrough is what makes your shopping measurable")
        print(">>> per task. Shop each one exactly as you normally would.")
        for i, (task, ptype, budget) in enumerate(seq, 1):
            log.emit("task_start", task_id=task)
            blabel = f" [{budget}]" if budget else ""
            print(f"\n>>> ({i}/{len(seq)}) Task {task}: "
                  f"{ptype[:70]}{blabel}")
            input(">>> Shop for it now; AFTER adding your pick to the "
                  "cart, press Enter... ")
            log.emit("task_end", task_id=task)
        # live capture summary WHILE the browser is still open — a
        # Wednesday problem must be visible Wednesday, not at pack time
        n_s = log.counts.get("search", 0)
        n_v = log.counts.get("product_view", 0)
        n_c = log.counts.get("cart_add", 0)
        print(f"\n>>> Captured this session: {n_s} searches, {n_v} product"
              f" views, {n_c} cart-add clicks.")
        if n_v < len(seq):
            print(">>> Product views look LOW (fewer than one per task) —")
            print(">>> picks added straight from the results grid never")
            print(">>> open a product page. Open each pick's product page")
            print(">>> NOW (click its title) so the view is on record,")
            print(">>> then continue.")
            input(">>> Done browsing your picks? Press Enter... ")
        print("\n>>> All tasks done. Now EMPTY the cart (your picks are")
        print(">>> recorded next; the cart must be clean for the agent).")
        input(">>> Cart emptied? Press Enter to confirm your picks... ")
        try:
            ctx.close()
        except Exception:
            pass

    log.emit("session_end")
    confirm_picks(log, args.student_id)
    # the attempt is COMMITTED once the picks are on file — from here a
    # re-run requires a recorded TA reset
    (HUMAN_DIR / f".attempt_{attempt_id}_committed").write_text(
        f"{datetime.now(timezone.utc).isoformat()} {args.student_id}\n",
        encoding="utf-8")
    print("\nDone. Next step: dtlab-start (the agent run).")
    print("Your picks live in ~/dtlab/quarantine/human/ — the agent "
          "cannot read them.")


if __name__ == "__main__":
    sys.exit(main())
