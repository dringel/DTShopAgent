#!/usr/bin/env python3
"""
analyze_cohort.py — INSTRUCTOR tool: turn a folder of submitted evidence
zips into one self-contained HTML report (plotly-express charts + stats)
for the in-class results debrief.

USAGE
  python3 tools/analyze_cohort.py --zips ~/Downloads/submissions \
      [--out cohort_report.html] [--title "DT Lab — Cohort 2026"]

INPUT   a directory containing the students' DT2026-###_evidence.zip files
        (as downloaded from the LMS; non-zip files are ignored).
OUTPUT  one HTML file, fully self-contained (plotly.js inlined) — open it,
        project it, discuss it.

DEPENDENCIES  pandas + plotly (pip install pandas plotly); scipy is
optional (exact tests instead of normal approximations when present).

WHAT IT REPORTS
  - Main metrics: verdict distribution by task and agent type
    (persona / ablated / single), acceptable-pick rates with Wilson CIs,
    head-to-head winners and pick overlap (ablation design), arm effects.
  - Ratings: student satisfaction with own vs agent picks (1-10).
  - Descriptives: purchase-profile length, brand alignment of agent picks
    with profile brands, price-range alignment, budget compliance,
    sponsored capture, contamination index, human search/view counts.
  - Data quality: parse coverage and validation-issue counts per student.

All inputs are read from each zip's manifest.json + CSVs; free text is
never interpreted beyond the machine-parsed fields the packer validated.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
    import plotly.express as px
except ImportError:
    sys.exit("This tool needs pandas and plotly:  pip install pandas plotly")

try:
    from scipy import stats as sps
except ImportError:
    sps = None

# ---- task structure ---------------------------------------------------
# Defaults match the classic 3-task design; main() replaces them from the
# first submission's config_snapshot/tasks_config.csv, so the report
# adapts to any task set (e.g. the 6-task utilitarian/hedonic design).
DEFAULT_TASKS = [
    {"id": "1", "name": "T1 Sneakers", "cls": "hedonic",
     "lo": 1000, "hi": 2500},
    {"id": "2", "name": "T2 Power bank", "cls": "utilitarian",
     "lo": 800, "hi": 1500},
    {"id": "3", "name": "T3 Backpack", "cls": "utilitarian",
     "lo": 1000, "hi": 2500},
    {"id": "4", "name": "T4 Laptop", "cls": "utilitarian",
     "lo": 40000, "hi": 120000},
    {"id": "5", "name": "T5 Perfume", "cls": "hedonic",
     "lo": 800, "hi": 1500},
]
TASKS = list(DEFAULT_TASKS)
TASK_IDS, TASK_NAMES, BUDGETS, TASK_CLASS = [], {}, {}, {}


def refresh_task_maps():
    TASK_IDS[:] = [t["id"] for t in TASKS]
    TASK_NAMES.clear()
    TASK_NAMES.update({t["id"]: t["name"] for t in TASKS})
    BUDGETS.clear()
    BUDGETS.update({t["id"]: (t["lo"], t["hi"]) for t in TASKS})
    TASK_CLASS.clear()
    TASK_CLASS.update({t["id"]: t["cls"] for t in TASKS})


refresh_task_maps()


def load_tasks_from_zip(path):
    """tasks_config.csv travels inside each zip's config_snapshot; use it
    so the report always matches what the cohort actually ran."""
    try:
        z = zipfile.ZipFile(path)
        name = next(n for n in z.namelist()
                    if n.endswith("config_snapshot/tasks_config.csv"))
        rows = list(csv.DictReader(
            io.StringIO(z.read(name).decode("utf-8-sig"))))
    except (Exception):
        return None
    tasks = []
    try:
        for r in rows:
            tid = (r.get("task_id") or "").strip()
            if not tid or tid.startswith("#"):  # '#' = inactive catalog
                continue
            # short_name (config column) keeps facet axes readable; fall
            # back to a truncated product_type when the column is absent
            short = (r.get("short_name") or "").strip() or \
                (r.get("product_type") or r.get("frame", "") or "?") \
                .split("(")[0].strip()[:14]
            tasks.append({
                "id": tid,
                "name": f"T{tid} {short}",
                "cls": (r.get("category_class") or "").strip()
                or "unclassified",
                "lo": int(r.get("budget_min_inr") or 0),
                "hi": int(r.get("budget_max_inr") or 10 ** 9)})
    except (ValueError, KeyError, TypeError) as e:
        # ONE malformed snapshot must never kill the whole ingest — skip
        # this zip's config and try the next submission's
        print(f"  SKIP tasks_config in {path.name}: {e}", file=sys.stderr)
        return None
    return tasks or None


ACCEPTABLE = {"better", "identical", "equivalent"}
VERDICT_ORDER = ["better", "identical", "equivalent", "inferior"]
# class-facing labels for the design codes (raw codes stay in the data)
ARM_LBL = {"H_FIRST": "Human first", "A_FIRST": "Agent first"}
ORDER_LBL = {"P_FIRST": "Persona run first",
             "NP_FIRST": "Ablated run first"}


def arm_name(a):
    return ARM_LBL.get(a, a)


def order_name(o):
    return ORDER_LBL.get(o, o)

# validated reference palette (dataviz skill): categorical slots 1-3 +
# diverging blue↔gray↔red for verdict polarity; fixed assignment, no
# cycling; each agent type keeps its own hue even when mixed cohorts
# appear in one chart
C_COND = {"persona": "#2a78d6", "ablated": "#eb6834", "single": "#1baf7a"}
C_VERDICT = {"better": "#2a78d6", "identical": "#86b6ef",
             "equivalent": "#c3c2b7", "inferior": "#e34948"}
C_HTH = {"persona": "#2a78d6", "ablated": "#eb6834", "tie": "#c3c2b7"}
# tier reads as a capability gradient of the same hue (not a new hue pair)
C_TIER = {"economy": "#86b6ef", "frontier": "#2a78d6"}
C_MODELW = {"frontier": "#2a78d6", "economy": "#86b6ef",
            "same": "#c3c2b7"}
C_WHO = {"my pick": "#1baf7a", "agent pick": "#2a78d6"}
# the human reference series on the provenance chart: a neutral dark
# that cannot be confused with any agent type (incl. legacy 'single')
C_COND["human"] = "#52514e"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e1e0d9"


# ---- parsing ----------------------------------------------------------
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


def parse_profile(text):
    """Compact order lines: date | cat > sub | brand | product | qty | ₹amt.
    Returns (n_order_lines, brands, prices). Tolerates free-form profiles
    (returns zeros — coverage is reported)."""
    brands, prices, n = [], [], 0
    for line in (text or "").splitlines():
        parts = [p.strip() for p in line.strip().lstrip("-* ").split("|")]
        if len(parts) >= 5:
            n += 1
            if len(parts[2]) >= 3:
                brands.append(parts[2].lower())
            p = parse_price(parts[-1])
            if p:
                prices.append(p)
    return n, sorted(set(brands)), prices


def bucket_source(raw):
    """Provenance bucket for a CAND source= string (fallback for packs
    from before the packer stored source_bucket itself)."""
    s = (raw or "").strip().lower()
    if s.startswith("search"):
        return "search"
    if s.startswith("carousel"):
        return "carousel"
    if s.startswith(("buy_again", "buy it again")):
        return "buy_again"
    if s.startswith("product_page"):
        return "product_page_link"
    if s.startswith("category"):
        return "category_page"
    return "other"


def bucket_ref(ref):
    """Human-side provenance: amazon's ref= slug on a product view ->
    the same buckets as the agent's CAND source= field. The slugs are
    undocumented Amazon internals — this mapping covers the common
    families and is a dry-run spot-check item (T-21); anything
    unrecognized lands in 'other', never an error."""
    r = (ref or "").strip().lower()
    if not r:
        return "other"
    if r.startswith(("sr_", "sspa_sr")) or "_sr_" in r:
        return "search"                     # search results (incl. rank)
    if (r.startswith(("pd_", "cm_", "sspa_dk")) or "sims" in r
            or "bxgy" in r):
        return "carousel"                   # recommendation modules
    if "byab" in r or "buy_again" in r or "buyagain" in r:
        return "buy_again"
    if (r.startswith(("lp_", "ct_", "nav_")) or "bbn" in r
            or "browse" in r):
        return "category_page"
    if r.startswith("dp_"):
        return "product_page_link"          # links on a product page
    return "other"


def read_submission(path):
    """One zip -> (student_meta, [task rows], [provenance rows]) or None
    if unreadable / a sandbox pack (excluded from the research dataset).

    Handles all three manifest generations: single-run, legacy 2-run
    ablation (condition only), and the four-run 2x2 (per-run condition +
    tier; verdict keys "{task}_{condition}_{tier}")."""
    try:
        z = zipfile.ZipFile(path)
        man_name = next(n for n in z.namelist()
                        if n.endswith("manifest.json") and n.count("/") == 1)
        root = man_name.split("/")[0]
        man = json.loads(z.read(man_name))
    except Exception as e:
        print(f"  SKIP {path.name}: {e}", file=sys.stderr)
        return None
    if man.get("sandbox"):
        print(f"  SKIP {path.name}: sandbox pack (excluded from the "
              "research dataset)", file=sys.stderr)
        return None

    def rd(name):
        try:
            return z.read(f"{root}/{name}").decode("utf-8", "replace")
        except KeyError:
            return None

    def rd_csv(name):
        t = rd(name)
        return list(csv.DictReader(io.StringIO(t))) if t else []

    sid = man.get("student_id", root)
    # the student's randomized task order (position 1..N per task)
    torder = man.get("task_order") or man.get("task_order_expected") or []
    tpos = {t: i + 1 for i, t in enumerate(torder)}
    ab = man.get("ablation") or {}
    ablation = bool(ab.get("enabled"))
    run_tiers = ab.get("run_tiers") or {}
    four_run = ablation and (ab.get("design") == "2x2" or bool(run_tiers))
    design = "2x2" if four_run else ("2run" if ablation else "single")
    verdicts = man.get("verdicts") or {}
    ratings = man.get("ratings") or {}
    rationales = man.get("rationales") or {}
    # verdict_at_utc per (task, condition, tier) from the staged
    # verdicts.csv (the manifest carries values only)
    v_at = {}
    for r in rd_csv("verdicts.csv"):
        k = (str(r.get("task_id", "")).strip(),
             (r.get("condition") or "").strip(),
             (r.get("tier") or "").strip())
        v_at[k] = (r.get("verdict_at_utc") or "").strip()
    # TA-authorized amendments: applied LAST-WINS to the analysis values
    # (research_protocol §6; the original rows stay untouched in the zip)
    amended_keys = set()
    n_amendments = 0
    for r in rd_csv("verdicts_amendments.csv"):
        t_ = str(r.get("task_id", "")).strip()
        c_ = (r.get("condition") or "").strip()
        ti_ = (r.get("tier") or "").strip()
        field = (r.get("field") or "").strip()
        val = (r.get("new_value") or "").strip()
        if not (t_ and c_ and field and val):
            continue
        n_amendments += 1
        key = f"{t_}_{c_}_{ti_}" if four_run else f"{t_}_{c_}"
        amended_keys.add((t_, c_, ti_))
        if field == "verdict":
            verdicts[key] = val
        elif field in ("rating_self", "rating_agent"):
            try:
                ratings.setdefault(key, {})[
                    field.split("_")[1]] = int(val)
            except ValueError:
                pass
        elif field == "rationale":
            rationales[key] = val
    hth = (ab.get("head_to_head") or {}) if ablation else {}
    contam = man.get("contamination_index") or {}
    cands = man.get("candidates") or {}
    overlap = (ab.get("pick_overlap") or {}) if four_run else {}
    human = {str(r.get("task_id", "")).strip(): r
             for r in rd_csv("human_picks.csv")}
    n_orders, brands, prices = parse_profile(rd("purchase_profile.md"))
    p_lo = min(prices) if prices else None
    p_hi = max(prices) if prices else None

    # human clickstream: viewed ASINs + leaf categories (humanlog v1.1)
    # + view provenance from the ref= slug (v1.2 `ref` field; the slug
    # embedded in the logged url path works as fallback for v1.1 logs)
    hviewed, hcats = set(), set()
    hbuckets = Counter()
    for line in (rd("human_session.jsonl") or "").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("type") == "product_view":
            if d.get("asin"):
                hviewed.add(d["asin"])
            leaf = (d.get("category") or "").split(">")[-1].strip().lower()
            if leaf:
                hcats.add(leaf)
            ref = d.get("ref")
            if ref is None:
                m = re.search(r"/ref=([^/?#]+)", d.get("url") or "")
                ref = m.group(1) if m else ""
            hbuckets[bucket_ref(ref)] += 1

    # shopping-process length (packer's process block + SRCH lines)
    srch = man.get("searches") or {}
    proc = man.get("process") or {}
    hproc = proc.get("human") or {}
    run_proc = proc.get("runs") or {}
    # partner-recorded interventions per run (D7; dtlab-cart)
    iv_by_run = man.get("interventions_by_run") or {}
    env = man.get("environment") or {}
    model_by_run = env.get("model_id_by_run") or {}
    soul_by_run = env.get("context_sha256_by_run") or {}
    cfg_by_run = env.get("config_sha256_by_run") or {}
    provider = None
    for cfg_line in (rd("config_snapshot/dtlab_config.env")
                     or "").splitlines():
        if cfg_line.strip().startswith("DTLAB_PROVIDER="):
            provider = cfg_line.split("=", 1)[1].strip().strip("'\"")
            break

    # picks per cell: label -> (condition, tier, run, {task: pick-row})
    cells = {}
    if ablation:
        for rn, cond in (ab.get("run_conditions") or {}).items():
            tier = run_tiers.get(rn) or man.get("model_tier")
            label = f"{cond}_{tier}" if four_run else cond
            cells[label] = (cond, tier, rn, {
                str(r.get("task_id", "")).strip(): r
                for r in rd_csv(f"{rn}/agent_picks.csv")})
    else:
        cells["single"] = ("single", man.get("model_tier"), None, {
            str(r.get("task_id", "")).strip(): r
            for r in rd_csv("agent_picks.csv")})

    def day_of(rn):
        """Lab day from the run index (runs 1-2 = day 1, runs 3-4 =
        day 2). With the tier order counterbalanced across days, day is
        its own variable — no longer synonymous with tier."""
        try:
            return 1 if int(str(rn)[3:]) <= 2 else 2
        except (ValueError, TypeError):
            return None

    rows, prov_rows = [], []
    # the human's product views join the provenance chart as their own
    # series ("tier" carries the facet label; views, not candidates)
    for b, n in hbuckets.items():
        prov_rows.append({"student": sid, "condition": "human",
                          "tier": "human session", "bucket": b, "n": n})
    jaccard = {}
    for label, (cond, tier, rn, by_task) in cells.items():
        c_idx = (contam.get(label) if ablation else contam) or {}
        cell_cands = cands.get(label) or {}
        cand_asins = {c.get("asin", "") for lst in cell_cands.values()
                      for c in lst if c.get("asin")}
        if cand_asins and hviewed:
            jaccard[label] = (len(cand_asins & hviewed) /
                              len(cand_asins | hviewed))
        # provenance mix of the candidate set (dtlab-candidates-v1)
        bucket_n = Counter(
            c.get("source_bucket") or bucket_source(c.get("source"))
            for lst in cell_cands.values() for c in lst)
        for b, n in bucket_n.items():
            prov_rows.append({"student": sid, "condition": cond,
                              "tier": tier, "bucket": b, "n": n})
        for t in TASK_IDS:
            a, h = by_task.get(t, {}), human.get(t, {})
            key = f"{t}_{label}" if ablation else t
            v = verdicts.get(key)
            rate = ratings.get(key) or {}
            ap = parse_price(a.get("price_inr"))
            lo, hi = BUDGETS[t]
            title = (a.get("title") or "").lower()
            if four_run:
                hw = (hth.get(f"grounding_{tier}") or {}).get(t)
                mw = (hth.get(f"tier_{cond}") or {}).get(t)
            else:
                hw = hth.get(t) if ablation else None
                mw = None
            rows.append({
                "student": sid, "arm": man.get("arm"),
                "tier": tier, "condition": cond,
                "run": rn,
                "day": day_of(rn) if rn else None,
                "run_order_in_day": (1 if rn in ("run1", "run3") else 2)
                if rn else None,
                "model_id": model_by_run.get(rn) if rn else None,
                "provider": provider,
                "hermes_version": env.get("hermes_version"),
                "soul_sha256": soul_by_run.get(rn) if rn else None,
                "config_sha256": cfg_by_run.get(rn) if rn else None,
                "verdict_at_utc": v_at.get((t, cond, tier or "")),
                "amended": (t, cond, tier or "") in amended_keys,
                "rationale": rationales.get(key),
                "ist_date": (rd(f"{rn}/ist_date.txt") or "").strip()
                or None if rn else None,
                "task": t, "task_name": TASK_NAMES[t],
                "task_position": tpos.get(t),
                "category_class": TASK_CLASS.get(t, "unclassified"),
                "n_candidates": len(cell_cands.get(t, []) or []),
                "n_searches": (len((srch.get(label) or {}).get(t, []))
                               if label in srch else None),
                "run_duration_min": (run_proc.get(rn) or {}).get(
                    "duration_min") if rn else None,
                "captchas": (iv_by_run.get(rn) or {}).get("captchas")
                if rn else None,
                "interventions": (iv_by_run.get(rn) or {}).get(
                    "interventions") if rn else None,
                "task_minutes": None,
                "verdict": v, "acceptable": (v in ACCEPTABLE)
                if v else None,
                "hth_winner": hw,
                "hth_model_winner": mw,
                "rating_self": rate.get("self"),
                "rating_agent": rate.get("agent"),
                "agent_asin": (a.get("asin") or "").strip(),
                "human_asin": (h.get("asin") or "").strip(),
                "agent_price": ap, "human_price": parse_price(
                    h.get("price_inr")),
                "sponsored": str(a.get("sponsored", "")).strip() == "1",
                "budget_ok": (ap is not None and lo <= ap <= hi)
                if ap is not None else None,
                "brand_aligned": any(b in title for b in brands)
                if (brands and title) else None,
                # None (not False) when either side is unknown, so shares
                # are computed over informative rows only
                "price_in_profile_range": (
                    (p_lo <= ap <= p_hi)
                    if (p_lo is not None and ap is not None) else None),
                "contamination": c_idx.get("index"),
            })

    # the human's own picks as a reference series (condition="human"):
    # verdict-free rows carrying only the human-side metrics, so agent
    # charts ignore them and the alignment/consideration charts can
    # show the human next to the twins
    n_views_total = (man.get("human_process") or {}).get(
        "product_views") or 0
    h_per_task = hproc.get("per_task") or {}
    for t in TASK_IDS:
        h = human.get(t, {})
        if not h:
            continue
        hp_price = parse_price(h.get("price_inr"))
        lo, hi = BUDGETS[t]
        htitle = (h.get("title") or "").lower()
        # EXACT per-task attribution when the guided logger ran
        # (task_start/task_end markers, or cart-add segmentation);
        # otherwise spread session totals evenly (approximate)
        pt = h_per_task.get(t) or {}
        rows.append({
            "student": sid, "arm": man.get("arm"),
            "tier": None, "condition": "human",
            "day": None, "ist_date": None,
            "task": t, "task_name": TASK_NAMES[t],
            "task_position": tpos.get(t),
            "category_class": TASK_CLASS.get(t, "unclassified"),
            "n_candidates": pt.get("product_views") if pt else (
                (n_views_total / len(TASK_IDS))
                if n_views_total else 0),
            "n_searches": pt.get("searches") if pt else (
                ((man.get("human_process") or {}).get("searches") or 0)
                / len(TASK_IDS) or None),
            "run_duration_min": hproc.get("duration_min"),
            "captchas": None, "interventions": None,
            "task_minutes": pt.get("minutes") if pt else (
                (hproc.get("per_task_min") or {}).get(t)),
            "verdict": None, "acceptable": None,
            "hth_winner": None, "hth_model_winner": None,
            "rating_self": None, "rating_agent": None,
            "agent_asin": "", "human_asin": (h.get("asin") or "").strip(),
            "agent_price": None, "human_price": hp_price,
            "sponsored": None,
            "budget_ok": (lo <= hp_price <= hi)
            if hp_price is not None else None,
            "brand_aligned": any(b in htitle for b in brands)
            if (brands and htitle) else None,
            "price_in_profile_range": (
                (p_lo <= hp_price <= p_hi)
                if (p_lo is not None and hp_price is not None) else None),
            "contamination": None,
        })

    if four_run:
        g_order = ab.get("grounding_order") or {}
        order_d1, order_d2 = g_order.get("day1"), g_order.get("day2")
        overlap_n = sum(len(v or []) for v in overlap.values())
        t_order = ab.get("tier_order") or {}
        tier_day1 = t_order.get("day1") or run_tiers.get("run1")
    else:
        tier_day1 = None
        order_d1 = ab.get("persona_order") if ablation else None
        order_d2 = None
        overlap_n = (len(ab.get("agent_pick_overlap_tasks") or [])
                     if ablation else None)
    # candidate ASINs per task (union over runs) + the human's viewed
    # set: raw material for the cross-student contamination permutation
    # baseline (student i's candidates vs student j's viewed sets)
    cand_by_task = {}
    for by_t in (cands or {}).values():
        for t, lst in (by_t or {}).items():
            cand_by_task.setdefault(t, set()).update(
                c.get("asin") for c in lst if c.get("asin"))
    # likely stock-outs: a human pick appearing in NO run's candidate
    # set makes 'identical' impossible for that task (human prices are
    # frozen Wednesday; listings move) — countable only where CAND
    # coverage exists
    stockout = 0
    for t_ in TASK_IDS:
        h_asin = (human.get(t_, {}).get("asin") or "").strip()
        pool = cand_by_task.get(t_)
        if h_asin and pool and h_asin not in pool:
            stockout += 1
    def z_sha(suffix):
        try:
            n = next(n for n in z.namelist() if n.endswith(suffix))
        except StopIteration:
            return None
        return hashlib.sha256(z.read(n)).hexdigest()

    # head-to-head rows for the dtlab-hth-v1 export
    hth_rows = []
    if four_run:
        for fam, tmap in hth.items():
            for t_, w_ in (tmap or {}).items():
                hth_rows.append({"student": sid, "task": t_,
                                 "contrast": fam, "winner": w_,
                                 "resolved_from_blind":
                                     bool(man.get(
                                         "verdicts_captured_blind"))})
    meta = {
        "student": sid, "arm": man.get("arm"), "tier": man.get("model_tier"),
        "zip_name": path.name,
        "packed_at_utc": man.get("packed_at_utc"),
        "tasks_config_sha256": z_sha("config_snapshot/tasks_config.csv"),
        "dtlab_config_sha256": z_sha("config_snapshot/dtlab_config.env"),
        "kit_version": (man.get("environment") or {}).get("kit_version"),
        "instrument_size": len(rd_csv("persona_survey.csv")) or None,
        "purchase_profile_sha256": man.get("purchase_profile_sha256"),
        "verdicts_captured_blind": bool(
            man.get("verdicts_captured_blind")),
        "n_amendments": n_amendments,
        "hth_rows": hth_rows,
        "cand_by_task": {t: sorted(s) for t, s in cand_by_task.items()},
        "viewed_asins": sorted(hviewed),
        "stockout_suspect_n": stockout if cand_by_task else None,
        "ablation": ablation, "design": design,
        "persona_order": order_d1,
        "persona_order_day2": order_d2,
        "tier_day1": tier_day1,
        "sensitive_excluded": bool(man.get("sensitive_items_excluded")),
        "n_captchas": sum(int((v or {}).get("captchas") or 0)
                          for v in iv_by_run.values()),
        "n_interventions": sum(int((v or {}).get("interventions") or 0)
                               for v in iv_by_run.values()),
        "has_intervention_log": bool(iv_by_run),
        "overlap_n": overlap_n,
        "pick_overlap": overlap or None,
        "n_profile_orders": n_orders, "n_profile_brands": len(brands),
        "profile_parsed": n_orders > 0,
        "jaccard": jaccard or None,
        "human_viewed_n": len(hviewed),
        "human_cats_n": len(hcats),
        "searches": (man.get("human_process") or {}).get("searches"),
        "product_views": (man.get("human_process") or {}).get(
            "product_views"),
        "n_issues": len(man.get("validation_issues") or []),
        # B22: checkout-attempt detection (guard-blocked; packer scans
        # decision logs + transcripts)
        "n_checkout_urls": sum(
            len(v.get("checkout_urls") or [])
            for v in (man.get("checkout_attempts") or {}).values()),
        "n_guard_fired": sum(
            int(v.get("guard_fired") or 0)
            for v in (man.get("checkout_attempts") or {}).values()),
    }
    return meta, rows, prov_rows


# ---- stats helpers ----------------------------------------------------
def wilson(k, n, zv=1.96):
    if not n:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + zv * zv / n
    c = (p + zv * zv / (2 * n)) / d
    m = zv * math.sqrt(p * (1 - p) / n + zv * zv / (4 * n * n)) / d
    return (max(0.0, c - m), min(1.0, c + m))


def binom_p(k, n):
    """Two-sided sign-test p for k successes of n at p=.5 — exact only
    when scipy is present; otherwise a NORMAL APPROXIMATION (never label
    the fallback 'exact'). Valid only for independent trials, so no
    confirmatory contrast uses it on pooled task-level rows (tasks
    cluster within students — see cboot_p)."""
    if not n:
        return float("nan")
    if sps:
        return sps.binomtest(k, n, 0.5).pvalue
    mu, sd = n / 2, math.sqrt(n) / 2
    zv = abs(k - mu) / sd if sd else 0.0
    return math.erfc(zv / math.sqrt(2))


def two_prop_p(k1, n1, k2, n2):
    if not n1 or not n2:
        return float("nan")
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if not se:
        return float("nan")
    zv = abs(k1 / n1 - k2 / n2) / se
    return math.erfc(zv / math.sqrt(2))


def pct(x):
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) \
        else f"{100 * x:.0f}%"


# Cluster bootstrap: students are the sampling units; task-level rows are
# NOT independent, so every headline CI is resampled at the student level.
# Seeded -> the report is reproducible run-to-run.
BOOT_N, BOOT_SEED = 4000, 2026


def cboot(fn, n_units, ci=95, n_boot=BOOT_N, seed=BOOT_SEED):
    """fn(index_array) -> statistic on that resample of cluster indices."""
    if not n_units:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    vals = np.array([fn(rng.integers(0, n_units, n_units))
                     for _ in range(n_boot)], dtype=float)
    vals = vals[~np.isnan(vals)]
    if vals.size == 0:
        return float("nan"), float("nan")
    a = (100 - ci) / 2
    lo, hi = np.percentile(vals, [a, 100 - a])
    return float(lo), float(hi)


def cboot_p(arr, n_boot=BOOT_N, seed=BOOT_SEED):
    """Cluster-level two-sided bootstrap p for a paired mean difference:
    resample the per-student differences (students are the sampling
    units), p = 2 x the smaller tail share of resampled means crossing 0
    (add-one smoothed so p is never exactly 0). This is the p that
    matches the cluster-bootstrap CIs; pooled task-level sign tests
    (McNemar-style) overstate n because tasks cluster within students."""
    arr = np.asarray(arr, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0 or np.abs(arr).sum() == 0:
        return float("nan")
    rng = np.random.default_rng(seed)
    means = np.array([arr[rng.integers(0, arr.size, arr.size)].mean()
                      for _ in range(n_boot)])
    lo = (np.sum(means <= 0) + 1) / (n_boot + 1)
    hi = (np.sum(means >= 0) + 1) / (n_boot + 1)
    return float(min(1.0, 2 * min(lo, hi)))


def kn_by_student(sub, col="acceptable"):
    g = sub.dropna(subset=[col]).groupby("student")[col]
    return (g.sum().to_numpy(float), g.count().to_numpy(float),
            list(g.count().index))


def rate_ci(sub, col="acceptable"):
    """Cluster-bootstrap 95% CI for a share, resampling students."""
    k, n, _ = kn_by_student(sub, col)
    if not len(n) or n.sum() == 0:
        return float("nan"), (float("nan"), float("nan"))
    est = k.sum() / n.sum()
    lo, hi = cboot(lambda ix: k[ix].sum() / n[ix].sum() if n[ix].sum()
                   else np.nan, len(n))
    return est, (lo, hi)


def cohens_h(p1, p2):
    if any(x is None or math.isnan(x) for x in (p1, p2)):
        return float("nan")
    return 2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2))


def holm(pvals):
    """Holm-Bonferroni step-down adjustment; NaNs pass through."""
    idx = [i for i, p in enumerate(pvals)
           if p is not None and not math.isnan(p)]
    m = len(idx)
    adj = [float("nan")] * len(pvals)
    prev = 0.0
    for rank, i in enumerate(sorted(idx, key=lambda i: pvals[i])):
        prev = max(prev, min(1.0, (m - rank) * pvals[i]))
        adj[i] = prev
    return adj


def fmt_ci(lo, hi):
    if math.isnan(lo):
        return "CI n/a"
    return f"[{100 * lo:.0f}%, {100 * hi:.0f}%]"


# ---- report assembly --------------------------------------------------
LOGO_URI = ""   # set in main() from assets/ringelai.png (or --logo)
# The CLASS report carries no pseudonyms (audit 3.5): student IDs stay
# in internal frames only. --identified restores hover IDs for the
# instructor's private diagnostic copy (banner: do not distribute).
HOVER_ID = None


def style_fig(fig, h=420, ytitle=None):
    mt, mb = 50, 74
    fig.update_layout(
        template="simple_white", height=h,
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif',
                  color=INK, size=13),
        paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb",
        legend_title_text="", margin=dict(l=60, r=30, t=mt, b=mb))
    fig.update_xaxes(gridcolor=GRID, linecolor="#c3c2b7", tickangle=0)
    fig.update_yaxes(gridcolor=GRID, linecolor="#c3c2b7")
    if ytitle is not None:
        # y title on the LEFTMOST axis only — never repeated per facet
        fig.update_yaxes(title="")
        fig.layout.yaxis.title.text = ytitle
    # facet labels read "persona", not "condition=persona"
    fig.for_each_annotation(
        lambda a: a.update(text=a.text.split("=")[-1]))
    # branding on the figure itself, so it survives PNG export and
    # copy-into-slides. Placement rule: charts with a right-side legend
    # carry the mark UNDER the legend (aligned with its column, styled
    # like a legend entry: logo, then the ringel.AI link); all other
    # charts carry it bottom-right in the margin band. Pixel xshifts
    # keep the logo/text pairing exact at any responsive width.
    ph = max(h - mt - mb, 1)
    link = '<a href="https://www.ringel.ai">ringel.AI</a>'
    legend_names = {t.name for t in fig.data
                    if getattr(t, "showlegend", None) is not False
                    and getattr(t, "name", "")}
    has_right_legend = (fig.layout.showlegend is not False
                        and getattr(fig.layout.legend, "orientation",
                                    None) != "h"
                        and len(legend_names) > 0)
    if has_right_legend:
        # legend starts at plot top; ~21 px per entry + padding. The
        # legend box edge is x=1.02; entry swatches sit ~6 px further
        # right, so the logo gets that nudge to left-align with them.
        y_pos = 1 - (len(legend_names) * 21 + 30) / ph
        x_pos = 1.02 + 0.0065
        if LOGO_URI:
            fig.add_layout_image(dict(
                source=LOGO_URI, xref="paper", yref="paper",
                x=x_pos, y=y_pos, xanchor="left", yanchor="top",
                sizex=0.08, sizey=18 / ph, sizing="contain",
                opacity=0.9, layer="above"))
        fig.add_annotation(
            text=link, xref="paper", yref="paper",
            x=x_pos, y=y_pos, xanchor="left", yanchor="top",
            xshift=24 if LOGO_URI else 0, yshift=-2,
            showarrow=False, font=dict(size=11, color="#898781"))
    else:
        y_bot = -(mb - 2) / ph
        if LOGO_URI:
            fig.add_layout_image(dict(
                source=LOGO_URI, xref="paper", yref="paper",
                x=1, y=y_bot, xanchor="right", yanchor="bottom",
                sizex=0.08, sizey=20 / ph, sizing="contain",
                opacity=0.9, layer="above"))
        fig.add_annotation(
            text=link, xref="paper", yref="paper", x=1, y=y_bot,
            xanchor="right", yanchor="bottom",
            xshift=-26 if LOGO_URI else 0, yshift=3,
            showarrow=False, font=dict(size=11, color="#898781"))
    return fig


def load_logo(path=None):
    """RingelAI logo as a data URI for the report header ('' if absent)."""
    import base64
    p = Path(path) if path else \
        Path(__file__).resolve().parent.parent / "assets" / "ringelai.png"
    if not p.exists():
        return ""
    return ("data:image/png;base64," +
            base64.b64encode(p.read_bytes()).decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zips", required=True,
                    help="directory of *_evidence.zip submissions")
    ap.add_argument("--out", default="cohort_report.html")
    ap.add_argument("--title", default="Digital Twin Lab — cohort results")
    ap.add_argument("--logo", default=None,
                    help="logo PNG for the header + figures (default: repo "
                         "assets/ringelai.png; silently skipped if absent)")
    ap.add_argument("--identified", action="store_true",
                    help="INSTRUCTOR-ONLY diagnostic copy: restore student "
                         "pseudonyms on chart hovers and tables (banner "
                         "added; never distribute this variant)")
    ap.add_argument("--decisions", default=None,
                    help="decisions.csv (student_id, action "
                         "{include|exclude}, reason) — instructor "
                         "overrides applied LAST and echoed verbatim in "
                         "the report (the audit trail)")
    ap.add_argument("--export-runs", default=None, metavar="runs.csv",
                    help="write the dtlab-runs-v1 run-level research "
                         "export (one record per participant x task x "
                         "run, confirmatory set only)")
    ap.add_argument("--export-hth", default=None, metavar="hth.csv",
                    help="write the dtlab-hth-v1 head-to-head export")
    ap.add_argument("--allow-mixed", action="store_true",
                    help="allow exports from mixed schema generations")
    args = ap.parse_args()
    globals()["LOGO_URI"] = load_logo(args.logo)
    if args.identified:
        globals()["HOVER_ID"] = ["student"]

    zdir = Path(args.zips).expanduser()
    paths = sorted(zdir.glob("*_evidence.zip")) or sorted(zdir.glob("*.zip"))
    if not paths:
        sys.exit(f"no zips found in {zdir}")
    for pk in paths:
        tset = load_tasks_from_zip(pk)
        if tset:
            TASKS[:] = tset
            refresh_task_maps()
            break
    budget_note = "Task budgets: " + "; ".join(
        f"{TASK_NAMES[t]} ₹{BUDGETS[t][0]:,}–₹{BUDGETS[t][1]:,}"
        for t in TASK_IDS) + "."
    parsed = []
    for p in paths:
        r = read_submission(p)
        if r:
            parsed.append(r)
    if not parsed:
        sys.exit("no submissions could be parsed")
    n_parsed = len(parsed)

    def mask_sid(s):
        """Class copies carry no pseudonyms (audit 3.5): quarantine and
        decision tables show a stable anonymous label unless
        --identified."""
        if args.identified:
            return str(s)
        return "anon-" + hashlib.sha256(str(s).encode()).hexdigest()[:8]

    # ---- duplicate student_ids across zips: latest packed_at_utc wins,
    # the rest are quarantined entirely (audit 4.7 item 4) ----
    quarantine = {}          # student -> [machine-readable reasons]
    by_sid = {}
    dup_notes = []
    for meta, rows_, prov_ in parsed:
        sid_ = meta["student"]
        prev = by_sid.get(sid_)
        if prev is None:
            by_sid[sid_] = (meta, rows_, prov_)
            continue
        newer = (meta.get("packed_at_utc") or "") > \
            (prev[0].get("packed_at_utc") or "")
        winner, loser = ((meta, rows_, prov_), prev) if newer \
            else (prev, (meta, rows_, prov_))
        dup_notes.append(
            (sid_, f"duplicate_student_id: kept the zip packed at "
                   f"{winner[0].get('packed_at_utc')}, dropped the one "
                   f"packed at {loser[0].get('packed_at_utc')}"))
        by_sid[sid_] = winner
    metas = [m for m, _, _ in by_sid.values()]
    rows = [r for _, rows_, _ in by_sid.values() for r in rows_]
    prov_rows = [r for _, _, prov_ in by_sid.values() for r in prov_]
    # the superseded zips are quarantined (table rows below); the KEPT
    # zip's student stays in the confirmatory set

    # ---- cohort homogeneity gates (audit 4.7): confirmatory inputs
    # must share the modal tasks-config hash + instrument size; invalid
    # packs (nonzero validation_issues) are quarantined by default ----
    def modal(vals):
        c = Counter(v for v in vals if v is not None)
        return c.most_common(1)[0][0] if c else None

    modal_cfg = modal([m["tasks_config_sha256"] for m in metas])
    modal_instr = modal([m["instrument_size"] for m in metas])
    for m in metas:
        reasons = []
        if modal_cfg and m["tasks_config_sha256"] != modal_cfg:
            reasons.append(
                "tasks_config_sha256_mismatch:"
                f"{(m['tasks_config_sha256'] or 'absent')[:12]}"
                f"!={modal_cfg[:12]}")
        if modal_instr and m["instrument_size"] not in (None,
                                                        modal_instr):
            reasons.append(f"instrument_size:{m['instrument_size']}"
                           f"!={modal_instr}")
        if m["n_issues"]:
            reasons.append(f"validation_issues:{m['n_issues']}")
        for r_ in reasons:
            quarantine.setdefault(m["student"], []).append(r_)

    # ---- instructor decisions, applied LAST and echoed verbatim ----
    decisions = []
    if args.decisions:
        with open(args.decisions, newline="", encoding="utf-8-sig") as f:
            decisions = list(csv.DictReader(f))
        for d in decisions:
            dsid = (d.get("student_id") or "").strip()
            act = (d.get("action") or "").strip().lower()
            if act == "include":
                quarantine.pop(dsid, None)
            elif act == "exclude":
                quarantine.setdefault(dsid, []).append(
                    "decision:"
                    + ((d.get("reason") or "").strip() or "excluded"))

    df_all = pd.DataFrame(rows)
    sdf_all = pd.DataFrame(metas)
    conf_sids = {m["student"] for m in metas
                 if m["student"] not in quarantine}
    df = df_all[df_all["student"].isin(conf_sids)].copy()
    sdf = sdf_all[sdf_all["student"].isin(conf_sids)].copy()
    prov_rows = [r for r in prov_rows if r["student"] in conf_sids]
    if not len(df):
        # every pack quarantined: emit a DIAGNOSTIC page (instructor
        # triage — pseudonyms + reasons belong here), never crash
        outp = Path(args.out)
        outp.write_text(
            f'<!doctype html><meta charset="utf-8">'
            f"<title>{args.title}</title><h1>{args.title}</h1>"
            f"<p><b>No analyzable packs:</b> {n_parsed} submission "
            "zip(s) parsed, but none survived the quarantine gates. "
            "Reasons: "
            + "; ".join(f"{s}: {', '.join(rs)}"
                        for s, rs in sorted(quarantine.items()))
            + ". Overrides go through decisions.csv (--decisions).</p>",
            encoding="utf-8")
        print(f"Report -> {outp.resolve()} (no confirmatory packs; "
              f"{len(quarantine)} quarantined)")
        return
    ablation = bool(sdf["ablation"].any())
    # four-run 2x2 cohort (grounding x tier)? Mixed cohorts degrade
    # gracefully: 2x2 charts appear when any 2x2 pack is present.
    four_run = "2x2" in set(sdf["design"])
    conds = [c for c in ("persona", "ablated", "single")
             if c in set(df["condition"])]
    tiers_present = [t for t in ("economy", "frontier")
                     if t in set(df["tier"].dropna())]

    figs = []

    def add(fig, heading, note=""):
        figs.append((heading, note, fig))

    # 1 — verdicts by task (and agent type); in the 2x2 the grid facets
    # grounding (columns) x tier (rows)
    vd = df.dropna(subset=["verdict"])
    if not len(vd):
        # zero parsed verdicts across the cohort: emit a diagnostic
        # report instead of crashing mid-chart
        out = Path(args.out)
        out.write_text(
            f"<!doctype html><meta charset=\"utf-8\">"
            f"<title>{args.title}</title>"
            f"<h1>{args.title}</h1>"
            f"<p><b>No analyzable packs:</b> {len(sdf)} submission "
            f"zip(s) parsed, but none carried a single verdict. Check "
            "that dtlab-verdict ran and that the zips are real "
            "dtlab-pack output (validation_issues per student: "
            + ", ".join(f"{m_['student']}={m_['n_issues']}"
                        for m_ in metas) + ").</p>",
            encoding="utf-8")
        print(f"Report -> {out.resolve()} (no analyzable verdicts in "
              f"{len(sdf)} submissions)")
        return
    fig = px.histogram(
        vd, x="task_name", color="verdict", barnorm="fraction",
        facet_col="condition" if ablation else None,
        facet_row="tier" if four_run else None,
        category_orders={"verdict": VERDICT_ORDER,
                         "task_name": list(TASK_NAMES.values()),
                         "condition": conds,
                         "tier": tiers_present},
        color_discrete_map=C_VERDICT)
    fig.update_yaxes(tickformat=".0%")
    fig.update_xaxes(title="")
    fig = style_fig(fig, h=560 if four_run else 420,
                    ytitle="share of students")
    fig.update_xaxes(tickangle=-30)
    add(fig, "Verdicts by task" +
        (", grounding, and model tier" if four_run else
         (" and agent type" if ablation else "")),
        "How each agent pick compares to the student's own pre-registered "
        "pick. 'identical' is ASIN-verified, not self-reported.")

    # 2 — acceptable rate per cell, cluster-bootstrap CIs (2x2 grid when
    # the tier factor is present)
    acc = []
    for c in conds:
        for ti in (tiers_present if four_run else [None]):
            sub = vd[(vd["condition"] == c) &
                     ((vd["tier"] == ti) if ti else True)].copy()
            if not len(sub):
                continue
            sub["acceptable"] = sub["acceptable"].astype(float)
            e, (lo, hi) = rate_ci(sub)
            acc.append({"condition": c, "tier": ti or "all", "rate": e,
                        "lo": lo, "hi": hi, "n": len(sub)})
    accdf = pd.DataFrame(acc)
    accdf["err_up"] = accdf["hi"] - accdf["rate"]
    accdf["err_dn"] = accdf["rate"] - accdf["lo"]
    if four_run:
        fig = px.bar(accdf, x="condition", y="rate", color="tier",
                     barmode="group", error_y="err_up",
                     error_y_minus="err_dn",
                     category_orders={"condition": conds,
                                      "tier": tiers_present},
                     color_discrete_map=C_TIER,
                     text=accdf["rate"].map(lambda r: f"{100 * r:.0f}%"))
        fig.update_traces(textposition="outside")
    else:
        fig = px.bar(accdf, x="condition", y="rate", color="condition",
                     color_discrete_map=C_COND,
                     category_orders={"condition": conds},
                     error_y="err_up", error_y_minus="err_dn",
                     text=accdf["rate"].map(lambda r: f"{100 * r:.0f}%"))
        fig.update_traces(width=0.5, showlegend=False,
                          textposition="outside")
    fig.update_yaxes(title="acceptable-pick rate", tickformat=".0%",
                     range=[0, 1.05])
    fig.update_xaxes(title="")
    add(style_fig(fig, 380), "Acceptable-pick rate (better/identical/"
        "equivalent) with cluster-bootstrap 95% CIs" +
        (" — grounding x tier" if four_run else ""),
        "The headline 'how well did the agents do' metric, per agent "
        "type. CIs resample students, not tasks (tasks are correlated "
        "within student).")

    # 3 — ablation: head-to-head + overlap (both contrast families in
    # the 2x2: grounding winner per tier, tier winner per grounding)
    if ablation:
        hh = df.dropna(subset=["hth_winner"]).drop_duplicates(
            ["student", "task", "tier"] if four_run
            else ["student", "task"])
        if len(hh):
            fig = px.histogram(hh, x="task_name", color="hth_winner",
                               barnorm="fraction",
                               facet_col="tier" if four_run else None,
                               category_orders={
                                   "hth_winner": ["persona", "tie",
                                                  "ablated"],
                                   "task_name": list(TASK_NAMES.values()),
                                   "tier": tiers_present},
                               color_discrete_map=C_HTH)
            fig.update_yaxes(tickformat=".0%")
            fig.update_xaxes(title="")
            fig = style_fig(fig, ytitle="share of students")
            fig.update_xaxes(tickangle=-30)
            add(fig, "Head-to-head: which GROUNDING chose better for you?" +
                (" (per tier)" if four_run else ""),
                "Direct within-student comparison of the persona vs "
                "ablated pick per task (ties allowed)" +
                (", separately per model tier." if four_run else "."))
        if four_run:
            hm = df.dropna(subset=["hth_model_winner"]).drop_duplicates(
                ["student", "task", "condition"])
            if len(hm):
                fig = px.histogram(
                    hm, x="task_name", color="hth_model_winner",
                    barnorm="fraction", facet_col="condition",
                    category_orders={
                        "hth_model_winner": ["frontier", "same",
                                             "economy"],
                        "task_name": list(TASK_NAMES.values()),
                        # never force an empty 'single' facet here
                        "condition": [c for c in conds
                                      if c in ("persona", "ablated")]},
                    color_discrete_map=C_MODELW)
                fig.update_yaxes(tickformat=".0%")
                fig.update_xaxes(title="")
                fig = style_fig(fig, ytitle="share of students")
                fig.update_xaxes(tickangle=-30)
                add(fig, "Head-to-head: which MODEL TIER chose better "
                    "for you? (per grounding)",
                    "Did the frontier model's pick beat the economy "
                    "model's pick for the same task and grounding? The "
                    "course's 'is it worth ~10x the price' question, per "
                    "student and task.")

        # pick overlap: same ASIN across the contrast's two runs
        def same_share(sub, other_cond=None, other_tier=None):
            def match(r):
                q = df[(df["student"] == r["student"]) &
                       (df["task"] == r["task"]) &
                       (df["condition"] == (other_cond or r["condition"])) &
                       ((df["tier"] == (other_tier or r["tier"]))
                        if four_run else True)]
                return bool(r["agent_asin"]) and \
                    r["agent_asin"] == q["agent_asin"].max()
            return sub.assign(same=sub.apply(match, axis=1))

        if four_run:
            ov_parts = []
            for ti in tiers_present:
                s = same_share(df[(df["condition"] == "persona") &
                                  (df["tier"] == ti)],
                               other_cond="ablated")
                s = s.assign(contrast=f"persona vs ablated ({ti})")
                ov_parts.append(s)
            for c in ("persona", "ablated"):
                if {"economy", "frontier"} <= set(
                        df[df["condition"] == c]["tier"]):
                    s = same_share(df[(df["condition"] == c) &
                                      (df["tier"] == "economy")],
                                   other_tier="frontier")
                    s = s.assign(
                        contrast=f"economy vs frontier ({c})")
                    ov_parts.append(s)
            ov = pd.concat(ov_parts) if ov_parts else pd.DataFrame()
            if len(ov):
                ovr = (ov.groupby(["contrast", "task_name"])["same"]
                       .mean().reset_index())
                fig = px.bar(ovr, x="task_name", y="same",
                             color="contrast", barmode="group",
                             category_orders={"task_name":
                                              list(TASK_NAMES.values())})
                fig.update_yaxes(title="same ASIN in both runs",
                                 tickformat=".0%", range=[0, 1.05])
                fig.update_xaxes(title="")
                add(style_fig(fig), "Pick overlap across runs, per "
                    "contrast",
                    "Tasks where the two runs of a contrast chose the "
                    "SAME product — where that factor changed nothing. "
                    "Grounding contrasts hold tier constant; tier "
                    "contrasts hold grounding constant.")
        else:
            ov = same_share(df[df["condition"] == "persona"],
                            other_cond="ablated")
            ovr = ov.groupby("task_name")["same"].mean().reset_index()
            fig = px.bar(ovr, x="task_name", y="same",
                         text=ovr["same"].map(lambda r: f"{100 * r:.0f}%"))
            fig.update_traces(marker_color="#2a78d6", width=0.5,
                              textposition="outside")
            fig.update_yaxes(title="same ASIN in both runs",
                             tickformat=".0%", range=[0, 1.05])
            fig.update_xaxes(title="")
            add(style_fig(fig, 380), "Pick overlap between the two runs",
                "Tasks where persona and ablated runs chose the SAME "
                "product — where the questionnaire changed nothing.")

    # 4 — ratings
    rat = df.melt(id_vars=["student", "condition", "task_name"],
                  value_vars=["rating_self", "rating_agent"],
                  var_name="who", value_name="rating").dropna(
        subset=["rating"])
    rat["who"] = rat["who"].map({"rating_self": "my pick",
                                 "rating_agent": "agent pick"})
    if len(rat):
        fig = px.box(rat, x="condition", y="rating", color="who",
                     category_orders={"condition": conds},
                     color_discrete_map=C_WHO, points="all")
        fig.update_yaxes(title="satisfaction (1-10)", range=[0.5, 10.5])
        fig.update_xaxes(title="")
        add(style_fig(fig), "Satisfaction ratings: own vs agent picks",
            "Would you be happy OWNING it? 1-10 per pick, from the "
            "comparison memo.")

    # convergent validity: the two DVs (categorical verdict, numeric
    # rating delta) should tell the same story
    val = df.dropna(subset=["verdict", "rating_self", "rating_agent"]).copy()
    if len(val) >= 6:
        val["rating_delta"] = val["rating_agent"] - val["rating_self"]
        fig = px.box(val, x="verdict", y="rating_delta", color="verdict",
                     category_orders={"verdict": VERDICT_ORDER},
                     color_discrete_map=C_VERDICT, points="all")
        fig.add_hline(y=0, line=dict(color="#898781", dash="dot", width=2))
        fig.update_layout(showlegend=False)
        fig.update_yaxes(title="agent rating − own rating")
        fig.update_xaxes(title="")
        add(style_fig(fig, 380),
            "Convergent validity: do ratings track verdicts?",
            "Each verdict category's distribution of (agent − own) rating "
            "deltas. 'better' should sit above zero, 'inferior' below; a "
            "flat pattern would mean the two measures disagree.")

    # 5 — price behavior
    pp = df.dropna(subset=["agent_price", "human_price"])
    if len(pp):
        fig = px.scatter(pp, x="human_price", y="agent_price",
                         color="condition", facet_col="task_name",
                         color_discrete_map=C_COND,
                         category_orders={"condition": conds},
                         hover_data=HOVER_ID)
        fig.update_traces(marker=dict(size=9, opacity=0.75,
                                      line=dict(width=1,
                                                color="#fcfcfb")))
        for i, t in enumerate(TASK_IDS, 1):
            hi = BUDGETS[t][1]
            fig.add_shape(type="line", x0=0, y0=0, x1=hi * 1.2,
                          y1=hi * 1.2, xref=f"x{i if i > 1 else ''}",
                          yref=f"y{i if i > 1 else ''}",
                          # explicit width: simple_white's shapedefaults
                          # set line.width=0, which hides the line
                          line=dict(color="#898781", dash="dot", width=2),
                          opacity=1)
        fig.update_xaxes(title="your price (₹)", matches=None)
        # free per-task scales NEED visible ticks on every facet
        fig.update_yaxes(matches=None, showticklabels=True)
        add(style_fig(fig, ytitle="agent price (₹)"),
            "Price: agent vs human, per task",
            "Dotted line = same price. Above it, the agent spent more "
            "than you did. Prices were captured on different days "
            "(human Wednesday, agents Thursday/Friday) — day-to-day "
            "price drift contributes to the scatter. " + budget_note)

    # 6 — alignment & compliance summary bars (the human's own picks
    # join as the reference series; sponsored is agent-only — the human
    # log does not flag it)
    has_human_rows = "human" in set(df["condition"])
    aconds = conds + (["human"] if has_human_rows else [])
    align = []
    for c in aconds:
        sub = df[df["condition"] == c]
        for label, col in (("brand in profile", "brand_aligned"),
                           ("price in profile range",
                            "price_in_profile_range"),
                           ("within task budget", "budget_ok"),
                           ("sponsored pick", "sponsored")):
            s = sub[col].dropna()
            if len(s):
                align.append({"condition": c, "metric": label,
                              "share": float(s.mean())})
    if align:
        adf = pd.DataFrame(align)
        fig = px.bar(adf, x="metric", y="share", color="condition",
                     barmode="group", color_discrete_map=C_COND,
                     category_orders={"condition": aconds})
        fig.update_yaxes(title="share of picks", tickformat=".0%",
                         range=[0, 1.05])
        fig.update_xaxes(title="")
        add(style_fig(fig), "Alignment with the student's history, "
            "budget compliance, sponsored capture — twins vs the human",
            "Brand/price alignment uses the compact order lines the agent "
            "wrote into purchase_profile.md (coverage reported below); "
            "the human bars score the student's OWN picks on the same "
            "yardsticks (no sponsored flag — the human log doesn't "
            "capture it). " + budget_note)

    # 6b — consideration sets (CAND protocol) vs human product views
    cs = df[df["n_candidates"] > 0]
    if len(cs):
        fig = px.box(cs, x="task_name", y="n_candidates",
                     color="condition",
                     category_orders={"condition": aconds,
                                      "task_name":
                                          list(TASK_NAMES.values())},
                     color_discrete_map=C_COND, points="all")
        fig.update_yaxes(title="candidates / views per task")
        fig.update_xaxes(title="")
        add(style_fig(fig), "Consideration-set size per task — "
            "twins vs the human",
            "Agents: machine-parsed CAND lines in the decision logs — "
            "how widely each twin searched before choosing. Human: "
            "product views per task, attributed EXACTLY by the guided "
            "one-task-at-a-time session (task markers; cart-add "
            "segmentation for older logs; evenly-spread approximation "
            "only when neither exists).")

    # 6c2 — search effort: queries per task, twins vs the human
    se = df[df["n_searches"].notna() & (df["n_searches"] > 0)]
    if len(se):
        fig = px.box(se, x="task_name", y="n_searches",
                     color="condition",
                     category_orders={"condition": aconds,
                                      "task_name":
                                          list(TASK_NAMES.values())},
                     color_discrete_map=C_COND, points="all")
        fig.update_yaxes(title="searches per task")
        fig.update_xaxes(title="")
        add(style_fig(fig), "Shopping effort: searches per task — "
            "twins vs the human",
            "Agents: machine-parsed SRCH lines in the decision logs "
            "(every query the agent typed, with any filters). Human: "
            "searches per task, attributed exactly by the guided "
            "one-task-at-a-time session (evenly-spread approximation "
            "only for logs without task boundaries).")

    # 6c3 — time spent: agent run durations vs the human session
    dd = df.dropna(subset=["run_duration_min"]).drop_duplicates(
        ["student", "condition", "tier"]).copy()
    if len(dd):
        dd["tier_lbl"] = dd["tier"].fillna("human session") \
            if dd["tier"].isna().any() else dd["tier"]
        dd.loc[dd["condition"] == "human", "tier_lbl"] = "human session"
        c_tier_h = dict(C_TIER, **{"human session": "#52514e"})
        fig = px.box(dd, x="condition", y="run_duration_min",
                     color="tier_lbl",
                     category_orders={
                         "condition": aconds,
                         "tier_lbl": tiers_present + ["human session"]},
                     color_discrete_map=c_tier_h, points="all")
        fig.update_yaxes(title="minutes")
        fig.update_xaxes(title="")
        add(style_fig(fig), "Time spent: agent run duration vs the "
            "human session",
            "One agent run and one human session both cover the full "
            "task set once, so the units are comparable. Agent duration "
            "= run start to the last write of its picks file; human "
            "duration = first to last clickstream event. Per-task agent "
            "timing needs the Hermes transcript timestamps (dry-run "
            "item).")

    # 6c4 — human time-to-selection per task (cart-add segmentation)
    hm = df[df["task_minutes"].notna()]
    if len(hm):
        fig = px.box(hm, x="task_name", y="task_minutes", points="all")
        fig.update_traces(marker_color="#52514e",
                          line_color="#52514e")
        fig.update_yaxes(title="minutes to cart-add")
        fig.update_xaxes(title="")
        add(style_fig(fig, 380), "Human minutes per task "
            "(time-to-selection)",
            "From the guided session's task_start/task_end timestamps "
            "(exact); for logs without markers, estimated by segmenting "
            "the clickstream at the cart-add events along the assigned "
            "task order.")

    # 6d — provenance mix: where the agents' candidates came from
    # (CAND source= buckets) vs where the human's product views came
    # from (amazon ref= slugs, same buckets)
    pdf = pd.DataFrame(prov_rows)
    if len(pdf):
        BUCKET_ORDER = ["search", "carousel", "buy_again",
                        "product_page_link", "category_page", "other"]
        grp = ["condition", "tier", "bucket"] if four_run \
            else ["condition", "bucket"]
        pmix = pdf.groupby(grp)["n"].sum().reset_index()
        denom = pmix.groupby(grp[:-1])["n"].transform("sum")
        pmix["share"] = pmix["n"] / denom
        has_human = "human" in set(pmix["condition"])
        pconds = conds + (["human"] if has_human else [])
        fig = px.bar(pmix, x="bucket", y="share", color="condition",
                     barmode="group",
                     facet_col="tier" if four_run else None,
                     category_orders={
                         "bucket": BUCKET_ORDER,
                         "condition": pconds,
                         "tier": tiers_present +
                         (["human session"] if has_human else [])},
                     color_discrete_map=C_COND)
        fig.update_yaxes(title="share of candidates / views",
                         tickformat=".0%")
        fig.update_xaxes(title="")
        fig = style_fig(fig)
        fig.update_xaxes(tickangle=-30)
        add(fig, "Provenance mix: agent candidates vs human views "
            "(choice-architecture exposure)",
            "Agent bars: where each candidate came from, per the CAND "
            "source= field (search rank, carousels, Buy-again, product-"
            "page links, category pages). Human bars: the same buckets "
            "inferred from the amazon ref= slug on each logged product "
            "view. Read with care: agents log an explicit CANDIDATE "
            "set, the human side counts product VIEWS, and ref= slugs "
            "are undocumented Amazon internals (mapping spot-checked at "
            "the dry run; unrecognized slugs land in 'other').")

    # 6c — utilitarian vs hedonic fidelity
    classes = [c for c in ("utilitarian", "hedonic", "unclassified")
               if c in set(df["category_class"])]
    if len(classes) > 1:
        vc = vd.dropna(subset=["acceptable"]).copy()
        vc["acceptable"] = vc["acceptable"].astype(float)
        rowsc = [{"class": cls, "condition": c,
                  "rate": float(sub["acceptable"].mean()), "n": len(sub)}
                 for cls in classes for c in conds
                 for sub in [vc[(vc["category_class"] == cls) &
                                (vc["condition"] == c)]] if len(sub)]
        cdf = pd.DataFrame(rowsc)
        fig = px.bar(cdf, x="class", y="rate", color="condition",
                     barmode="group", color_discrete_map=C_COND,
                     category_orders={"condition": conds,
                                      "class": classes},
                     text=cdf["rate"].map(lambda r: f"{100 * r:.0f}%"))
        fig.update_traces(textposition="outside")
        fig.update_yaxes(title="acceptable-pick rate", tickformat=".0%",
                         range=[0, 1.1])
        fig.update_xaxes(title="")
        add(style_fig(fig, 380), "Twin fidelity by product-category class",
            "Utilitarian vs hedonic tasks (class assigned per task in "
            "tasks_config.csv). Hedonic/taste goods are where twins are "
            "expected to struggle.")

    # 7 — purchase history descriptives
    fig = px.histogram(sdf, x="n_profile_orders", nbins=20)
    fig.update_traces(marker_color="#2a78d6")
    fig.update_xaxes(title="orders listed in purchase_profile.md")
    fig.update_yaxes(title="students")
    add(style_fig(fig, 360), "Purchase-history length",
        "Thin profiles produce persona-only twins — a comparison "
        "subgroup, not failures.")

    per_student = (vd[vd["condition"] == conds[0]]
                   .assign(acceptable=lambda d:
                           d["acceptable"].astype(float))
                   .groupby("student")["acceptable"].mean().reset_index()
                   .merge(sdf[["student", "n_profile_orders"]],
                          on="student"))
    if len(per_student) > 4:
        fig = px.scatter(per_student, x="n_profile_orders", y="acceptable",
                         hover_data=HOVER_ID)
        fig.update_traces(marker=dict(size=10, color="#2a78d6",
                                      opacity=0.75))
        xs = per_student["n_profile_orders"].astype(float)
        if xs.nunique() > 1:
            m, b = np.polyfit(xs, per_student["acceptable"], 1)
            xr = [xs.min(), xs.max()]
            fig.add_scatter(x=xr, y=[m * x + b for x in xr], mode="lines",
                            line=dict(color="#c3c2b7", dash="dot"),
                            showlegend=False, hoverinfo="skip")
        fig.update_yaxes(title=f"acceptable rate ({conds[0]} run)",
                         tickformat=".0%")
        fig.update_xaxes(title="orders in profile")
        add(style_fig(fig, 380), "Does more history help?",
            "Per-student acceptable rate vs profile length.")

    # 8 — arm + contamination
    co = df.dropna(subset=["contamination"]).drop_duplicates(
        ["student", "condition"])
    if len(co):
        co = co.assign(arm_lbl=co["arm"].map(arm_name))
        fig = px.box(co, x="arm_lbl", y="contamination",
                     color="condition" if ablation else None,
                     color_discrete_map=C_COND, points="all",
                     category_orders={"arm_lbl":
                                      list(ARM_LBL.values())})
        fig.update_yaxes(title="contamination index")
        fig.update_xaxes(title="")
        add(style_fig(fig, 380), "Contamination index by run",
            "Share of each run's candidate set (CAND lines) the human "
            "had viewed; legacy packs carry the older pick-based index. "
            "Read against the cross-student permutation baseline in the "
            "stats table — shopping the same category overlaps naturally "
            "even with zero contamination.")

    # ---- statistics (cluster-robust: students are the sampling units;
    #      seeded bootstrap so the report is reproducible) ----
    srows = []
    pair_cov = []   # per-contrast pair counts + missingness (Data quality)

    def srow(label, result, p=None, hyp=None):
        """hyp marks a member of the pre-registered confirmatory family
        {H1, H2, H3} (research_protocol §1) — the ONLY rows Holm adjusts;
        everything else is exploratory and unadjusted."""
        srows.append({"label": label, "result": result, "p": p,
                      "hyp": hyp})

    vd_ = vd.dropna(subset=["acceptable"]).copy()
    vd_["acceptable"] = vd_["acceptable"].astype(float)
    est, (blo, bhi) = rate_ci(vd_)
    k_all, n_all = int(vd_["acceptable"].sum()), len(vd_)
    wlo, whi = wilson(k_all, n_all)
    srow("Acceptable-pick rate, overall",
         f"{pct(est)} ({k_all}/{n_all}); cluster-bootstrap 95% CI "
         f"{fmt_ci(blo, bhi)} (naive Wilson {fmt_ci(wlo, whi)} — "
         "tasks cluster within students, trust the bootstrap)")
    for c in conds:
        e, (l2, h2) = rate_ci(vd_[vd_["condition"] == c])
        srow(f"Acceptable rate — {c} run",
             f"{pct(e)}; cluster-bootstrap 95% CI {fmt_ci(l2, h2)}")

    w, nw = Counter(), 0
    if ablation and {"persona", "ablated"} <= set(conds):
        # restrict to the two paired conditions BEFORE pivoting — in a
        # mixed cohort a 'single' column would empty every dropna().
        # The tier column joins the index so the 2x2's two runs per
        # grounding pair up within tier (constant per student in legacy
        # 2-run packs, so those are unaffected).
        pair = vd_[vd_["condition"].isin(["persona", "ablated"])]
        piv_all = pair.pivot_table(index=["student", "task", "tier"],
                                   columns="condition",
                                   values="acceptable", aggfunc="first")
        piv = piv_all.dropna()
        pair_cov.append(
            f"H1 grounding: {len(piv)}/{len(piv_all)} task-cell pairs "
            "complete (a pair drops when either run's verdict is missing)")
        by_s = (piv.reset_index().groupby("student")
                [["persona", "ablated"]].mean())
        darr = (by_s["persona"] - by_s["ablated"]).to_numpy(float)
        dlo, dhi = cboot(lambda ix: darr[ix].mean(), len(darr))
        b = int(((piv["persona"] == 1) & (piv["ablated"] == 0)).sum())
        c_ = int(((piv["persona"] == 0) & (piv["ablated"] == 1)).sum())
        srow("H1 — Questionnaire effect: persona − ablated "
             "acceptable-pick rate (paired within student)",
             f"Δ = {100 * darr.mean():+.1f} pp; 95% CI {fmt_ci(dlo, dhi)}; "
             f"{len(piv)} task-cell pairs from {len(by_s)} students; "
             f"discordant tasks {b} vs {c_} (descriptive); Cohen's h = "
             f"{cohens_h(float(piv['persona'].mean()), float(piv['ablated'].mean())):.2f}",
             p=cboot_p(darr), hyp="H1")
        if len(darr) > 1:
            sd_d = float(np.std(darr, ddof=1))
            if sd_d > 0:
                srow("Minimum detectable questionnaire effect "
                     "(80% power, α=.05, paired design)",
                     f"≈ {100 * 2.80 * sd_d / math.sqrt(len(darr)):.0f} pp "
                     f"with {len(darr)} students contributing pairs "
                     "(2.80 x sd of the per-student Δ / √n) — report "
                     "MDE, never post-hoc power")
        hh = df.dropna(subset=["hth_winner"]).drop_duplicates(
            ["student", "task", "tier"] if four_run
            else ["student", "task"])
        w = Counter(hh["hth_winner"])
        nw = w["persona"] + w["ablated"]
        if nw:
            hw = hh[hh["hth_winner"] != "tie"].assign(
                win=lambda d: (d["hth_winner"] == "persona").astype(float))
            ka, na, _ = kn_by_student(hw, "win")
            hlo, hhi = cboot(lambda ix: ka[ix].sum() / na[ix].sum()
                             if na[ix].sum() else np.nan, len(na))
            srow("Head-to-head: persona win share (excl. ties" +
                 ("; pooled over tiers)" if four_run else ")"),
                 f"{pct(ka.sum() / na.sum())} ({w['persona']} vs "
                 f"{w['ablated']}, ties {w['tie']}); cluster-bootstrap "
                 f"95% CI {fmt_ci(hlo, hhi)}",
                 p=cboot_p(ka / na - 0.5))
        if len(ov):
            srow("Pick overlap (same ASIN in a contrast's two runs)",
                 f"{pct(float(ov['same'].mean()))} of task-contrasts — "
                 "the share of decisions the varied factor did not change"
                 if four_run else
                 f"{pct(float(ov['same'].mean()))} of tasks — the share "
                 "of decisions the questionnaire did not change")
        spiv = (df[df["condition"].isin(["persona", "ablated"])]
                .pivot_table(index=["student", "task", "tier"],
                             columns="condition", values="sponsored",
                             aggfunc="first").dropna())
        if len(spiv) and {"persona", "ablated"} <= set(spiv.columns):
            sb = int(((spiv["persona"] == 1) &
                      (spiv["ablated"] == 0)).sum())
            sc = int(((spiv["persona"] == 0) &
                      (spiv["ablated"] == 1)).sum())
            s_by = (spiv.reset_index().groupby("student")
                    [["persona", "ablated"]].mean())
            sarr = (s_by["persona"].astype(float) -
                    s_by["ablated"].astype(float)).to_numpy(float)
            srow("Sponsored capture: persona vs ablated (paired)",
                 f"{pct(float(spiv['persona'].mean()))} vs "
                 f"{pct(float(spiv['ablated'].mean()))}; discordant "
                 f"{sb} vs {sc} (descriptive)",
                 p=cboot_p(sarr))
        pf = df[df["condition"].isin(["persona", "ablated"])].dropna(
            subset=["agent_price", "human_price"])
        pf = pf[(pf["agent_price"] > 0) & (pf["human_price"] > 0)].copy()
        if len(pf):
            pf["gap"] = (np.log(pf["agent_price"]) -
                         np.log(pf["human_price"])).abs()
            gpiv = pf.pivot_table(index=["student", "task", "tier"],
                                  columns="condition", values="gap",
                                  aggfunc="first").dropna()
            if len(gpiv) and {"persona", "ablated"} <= set(gpiv.columns):
                gs = (gpiv.reset_index().groupby("student")
                      [["persona", "ablated"]].mean())
                garr = (gs["persona"] - gs["ablated"]).to_numpy(float)
                glo, ghi = cboot(lambda ix: garr[ix].mean(), len(garr))
                pw = (sps.wilcoxon(gs["persona"], gs["ablated"]).pvalue
                      if sps and len(gs) > 5 and
                      np.abs(garr).sum() > 0 else None)
                srow("Price fidelity: |log(agent/human price)|, "
                     "persona − ablated (paired)",
                     f"Δ = {garr.mean():+.3f} (negative = questionnaire "
                     "brings prices closer to the human's); 95% CI "
                     f"[{glo:+.3f}, {ghi:+.3f}]. Human prices are "
                     "Wednesday's, agent prices Thursday's/Friday's — "
                     "drift adds noise common to both conditions", p=pw)
        if four_run:
            # within-day run order: which condition ran first that day
            # comes from the per-day counterbalanced grounding order
            po1 = sdf.set_index("student")["persona_order"]
            po2 = sdf.set_index("student")["persona_order_day2"]
            vr = vd_[vd_["condition"].isin(["persona", "ablated"])].copy()
            # the run's lab DAY picks the day's grounding order (tier no
            # longer identifies the day — tier order is counterbalanced)
            vr["porder"] = np.where(vr["day"] == 2,
                                    vr["student"].map(po2),
                                    vr["student"].map(po1))
            vr = vr.dropna(subset=["porder"])
            first = np.where(vr["porder"] == "P_FIRST", "persona",
                             "ablated")
            vr["pos"] = np.where(vr["condition"] == first,
                                 "first_of_day", "second_of_day")
            rpiv = vr.pivot_table(index="student", columns="pos",
                                  values="acceptable",
                                  aggfunc="mean").dropna()
            if len(rpiv) and {"first_of_day",
                              "second_of_day"} <= set(rpiv.columns):
                rarr = (rpiv["second_of_day"] -
                        rpiv["first_of_day"]).to_numpy(float)
                rlo, rhi = cboot(lambda ix: rarr[ix].mean(), len(rarr))
                r90lo, r90hi = cboot(lambda ix: rarr[ix].mean(),
                                     len(rarr), ci=90)
                req = ("EQUIVALENT within ±10 pp"
                       if -0.10 < r90lo and r90hi < 0.10
                       else "equivalence NOT established")
                srow("Within-day run-order effect (2nd − 1st run of the "
                     "day, acceptable rate)",
                     f"Δ = {100 * rarr.mean():+.1f} pp; 95% CI "
                     f"{fmt_ci(rlo, rhi)} — estimable because the "
                     "grounding order is counterbalanced within each day")
                srow("Run-order equivalence (TOST via 90% CI, "
                     "pre-registered ±10 pp margin)",
                     f"90% CI {fmt_ci(r90lo, r90hi)} → {req}")
        elif sdf["persona_order"].notna().any():
            po = sdf.set_index("student")["persona_order"]
            vr = vd_[vd_["condition"].isin(["persona", "ablated"])].copy()
            vr["porder"] = vr["student"].map(po)
            vr = vr.dropna(subset=["porder"])
            vr["run"] = np.where(
                ((vr["porder"] == "P_FIRST") &
                 (vr["condition"] == "persona")) |
                ((vr["porder"] == "NP_FIRST") &
                 (vr["condition"] == "ablated")), "run1", "run2")
            rpiv = vr.pivot_table(index="student", columns="run",
                                  values="acceptable",
                                  aggfunc="mean").dropna()
            if len(rpiv) and {"run1", "run2"} <= set(rpiv.columns):
                rarr = (rpiv["run2"] - rpiv["run1"]).to_numpy(float)
                rlo, rhi = cboot(lambda ix: rarr[ix].mean(), len(rarr))
                srow("Run-order effect (run 2 − run 1, acceptable rate)",
                     f"Δ = {100 * rarr.mean():+.1f} pp; 95% CI "
                     f"{fmt_ci(rlo, rhi)} — net cross-run carry-over/"
                     "learning, estimable because the condition order is "
                     "counterbalanced")

    # ---- the tier factor (four-run 2x2): frontier − economy, paired ----
    if four_run and {"economy", "frontier"} <= set(vd_["tier"].dropna()):
        tp = vd_[vd_["condition"].isin(["persona", "ablated"])]

        def tier_contrast(sub, label, hyp=None):
            piv_all_ = sub.pivot_table(
                index=["student", "task", "condition"],
                columns="tier", values="acceptable", aggfunc="first")
            piv = piv_all_.dropna()
            if not len(piv) or not {"economy",
                                    "frontier"} <= set(piv.columns):
                return
            if hyp:
                pair_cov.append(
                    f"H2 tier: {len(piv)}/{len(piv_all_)} task-cell pairs "
                    "complete (if economy runs fail more often, the tier "
                    "contrast gains a selection gradient — check this "
                    "split)")
            by_s = (piv.reset_index().groupby("student")
                    [["frontier", "economy"]].mean())
            darr = (by_s["frontier"] - by_s["economy"]).to_numpy(float)
            dlo, dhi = cboot(lambda ix: darr[ix].mean(), len(darr))
            b = int(((piv["frontier"] == 1) & (piv["economy"] == 0)).sum())
            c_ = int(((piv["frontier"] == 0) & (piv["economy"] == 1)).sum())
            srow((f"H2 — Tier effect (day-counterbalanced across "
                  f"students){label}" if hyp else
                  f"Tier effect{label}") + ": frontier "
                 "− economy acceptable-pick rate (paired within student)",
                 f"Δ = {100 * darr.mean():+.1f} pp; 95% CI "
                 f"{fmt_ci(dlo, dhi)}; {len(piv)} task-cell pairs from "
                 f"{len(by_s)} students; discordant tasks {b} vs {c_} "
                 "(descriptive); Cohen's h = "
                 f"{cohens_h(float(piv['frontier'].mean()), float(piv['economy'].mean())):.2f}",
                 p=cboot_p(darr), hyp=hyp)

        tier_contrast(tp, "", hyp="H2")
        # paired MDE for the tier contrast (same construction as the
        # questionnaire MDE above)
        tpiv_all = tp.pivot_table(index=["student", "task", "condition"],
                                  columns="tier", values="acceptable",
                                  aggfunc="first").dropna()
        if len(tpiv_all) and {"economy",
                              "frontier"} <= set(tpiv_all.columns):
            t_by = (tpiv_all.reset_index().groupby("student")
                    [["frontier", "economy"]].mean())
            t_arr = (t_by["frontier"] - t_by["economy"]).to_numpy(float)
            if len(t_arr) > 1:
                sd_t = float(np.std(t_arr, ddof=1))
                if sd_t > 0:
                    srow("Minimum detectable tier effect "
                         "(80% power, α=.05, paired design)",
                         f"≈ {100 * 2.80 * sd_t / math.sqrt(len(t_arr)):.0f}"
                         f" pp with {len(t_arr)} students contributing "
                         "pairs (2.80 x sd of the per-student Δ / √n) — "
                         "report MDE, never post-hoc power")
        for g in ("persona", "ablated"):
            tier_contrast(tp[tp["condition"] == g], f" — {g} runs")
        # grounding x tier interaction: (P−A under frontier) − (P−A
        # under economy), per student
        cellpiv = tp.pivot_table(index="student",
                                 columns=["condition", "tier"],
                                 values="acceptable", aggfunc="mean")
        cols = [("persona", "frontier"), ("ablated", "frontier"),
                ("persona", "economy"), ("ablated", "economy")]
        if all(c in cellpiv.columns for c in cols):
            cp = cellpiv[cols].dropna()
            iarr = ((cp[("persona", "frontier")] -
                     cp[("ablated", "frontier")]) -
                    (cp[("persona", "economy")] -
                     cp[("ablated", "economy")])).to_numpy(float)
            if len(iarr):
                ilo, ihi = cboot(lambda ix: iarr[ix].mean(), len(iarr))
                pair_cov.append(
                    f"H3 interaction: {len(cp)}/{len(cellpiv)} students "
                    "with all four cells")
                srow("H3 — Grounding x tier interaction (questionnaire "
                     "effect under frontier − under economy)",
                     f"Δ = {100 * iarr.mean():+.1f} pp; 95% CI "
                     f"{fmt_ci(ilo, ihi)}; {len(cp)} students with all "
                     "four cells — positive = the questionnaire helps "
                     "MORE with the stronger model",
                     p=cboot_p(iarr), hyp="H3")
        # tier head-to-heads (which model's pick won, per grounding)
        hm = df.dropna(subset=["hth_model_winner"]).drop_duplicates(
            ["student", "task", "condition"])
        wm = Counter(hm["hth_model_winner"])
        nm = wm["frontier"] + wm["economy"]
        if nm:
            hwm = hm[hm["hth_model_winner"] != "same"].assign(
                win=lambda d: (d["hth_model_winner"] ==
                               "frontier").astype(float))
            km, nmc, _ = kn_by_student(hwm, "win")
            mlo, mhi = cboot(lambda ix: km[ix].sum() / nmc[ix].sum()
                             if nmc[ix].sum() else np.nan, len(nmc))
            srow("Head-to-head: frontier win share (excl. 'same'; "
                 "pooled over groundings)",
                 f"{pct(km.sum() / nmc.sum())} ({wm['frontier']} vs "
                 f"{wm['economy']}, same {wm['same']}); "
                 f"cluster-bootstrap 95% CI {fmt_ci(mlo, mhi)}",
                 p=cboot_p(km / nmc - 0.5))
        # exploratory day effect — estimable as its own contrast because
        # the tier order is counterbalanced across days per student
        if "day" in vd_.columns and vd_["day"].notna().any():
            vday = vd_[vd_["condition"].isin(["persona", "ablated"])]
            daypiv = vday.pivot_table(index="student", columns="day",
                                      values="acceptable",
                                      aggfunc="mean").dropna()
            if {1, 2} <= set(daypiv.columns):
                day_arr = (daypiv[2] - daypiv[1]).to_numpy(float)
                if len(day_arr):
                    dylo, dyhi = cboot(lambda ix: day_arr[ix].mean(),
                                       len(day_arr))
                    srow("Exploratory day effect (day 2 − day 1 "
                         "acceptable rate, paired within student)",
                         f"Δ = {100 * day_arr.mean():+.1f} pp; 95% CI "
                         f"{fmt_ci(dylo, dyhi)}; {len(day_arr)} students "
                         "— identified separately from tier because the "
                         "tier order is counterbalanced across days",
                         p=cboot_p(day_arr))
        srow("Verdict occasion",
             "all verdicts for all four runs are captured in ONE blind "
             "Friday session by design (single-session capture), so no "
             "cell carries a judgment-occasion difference; verdicts.csv "
             "records verdict_at_utc per row, so the occasion is "
             "auditable")

    arms = sorted(a for a in set(vd_["arm"].dropna()) if a != "UNKNOWN")
    if len(arms) == 2:
        k1, n1, _ = kn_by_student(vd_[vd_["arm"] == arms[0]])
        k2, n2, _ = kn_by_student(vd_[vd_["arm"] == arms[1]])
        if n1.sum() and n2.sum():
            p1, p2 = k1.sum() / n1.sum(), k2.sum() / n2.sum()
            rng = np.random.default_rng(BOOT_SEED)
            diffs = []
            for _ in range(BOOT_N):
                i1 = rng.integers(0, len(n1), len(n1))
                i2 = rng.integers(0, len(n2), len(n2))
                if n1[i1].sum() and n2[i2].sum():
                    diffs.append(k1[i1].sum() / n1[i1].sum() -
                                 k2[i2].sum() / n2[i2].sum())
            alo, ahi = np.percentile(diffs, [2.5, 97.5])
            a90 = np.percentile(diffs, [5, 95])
            # the arm factor is retired (all 2x2 packs are human-first);
            # this branch only fires when legacy packs are ingested
            srow(f"Arm effect ({arm_name(arms[0])} − "
                 f"{arm_name(arms[1])}, acceptable rate) — legacy arm "
                 "design",
                 f"Δ = {100 * (p1 - p2):+.1f} pp; cluster-bootstrap 95% CI "
                 f"[{100 * alo:+.0f}, {100 * ahi:+.0f}] pp; Cohen's h = "
                 f"{cohens_h(p1, p2):.2f} (between-student p, clustering "
                 "ignored — legacy descriptives only)",
                 p=two_prop_p(int(k1.sum()), int(n1.sum()),
                              int(k2.sum()), int(n2.sum())))
            eq = ("EQUIVALENT within ±10 pp"
                  if -0.10 < a90[0] and a90[1] < 0.10
                  else "equivalence NOT established")
            srow("Arm-order equivalence (TOST via 90% CI, ±10 pp margin) "
                 "— legacy arm design",
                 f"90% CI [{100 * a90[0]:+.0f}, {100 * a90[1]:+.0f}] pp → "
                 f"{eq}")
            sacc = (vd_.groupby("student")
                    .agg(r=("acceptable", "mean"), arm=("arm", "first")))
            sd = float(sacc["r"].std())
            nmin = int(min((sacc["arm"] == arms[0]).sum(),
                           (sacc["arm"] == arms[1]).sum()))
            if nmin > 1 and not math.isnan(sd):
                srow("Minimum detectable arm effect (80% power, α=.05, "
                     "student-level) — legacy arm design",
                     f"≈ {100 * 2.80 * sd * math.sqrt(2 / nmin):.0f} pp "
                     f"with {nmin} students in the smaller arm — report "
                     "MDE, never post-hoc power")

    tiers = sorted(set(vd_["tier"].dropna()))
    if len(tiers) == 2 and not four_run:
        # legacy between-student tier factor (the 2x2 reports the paired
        # within-student contrast above instead)
        e1, _ = rate_ci(vd_[vd_["tier"] == tiers[0]])
        e2, _ = rate_ci(vd_[vd_["tier"] == tiers[1]])
        srow(f"Model tier ({tiers[0]} vs {tiers[1]}, acceptable rate)",
             f"{pct(e1)} vs {pct(e2)} (descriptive — check the cell sizes "
             "under Data quality before formal testing)")

    if len(rat):
        d_r = df.dropna(subset=["rating_self", "rating_agent"])
        rg = (d_r.assign(delta=d_r["rating_agent"] - d_r["rating_self"])
              .groupby("student")["delta"].mean())
        rarr2 = rg.to_numpy(float)
        r_lo, r_hi = cboot(lambda ix: rarr2[ix].mean(), len(rarr2))
        pw = (sps.wilcoxon(rg).pvalue if sps and len(rg) > 5 and
              np.abs(rarr2).sum() > 0 else None)
        # the OWN-pick rating is one judgment per task (the same
        # Wednesday pick), so its mean deduplicates to one row per
        # (student, task) — pooling all runs would quadruple-count it
        own_mean = (d_r.drop_duplicates(["student", "task"])
                    ["rating_self"].mean())
        srow("Satisfaction: agent − own rating",
             f"mean Δ = {rarr2.mean():+.2f} points (agent "
             f"{d_r['rating_agent'].mean():.1f} vs own "
             f"{own_mean:.1f}, own deduplicated per task); "
             "cluster-bootstrap 95% CI "
             f"[{r_lo:+.2f}, {r_hi:+.2f}]", p=pw)
        if len(val) >= 6 and sps:
            vmap = {"inferior": 0, "equivalent": 1, "identical": 1,
                    "better": 2}
            vv = val.assign(vnum=val["verdict"].map(vmap))
            rho = float(sps.spearmanr(vv["vnum"],
                                      vv["rating_delta"])[0])
            # the ~4 x tasks rows per student are correlated: report rho
            # with a cluster-bootstrap CI (resample students), no naive p
            studs = vv["student"].unique()
            by_stud = {s: g for s, g in vv.groupby("student")}

            def rho_of(ix):
                d = pd.concat([by_stud[studs[k]] for k in ix])
                if d["vnum"].nunique() < 2 or \
                        d["rating_delta"].nunique() < 2:
                    return float("nan")
                return float(sps.spearmanr(d["vnum"],
                                           d["rating_delta"])[0])

            rho_lo, rho_hi = cboot(rho_of, len(studs), n_boot=1000)
            srow("Convergent validity: verdict rank vs rating delta",
                 f"Spearman ρ = {rho:.2f} (inferior=0, equivalent="
                 "identical=1, better=2); cluster-bootstrap 95% CI "
                 f"[{rho_lo:.2f}, {rho_hi:.2f}] — no naive p (rows "
                 "cluster within students)")

    # deliberation time: does the frontier model take longer, and how do
    # agents compare to the human session?
    da = dd[dd["condition"].isin(["persona", "ablated"])]
    if four_run and len(da):
        dpiv = da.pivot_table(index=["student", "condition"],
                              columns="tier", values="run_duration_min",
                              aggfunc="mean")
        if {"economy", "frontier"} <= set(dpiv.columns):
            dp = dpiv.dropna()
            if len(dp):
                by_s = (dp.reset_index().groupby("student")
                        [["frontier", "economy"]].mean())
                tarr = (by_s["frontier"] -
                        by_s["economy"]).to_numpy(float)
                tlo, thi = cboot(lambda ix: tarr[ix].mean(), len(tarr))
                pw = (sps.wilcoxon(by_s["frontier"],
                                   by_s["economy"]).pvalue
                      if sps and len(by_s) > 5
                      and np.abs(tarr).sum() > 0 else None)
                srow("Deliberation time: frontier − economy run "
                     "duration (paired within student)",
                     f"Δ = {tarr.mean():+.1f} min; 95% CI "
                     f"[{tlo:+.1f}, {thi:+.1f}] — does the stronger "
                     "model shop longer?", p=pw)
    if len(dd):
        hdur = dd[dd["condition"] == "human"]["run_duration_min"]
        adur = da["run_duration_min"]
        if len(hdur) and len(adur):
            srow("Time on the task set: human session vs one agent run",
                 f"human mean {hdur.mean():.0f} min vs agent run mean "
                 f"{adur.mean():.0f} min (both cover the full task set "
                 "once; descriptive)")

    # task-position effect: the shopping order is randomized across
    # students (fixed within student), so position effects are estimable
    if vd_["task_position"].notna().any() and len(TASK_IDS) >= 2:
        vp = vd_.dropna(subset=["task_position"]).copy()
        mid = (len(TASK_IDS) + 1) / 2
        vp["late"] = vp["task_position"] > mid
        ppiv = vp.pivot_table(index="student", columns="late",
                              values="acceptable", aggfunc="mean")
        if {True, False} <= set(ppiv.columns):
            parr = (ppiv[True] - ppiv[False]).dropna().to_numpy(float)
            if len(parr):
                plo, phi = cboot(lambda ix: parr[ix].mean(), len(parr))
                p90lo, p90hi = cboot(lambda ix: parr[ix].mean(),
                                     len(parr), ci=90)
                peq = ("EQUIVALENT within ±10 pp"
                       if -0.10 < p90lo and p90hi < 0.10
                       else "equivalence NOT established")
                srow("Task-position effect (late − early positions, "
                     "acceptable rate)",
                     f"Δ = {100 * parr.mean():+.1f} pp; 95% CI "
                     f"{fmt_ci(plo, phi)} — task order is randomized "
                     "across students and held constant within student "
                     "(human session + all runs), so what an agent "
                     "chooses early cannot systematically bias a "
                     "particular category")
                srow("Task-position equivalence (TOST via 90% CI, "
                     "pre-registered ±10 pp margin)",
                     f"90% CI {fmt_ci(p90lo, p90hi)} → {peq}")

    # contamination: observed candidate-viewed overlap against a
    # cross-student permutation baseline. Everyone shops the same five
    # categories, so candidate/viewed overlap is high under ZERO
    # contamination (same first page of the same category); the EXCESS
    # of own-student over other-student overlap is the signal.
    cw = [(m_["student"],
           {t: set(a) for t, a in (m_.get("cand_by_task") or {}).items()
            if a},
           set(m_.get("viewed_asins") or [])) for m_ in metas]
    cw = [(s, c, v) for s, c, v in cw if c and v]
    if len(cw) >= 2:
        def ov_share(cbt, viewed):
            shares = [len(a & viewed) / len(a) for a in cbt.values()]
            return float(np.mean(shares)) if shares else float("nan")
        obs = [ov_share(c, v) for _, c, v in cw]
        base = []
        for i, (_, c, _) in enumerate(cw):
            vals = [ov_share(c, cw[j][2]) for j in range(len(cw))
                    if j != i]
            vals = [x for x in vals if not math.isnan(x)]
            if vals:
                base.append(float(np.mean(vals)))
        obs_m = float(np.nanmean(obs))
        base_m = float(np.mean(base)) if base else float("nan")
        srow("Contamination: candidate-viewed overlap vs cross-student "
             "permutation baseline",
             f"observed {pct(obs_m)} of a run's candidates were "
             f"human-viewed by the SAME student vs {pct(base_m)} against "
             "OTHER students' viewed sets (same tasks) → excess "
             f"{100 * (obs_m - base_m):+.1f} pp. Descriptive, and a "
             "robustness subgroup below — never a regression covariate")

    # consideration-set overlap (needs CAND lines + humanlog v1.1)
    jd = [(m_["student"], j) for m_ in metas
          for j in (m_.get("jaccard") or {}).values()]
    if jd:
        js = (pd.DataFrame(jd, columns=["student", "j"])
              .groupby("student")["j"].mean().to_numpy(float))
        jlo, jhi = cboot(lambda ix: js[ix].mean(), len(js))
        srow("Process comparison: agent-candidate vs human-viewed "
             "overlap (Jaccard)",
             f"per-student mean {js.mean():.2f}; cluster-bootstrap 95% CI "
             f"[{jlo:.2f}, {jhi:.2f}] — 0 = fully disjoint search "
             "processes, 1 = identical consideration sets")

    # category class (utilitarian vs hedonic), paired within student
    if {"utilitarian", "hedonic"} <= set(df["category_class"]):
        cls_piv = (vd_.groupby(["student", "category_class"])["acceptable"]
                   .mean().unstack())
        if {"utilitarian", "hedonic"} <= set(cls_piv.columns):
            cp = cls_piv.dropna(subset=["utilitarian", "hedonic"])
            carr = (cp["utilitarian"] - cp["hedonic"]).to_numpy(float)
            if len(carr):
                clo, chi_ = cboot(lambda ix: carr[ix].mean(), len(carr))
                srow("Category class: utilitarian − hedonic acceptable "
                     "rate (paired within student)",
                     f"Δ = {100 * carr.mean():+.1f} pp; 95% CI "
                     f"{fmt_ci(clo, chi_)} — positive = twins do better "
                     "on utilitarian goods")

    # Holm-Bonferroni over EXACTLY the pre-registered confirmatory family
    # {H1, H2, H3} (research_protocol §1: grounding, tier(+day),
    # grounding x tier, all on the acceptable-pick rate). Everything else
    # is exploratory and reported unadjusted — mixing descriptive and
    # dead-design rows into one family distorts both.
    conf_idx = [i for i, r in enumerate(srows) if r["hyp"]]
    conf_adj = holm([srows[i]["p"] for i in conf_idx])
    adj_map = dict(zip(conf_idx, conf_adj))
    stats_rows = []
    for i, r in enumerate(srows):
        if r["p"] is None or math.isnan(r["p"]):
            pcell = "—"
        elif r["hyp"]:
            pcell = (f"{r['p']:.3f} (Holm {adj_map[i]:.3f} over "
                     f"H1–H3; {r['hyp']})")
        else:
            pcell = f"{r['p']:.3f} (exploratory, unadjusted)"
        stats_rows.append((r["label"], r["result"], pcell))

    # ---- robustness / sensitivity specifications ----
    def rate_of(sub):
        s = sub.dropna(subset=["acceptable"])
        return float(s["acceptable"].mean()) if len(s) else float("nan")

    def spec_rates(sub):
        return [pct(rate_of(sub[sub["condition"] == c])) for c in conds]

    clean = set(sdf[sdf["n_issues"] == 0]["student"])
    thick = set(sdf[sdf["n_profile_orders"] >= 3]["student"])
    strict = vd_.assign(
        acceptable=vd_["verdict"].isin(["better", "identical"]))
    fid = vd_.assign(
        acceptable=vd_["verdict"].isin(["identical", "equivalent"]))
    robust_rows = [
        ("Main: acceptable-pick rate = better/identical/equivalent "
         "(the quality metric)", spec_rates(vd_)),
        (f"Excl. packs with validation issues (n={len(clean)})",
         spec_rates(vd_[vd_["student"].isin(clean)])),
        (f"Excl. thin purchase profiles <3 parsed orders (n={len(thick)})",
         spec_rates(vd_[vd_["student"].isin(thick)])),
        ("Strict: acceptable = better/identical only",
         spec_rates(strict)),
        ("Agreement/fidelity rate = identical/equivalent (did the twin "
         "converge on or substitute the human's choice)",
         spec_rates(fid)),
    ]
    # the contamination robustness subgroup: the grounding/tier story
    # must survive dropping the runs most exposed to human carry-over
    contam_vals = vd_["contamination"].dropna()
    if len(contam_vals) and contam_vals.nunique() > 1:
        q75 = float(contam_vals.quantile(0.75))
        lowc = vd_[vd_["contamination"].isna() |
                   (vd_["contamination"] <= q75)]
        robust_rows.append(
            (f"Excl. top-quartile contamination runs (index > {q75:.2f})",
             spec_rates(lowc)))
    if quarantine:
        # quarantined packs appear ONLY here — never in confirmatory or
        # headline outputs
        robust_rows.append(
            (f"Including the {len(quarantine)} quarantined "
             "submission(s) — sensitivity appendix only",
             spec_rates(df_all.dropna(subset=["verdict"]))))

    # ---- data quality ----
    quality = [
        ("Submissions (exact counts, audit 4.7)",
         f"{n_parsed} parsed of {len(paths)} zips; {len(sdf)} "
         f"confirmatory; {len(quarantine) + len(dup_notes)} quarantined "
         "(reasons in the Quarantined submissions table)"),
        ("Task-level records (confirmatory set)", str(len(df))),
        ("Task set (from config_snapshot/tasks_config.csv)",
         f"{len(TASK_IDS)} tasks: " + ", ".join(
             f"{TASK_NAMES[t]} [{TASK_CLASS[t]}]" for t in TASK_IDS)),
        ("Students with machine-parsed CAND candidate lines",
         pct(float((df.groupby("student")["n_candidates"].sum()
                    > 0).mean()))),
        ("Mean human product views / searches per student",
         f"{sdf['product_views'].dropna().mean():.1f} / "
         f"{sdf['searches'].dropna().mean():.1f}"),
        ("Purchase profiles in parseable compact format",
         pct(float(sdf["profile_parsed"].mean()))),
        ("Students with validation issues at pack time",
         str(int((sdf["n_issues"] > 0).sum()))),
        ("Model tiers", ", ".join(f"{k}: {v}" for k, v in
                                  Counter(sdf["tier"].dropna()).items())),
        ("Session-order arms (counterbalanced)",
         ", ".join(f"{arm_name(k)}: {v}" for k, v in
                   Counter(sdf["arm"].dropna()).items())),
    ]
    if pair_cov:
        quality.append(("Paired-contrast coverage (missingness — "
                        "dropped pairs are runs whose verdict is "
                        "missing/invalid)", "; ".join(pair_cov)))
    so = sdf["stockout_suspect_n"].dropna()
    if len(so):
        quality.append((
            "Likely stock-outs (human pick in NO run's candidate set)",
            f"{int(so.sum())} task(s) across {int((so > 0).sum())} "
            "student(s) — 'identical' was impossible there (human picks "
            "are frozen Wednesday; listings move)"))
    quality.append((
        "Checkout attempts (network-blocked by the guard extension)",
        f"{int(sdf['n_checkout_urls'].sum())} checkout-shaped URL(s) in "
        f"logs across {int((sdf['n_checkout_urls'] > 0).sum())} "
        f"student(s); guard-fired sightings: "
        f"{int(sdf['n_guard_fired'].sum())} — a nonzero count is itself "
        "a finding about agent behavior; review the flagged packs"))
    if ablation:
        quality.append((
            "Grounding order day 1 (counterbalanced)" if four_run
            else "Ablation run order (counterbalanced)",
            ", ".join(f"{order_name(k)}: {v}" for k, v in
                      Counter(sdf["persona_order"].dropna()).items())))
    if four_run and sdf["persona_order_day2"].notna().any():
        quality.append((
            "Grounding order day 2 (independently re-randomized)",
            ", ".join(f"{order_name(k)}: {v}" for k, v in
                      Counter(sdf["persona_order_day2"].dropna()).items())))
    if four_run and sdf["tier_day1"].notna().any():
        quality.append((
            "Tier order across days (counterbalanced across students; "
            "per-section balance is validated at sheet generation)",
            ", ".join(f"{k}-first: {v}" for k, v in
                      Counter(sdf["tier_day1"].dropna()).items())))
    quality.append((
        "Sensitive-item opt-outs (agent persona excludes "
        "D04/D09/D10/D11/D12 at the student's request)",
        f"{int(sdf['sensitive_excluded'].sum())} of {len(sdf)} students"))
    quality.append((
        "Human interventions recorded by the partner at dtlab-cart",
        f"{int(sdf['n_captchas'].sum())} CAPTCHA(s) + "
        f"{int(sdf['n_interventions'].sum())} other intervention(s); "
        f"{int(sdf['has_intervention_log'].sum())} of {len(sdf)} "
        "students have intervention logs on file"))
    quality.append((
        "Verdict amendments applied (last-wins; originals untouched "
        "in the zips)",
        f"{int(sdf['n_amendments'].sum())} amendment(s) across "
        f"{int((sdf['n_amendments'] > 0).sum())} student(s)"))

    # ---- cards ----
    cards = [("Students", f"{len(sdf)}"),
             ("Acceptable picks", pct(k_all / n_all if n_all else None)),
             ("Identical picks", pct(float((vd["verdict"] ==
                                            "identical").mean())))]
    if ablation:
        cards += [("Persona wins head-to-head",
                   pct(w["persona"] / nw if nw else None))]
        if len(ov):
            cards += [("Run overlap", pct(float(ov["same"].mean())))]
    if len(rat):
        cards.append(("Mean agent rating",
                      f"{df['rating_agent'].dropna().mean():.1f}/10"))

    # ---- html ----
    def esc(s):
        return (str(s).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;"))

    logo = LOGO_URI
    logo_html = (
        f'<div style="float:right;text-align:center;margin:4px 0 12px 16px">'
        f'<img src="{logo}" alt="RingelAI" '
        'style="height:64px;display:block;margin:0 auto 4px">'
        '<a href="https://www.ringel.ai" style="color:#52514e;'
        'font-size:12px;text-decoration:none">ringel.AI</a></div>'
        if logo else "")
    parts = [f"""<!doctype html><meta charset="utf-8">
