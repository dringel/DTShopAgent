#!/usr/bin/env python3
"""
test_analyze_cohort.py — fabricate a small cohort of evidence zips (shaped
exactly like pack_evidence.py output: manifest.json + CSVs + profile) and
check that tools/analyze_cohort.py produces a complete report from them.

The synthetic cohort mixes all three manifest generations — four-run 2x2
(plan of record), legacy 2-run ablation, and single-run — plus one
sandbox pack (must be excluded) and one LMS-renamed zip (identity must
resolve from inside the zip, never the filename).

Skips (exit 0) when pandas/plotly are not installed — CI installs them.
Run from repo root:  python3 tests/test_analyze_cohort.py
"""

import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

try:
    import pandas  # noqa: F401
    import plotly  # noqa: F401
except ImportError:
    print("SKIP: pandas/plotly not installed (pip install pandas plotly)")
    sys.exit(0)

ASINS = [f"B0{i:08d}" for i in range(500)]
VERDS = ["better", "identical", "equivalent", "inferior"]
T5 = ("1", "2", "3", "4", "5")
# task budgets of the 5-category self-purchase set (matches TASKS_CFG)
BUDGETS5 = ((1000, 2500), (800, 1500), (1000, 2500),
            (40000, 120000), (800, 1500))


def _a(series, j, i):
    """Distinct ASIN per (pick-series, task, student): series 0=human,
    1=persona-economy, 2=ablated-economy, 3=persona-frontier,
    4=ablated-frontier."""
    return ASINS[series * 100 + j * 10 + i]


def task_order_of(sid):
    """Same derivation as student_start.sh / pack_evidence.py."""
    import hashlib
    return sorted(T5, key=lambda t: hashlib.sha256(
        f"{sid}|{t}".encode()).hexdigest())


def picks_csv(asins, prices, sponsored):
    lines = ["task_id,title,asin,price_inr,sponsored"]
    for i, t in enumerate(T5):
        lines.append(f"{t},Product {asins[i][-4:]},{asins[i]},"
                     f"{prices[i]},{sponsored[i]}")
    return "\n".join(lines) + "\n"


def profile_md(n_orders, brand):
    rows = [f"- 2026-0{(i % 9) + 1}-01 | grocery > snacks | {brand} | "
            f"item {i} | 1 | ₹{150 + 40 * i}" for i in range(n_orders)]
    return "# Purchase profile\n" + "\n".join(rows) + "\n"


TASKS_CFG = (
    "task_id,frame,short_name,product_type,category_class,"
    "budget_min_inr,budget_max_inr\n"
    "1,Self-purchase,Sneakers,a pair of sneakers,hedonic,1000,2500\n"
    "2,Self-purchase,Power bank,a power bank,utilitarian,800,1500\n"
    "3,Self-purchase,Backpack,a backpack,utilitarian,1000,2500\n"
    "4,Self-purchase,Laptop,a laptop,utilitarian,40000,120000\n"
    "5,Self-purchase,Perfume,a fragrance,hedonic,800,1500\n")

BUCKETS = ("search", "carousel", "buy_again", "product_page_link",
           "category_page", "other")
# human product-view provenance: real-shaped amazon ref= slugs covering
# search, carousel, Buy-again, and an unknown one (-> 'other')
REFS = ("sr_1_3", "pd_sim_d_1", "byab_dp_1", "zz_unknown_slug")


def cand_list(asins, task, salt=0):
    return [{"asin": a, "category": f"Cat {task} > Leaf {task}",
             "price": "300", "sponsored": "0",
             "source": f"search#{k + 1}",
             "source_bucket": BUCKETS[(salt + k) % len(BUCKETS)]}
            for k, a in enumerate(asins)]


