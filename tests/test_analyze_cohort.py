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
           "model_tier": "economy" if (mode != "4run" and i % 4 == 0)
           else "frontier",
           "human_process": {"searches": 5 + i, "product_views": 8 + i},
           "task_order": task_order_of(sid),
           "task_order_expected": task_order_of(sid),
           "validation_issues": [], "warnings": [], "ratings": {},
           "rationales": {}}
    files = base_files(sid, i, human, hp)

    if mode == "4run":
        cells = {("persona", "economy"): ("run1", pe, [0, 1, 0, 0, 0]),
                 ("ablated", "economy"): ("run2", ae, [1, 0, 0, 0, 1]),
                 ("ablated", "frontier"): ("run3", af, [0, 0, 0, 0, 0]),
                 ("persona", "frontier"): ("run4", pf, [0, 1, 0, 1, 0])}
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
        man["ablation"] = {
            "enabled": True, "design": "2x2",
            "grounding_order": {
                "day1": "P_FIRST" if i % 2 else "NP_FIRST",
                "day2": "NP_FIRST" if i % 3 else "P_FIRST"},
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


def main():
    test_parse_price()
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        n_valid = fabricate_cohort(td)
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
                       "frontier win share", "confounded with day",
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
        assert out.stat().st_size > 100_000, "report suspiciously small"
        print(f"PASS: report generated ({out.stat().st_size >> 10} KB) "
              f"from {n_valid} students (2x2 + legacy + renamed zip; "
              "sandbox excluded) with all sections present")


if __name__ == "__main__":
    main()