<title>{esc(args.title)}</title>
<style>
body{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
color:{INK};background:#f9f9f7;max-width:1100px;margin:2em auto;
padding:0 1em}}
h1{{font-size:26px}} h2{{font-size:19px;border-bottom:1px solid {GRID};
padding-bottom:6px;margin-top:2em}}
.cards{{display:flex;flex-wrap:wrap;gap:12px;margin:1em 0}}
.card{{background:#fcfcfb;border:1px solid {GRID};border-radius:8px;
padding:14px 20px;min-width:130px}}
.card .v{{font-size:26px;font-weight:650}} .card .k{{font-size:12px;
color:{INK2}}}
.note{{color:{INK2};font-size:13px;margin:4px 0 12px}}
table.st{{border-collapse:collapse;background:#fcfcfb;width:100%}}
table.st td{{border:1px solid {GRID};padding:8px 10px;font-size:14px;
vertical-align:top}} table.st td:first-child{{font-weight:600;width:38%}}
.fig{{background:#fcfcfb;border:1px solid {GRID};border-radius:8px;
padding:8px;margin:0 0 8px}}
</style>
{logo_html}{'<p style="background:#f8d7da;border:2px solid #c02a2a;'
            'padding:10px;font-weight:700">IDENTIFIED COPY — chart hovers '
            'carry student pseudonyms. Instructor diagnostics only; do '
            'not distribute.</p>' if args.identified else ''}
<h1>{esc(args.title)}</h1>
<p class="note">Generated by tools/analyze_cohort.py from
{n_parsed} parsed submission zips — {len(sdf)} in the confirmatory set,
{len(quarantine) + len(dup_notes)} quarantined (see the Quarantined
submissions table). Agent types in this cohort:
{esc(', '.join(conds))} — persona = grounded in questionnaire + purchase
profile; ablated = purchase profile only (no questionnaire){
'; single = the one persona-grounded run of the legacy non-ablation design'
if 'single' in conds else ''}. Task order is randomized across
students and held constant within student.{
' Model tier is the second within-student factor: every grounding ran '
'under both the economy and the frontier model, with the tier order '
'counterbalanced across the two lab days per student — the tier effect '
'is identified separately from the day.'
if four_run else
' "Human first" / "Agent first" is the counterbalanced session order.'}
Sandbox packs are excluded.</p>
<div class="cards">""" + "".join(
        f'<div class="card"><div class="v">{esc(v)}</div>'
        f'<div class="k">{esc(k)}</div></div>' for k, v in cards) +
        "</div>"]

    # chart QA hook: export every figure as PNG (needs kaleido installed)
    png_dir = __import__("os").environ.get("DTLAB_DEBUG_PNG")
    if png_dir:
        Path(png_dir).mkdir(parents=True, exist_ok=True)
        for i, (heading, _, fig) in enumerate(figs):
            fig.write_image(f"{png_dir}/{i:02d}_{re.sub(r'[^a-z0-9]+', '_', heading.lower())[:40]}.png",
                            width=1000, scale=1)

    first = True
    for heading, note, fig in figs:
        parts.append(f"<h2>{esc(heading)}</h2>")
        if note:
            parts.append(f'<p class="note">{esc(note)}</p>')
        parts.append('<div class="fig">' + fig.to_html(
            full_html=False, include_plotlyjs="inline" if first else False,
            config={"displaylogo": False}) + "</div>")
        first = False

    parts.append(
        "<h2>Statistics</h2>"
        f'<p class="note">All CIs marked cluster-bootstrap resample '
        f'STUDENTS (n_boot={BOOT_N}, seed={BOOT_SEED}, reproducible) '
        "because tasks — and in the ablation design all runs — are "
        "correlated within student. p-values are two-sided and computed "
        "at the CLUSTER level (bootstrap of per-student mean differences "
        "— pooled task-level counts appear only as descriptives)."
        "</p>"
        "<table class='st'><tr><td><b>Analysis</b></td>"
        "<td><b>Result</b></td><td><b>p (Holm)</b></td></tr>" + "".join(
            f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td></tr>"
            for a, b, c in stats_rows) + "</table>")
    parts.append(
        "<h2>Robustness (sensitivity of the headline rate to "
        "specification)</h2>"
        '<p class="note">The acceptable-pick rate recomputed under '
        "alternative inclusion rules and outcome definitions. Stable "
        "rates across rows = the result is not an artifact of one "
        "choice.</p>"
        "<table class='st'><tr><td><b>Specification</b></td>" +
        "".join(f"<td><b>{esc(c)} run</b></td>" for c in conds) +
        "</tr>" + "".join(
            "<tr><td>" + esc(name) + "</td>" +
            "".join(f"<td>{esc(v)}</td>" for v in vals) + "</tr>"
            for name, vals in robust_rows) + "</table>")
    parts.append("<h2>Data quality &amp; coverage</h2><table class='st'>" +
                 "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>"
                         for a, b in quality) + "</table>")
    # ---- quarantined submissions (audit 4.7): machine-readable reasons;
    # excluded from every confirmatory and headline output ----
    parts.append(
        "<h2>Quarantined submissions</h2>"
        '<p class="note">Excluded from all confirmatory and headline '
        "outputs; included only in the sensitivity appendix row of the "
        "Robustness table. Overrides go through decisions.csv "
        "(--decisions), applied last and echoed below."
        + ("" if args.identified else
           " Labels are anonymized in the class copy "
           "(--identified restores pseudonyms).") + "</p>")
    q_table = [(mask_sid(s), "; ".join(rs))
               for s, rs in sorted(quarantine.items())]
    q_table += [(mask_sid(s) + " (superseded zip)", note_)
                for s, note_ in dup_notes]
    if q_table:
        parts.append(
            "<table class='st'><tr><td><b>Submission</b></td>"
            "<td><b>Machine-readable reasons</b></td></tr>" + "".join(
                f"<tr><td>{esc(s)}</td><td>{esc(rs)}</td></tr>"
                for s, rs in q_table) + "</table>")
    else:
        parts.append('<p class="note">(none)</p>')
    if decisions:
        parts.append(
            "<h2>Cohort decisions (decisions.csv — the audit trail)</h2>"
            "<table class='st'><tr><td><b>Submission</b></td>"
            "<td><b>Action</b></td><td><b>Reason</b></td></tr>" + "".join(
                f"<tr><td>{esc(mask_sid((d.get('student_id') or '').strip()))}</td>"
                f"<td>{esc((d.get('action') or '').strip())}</td>"
                f"<td>{esc((d.get('reason') or '').strip())}</td></tr>"
                for d in decisions) + "</table>")
    # ---- version counts (audit 4.7 item 6) ----
    def vcount(series):
        return ", ".join(f"{k}: {v}" for k, v in
                         Counter(series.fillna("unknown")).items())
    parts.append(
        "<h2>Version counts</h2><table class='st'>" + "".join(
            f"<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for a, b in (
                ("kit_version", vcount(sdf_all["kit_version"])),
                ("schema generation", vcount(sdf_all["design"])),
                ("tasks_config sha256 (prefix)",
                 vcount(sdf_all["tasks_config_sha256"].str[:12])),
                ("dtlab_config sha256 (prefix)",
                 vcount(sdf_all["dtlab_config_sha256"].str[:12])),
            )) + "</table>")
    parts.append('<p class="note">Verdict semantics: better / identical '
                 '(ASIN-verified) / equivalent / inferior, always the '
                 'agent pick relative to the student\'s own pre-registered '
                 'pick. See research_protocol.md for schemas.</p>')
    parts.append(
        f'<p class="note" style="border-top:1px solid {GRID};'
        'padding-top:10px;margin-top:2em">Digital Twin Shopping Agent Lab '
        '— Daniel M. Ringel · <a href="https://www.ringel.ai" '
        'style="color:#2a78d6">ringel.AI</a></p>')

    out = Path(args.out)
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"Report -> {out.resolve()}  ({out.stat().st_size >> 10} KB, "
          f"{len(figs)} charts, {len(sdf)} students)")

    # ---- run-level research export (audit 2.6; research_protocol §6):
    # dtlab-runs-v1, one record per participant x task x run,
    # confirmatory set only, amendments already applied last-wins ----
    if args.export_runs or args.export_hth:
        gens = sorted(set(sdf["design"]))
        if len(gens) > 1 and not args.allow_mixed:
            sys.exit(f"mixed schema generations {gens} in the "
                     "confirmatory set — pass --allow-mixed to export "
                     "anyway")
    if args.export_runs:
        exp = df[df["condition"].isin(["persona", "ablated", "single"])
                 & df["run"].notna()].copy()
        mmap = sdf.set_index("student")

        def mcol(col):
            return exp["student"].map(mmap[col])

        runs_out = pd.DataFrame({
            "student_id": exp["student"],
            "run": exp["run"].str[3:].astype(int),
            "day": exp["day"],
            "run_order_in_day": exp["run_order_in_day"],
            "condition": exp["condition"],
            "tier": exp["tier"],
            "model_id": exp["model_id"],
            "provider": exp["provider"],
            "hermes_version": exp["hermes_version"],
            "verdict": exp["verdict"],
            "rating_self": exp["rating_self"],
            "rating_agent": exp["rating_agent"],
            "rationale": exp["rationale"],
            "verdict_at_utc": exp["verdict_at_utc"],
            "amended": exp["amended"],
            "agent_asin": exp["agent_asin"],
            "agent_price": exp["agent_price"],
            "human_asin": exp["human_asin"],
            "human_price": exp["human_price"],
            "sponsored": exp["sponsored"],
            "n_candidates": exp["n_candidates"],
            "n_searches": exp["n_searches"],
            "contamination_index": exp["contamination"],
            "task_id": exp["task"],
            "task_position": exp["task_position"],
            "category_class": exp["category_class"],
            "tasks_config_sha256": mcol("tasks_config_sha256"),
            "soul_sha256": exp["soul_sha256"],
            "config_sha256": exp["config_sha256"],
            "purchase_profile_sha256": mcol("purchase_profile_sha256"),
            "instrument_version": mcol("instrument_size"),
            "kit_version": mcol("kit_version"),
            "sensitive_items_excluded": mcol("sensitive_excluded"),
            "verdicts_captured_blind": mcol("verdicts_captured_blind"),
        })
        runs_out.to_csv(args.export_runs, index=False)
        print(f"Runs export (dtlab-runs-v1) -> {args.export_runs} "
              f"({len(runs_out)} records)")
    if args.export_hth:
        hth_out = [r for m in metas if m["student"] in conf_sids
                   for r in m.get("hth_rows", [])]
        with open(args.export_hth, "w", newline="",
                  encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "student", "task", "contrast", "winner",
                "resolved_from_blind"])
            w.writeheader()
            w.writerows(hth_out)
        print(f"Head-to-head export (dtlab-hth-v1) -> {args.export_hth} "
              f"({len(hth_out)} records)")


if __name__ == "__main__":
    main()