def vfor(a, h, i, j):
    """ASIN-consistent verdict (identical iff same product). Students
    i%5==0 approve everything and i%5==4 reject everything, so task
    outcomes CLUSTER within students — the shape the cluster-level
    p-values (B9) exist for."""
    if a == h:
        return "identical"
    if i % 5 == 0:
        return "better"
    if i % 5 == 4:
        return "inferior"
    v = VERDS[(i + j) % 4]
    return v if v != "identical" else "equivalent"


def base_files(sid, i, human, hp):
    return {"human_picks.csv":
            "task_id,title,asin,url,price_inr,reasoning\n" + "".join(
                f"{t},H{j},{human[j]},u,{hp[j]},r\n"
                for j, t in enumerate(T5)),
            "purchase_profile.md": profile_md(4 + i % 12, f"brand{i % 5}"),
            "config_snapshot/tasks_config.csv": TASKS_CFG,
            "human_session.jsonl": "\n".join(
                json.dumps({"type": "product_view", "asin": a,
                            "category": f"Cat {j} > Leaf {j}",
                            "url": f"/x/dp/{a}/ref={REFS[j % len(REFS)]}",
                            "ref": REFS[j % len(REFS)]})
                for j, a in enumerate(human + [ASINS[i + 5]])) + "\n"}


def make_zip(path, sid, i, mode, sandbox=False):
    """mode: '4run' | '2run' | 'single' (manifest generations)."""
    # the order-arm factor is retired (all 2x2 packs are human-first);
    # legacy packs keep their historical arm values for backward compat
    arm = "H_FIRST" if (mode == "4run" or i % 2) else "A_FIRST"
    human = [_a(0, j, i) for j in range(5)]
    hp = [1800 + 20 * i, 1200 + 10 * i, 1600 + 25 * i,
          92000 + 800 * i, 950 + 5 * i]
    # per-cell agent picks (2x2); 2run/single use the economy cells.
    # Deliberate overlaps: some identical-to-human picks and some
    # same-pick-across-runs cases so verdicts/overlap sets vary.
    pe = [human[0] if i % 3 == 0 else _a(1, 0, i)] + \
        [human[1]] + [_a(1, j, i) for j in (2, 3, 4)]
    ae = [pe[0] if i % 2 == 0 else _a(2, 0, i), _a(2, 1, i),
          _a(2, 2, i), _a(2, 3, i), _a(2, 4, i)]
    pf = [pe[0], human[1] if i % 2 else _a(3, 1, i),
          _a(3, 2, i), _a(3, 3, i), _a(3, 4, i)]
    af = [ae[0] if i % 3 else _a(4, 0, i), ae[1],
          _a(4, 2, i), _a(4, 3, i), _a(4, 4, i)]
    ap = [1500 + 25 * i, 1100 + 10 * i, 1900 + 30 * i,
          58000 + 900 * i, 1000 + 15 * i]

    man = {"student_id": sid, "arm": arm, "sandbox": sandbox,
           "packed_at_utc": f"2026-09-28T10:{i % 60:02d}:00+00:00",
           "sensitive_items_excluded": i % 5 == 2,
           "model_tier": "economy" if (mode != "4run" and i % 4 == 0)
           else "frontier",
           "human_process": {"searches": 5 + i, "product_views": 8 + i},
           "task_order": task_order_of(sid),
           "task_order_expected": task_order_of(sid),
           "validation_issues": [], "warnings": [], "ratings": {},
           "rationales": {}}
    files = base_files(sid, i, human, hp)

    if mode == "4run":
        # tier order is counterbalanced ACROSS DAYS per student: even i
        # runs economy on day 1, odd i runs frontier on day 1
        t1, t2 = (("economy", "frontier") if i % 2 == 0
                  else ("frontier", "economy"))
        cells = {("persona", t1): ("run1", pe, [0, 1, 0, 0, 0]),
                 ("ablated", t1): ("run2", ae, [1, 0, 0, 0, 1]),
                 ("ablated", t2): ("run3", af, [0, 0, 0, 0, 0]),
                 ("persona", t2): ("run4", pf, [0, 1, 0, 1, 0])}
        man["verdicts"], man["contamination_index"] = {}, {}
        man["candidates"] = {}
        hth = {"grounding_economy": {}, "grounding_frontier": {},
               "tier_persona": {}, "tier_ablated": {}}
        for j, t in enumerate(T5):
            hth["grounding_economy"][t] = \
                ["persona", "ablated", "tie"][(i + j) % 3]
            hth["grounding_frontier"][t] = \
                ["persona", "ablated", "tie"][(i + j + 1) % 3]
            hth["tier_persona"][t] = \
                ["frontier", "economy", "same"][(i + j) % 3]
            hth["tier_ablated"][t] = \
                ["frontier", "economy", "same"][(i + j + 2) % 3]
        for (cond, tier), (rn, picks, spons) in cells.items():
            label = f"{cond}_{tier}"
            files[f"{rn}/agent_picks.csv"] = picks_csv(picks, ap, spons)
            man["contamination_index"][label] = {
                "index": ((i + len(label)) % 4) / 6.0}
            man["candidates"][label] = {
                t: cand_list([picks[j], ASINS[j + 25], human[j]], t,
                             salt=i + j)
                for j, t in enumerate(T5)}
            for j, t in enumerate(T5):
                key = f"{t}_{label}"
                man["verdicts"][key] = vfor(picks[j], human[j], i, j +
                                            (0 if tier == "economy" else 1))
                man["ratings"][key] = {"self": 6 + (i + j) % 4,
                                       "agent": 3 + (i + j + len(cond)) % 6}
                man["rationales"][key] = "one-line why"
        man["verdict_source"] = "verdicts_csv"
        man["interventions_by_run"] = {
            "run1": {"captchas": i % 2, "interventions": i % 3,
                     "note": ""}}
        man["searches"] = {
            f"{cond}_{tier}": {t_: [{"query": f"q {t_} {k}",
                                     "filters": "none"}
                               for k in range(1 + (i + j) % 3)]
                              for j, t_ in enumerate(T5)}
            for (cond, tier) in cells}
        man["process"] = {
            "human": {"duration_min": 38.0 + i,
                      "searches": 5 + i, "product_views": 8 + i,
                      "filter_sorts": 2 + i % 3, "cart_adds": 5,
                      "attribution": "task_markers",
                      "per_task": {t_: {"minutes": 4.0 + (i + j) % 6,
                                        "searches": 1 + (i + j) % 2,
                                        "product_views": 2 + (i + j) % 3,
                                        "filter_sorts": (i + j) % 2}
                                   for j, t_ in
                                   enumerate(task_order_of(sid))}},
            "runs": {rn: {"duration_min":
                          (15.0 if tier == "economy" else 23.0) + i}
                     for (cond, tier), (rn, _, _) in cells.items()}}
        if i == 1:
            # one student's agent tried a checkout (guard blocked it) —
            # the cohort report must surface the count
            man["checkout_attempts"] = {
                "run2/decision_log.md": {
                    "checkout_urls": ["amazon.in/gp/buy/spc/handlers"
                                      "/display.html"],
                    "guard_fired": 1}}
        man["ablation"] = {
            "enabled": True, "design": "2x2",
            "grounding_order": {
                "day1": "P_FIRST" if i % 2 else "NP_FIRST",
                "day2": "NP_FIRST" if i % 3 else "P_FIRST"},
            "tier_order": {"day1": t1, "day2": t2},
            "run_conditions": {rn: cond for (cond, _), (rn, _, _)
                               in cells.items()},
            "run_tiers": {rn: tier for (_, tier), (rn, _, _)
                          in cells.items()},
            "head_to_head": hth,
            "pick_overlap": {
                "within_economy": [t for j, t in enumerate(T5)
                                   if pe[j] == ae[j]],
                "within_frontier": [t for j, t in enumerate(T5)
                                    if pf[j] == af[j]],
                "within_persona": [t for j, t in enumerate(T5)
                                   if pe[j] == pf[j]],
                "within_ablated": [t for j, t in enumerate(T5)
                                   if ae[j] == af[j]]},
            "manipulation_check_cited_codes": {"run2": [], "run3": []},
            "cart_verified": {"run1": True, "run2": True, "run3": None,
                              "run4": True}}
    elif mode == "2run":
        man["ablation"] = {
            "enabled": True, "design": "2run",
            "persona_order": "P_FIRST" if i % 2 else "NP_FIRST",
            "run_conditions": {"run1": "persona", "run2": "ablated"},
            "head_to_head": {t: ["persona", "ablated", "tie"][(i + j) % 3]
                             for j, t in enumerate(T5)},
            "agent_pick_overlap_tasks":
            [t for j, t in enumerate(T5) if pe[j] == ae[j]],
            "manipulation_check_cited_codes": []}
        man["verdicts"] = {}
        man["contamination_index"] = {
            "persona": {"index": (i % 4) / 6.0},
            "ablated": {"index": (i % 3) / 6.0}}
        for j, t in enumerate(T5):
            man["verdicts"][f"{t}_persona"] = vfor(pe[j], human[j], i, j)
            man["verdicts"][f"{t}_ablated"] = vfor(ae[j], human[j], i,
                                                   j + 1)
            man["ratings"][f"{t}_persona"] = {"self": 6 + (i + j) % 4,
                                              "agent": 4 + (i + j) % 6}
            man["ratings"][f"{t}_ablated"] = {"self": 6 + (i + j) % 4,
                                              "agent": 3 + (i + j) % 6}
        files["run1/agent_picks.csv"] = picks_csv(pe, ap, [0, 1, 0, 0, 0])
        files["run2/agent_picks.csv"] = picks_csv(ae, ap, [1, 0, 0, 0, 1])
        man["candidates"] = {
            "persona": {t: cand_list([pe[j], ASINS[j + 25], human[j]], t)
                        for j, t in enumerate(T5)},
            "ablated": {t: cand_list([ae[j], ASINS[j + 35]], t)
                        for j, t in enumerate(T5)}}
    else:
        man["ablation"] = {"enabled": False}
        man["verdicts"] = {t: vfor(pe[j], human[j], i, j)
                           for j, t in enumerate(T5)}
        man["contamination_index"] = {"index": (i % 3) / 6.0}
        for j, t in enumerate(T5):
            man["ratings"][t] = {"self": 6 + (i + j) % 4,
                                 "agent": 4 + (i + j) % 6}
        files["agent_picks.csv"] = picks_csv(pe, ap, [0, 1, 0, 0, 0])
        man["candidates"] = {
            "single": {t: cand_list([pe[j], ASINS[j + 25]], t)
                       for j, t in enumerate(T5)}}
    files["manifest.json"] = json.dumps(man)
    with zipfile.ZipFile(path, "w") as z:
        for name, content in files.items():
            z.writestr(f"{sid}/{name}", content)


def fabricate_cohort(td, mixed=True):
    """Returns the number of VALID students (the sandbox pack is
    excluded by the analyzer).

    mixed=True (the TEST cohort): 2x2 + legacy 2-run + single packs +
    an LMS-renamed zip + a sandbox pack — exercises every manifest
    generation and both exclusion/identity rules.

    mixed=False (the SAMPLE-report cohort): pure plan-of-record 2x2,
    the shape a real 2026 cohort produces (no legacy 'single' series)."""
    n = 0
    if not mixed:
        for i in range(10):
            sid = f"DT2026-{100 + i:03d}"
            make_zip(td / f"{sid}_evidence.zip", sid, i, "4run")
            n += 1
        return n
    for i in range(6):                       # plan-of-record 2x2 packs
        sid = f"DT2026-{100 + i:03d}"
        make_zip(td / f"{sid}_evidence.zip", sid, i, "4run")
        n += 1
    for i in (6, 7):                         # legacy 2-run packs
        sid = f"DT2026-{100 + i:03d}"
        make_zip(td / f"{sid}_evidence.zip", sid, i, "2run")
        n += 1
    make_zip(td / "DT2026-108_evidence.zip", "DT2026-108", 8, "single")
    n += 1
    # LMS bulk downloads rename files — identity must come from inside
    make_zip(td / "lastname_12345_DT2026-042_evidence.zip",
             "DT2026-042", 9, "4run")
    n += 1
    # sandbox pack: must be skipped, never counted
    make_zip(td / "DT2026-109_evidence.zip", "DT2026-109", 3, "4run",
             sandbox=True)
    return n


def _load_module(relpath):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        Path(relpath).stem, REPO / relpath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_parse_price():
    """B13: 'Rs.1499' must parse as 1499, never 0.1499 — in the analyzer
    AND the cart parser (same function, kept in lockstep)."""
    cases = {"Rs.1499": 1499.0, "₹1,499": 1499.0, "1499.00": 1499.0,
             "1,20,000": 120000.0, "Rs. 2,349.50": 2349.5,
             "": None, "n/a": None}
    for mod_path in ("tools/analyze_cohort.py", "tools/capture_cart.py"):
        mod = _load_module(mod_path)
        for raw, want in cases.items():
            got = mod.parse_price(raw)
            assert got == want, f"{mod_path} parse_price({raw!r}) = " \
                                f"{got}, want {want}"
    print("PASS: parse_price handles Rs./₹/Indian grouping in both tools")


def test_robustness():
    """B20: a malformed tasks_config snapshot must not kill the ingest,
    and a cohort with zero verdicts must produce a diagnostic report,
    not a KeyError."""
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        with zipfile.ZipFile(td / "DT2026-500_evidence.zip", "w") as z:
            z.writestr("DT2026-500/manifest.json", json.dumps(
                {"student_id": "DT2026-500", "sandbox": False,
                 "verdicts": {}, "validation_issues": ["missing verdicts"],
                 "ablation": {"enabled": False}}))
        out = td / "empty.html"
        r = subprocess.run(
            [sys.executable, str(REPO / "tools" / "analyze_cohort.py"),
             "--zips", str(td), "--out", str(out)],
            capture_output=True, text=True, check=False)
        assert r.returncode == 0, r.stderr
        html = out.read_text(encoding="utf-8")
        assert "No analyzable packs" in html and "DT2026-500" in html
    print("PASS: zero-verdict cohort emits a diagnostic report (exit 0)")


def rezip_with(path, member_suffix, new_content):
    """Rewrite one member of an existing zip (fixture surgery)."""
    tmpz = path.with_suffix(".tmp")
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmpz, "w") as zout:
        for n in zin.namelist():
            zout.writestr(n, new_content if n.endswith(member_suffix)
                          else zin.read(n))
    tmpz.replace(path)


def test_quarantine_and_export():
    """C2.7/C2.8: homogeneity quarantine, duplicate handling, decisions
    overrides, and the dtlab-runs-v1 / dtlab-hth-v1 exports (H1
    recomputable from the export alone)."""
    import re as _re
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        fabricate_cohort(td, mixed=False)          # 10 pure 2x2 packs
        # mismatched tasks-config hash -> quarantined
        make_zip(td / "DT2026-200_evidence.zip", "DT2026-200", 20, "4run")
        rezip_with(td / "DT2026-200_evidence.zip",
                   "config_snapshot/tasks_config.csv",
                   TASKS_CFG + "# drifted config\n")
        # invalid pack (validation_issues) -> quarantined by default,
        # then rescued by a decisions.csv include
        make_zip(td / "DT2026-201_evidence.zip", "DT2026-201", 21, "4run")
        z = zipfile.ZipFile(td / "DT2026-201_evidence.zip")
        man201 = json.loads(z.read("DT2026-201/manifest.json"))
        z.close()
        man201["validation_issues"] = ["fixture issue"]
        rezip_with(td / "DT2026-201_evidence.zip", "manifest.json",
                   json.dumps(man201))
        # duplicate student id: a NEWER zip for DT2026-100 wins
        make_zip(td / "dup_DT2026-100_evidence.zip", "DT2026-100", 0,
                 "4run")
        zdup = td / "dup_DT2026-100_evidence.zip"
        z = zipfile.ZipFile(zdup)
        mandup = json.loads(z.read("DT2026-100/manifest.json"))
        z.close()
        mandup["packed_at_utc"] = "2026-09-29T09:00:00+00:00"
        rezip_with(zdup, "manifest.json", json.dumps(mandup))
        # decisions: exclude one clean student, include the invalid one
        dec = td / "decisions.csv"
        dec.write_text("student_id,action,reason\n"
                       "DT2026-101,exclude,withdrew consent\n"
                       "DT2026-201,include,issue reviewed and waived\n",
                       encoding="utf-8")
        out = td / "report.html"
        runs_csv = td / "runs.csv"
        hth_csv = td / "hth.csv"
        r = subprocess.run(
            [sys.executable, str(REPO / "tools" / "analyze_cohort.py"),
             "--zips", str(td), "--out", str(out),
             "--decisions", str(dec),
             "--export-runs", str(runs_csv),
             "--export-hth", str(hth_csv)],
            capture_output=True, text=True, check=False)
        assert r.returncode == 0, r.stderr
        html = out.read_text(encoding="utf-8")
        # confirmatory set: 10 - 1 (excluded) + 1 (included) = 10
        assert "10 students" in r.stdout, r.stdout
        assert "Quarantined submissions" in html
        for marker in ("tasks_config_sha256_mismatch",
                       "decision:withdrew consent",
                       "duplicate_student_id",
                       "sensitivity appendix only",
                       "issue reviewed and waived",       # decisions echo
                       "Version counts"):
            assert marker in html, f"missing C2.7 marker: {marker}"
        # class copy stays pseudonym-free even with quarantine tables
        assert not _re.search(r"DT\d{4}-\d{3}", html)
        assert "anon-" in html
        # ---- dtlab-runs-v1 export round-trip ----
        import csv as _csv
        with open(runs_csv, newline="", encoding="utf-8") as f:
            rrows = list(_csv.DictReader(f))
        assert len(rrows) == 10 * 5 * 4, len(rrows)   # students x tasks x runs
        assert {r_["run"] for r_ in rrows} == {"1", "2", "3", "4"}
        need_cols = {"student_id", "run", "day", "run_order_in_day",
                     "condition", "tier", "model_id", "provider",
                     "hermes_version", "verdict", "rating_self",
                     "rating_agent", "rationale", "verdict_at_utc",
                     "amended", "agent_asin", "agent_price",
                     "human_asin", "human_price", "sponsored",
                     "n_candidates", "n_searches", "contamination_index",
                     "task_id", "task_position", "category_class",
                     "tasks_config_sha256", "soul_sha256",
                     "config_sha256", "purchase_profile_sha256",
                     "instrument_version", "kit_version",
                     "sensitive_items_excluded",
                     "verdicts_captured_blind"}
        assert need_cols <= set(rrows[0]), \
            need_cols - set(rrows[0])
        # H1 recomputed from the export ALONE must match the report
        acc = {"better", "identical", "equivalent"}
        cells = {}
        for r_ in rrows:
            k = (r_["student_id"], r_["task_id"], r_["tier"])
            cells.setdefault(k, {})[r_["condition"]] = \
                1.0 if r_["verdict"] in acc else 0.0
        by_student = {}
        for (sid, _t, _ti), v in cells.items():
            if {"persona", "ablated"} <= set(v):
                by_student.setdefault(sid, []).append(
                    (v["persona"], v["ablated"]))
        deltas = []
        for sid, pairs in by_student.items():
            deltas.append(sum(p for p, _ in pairs) / len(pairs)
                          - sum(a for _, a in pairs) / len(pairs))
        h1_export = 100 * sum(deltas) / len(deltas)
        m = _re.search(r"H1 — Questionnaire effect.*?Δ = "
                       r"([+-]?\d+\.\d) pp", html, _re.DOTALL)
        assert m, "H1 row not found in the report"
        assert abs(h1_export - float(m.group(1))) < 0.06, \
            (h1_export, m.group(1))
        # ---- dtlab-hth-v1 export ----
        with open(hth_csv, newline="", encoding="utf-8") as f:
            hrows = list(_csv.DictReader(f))
        assert len(hrows) == 10 * 5 * 4, len(hrows)  # students x tasks x fams
        assert set(hrows[0]) == {"student", "task", "contrast", "winner",
                                 "resolved_from_blind"}
        # mixed generations refuse to export without --allow-mixed
        make_zip(td / "DT2026-300_evidence.zip", "DT2026-300", 30, "2run")
        r = subprocess.run(
            [sys.executable, str(REPO / "tools" / "analyze_cohort.py"),
             "--zips", str(td), "--out", str(td / "r2.html"),
             "--export-runs", str(td / "r2.csv")],
            capture_output=True, text=True, check=False)
        assert r.returncode != 0 and "mixed schema" in \
            (r.stdout + r.stderr), (r.returncode, r.stderr[-500:])
    print("PASS: quarantine gates, decisions overrides, and the "
          "runs/hth exports round-trip (H1 recomputed from the export)")


def main():
    test_parse_price()
    test_robustness()
    test_quarantine_and_export()
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        n_valid = fabricate_cohort(td)
        # sorts FIRST: a sandbox pack whose tasks_config snapshot is
        # malformed — the task-set loader must skip-and-log it (B20),
        # never kill the whole ingest
        with zipfile.ZipFile(td / "DT2026-000_evidence.zip", "w") as z:
            z.writestr("DT2026-000/manifest.json", json.dumps(
                {"student_id": "DT2026-000", "sandbox": True}))
            z.writestr("DT2026-000/config_snapshot/tasks_config.csv",
                       "task_id,frame,short_name,product_type,"
                       "category_class,budget_min_inr,budget_max_inr\n"
                       "1,Self-purchase,X,item,utilitarian,abc,def\n")
        out = td / "report.html"
        r = subprocess.run(
            [sys.executable, str(REPO / "tools" / "analyze_cohort.py"),
             "--zips", str(td), "--out", str(out)],
            capture_output=True, text=True, check=False)
        if r.returncode != 0:
            print(r.stdout)
            print(r.stderr)
            sys.exit("FAIL: analyze_cohort.py exited non-zero")
        assert f"{n_valid} students" in r.stdout, \
            f"expected {n_valid} students in: {r.stdout} (LMS-renamed " \
            "zip must parse; sandbox pack must be excluded)"
        assert "sandbox pack" in r.stderr, \
            "sandbox pack skip should be reported on stderr"
        html = out.read_text(encoding="utf-8")
        for marker in ("Acceptable-pick rate", "Head-to-head",
                       "Pick overlap", "Satisfaction ratings",
                       "Contamination", "Statistics", "plotly",
                       "Data quality", "Robustness", "cluster-bootstrap",
                       "Holm", "Convergent validity",
                       "Questionnaire effect", "equivalence",
                       "Minimum detectable", "Consideration-set size",
                       "Jaccard", "utilitarian", "CAND",
                       # four-run 2x2 additions
                       "Tier effect", "interaction", "MODEL TIER",
                       "Provenance mix", "Within-day run-order",
                       "frontier win share",
                       "H2 — Tier effect (day-counterbalanced",
                       "Exploratory day effect",
                       "Tier order across days",
                       "Sensitive-item opt-outs",
                       "Human interventions recorded",
                       "Grounding order day 2",
                       "Task-position effect",
                       "Shopping effort", "Deliberation time",
                       "Human minutes per task",
                       "agent candidates vs human views",
                       "human session"):
            assert marker in html, f"missing section: {marker}"
        assert "nan" not in html.split("Statistics")[1].split(
            "Robustness")[0].lower(), "nan leaked into the stats table"
        # B9: pooled-count tests are gone from inference; p is cluster-level
        assert "McNemar" not in html, \
            "pooled McNemar label must not survive (cluster-level p now)"
        assert "computed \nat the CLUSTER level".replace("\n", "") in \
            html.replace("\n", " ").replace("  ", " ") or \
            "CLUSTER level" in html, "cluster-level p note missing"
        assert "no naive p" in html, \
            "Spearman must report a cluster-bootstrap CI, not a naive p"
        assert "(descriptive)" in html, \
            "discordant counts must be labeled descriptive"
        # B11: TOST/MDE retargeted at the operative contrasts
        for marker in ("Run-order equivalence",
                       "Task-position equivalence",
                       "Minimum detectable questionnaire effect",
                       "Minimum detectable tier effect",
                       "legacy arm design"):
            assert marker in html, f"missing B11 row: {marker}"
        # B22: guard-blocked checkout attempts surface in Data Quality
        assert "Checkout attempts (network-blocked" in html
        assert "1 checkout-shaped URL(s) in logs across 1 student(s)" \
            in html, "cohort checkout-attempt count wrong"
        # B15/C1.2: single-occasion note + price-drift caveat +
        # stock-out flag; the day-confound caveat must be GONE (tier is
        # day-counterbalanced now)
        for marker in ("ONE blind",
                       "captured on different days",
                       "Likely stock-outs"):
            assert marker in html, f"missing B15 marker: {marker}"
        assert "confounded with day" not in html, \
            "day-confound caveat must not survive the counterbalance"
        assert "verdict occasion tracks tier" not in html, \
            "per-day verdict-occasion caveat must not survive the " \
            "single Friday session"
        # B14: contamination read against a null, used as a subgroup
        for marker in ("permutation baseline",
                       "top-quartile contamination",
                       "never a regression covariate"):
            assert marker in html, f"missing B14 marker: {marker}"
        # B12: Holm over exactly {H1,H2,H3}; everything else exploratory
        for marker in ("H1 — Questionnaire effect", "H2 — Tier effect",
                       "H3 — Grounding x tier interaction",
                       "over \nH1–H3".replace("\n", ""),
                       "(exploratory, unadjusted)",
                       "Agreement/fidelity rate = identical/equivalent",
                       "Paired-contrast coverage",
                       "own deduplicated per task"):
            assert marker in html, f"missing B12 marker: {marker}"
        assert out.stat().st_size > 100_000, "report suspiciously small"
        # C2.4: the CLASS report carries zero pseudonyms (course pattern)
        import re as _re
        idpat = _re.compile(r"DT\d{4}-\d{3}")
        leak = idpat.search(html)
        assert not leak, f"pseudonym leaked into the class report: " \
                         f"{leak.group(0)}"
        out_id = td / "report_identified.html"
        r = subprocess.run(
            [sys.executable, str(REPO / "tools" / "analyze_cohort.py"),
             "--zips", str(td), "--out", str(out_id), "--identified"],
            capture_output=True, text=True, check=False)
        assert r.returncode == 0, r.stderr
        html_id = out_id.read_text(encoding="utf-8")
        assert idpat.search(html_id), \
            "--identified must restore hover pseudonyms"
        assert "IDENTIFIED COPY" in html_id and "do \nnot distribute" \
            .replace("\n", "") in html_id.replace("\n", " ") \
            .replace("  ", " "), "identified banner missing"
        print(f"PASS: report generated ({out.stat().st_size >> 10} KB) "
              f"from {n_valid} students (2x2 + legacy + renamed zip; "
              "sandbox excluded), zero pseudonyms in the class copy, "
              "--identified banner present")


if __name__ == "__main__":
    main()
