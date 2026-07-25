#!/usr/bin/env python3
"""
pack_evidence.py — collect, validate, and bundle ALL SEVEN deliverables into
one submission file:  ~/dtlab/<STUDENT_ID>_evidence.zip

  #1 persona_survey.csv + .md      (questionnaire with answers)
  #2 purchase_profile.md            (agent-extracted from amazon.in orders;
                                     raw purchase_history.csv only if the
                                     optional research add-on was used)
  #3 tasks.md                      (the task set given to the agent;
                                     structure defined in tasks_config.csv)
  #4 hermes_logs/ + decision logs   (full agent trace, per run)
  #5 agent_picks.csv + cart evidence per run (screenshot + parsed cart JSON
                                     from dtlab-cart, cross-checked)
  #6 human_picks.csv               (what the student chose, pre-registered)
  #7 verdicts.csv + overall_reflections.md  (captured by dtlab-verdict;
                                     comparison.md memo parsing retained as
                                     the backward-compatible fallback)

Design modes, auto-detected from ~/dtlab/runs/:
  single  — no run dirs (legacy non-ablation flow)
  2run    — run1/run2 with condition.txt only (legacy ablation factor)
  2x2     — run1..run4 with condition.txt + tier.txt (plan of record:
            grounding persona|ablated x tier economy|frontier; verdict keys
            "{task}_{condition}_{tier}")

Also writes report.html inside the zip: a single self-contained page a grader
can open — side-by-side picks table, verdicts, embedded cart screenshot, and
the decision log / comparison inline. Plus manifest.json with SHA-256 hashes
and validation results (research integrity: hash before you grade).

Run on the VM:   dtlab-pack        (alias for: python3 ~/dtlab/tools/pack_evidence.py)
Exit code is non-zero if any REQUIRED component is missing/invalid, and the
zip is still produced with the manifest marking what failed (partial packs
are data — a lost run is not a lost student).
"""

import base64
import csv
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
WS = HOME / "dtlab" / "workspace"
EV = HOME / "dtlab" / "evidence"
HU = HOME / "dtlab" / "human"      # human shopping log + picks (agent-quarantined)
MARKER = HOME / "dtlab" / ".run_started"   # touched at FIRST agent-run start
SANDBOX_MARKER = HOME / "dtlab" / "sandbox.txt"   # smoke test / fallback run
# questionnaire-ablation factor: per-run archives + the hold dir where
# persona files sit while an ablated run is in progress
RUNS = HOME / "dtlab" / "runs"
HOLD = HOME / "dtlab" / "persona_hold"
VD = HOME / "dtlab" / "verdicts"   # dtlab-verdict output (agent-quarantined)
RUN_NAMES = ("run1", "run2", "run3", "run4")


def blind_labels(student_id, task_id, run_names):
    """Blind label -> run name for one task (verdict capture is BLIND:
    runs appear as Run A-D in per-task randomized order). LOCKSTEP with
    capture_verdicts.py::blind_labels — the memo fallback's
    'Task N (Run X)' blocks resolve through this same derivation."""
    ordered = sorted(run_names, key=lambda rn: hashlib.sha256(
        f"{student_id}|{task_id}|{rn}|verdictorder".encode()).hexdigest())
    return dict(zip("ABCD", ordered))


def load_config():
    """Shared constants from ~/dtlab/dtlab_config.env (see repo root);
    every value has a fallback so a missing file degrades gracefully."""
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


CFG = load_config()
ID_RE = re.compile(CFG.get("DTLAB_ID_PATTERN", r"DT[0-9]{4}-[0-9]{3}"))
ASIN_RE = re.compile(r"[A-Z0-9]{10}")
CONDITIONS = ("persona", "ablated")
TIERS = ("economy", "frontier")


def load_task_ids():
    """Task ids from ~/dtlab/tasks_config.csv (single source for the task
    structure); a generic three-task fallback when the file is absent. Rows whose
    task_id starts with '#' are inactive catalog entries (activate by
    removing the '#'; see docs/TASK_CATEGORIES_10.md)."""
    p = HOME / "dtlab" / "tasks_config.csv"
    ids = []
    if p.exists():
        with open(p, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                tid = (r.get("task_id") or "").strip()
                if tid and not tid.startswith("#"):
                    ids.append(tid)
    return tuple(ids) if ids else ("1", "2", "3")


TASK_IDS = load_task_ids()
NT = len(TASK_IDS)


def derived_task_order(student_id, task_ids):
    """The student's randomized (deterministic) task order — LOCKSTEP
    with student_start.sh and log_human_session.py."""
    return sorted(task_ids, key=lambda t: hashlib.sha256(
        f"{student_id}|{t}".encode()).hexdigest())

# machine-parsed candidate lines the ECP requires in decision_log.md:
# CAND | task=<n> | asin=<...> | category=<...> | price=<...> | ...
CAND_RE = re.compile(r"(?m)^\s*CAND\s*\|(.+)$")

# provenance buckets for the CAND source= field (raw string is kept too)
SOURCE_BUCKETS = ("search", "carousel", "buy_again", "product_page_link",
                  "category_page", "other")


def bucket_source(raw):
    """Normalize an arbitrary CAND source= string into one of the fixed
    provenance buckets (dtlab-candidates-v1 tolerates any raw string)."""
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


def parse_candidates(text):
    """CAND lines -> {task_id: [ {asin, category, price, sponsored,
    source, source_bucket}, ... ]}. Tolerant: unknown keys ignored,
    order-free."""
    out = {}
    for m in CAND_RE.finditer(text or ""):
        fields = {}
        for part in m.group(1).split("|"):
            if "=" in part:
                k, v = part.split("=", 1)
                fields[k.strip().lower()] = v.strip()
        t = fields.get("task", "")
        if t:
            cand = {k: fields.get(k, "") for k in
                    ("asin", "category", "price", "sponsored", "source")}
            cand["source_bucket"] = bucket_source(cand["source"])
            out.setdefault(t, []).append(cand)
    return out


# machine-parsed search lines the ECP requires (search-effort analyses):
# SRCH | task=<n> | query=<verbatim> | filters=<filters/sort or none>
SRCH_RE = re.compile(r"(?m)^\s*SRCH\s*\|(.+)$")


def parse_searches(text):
    """SRCH lines -> {task_id: [ {query, filters}, ... ]} (dtlab-searches-v1)."""
    out = {}
    for m in SRCH_RE.finditer(text or ""):
        fields = {}
        for part in m.group(1).split("|"):
            if "=" in part:
                k, v = part.split("=", 1)
                fields[k.strip().lower()] = v.strip()
        t = fields.get("task", "")
        if t:
            out.setdefault(t, []).append(
                {"query": fields.get("query", ""),
                 "filters": fields.get("filters", "")})
    return out


def parse_ts(s):
    """ISO timestamp -> aware datetime, or None."""
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except ValueError:
        return None
def hermes_dirs():
    """Transcript locations, best evidence first: the explicit override,
    then the dirs dtlab-start actually PROBED and recorded at run time
    (~/dtlab/.hermes_dirs — so a wrong guess surfaces on lab day, not at
    Sunday pack time), then the historical guesses.
    TODO(dry-run): confirm against the Hermes release pinned for the
    course; override with DTLAB_HERMES_DIRS=/path/one:/path/two."""
    env = os.environ.get("DTLAB_HERMES_DIRS", "")
    if env:
        return [Path(p).expanduser() for p in env.split(":") if p]
    rec = HOME / "dtlab" / ".hermes_dirs"
    if rec.exists():
        dirs = [Path(p).expanduser() for p in
                rec.read_text(encoding="utf-8").strip().split(":") if p]
        if dirs:
            return dirs
    return [HOME / ".hermes", HOME / ".config" / "hermes"]


VERDICTS = {"better", "identical", "equivalent", "inferior"}
MAX_LOG_MB = int(os.environ.get("DTLAB_MAX_LOG_MB", "50"))

# ---- checkout-attempt detection (B22): the guard extension makes
#      checkout technically impossible; a checkout-shaped URL in a log is
#      therefore always a reviewable event, and a blocked.html sighting is
#      evidence the guard fired ----
CHECKOUT_URL_RE = re.compile(
    r"amazon\.in/(?:gp/buy|checkout|gp/product/one-click|"
    r"hz/mobile/checkout|gp/aw/buy)[^\s\"'<>)\]]*")
GUARD_FIRED_RE = re.compile(r"chrome-extension://[^\s\"'<>]*blocked\.html")

# ---- content redaction (P0.4): filenames are not enough; transcripts can
#      contain the API key or PII seen on amazon.in pages ----
KEY_RE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")
KEYLINE_RE = re.compile(r"(ANTHROPIC_API_KEY\s*[=:]\s*)[^\s\"']+")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+91[-\s]?)?[6-9]\d{9}(?!\d)")
# .env included so a key pasted into the staged dtlab_config.env copy is
# scanned (KEYLINE_RE catches it) before the snapshot enters the zip
TEXT_SUFFIXES = {".md", ".txt", ".log", ".json", ".jsonl", ".csv", ".html",
                 ".env"}

issues = []
warnings_ = []   # recorded + printed, but never fail the pack


def need(cond, msg):
    if not cond:
        issues.append(msg)
    return cond


def warn(msg):
    warnings_.append(msg)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(p):
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def find_student_id():
    # the persona file may sit in the hold dir if the last agent run was
    # an ablated one (questionnaire-ablation factor)
    for p in (WS / "persona_survey.csv", HOLD / "persona_survey.csv"):
        if p.exists():
            rows = read_csv(p)
            if rows and rows[0].get("student_id"):
                return rows[0]["student_id"].strip()
    return None


def collect_hermes_logs(staging):
    """Copy session/transcript/log files modified since the run marker.
    Newest-first, so if the size cap trips it drops the OLDEST files —
    loudly (warn), never mid-scan in rglob order; destination names are
    deduplicated so same-named files from different dirs can't silently
    overwrite each other."""
    out = staging / "hermes_logs"
    out.mkdir(parents=True, exist_ok=True)
    since = MARKER.stat().st_mtime if MARKER.exists() else 0
    files = []
    for root in hermes_dirs():
        if not root.exists():
            continue
        for f in root.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix.lower() not in {".jsonl", ".json", ".log", ".md",
                                        ".txt"}:
                continue
            if f.stat().st_mtime < since:
                continue
            # never pack credentials/config
            if any(s in f.name.lower() for s in
                   ("key", "secret", "credential", "auth", "env", "config")):
                continue
            files.append(f)
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    n, total, dropped, seen = 0, 0, 0, set()
    for f in files:
        size = f.stat().st_size
        if total + size > MAX_LOG_MB * (1 << 20):
            dropped += 1
            continue
        total += size
        dest = f"{f.parent.name}__{f.name}"
        k = 2
        while dest in seen:
            p = Path(f"{f.parent.name}__{f.name}")
            dest = f"{p.stem}__{k}{p.suffix}"
            k += 1
        seen.add(dest)
        shutil.copy2(f, out / dest)
        n += 1
    if dropped:
        warn(f"Hermes logs exceed the {MAX_LOG_MB} MB cap — kept the "
             f"{n} newest file(s), dropped {dropped} older one(s)")
    return n


def redact_staging(staging):
    """Redact API keys, email addresses, and Indian mobile numbers out of
    every staged text file (written back in place, counts kept for the
    report); "deliver to" occurrences are flagged for review. Returns the
    redaction report recorded in manifest.json so the instructor sees
    exactly what was scrubbed or needs review."""
    report = {}
    for p in sorted(staging.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        text, n_key = KEY_RE.subn("[REDACTED-API-KEY]", text)
        text, n_line = KEYLINE_RE.subn(r"\1[REDACTED]", text)
        text, n_email = EMAIL_RE.subn("[REDACTED-EMAIL]", text)
        text, n_phone = PHONE_RE.subn("[REDACTED-PHONE]", text)
        flags = {}
        if n_email:
            flags["emails_redacted"] = n_email
        if n_phone:
            flags["phones_redacted"] = n_phone
        n = text.lower().count("deliver to")
        if n:
            flags["deliver_to"] = n
        if n_key or n_line or n_email or n_phone:
            p.write_text(text, encoding="utf-8")
        if n_key or n_line or flags:
            report[str(p.relative_to(staging))] = {
                "api_keys_redacted": n_key + n_line, "pii_flags": flags}
    return report


def run_day(rn):
    """runs 1-2 = day 1, runs 3-4 = day 2 (COURSE_PLAN: Thu/Fri)."""
    return 1 if rn in ("run1", "run2") else 2


def env_metadata(runs_present=()):
    """Reproducibility metadata (P1.7): which twin produced this run."""
    md = {}
    try:
        r = subprocess.run(["hermes", "--version"], capture_output=True,
                           text=True, timeout=10, check=False)
        md["hermes_version"] = ((r.stdout or r.stderr).strip()
                                .splitlines()[0][:200]
                                if (r.stdout or r.stderr).strip() else None)
    except Exception:
        md["hermes_version"] = None
    # TODO(dry-run): confirm how to read the model ID Hermes actually used;
    # until then the course exports DTLAB_MODEL_ID_DAY1/DAY2 (per lab day)
    # or DTLAB_MODEL_ID for the manifest.
    md["model_id"] = os.environ.get("DTLAB_MODEL_ID")
    if runs_present:
        md["model_id_by_run"] = {
            rn: os.environ.get(f"DTLAB_MODEL_ID_DAY{run_day(rn)}")
            or md["model_id"] for rn in runs_present}
    kv = HOME / "dtlab" / "kit_version.txt"
    md["kit_version"] = kv.read_text().strip() if kv.exists() else None
    md["devcontainer_image"] = os.environ.get("DTLAB_IMAGE_TAG")
    soul = WS / "SOUL.md"
    md["soul_sha256"] = sha256(soul) if soul.exists() else None
    tasks_p = WS / "tasks.md"
    if tasks_p.exists():
        ttext = tasks_p.read_text(encoding="utf-8")
        m = re.search(r"Standardized agent prompt[^\n]*\n(.*)\Z", ttext,
                      re.DOTALL)
        md["task_prompt_sha256"] = hashlib.sha256(
            (m.group(1) if m else ttext).strip().encode()).hexdigest()
    else:
        md["task_prompt_sha256"] = None
    return md


def picks_table(agent, human):
    rows = []
    for t in TASK_IDS:
        a = next((r for r in agent if str(r.get("task_id", "")).strip() == t),
                 {})
        h = next((r for r in human if str(r.get("task_id", "")).strip() == t),
                 {})
        rows.append((t, h.get("title", "—"), h.get("price_inr", ""),
                     a.get("title", "—"), a.get("price_inr", ""),
                     a.get("sponsored", "")))
    return rows


def build_report(staging, student_id, sections, inlines, screenshots,
                 sandbox=False):
    """sections: list of (heading, picks-table rows, {task: verdict})."""
    def esc(s):
        return html.escape(str(s))
    logo_p = HOME / "dtlab" / "assets" / "ringelai.png"
    logo = ('<img src="data:image/png;base64,' +
            base64.b64encode(logo_p.read_bytes()).decode() +
            '" alt="RingelAI" style="float:right;height:56px;'
            'margin:4px 0 8px 16px">') if logo_p.exists() else ""
    banner = ('<p style="background:#fff3cd;border:1px solid #e0a800;'
              'padding:10px;font-weight:600">SANDBOX RUN — practice-store '
              'exercise; EXCLUDED from the research dataset.</p>'
              if sandbox else "")
    shots = ""
    for s in screenshots[:4]:
        b64 = base64.b64encode(s.read_bytes()).decode()
        mime = "image/png" if s.suffix.lower() == ".png" else "image/jpeg"
        shots += (f'<img src="data:{mime};base64,{b64}" '
                  f'style="max-width:100%;border:1px solid #ccc;margin:8px 0">')
    tables = ""
    for heading, table, vmap in sections:
        trs = "".join(
            f"<tr><td>{t}</td><td>{esc(ht)}</td><td>{esc(hp)}</td>"
            f"<td>{esc(at)}</td><td>{esc(ap)}</td><td>{esc(sp)}</td>"
            f"<td><b>{esc(vmap.get(t, '?'))}</b></td></tr>"
            for t, ht, hp, at, ap, sp in table)
        tables += (f"<h2>{esc(heading)}</h2>"
                   "<table><tr><th>Task</th><th>Human pick</th><th>Rs.</th>"
                   "<th>Agent pick</th><th>Rs.</th><th>Sponsored?</th>"
                   f"<th>Verdict</th></tr>{trs}</table>")

    def inline(name):
        p = staging / name
        return (f"<h2>{name}</h2><pre>{esc(p.read_text(encoding='utf-8'))}"
                "</pre>") if p.exists() else ""

    doc = f"""<!doctype html><meta charset="utf-8">
<title>DT Lab submission — {esc(student_id)}</title>
<style>body{{font-family:system-ui;max-width:960px;margin:2em auto;
padding:0 1em}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #bbb;padding:6px;font-size:14px;vertical-align:top}}
pre{{white-space:pre-wrap;background:#f6f6f6;padding:1em;font-size:13px}}
h1,h2{{border-bottom:2px solid #eee;padding-bottom:4px}}</style>
{logo}<h1>Digital Twin Lab — {esc(student_id)}</h1>
{banner}<p>Packed {datetime.now(timezone.utc).isoformat()} UTC.
Validation issues: {len(issues)} {esc('; '.join(issues)) if issues else '(none)'}</p>
{tables}
<h2>Cart evidence</h2>{shots or '<p>(no screenshot found)</p>'}
{''.join(inline(n) for n in inlines)}
<p style="border-top:1px solid #e1e0d9;padding-top:10px;margin-top:2em;
color:#52514e;font-size:13px">Digital Twin Shopping Agent Lab —
Daniel M. Ringel · <a href="https://www.ringel.ai"
style="color:#2a78d6">ringel.AI</a></p>
"""
    (staging / "report.html").write_text(doc, encoding="utf-8")


def parse_head_to_head_lines(text):
    """The four machine-parsed contrast families (2x2 comparison memo):
      Task N winner (economy): persona|ablated|tie
      Task N winner (frontier): persona|ablated|tie
      Task N better model (persona): frontier|economy|same
      Task N better model (ablated): frontier|economy|same
    -> {"grounding_economy": {t: w}, ..., "tier_ablated": {t: w}}"""
    hth = {}
    for t, tier, w in re.findall(
            r"Task\s*(\d+)\s*winner\s*\((economy|frontier)\)\s*:\s*(\w+)",
            text):
        hth.setdefault(f"grounding_{tier}", {})[t] = w.lower()
    for t, cond, w in re.findall(
            r"Task\s*(\d+)\s*better model\s*\((persona|ablated)\)\s*:\s*(\w+)",
            text):
        hth.setdefault(f"tier_{cond}", {})[t] = w.lower()
    return hth


def main():
    sandbox = SANDBOX_MARKER.exists()
    student_id = find_student_id() or (
        sys.argv[sys.argv.index("--student-id") + 1]
        if "--student-id" in sys.argv else None)
    need(student_id, "cannot determine student_id "
                     "(persona_survey.csv missing? use --student-id)")
    if student_id and not ID_RE.fullmatch(student_id):
        # never let a malformed ID reach file paths (it names dirs + the zip)
        need(False, f"student_id '{student_id}' does not match the course "
                    "pattern — fix persona_survey.csv or --student-id")
        student_id = None
    student_id = student_id or "UNKNOWN"

    staging = HOME / "dtlab" / f"_staging_{student_id}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    # ---- design mode: single / 2run (legacy) / 2x2 (four runs) ----
    all_run_dirs = [rn for rn in RUN_NAMES if (RUNS / rn).exists()]
    # per-run sandbox stamps (flagged-account fallback mid-week): those
    # runs are excluded from the research dataset INDIVIDUALLY — the
    # remaining real runs keep validating; only the global marker stamps
    # the whole zip SANDBOX
    sandbox_runs = [rn for rn in all_run_dirs
                    if (RUNS / rn / "sandbox.txt").exists()]
    for rn in sandbox_runs:
        warn(f"{rn} is a sandbox run (flagged-account fallback) — "
             "excluded from the research dataset; the remaining runs "
             "validate normally")
    runs_present = [rn for rn in all_run_dirs if rn not in sandbox_runs]
    ablation = bool(runs_present)
    # per-run tier files mark the four-run 2x2; their absence marks a
    # legacy two-run pack (backward compatibility)
    four_run = ablation and any((RUNS / rn / "tier.txt").exists()
                                for rn in runs_present)
    expected_runs = tuple(
        rn for rn in (RUN_NAMES if four_run else ("run1", "run2"))
        if rn not in sandbox_runs)

    # ---- #1, #2, #3, #4(decision log), #5(picks), #7: copy from WS ----
    # dtlab-verdict artifacts live in ~/dtlab/verdicts/ (quarantined from
    # the agent workspace); the workspace location is the legacy fallback
    verdict_dir = VD if (VD / "verdicts.csv").exists() else WS
    verdicts_csv = verdict_dir / "verdicts.csv"  # dtlab-verdict (primary)
    use_verdicts_csv = verdicts_csv.exists()
    blind_meta = VD / "capture_meta.json"
    verdicts_captured_blind = False
    if use_verdicts_csv and blind_meta.exists():
        try:
            verdicts_captured_blind = bool(json.loads(
                blind_meta.read_text(encoding="utf-8")).get("blind"))
        except (json.JSONDecodeError, OSError):
            pass
    required = ["persona_survey.csv", "persona_survey.md",
                "purchase_profile.md", "tasks.md", "decision_log.md",
                "agent_picks.csv", "comparison.md"]
    if ablation:
        # per-run artifacts are staged from ~/dtlab/runs/ below instead
        required = [n for n in required
                    if n not in ("decision_log.md", "agent_picks.csv")]
    if use_verdicts_csv:
        # the guided dtlab-verdict capture replaces the comparison memo
        required = [n for n in required if n != "comparison.md"]
    # optional: only present if the (research add-on) extraction path was used
    optional = ["purchase_history.csv", "purchase_history_provenance.json"]
    for name in required:
        src = WS / name
        if not src.exists() and name.startswith("persona_survey") \
                and (HOLD / name).exists():
            src = HOLD / name    # held while an ablated run was live
        if need(src.exists(), f"missing {name}"):
            shutil.copy2(src, staging / name)
    for name in optional:
        if (WS / name).exists():
            shutil.copy2(WS / name, staging / name)
    # dtlab-verdict artifacts (verdicts.csv + head-to-heads + reflections);
    # a filled comparison.md is still staged as supporting material
    for name in ("verdicts.csv", "head_to_heads.csv",
                 "overall_reflections.md"):
        src = verdict_dir / name
        if not src.exists() and (WS / name).exists():
            src = WS / name          # mixed legacy layout
        if src.exists():
            shutil.copy2(src, staging / name)
    if use_verdicts_csv and (WS / "comparison.md").exists() \
            and "{" not in (WS / "comparison.md").read_text(encoding="utf-8"):
        shutil.copy2(WS / "comparison.md", staging / "comparison.md")

    # ---- ablation factor: stage every existing run dir ----
    conds = {}                    # runN -> persona/ablated
    tiers = {}                    # runN -> economy/frontier (2x2 only)
    pick_sets = {}                # label -> picks rows
    run_label = {}                # runN -> label ("persona_economy" | cond)
    if ablation:
        # the final run's artifacts may still sit in the workspace — adopt
        # them into the HIGHEST-numbered started run (copy, never move)
        last = runs_present[-1]
        for f in ("decision_log.md", "agent_picks.csv"):
            if not (RUNS / last / f).exists() and (WS / f).exists():
                shutil.copy2(WS / f, RUNS / last / f)
        for rn in expected_runs:
            rdir = RUNS / rn
            if not need(rdir.exists(),
                        f"ablation factor: {rn} missing under ~/dtlab/runs/ "
                        "— did all agent runs happen? (dtlab-start runs "
                        "them one at a time; a lost run still packs)"):
                continue
            cond = ((rdir / "condition.txt").read_text().strip()
                    if (rdir / "condition.txt").exists() else "")
            need(cond in CONDITIONS,
                 f"ablation factor: {rn}/condition.txt missing or invalid")
            conds[rn] = cond
            if four_run:
                tier = ((rdir / "tier.txt").read_text().strip()
                        if (rdir / "tier.txt").exists() else "")
                need(tier in TIERS,
                     f"2x2 design: {rn}/tier.txt missing or invalid")
                tiers[rn] = tier
            sdir = staging / rn
            sdir.mkdir(exist_ok=True)
            for f in ("decision_log.md", "agent_picks.csv",
                      "condition.txt", "tier.txt", "started_at.txt",
                      "ist_date.txt"):
                if (rdir / f).exists():
                    shutil.copy2(rdir / f, sdir / f)
                elif f in ("decision_log.md", "agent_picks.csv"):
                    need(False, f"ablation factor: {rn} is missing {f}")
            label = (f"{cond}_{tiers.get(rn, '')}" if four_run
                     else cond) if cond in CONDITIONS else rn
            run_label[rn] = label
            if cond in CONDITIONS and (sdir / "agent_picks.csv").exists():
                pick_sets[label] = read_csv(sdir / "agent_picks.csv")
        if four_run:
            # each day must hold one persona and one ablated run
            for day, pair in ((1, ("run1", "run2")), (2, ("run3", "run4"))):
                got = {conds[rn] for rn in pair if rn in conds}
                if len([rn for rn in pair if rn in conds]) == 2:
                    need(got == set(CONDITIONS),
                         f"2x2 design: day-{day} runs must be one persona "
                         f"and one ablated run (got "
                         f"{ {rn: conds[rn] for rn in pair if rn in conds} })")
        elif len(conds) == 2:
            need(set(conds.values()) == set(CONDITIONS),
                 f"ablation factor: the two runs must be one persona and "
                 f"one ablated run (got {conds})")

    # human-side artifacts live OUTSIDE the agent workspace (bias quarantine)
    for name in ("human_picks.csv", "human_session.jsonl"):
        src = HU / name
        if need(src.exists(), f"missing {name} in ~/dtlab/human/ "
                              "(run dtlab-shop first)") and src.exists():
            shutil.copy2(src, staging / name)
    need(not (WS / "human_picks.csv").exists(),
         "human_picks.csv found INSIDE the agent workspace — bias "
         "quarantine violated; keep human files in ~/dtlab/human/ only")
    # the sid the human session was LOGGED under must be the sid this
    # pack belongs to — a typo'd --student-id would silently
    # desynchronize the human task order from every agent run
    if (staging / "human_session.jsonl").exists() \
            and student_id != "UNKNOWN":
        hs_sid = None
        for line in (staging / "human_session.jsonl").read_text(
                encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (d.get("student_id") or "").strip():
                hs_sid = d["student_id"].strip()
                break
        if hs_sid:            # older logs carry no sid — nothing to check
            need(hs_sid == student_id,
                 f"human_session.jsonl was logged as {hs_sid} but this "
                 f"pack belongs to {student_id} — the human task order "
                 "is desynchronized from the agent runs; tell a TA")
    # ordering check against the agent run marker (all students are
    # human-first; A_FIRST branch kept for legacy packs only)
    armfile = HOME / "dtlab" / "arm.txt"
    arm = armfile.read_text().strip() if armfile.exists() else "UNKNOWN"
    if sandbox:
        arm = "SANDBOX"
    else:
        need(arm in ("H_FIRST", "A_FIRST"),
             "experimental arm not recorded — run dtlab-start once to set it")
    hs = HU / "human_session.jsonl"
    if hs.exists() and MARKER.exists() and not sandbox:
        if arm == "H_FIRST":
            need(hs.stat().st_mtime <= MARKER.stat().st_mtime + 300,
                 "H_FIRST arm: human_session.jsonl was modified AFTER the "
                 "agent run started — ordering violated")
        elif arm == "A_FIRST":
            need(hs.stat().st_mtime >= MARKER.stat().st_mtime - 300,
                 "A_FIRST arm: human session predates the agent run — "
                 "ordering violated")

    # ---- validations ----
    agent = read_csv(staging / "agent_picks.csv") \
        if (staging / "agent_picks.csv").exists() else []
    if not ablation:
        pick_sets = {"": agent}
    human = read_csv(staging / "human_picks.csv") \
        if (staging / "human_picks.csv").exists() else []
    if (staging / "human_session.jsonl").exists():
        ev_lines = (staging / "human_session.jsonl").read_text(
            encoding="utf-8").strip().splitlines()
        n_search = sum(1 for ln in ev_lines if '"type": "search"' in ln
                       or '"type":"search"' in ln)
        n_views = sum(1 for ln in ev_lines if '"product_view"' in ln)
        if n_views < NT:
            # legitimate shopping can produce few product views (adding
            # straight from the results grid never opens a product page)
            # — record for review, never fail an un-redoable Wednesday
            # session at Sunday pack time
            warn(f"human_session.jsonl has only {n_views} product views "
                 f"for {NT} tasks — picks added straight from the results "
                 "grid don't open product pages; recorded for review")
    else:
        n_search = n_views = 0
    for label, rows_ in pick_sets.items():
        if four_run and label:
            tag = " ({} run, {})".format(*label.split("_"))
        elif label:
            tag = f" ({label} run)"
        else:
            tag = ""
        need(len(rows_) == NT,
             f"agent_picks.csv{tag} has {len(rows_)} rows, need {NT}")
        for r in rows_:
            need(ASIN_RE.fullmatch(r.get("asin", "").strip() or ""),
                 f"agent pick task {r.get('task_id')}{tag}: bad/missing ASIN")
    need(len(human) == NT,
         f"human_picks.csv has {len(human)} rows, need {NT}")
    need(not any("REPLACE" in json.dumps(r) for r in human),
         "human_picks.csv still contains REPLACE placeholders")
    for r in human:
        need(ASIN_RE.fullmatch(r.get("asin", "").strip() or ""),
             f"human pick task {r.get('task_id')}: bad/missing ASIN")

    def key_of(task, label):
        """Verdict/rating key for a task within a pick-set label."""
        if not label:
            return task
        return f"{task}_{label}"      # cond or cond_tier — same shape

    verdicts = {}
    head_to_head = {}
    ratings = {}          # key -> {"self": n, "agent": n} (1-10, optional)
    rationales = {}       # key -> one-line free text (dtlab-verdict)

    # ---- verdict source A (primary): verdicts.csv from dtlab-verdict ----
    if use_verdicts_csv:
        for r in read_csv(staging / "verdicts.csv"):
            t = (r.get("task_id") or "").strip()
            cond = (r.get("condition") or "").strip()
            tier = (r.get("tier") or "").strip()
            v = (r.get("verdict") or "").strip().lower()
            if not t:
                continue
            if ablation:
                label = f"{cond}_{tier}" if four_run else cond
            else:
                label = ""
            k = key_of(t, label)
            if need(v in VERDICTS,
                    f"verdicts.csv task {t} ({cond}, {tier}): verdict "
                    f"'{v}' invalid"):
                verdicts[k] = v
            entry = {}
            for rkey, col in (("self", "rating_self"),
                              ("agent", "rating_agent")):
                raw = (r.get(col) or "").strip()
                if raw:
                    try:
                        val = int(raw)
                    except ValueError:
                        val = -1
                    need(1 <= val <= 10,
                         f"verdicts.csv task {t} ({cond}, {tier}): "
                         f"{rkey} rating '{raw}' out of range (1-10)")
                    if 1 <= val <= 10:
                        entry[rkey] = val
            if entry:
                ratings[k] = entry
            if (r.get("rationale") or "").strip():
                rationales[k] = r["rationale"].strip()
        # head-to-heads captured by the same guided session
        if (staging / "head_to_heads.csv").exists():
            for r in read_csv(staging / "head_to_heads.csv"):
                fam = (r.get("contrast") or "").strip()
                t = (r.get("task_id") or "").strip()
                w = (r.get("winner") or "").strip().lower()
                if fam and t and w:
                    head_to_head.setdefault(fam, {})[t] = w
        # coverage: every task x staged run needs a verdict row
        if ablation:
            for label in pick_sets:
                for t in TASK_IDS:
                    need(verdicts.get(key_of(t, label)) in VERDICTS,
                         f"verdicts.csv: missing/invalid verdict for task "
                         f"{t} ({label.replace('_', ', ')}) — re-run "
                         "dtlab-verdict")
        else:
            need(all(verdicts.get(t) in VERDICTS for t in TASK_IDS),
                 "verdicts.csv: every task needs a verdict — re-run "
                 "dtlab-verdict")

    # ---- verdict source B (fallback): the comparison.md memo ----
    comp = staging / "comparison.md"
    if not use_verdicts_csv and comp.exists():
        text = comp.read_text(encoding="utf-8")
        # Parse per-section: a task whose verdict is missing (e.g. left as
        # the {better|...} placeholder) must never cascade-capture the NEXT
        # task's verdict. Each section runs to the following '## ' header.
        # In ablation mode headers carry the run label; in the 2x2 they
        # also carry the tier, and verdicts are keyed
        # "<task>_<condition>_<tier>".
        heads = list(re.finditer(r"(?m)^##\s.*$", text))
        # (match, task, key, label) per verdict block. The shipped 2x2
        # template is BLIND ("## Task N (Run A)"; labels resolved via the
        # shared derivation); the pre-blind header styles keep parsing
        # for legacy packs.
        blocks = []
        if four_run:
            for m in re.finditer(
                    r"(?m)^##\s*Task\s*(\d+)\s*\((persona|ablated)\s+"
                    r"run,\s*(economy|frontier)\).*$", text):
                blocks.append((m, m.group(1),
                               f"{m.group(1)}_{m.group(2)}_{m.group(3)}",
                               f" ({m.group(2)} run, {m.group(3)})"))
            run_names = sorted(conds)
            for m in re.finditer(
                    r"(?m)^##\s*Task\s*(\d+)\s*\(Run\s*([A-D])\).*$", text):
                t = m.group(1)
                rn = blind_labels(student_id, t,
                                  run_names).get(m.group(2))
                if not rn:
                    continue
                blocks.append((m, t,
                               f"{t}_{conds[rn]}_{tiers.get(rn, '')}",
                               f" (Run {m.group(2)})"))
        elif ablation:
            for m in re.finditer(
                    r"(?m)^##\s*Task\s*(\d+)\s*\((persona|ablated)\s+"
                    r"run\).*$", text):
                blocks.append((m, m.group(1),
                               f"{m.group(1)}_{m.group(2)}",
                               f" ({m.group(2)} run)"))
        else:
            for m in re.finditer(r"(?m)^##\s*Task\s*(\d+)\b.*$", text):
                blocks.append((m, m.group(1), m.group(1), ""))
        for m, task, key, label in blocks:
            end = min((h.start() for h in heads if h.start() > m.start()),
                      default=len(text))
            sec = text[m.end():end]
            vm = re.search(r"Verdict:\s*(\w+)", sec)
            if vm:
                verdicts[key] = vm.group(1).lower()
            # satisfaction ratings (1-10; template lines are optional so
            # older templates keep validating)
            entry = {}
            for rkey, pat in (("self", r"My pick rating[^:]*:\s*(\d{1,2})"),
                              ("agent",
                               r"Agent pick rating[^:]*:\s*(\d{1,2})")):
                rm = re.search(pat, sec)
                if rm:
                    val = int(rm.group(1))
                    need(1 <= val <= 10,
                         f"comparison.md Task {task}{label}: "
                         f"{rkey} rating {val} out of range (1-10)")
                    entry[rkey] = val
            if entry:
                ratings[key] = entry
        # leftover {...} placeholders anywhere in a Task-headed section
        # (incl. the per-task synthesis sections of the 2x2 template)
        for m in re.finditer(r"(?m)^##\s*Task\s*(\d+)\b.*$", text):
            end = min((h.start() for h in heads if h.start() > m.start()),
                      default=len(text))
            sec = text[m.end():end]
            need("{" not in sec and "}" not in sec,
                 f"comparison.md Task {m.group(1)} still contains "
                 "template placeholders {...} — replace every one with "
                 "your answer")
        mo = re.search(r"(?m)^##\s*Overall.*$", text)
        if mo:
            need("{" not in text[mo.end():],
                 "comparison.md Overall section still contains template "
                 "placeholders {...} — answer all questions")
        if four_run:
            need(all(verdicts.get(f"{t}_{c}_{ti}") in VERDICTS
                     for t in TASK_IDS
                     for c, ti in {tuple(lb.split("_"))
                                   for lb in pick_sets}),
                 "comparison.md: the 2x2 design needs a 'Verdict: "
                 "better|identical|equivalent|inferior' line for every "
                 "task in ALL runs — use the four-run ablation template "
                 "(or dtlab-verdict)")
            head_to_head = parse_head_to_head_lines(text)
        elif ablation:
            need(all(verdicts.get(f"{t}_{c}") in VERDICTS
                     for t in TASK_IDS
                     for c in CONDITIONS),
                 "comparison.md: the ablation design needs a 'Verdict: "
                 "better|identical|equivalent|inferior' line for every "
                 "task in BOTH runs — use templates/comparison_ablation.md")
            hh = re.search(r"(?m)^##\s*Head-to-head.*$", text)
            if need(hh, "comparison.md: '## Head-to-head' section missing "
                        "(ablation template)"):
                end = min((h.start() for h in heads if h.start() > hh.start()),
                          default=len(text))
                for t, w in re.findall(r"Task\s*(\d+)\s*winner:\s*(\w+)",
                                       text[hh.end():end]):
                    head_to_head[t] = w.lower()
        else:
            need(all(verdicts.get(t) in VERDICTS for t in TASK_IDS),
                 "comparison.md: each Task needs 'Verdict: "
                 "better|identical|equivalent|inferior'")

    # ---- head-to-head completeness + verdict/ASIN cross-check ----
    if ablation and four_run:
        # a contrast family is checkable only when both of its cells exist
        for tier in TIERS:
            if {f"persona_{tier}", f"ablated_{tier}"} <= set(pick_sets):
                fam = f"grounding_{tier}"
                need(all(head_to_head.get(fam, {}).get(t)
                         in ("persona", "ablated", "tie")
                         for t in TASK_IDS),
                     f"head-to-head: each task needs 'Task N winner "
                     f"({tier}): persona|ablated|tie'")
        for cond in CONDITIONS:
            if {f"{cond}_economy", f"{cond}_frontier"} <= set(pick_sets):
                fam = f"tier_{cond}"
                need(all(head_to_head.get(fam, {}).get(t)
                         in ("frontier", "economy", "same")
                         for t in TASK_IDS),
                     f"head-to-head: each task needs 'Task N better model "
                     f"({cond}): frontier|economy|same'")
    elif ablation and not use_verdicts_csv:
        # legacy 2-run memo: flat per-task winner lines (parsed above)
        need(all(head_to_head.get(t) in ("persona", "ablated", "tie")
                 for t in TASK_IDS),
             "comparison.md Head-to-head: each task needs "
             "'Task N winner: persona|ablated|tie'")

    # Cross-check verdicts against ASINs: "identical" iff same product
    for label, rows_ in pick_sets.items():
        if four_run and label:
            tag = " ({} run, {})".format(*label.split("_"))
        elif label:
            tag = f" ({label} run)"
        else:
            tag = ""
        for t in TASK_IDS:
            a = next((r.get("asin", "").strip() for r in rows_
                      if str(r.get("task_id", "")).strip() == t), "")
            h = next((r.get("asin", "").strip() for r in human
                      if str(r.get("task_id", "")).strip() == t), "")
            v = verdicts.get(key_of(t, label))
            if a and h and v:
                need(not (a == h and v != "identical"),
                     f"task {t}{tag}: agent and you picked the SAME "
                     f"ASIN ({a}) — verdict must be 'identical', "
                     f"not '{v}'")
                need(not (a != h and v == "identical"),
                     f"task {t}{tag}: verdict 'identical' but ASINs "
                     f"differ (agent {a} vs yours {h}) — use "
                     f"better/equivalent/inferior")

    # ---- ablation manipulation check: NO ablated run's decision log may
    #      cite persona item codes (it never saw the questionnaire) ----
    cited_by_run = {}
    if ablation and (staging / "persona_survey.csv").exists():
        codes = [r["item_code"] for r in
                 read_csv(staging / "persona_survey.csv")
                 if r.get("item_code")]
        for rn, c in conds.items():
            if c != "ablated":
                continue
            logp = staging / rn / "decision_log.md"
            if not logp.exists():
                continue
            logtext = logp.read_text(encoding="utf-8")
            cited = sorted({cd for cd in codes
                            if re.search(rf"\b{re.escape(cd)}\b", logtext)})
            cited_by_run[rn] = cited
            need(not cited,
                 f"ablated run's decision log ({rn}) cites persona item "
                 f"codes {cited[:5]} — the ablation condition was "
                 "violated; tell a TA (do not edit the log)")

    # ---- #4: hermes session logs; #5: cart evidence; recording note ----
    n_logs = collect_hermes_logs(staging)
    need(n_logs > 0, "no Hermes session logs found since run start "
                     "(did dtlab-start create the run marker?)")

    # ---- checkout-attempt scan (B22): decision logs + collected
    #      transcripts. Query strings are stripped (they may embed
    #      tokens); any checkout-shaped amazon.in URL is a blocking
    #      issue, blocked.html sightings are guard-fired evidence.
    checkout_attempts = {}

    def scan_checkout(src_name, path):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        urls = sorted({m.group(0).split("?")[0].split("#")[0]
                       for m in CHECKOUT_URL_RE.finditer(text)})
        fired = len(GUARD_FIRED_RE.findall(text))
        if urls or fired:
            checkout_attempts[src_name] = {
                "checkout_urls": urls, "guard_fired": fired}
        if urls:
            need(False,
                 f"checkout-shaped URL in {src_name} — the guard blocked "
                 "it, but the attempt must be reviewed (tell a TA; do "
                 "not edit the log)")

    for rn in conds:
        logp = staging / rn / "decision_log.md"
        if logp.exists():
            scan_checkout(f"{rn}/decision_log.md", logp)
    if (staging / "decision_log.md").exists():
        scan_checkout("decision_log.md", staging / "decision_log.md")
    for f in sorted((staging / "hermes_logs").glob("*")):
        if f.is_file():
            scan_checkout(f"hermes_logs/{f.name}", f)
    screenshots = sorted(list(EV.glob("*.png")) + list(EV.glob("*.jpg")))
    cart_verified = {}
    if four_run:
        # per-run cart evidence from dtlab-cart: screenshot required,
        # parsed JSON preferred (enables the picks-vs-cart cross-check)
        for rn in expected_runs:
            if rn not in conds:
                continue           # missing run already reported above
            n = rn[3:]
            shot = EV / f"cart_run{n}.png"
            need(shot.exists(),
                 f"missing cart screenshot cart_run{n}.png in "
                 f"~/dtlab/evidence/ ({rn} — partner runs dtlab-cart "
                 "after the run; a manual screenshot also works)")
            cart_json = EV / f"cart_run{n}.json"
            if not cart_json.exists():
                cart_verified[rn] = None
                warn(f"{rn}: no parsed cart_run{n}.json — picks cannot be "
                     "cross-checked against the actual cart (manual "
                     "screenshot fallback; not blocking)")
                continue
            try:
                cart_items = json.loads(
                    cart_json.read_text(encoding="utf-8")).get("items", [])
            except (json.JSONDecodeError, OSError):
                cart_items = None
            if cart_items is None:
                cart_verified[rn] = None
                warn(f"{rn}: cart_run{n}.json unreadable — cross-check "
                     "skipped")
                continue
            cart_asins = {(c.get("asin") or "").strip()
                          for c in cart_items if c.get("asin")}
            picks = pick_sets.get(run_label.get(rn, ""), [])
            missing = [f"task {r.get('task_id')}: {r.get('asin', '').strip()}"
                       for r in picks
                       if r.get("asin", "").strip()
                       and r.get("asin", "").strip() not in cart_asins]
            if missing:
                cart_verified[rn] = False
                warn(f"{rn}: agent_picks.csv items not found in the "
                     f"captured cart ({'; '.join(missing)}) — "
                     "self-reported picks vs cart ground truth mismatch")
            else:
                cart_verified[rn] = True
    else:
        need(len(screenshots) > 0, "no cart screenshot in ~/dtlab/evidence/")
    shots_dir = staging / "screenshots"
    shots_dir.mkdir(exist_ok=True)
    for s in screenshots:
        shutil.copy2(s, shots_dir / s.name)
    for j in sorted(EV.glob("cart_run*.json")):
        shutil.copy2(j, shots_dir / j.name)
    recordings = list(EV.glob("run_*.mkv"))
    (staging / "RECORDINGS.txt").write_text(
        "Screen recordings are uploaded separately (size):\n" +
        "\n".join(f"{r.name}  {r.stat().st_size >> 20} MB"
                  for r in recordings) + "\n" if recordings
        else "No screen recording made — recordings are OPTIONAL evidence "
             "(partner blinding + parsed cart JSON + Hermes transcripts "
             "cover the trail).\n")

    # ---- contamination index: agent picks that the human had viewed,
    human_viewed = set()
    hs_path = staging / "human_session.jsonl"
    if hs_path.exists():
        for line in hs_path.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "product_view" and d.get("asin"):
                human_viewed.add(d["asin"])
    # (contamination itself is computed AFTER the CAND parsing below —
    #  the index is candidate-set based)

    # ---- ablation metadata: pick overlap across runs is the headline
    #      measure of each factor's marginal behavioral effect ----
    ablation_meta = {"enabled": False}
    if ablation:
        asins = {label: {str(r.get("task_id", "")).strip():
                         r.get("asin", "").strip() for r in rows_}
                 for label, rows_ in pick_sets.items()}

        def overlap(label_a, label_b):
            a, b = asins.get(label_a, {}), asins.get(label_b, {})
            return [t for t in TASK_IDS if a.get(t) and a.get(t) == b.get(t)]

        started = {rn: ((staging / rn / "started_at.txt")
                        .read_text().strip()
                        if (staging / rn / "started_at.txt").exists()
                        else None) for rn in conds}
        if four_run:
            def order_of(day):
                p = HOME / "dtlab" / f"persona_order_day{day}.txt"
                return p.read_text().strip() if p.exists() else "UNKNOWN"
            ablation_meta = {
                "enabled": True,
                "design": "2x2",
                "grounding_order": {"day1": order_of(1),
                                    "day2": order_of(2)},
                "run_conditions": conds,
                "run_tiers": tiers,
                "run_started_at": started,
                "head_to_head": head_to_head,
                "pick_overlap": {
                    # persona vs ablated within tier
                    "within_economy": overlap("persona_economy",
                                              "ablated_economy"),
                    "within_frontier": overlap("persona_frontier",
                                               "ablated_frontier"),
                    # economy vs frontier within grounding
                    "within_persona": overlap("persona_economy",
                                              "persona_frontier"),
                    "within_ablated": overlap("ablated_economy",
                                              "ablated_frontier"),
                },
                "manipulation_check_cited_codes": cited_by_run,
                "cart_verified": cart_verified,
            }
        else:
            orderfile = HOME / "dtlab" / "persona_order.txt"
            ablation_meta = {
                "enabled": True,
                "design": "2run",
                "persona_order": (orderfile.read_text().strip()
                                  if orderfile.exists() else "UNKNOWN"),
                "run_conditions": conds,
                "run_started_at": started,
                "head_to_head": head_to_head,
                "agent_pick_overlap_tasks": overlap("persona", "ablated"),
                "manipulation_check_cited_codes": sorted(
                    {c for lst in cited_by_run.values() for c in lst}),
            }

    # ---- machine-parsed candidate + search sets (process analyses) ----
    candidates = {}
    searches = {}
    if ablation:
        for rn, cond in conds.items():
            logp = staging / rn / "decision_log.md"
            if logp.exists():
                logtext = logp.read_text(encoding="utf-8")
                candidates[run_label[rn]] = parse_candidates(logtext)
                searches[run_label[rn]] = parse_searches(logtext)
    else:
        logp = staging / "decision_log.md"
        if logp.exists():
            logtext = logp.read_text(encoding="utf-8")
            candidates["single"] = parse_candidates(logtext)
            searches["single"] = parse_searches(logtext)
    n_cand = sum(len(v) for by_t in candidates.values()
                 for v in by_t.values())
    n_srch = sum(len(v) for by_t in searches.values()
                 for v in by_t.values())
    if n_cand and not n_srch:
        warn("decision log contains no machine-parsed 'SRCH |' search "
             "lines — search-effort analyses will be empty for this "
             "student (agent ignored or predates the SRCH protocol in "
             "SOUL.md)")
    # ---- contamination diagnostics (descriptive; PERSONALIZATION
    #      Layer 3): index = share of the run's CANDIDATE set the human
    #      had viewed. Pick-level overlap is kept as a secondary field.
    #      Identical-verdict tasks are NOT excluded (that removed exactly
    #      the cases where carry-over fully succeeded), and tasks with
    #      missing verdicts are listed explicitly instead of silently
    #      counting as non-identical. The analyzer reads this against a
    #      cross-student permutation baseline — never as a covariate.
    def contam(label, rows_, vget):
        cbt = candidates.get(label if ablation else "single") or {}
        per_task = {}
        for t in TASK_IDS:
            cl = [c.get("asin", "") for c in (cbt.get(t) or [])
                  if ASIN_RE.fullmatch(c.get("asin", ""))]
            if cl:
                per_task[t] = round(
                    sum(1 for a in cl if a in human_viewed) / len(cl), 3)
        pick_ov = [str(r.get("task_id", "")).strip() for r in rows_
                   if r.get("asin", "").strip() in human_viewed]
        vals = list(per_task.values())
        return {"index": (round(sum(vals) / len(vals), 3)
                          if vals else None),
                "basis": "candidate_set",
                "per_task_candidate_viewed_share": per_task,
                "overlapping_pick_tasks": pick_ov,
                "tasks_missing_verdict": [t for t in TASK_IDS
                                          if vget(t) not in VERDICTS],
                "human_viewed_asin_count": len(human_viewed)}

    if ablation:
        contamination = {
            label: contam(label, rows_,
                          lambda t, lb=label: verdicts.get(key_of(t, lb)))
            for label, rows_ in pick_sets.items()}
    else:
        contamination = contam("", agent, verdicts.get)

    if n_cand == 0:
        warn("decision log contains no machine-parsed 'CAND |' lines — "
             "consideration-set analyses will be empty for this student "
             "(agent ignored or predates the CAND protocol in SOUL.md)")
    else:
        bad_cand = [c["asin"] for by_t in candidates.values()
                    for v in by_t.values() for c in v
                    if not ASIN_RE.fullmatch(c.get("asin", ""))]
        if bad_cand:
            warn(f"{len(bad_cand)} CAND line(s) with malformed ASINs "
                 f"(first: {bad_cand[:3]})")

    # ---- task order: randomized across students (derived from the
    #      pseudonym), enforced by dtlab-start re-ordering tasks.md ----
    task_order = None
    tmd = staging / "tasks.md"
    if tmd.exists():
        seq = re.findall(r"(?m)^##\s*Task\s+(\d+)",
                         tmd.read_text(encoding="utf-8"))
        if len(seq) == NT and set(seq) == set(TASK_IDS):
            task_order = seq
    expected_order = (derived_task_order(student_id, TASK_IDS)
                      if student_id != "UNKNOWN" else None)
    if task_order and expected_order and task_order != expected_order \
            and not sandbox:
        warn(f"tasks.md lists the tasks as {task_order} but this "
             f"student's assigned randomized order is {expected_order} — "
             "was tasks.md re-sorted by hand? (dtlab-start orders it at "
             "pre-flight)")

    # ---- shopping-process length: time, steps, searches, filters ----
    # Human side: the guided dtlab-shop session walks the student
    # through the tasks ONE AT A TIME and stamps task_start/task_end
    # events (humanlog v1.3), so every search/view/filter and the time
    # to selection are attributed to their task EXACTLY. For older logs
    # without markers, the cart-add events segment the session along
    # the assigned task order instead (approximate). Agent side:
    # per-run wall-clock from started_at -> the picks file's last
    # write; per-task agent TIME needs the Hermes transcript timestamps
    # (dry-run item) — searches, filters, and products viewed come from
    # the SRCH/CAND lines.
    hb = {"duration_min": None, "searches": n_search,
          "product_views": n_views, "filter_sorts": 0, "cart_adds": 0,
          "per_task": None, "attribution": None}
    if hs_path.exists():
        events = []
        for line in hs_path.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            d["_ts"] = parse_ts(d.get("ts"))
            events.append(d)
        ev_ts = [d["_ts"] for d in events if d["_ts"]]
        cart_ts = sorted(d["_ts"] for d in events
                         if d.get("type") == "cart_add" and d["_ts"])
        hb["filter_sorts"] = sum(1 for d in events
                                 if d.get("type") == "filter_sort")
        hb["cart_adds"] = len(cart_ts)
        if len(ev_ts) >= 2:
            hb["duration_min"] = round(
                (max(ev_ts) - min(ev_ts)).total_seconds() / 60, 1)

        def window_stats(start, end):
            inside = [d for d in events if d["_ts"]
                      and start <= d["_ts"] <= end]
            return {"minutes":
                    round((end - start).total_seconds() / 60, 1),
                    "searches": sum(1 for d in inside
                                    if d.get("type") == "search"),
                    "product_views": sum(1 for d in inside
                                         if d.get("type")
                                         == "product_view"),
                    "filter_sorts": sum(1 for d in inside
                                        if d.get("type")
                                        == "filter_sort")}

        # exact attribution: task_start/task_end markers (v1.3 logs)
        starts = {d.get("task_id"): d["_ts"] for d in events
                  if d.get("type") == "task_start" and d["_ts"]}
        ends = {d.get("task_id"): d["_ts"] for d in events
                if d.get("type") == "task_end" and d["_ts"]}
        if set(starts) >= set(TASK_IDS) and set(ends) >= set(TASK_IDS):
            hb["per_task"] = {t: window_stats(starts[t], ends[t])
                              for t in TASK_IDS
                              if starts[t] <= ends[t]}
            hb["attribution"] = "task_markers"
        # fallback: segment at the cart-adds along the assigned order
        elif expected_order and len(cart_ts) == NT and ev_ts:
            prev = min(ev_ts)
            per_task = {}
            for t, ct in zip(expected_order, cart_ts):
                if ct < prev:
                    per_task = None
                    break
                per_task[t] = window_stats(prev, ct)
                prev = ct
            if per_task:
                hb["per_task"] = per_task
                hb["attribution"] = "cart_add_segments"
    run_proc = {}
    for rn in conds:
        dur = None
        st = parse_ts((staging / rn / "started_at.txt")
                      .read_text().strip()
                      if (staging / rn / "started_at.txt").exists()
                      else "")
        picks_p = staging / rn / "agent_picks.csv"
        if st and picks_p.exists():
            end = datetime.fromtimestamp(picks_p.stat().st_mtime,
                                         timezone.utc)
            minutes = (end - st).total_seconds() / 60
            if 0 < minutes < 24 * 60:      # copy2/mv preserve mtimes
                dur = round(minutes, 1)
        run_proc[rn] = {"duration_min": dur}
    process_block = {"human": hb, "runs": run_proc}

    # ---- configuration snapshot: the run's config + assignment files ----
    snap = staging / "config_snapshot"
    snap.mkdir(exist_ok=True)
    for name in ("dtlab_config.env", "tasks_config.csv", "arm.txt",
                 "tier.txt", "persona_order.txt", "persona_order_day1.txt",
                 "persona_order_day2.txt", "task_order.txt",
                 "kit_version.txt", "sandbox.txt"):
        src = HOME / "dtlab" / name
        if src.exists():
            shutil.copy2(src, snap / name)

    # ---- redaction pass BEFORE the report, so report.html inlines the
    #      redacted versions ----
    redaction_report = redact_staging(staging)

    # legacy per-student tier file (the 2x2 records tier PER RUN; this
    # top-level field is kept for manifest backward compatibility)
    tierfile = HOME / "dtlab" / "tier.txt"
    tier = tierfile.read_text().strip() if tierfile.exists() else "frontier"
    if tier not in TIERS:
        tier = "frontier"

    # ---- report + manifest + zip ----
    if ablation:
        def sec_head(label):
            if four_run:
                c, ti = label.split("_")
                return f"Human vs. agent picks — {c} run ({ti})"
            return f"Human vs. agent picks — {label} run"
        sections = [
            (sec_head(label), picks_table(rows_, human),
             {t: verdicts.get(key_of(t, label), "?") for t in TASK_IDS})
            for label, rows_ in pick_sets.items()]
        inlines = (["comparison.md", "overall_reflections.md"] +
                   [f"{rn}/decision_log.md" for rn in expected_runs
                    if rn in conds] + ["tasks.md"])
    else:
        sections = [("Human vs. agent picks",
                     picks_table(agent, human), verdicts)]
        inlines = ["comparison.md", "overall_reflections.md",
                   "decision_log.md", "tasks.md"]
    build_report(staging, student_id, sections, inlines, screenshots,
                 sandbox=sandbox)

    # every file with size + last-modified + hash: the audit trail of what
    # the student changed and when (copy2 preserves source mtimes)
    inventory = {}
    for p in sorted(staging.rglob("*")):
        if p.is_file():
            st = p.stat()
            inventory[str(p.relative_to(staging))] = {
                "sha256": sha256(p), "bytes": st.st_size,
                "mtime_utc": datetime.fromtimestamp(
                    st.st_mtime, timezone.utc).isoformat()}

    if ablation:
        runs_desc = " + ".join(rn for rn in expected_runs if rn in conds)
        d4 = f"{runs_desc} decision logs + hermes_logs/ ({n_logs} files)"
        d5 = f"{runs_desc} agent_picks.csv + screenshots/ (+ cart JSON)"
    else:
        d4 = f"decision_log.md + hermes_logs/ ({n_logs} files)"
        d5 = "agent_picks.csv + screenshots/"
    manifest = {
        "student_id": student_id,
        "packed_at_utc": datetime.now(timezone.utc).isoformat(),
        "sandbox": sandbox,
        "sandbox_runs": sandbox_runs,
        "deliverables": {
            "1_questionnaire": "persona_survey.csv|md",
            "2_purchase_history": "purchase_profile.md "
                                  "(agent-extracted from amazon.in orders; "
                                  "raw CSV only if research add-on used)",
            "3_tasks": "tasks.md",
            "4_agent_trace": d4,
            "5_agent_picks": d5,
            "6_human_picks": "human_picks.csv + human_session.jsonl "
                             "(shopping-process clickstream)",
            "7_comparison": ("verdicts.csv + overall_reflections.md "
                             "(dtlab-verdict)" if use_verdicts_csv
                             else "comparison.md"),
        },
        "arm": arm,
        "model_tier": tier,
        "task_order": task_order,
        "task_order_expected": expected_order,
        "ablation": ablation_meta,
        "environment": env_metadata(tuple(conds) if ablation else ()),
        "verdicts": verdicts,
        "ratings": ratings,
        "rationales": rationales,
        "verdict_source": ("verdicts_csv" if use_verdicts_csv
                           else "comparison_md"),
        "verdicts_captured_blind": verdicts_captured_blind,
        "checkout_attempts": checkout_attempts,
        "candidates": candidates,
        "searches": searches,
        "warnings": warnings_,
        "human_process": {"searches": n_search, "product_views": n_views},
        "process": process_block,
        "contamination_index": contamination,
        "first_agent_run_started_utc": (
            datetime.fromtimestamp(MARKER.stat().st_mtime,
                                   timezone.utc).isoformat()
            if MARKER.exists() else None),
        "redaction_report": redaction_report,
        "validation_issues": issues,
        "sha256": {k: v["sha256"] for k, v in inventory.items()},
        "file_inventory": inventory,
    }
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (staging / "SUBMISSION_INFO.txt").write_text(
        f"student_id: {student_id}\n"
        f"packed_at_utc: {manifest['packed_at_utc']}\n"
        f"arm: {arm}\nmodel_tier: {tier}\n"
        f"ablation: {ablation_meta.get('enabled')}"
        f"{' (design ' + ablation_meta['design'] + ')' if ablation_meta.get('enabled') else ''}\n"
        f"kit: {manifest['environment'].get('kit_version')}\n"
        + ("SANDBOX RUN — practice-store exercise; EXCLUDED from the "
           "research dataset (graded normally).\n" if sandbox else "")
        + "Every file in this zip belongs to the student_id above; "
        "manifest.json carries per-file SHA-256 hashes and timestamps.\n"
        "Digital Twin Shopping Agent Lab — Daniel M. Ringel "
        "(ringel.AI)\n")

    out = HOME / "dtlab" / f"{student_id}_evidence.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(staging.rglob("*")):
            if p.is_file():
                z.write(p, f"{student_id}/{p.relative_to(staging)}")
    shutil.rmtree(staging)

    print(f"\nPacked -> {out}")
    if warnings_:
        print("Warnings (recorded in the manifest, not blocking):")
        for wmsg in warnings_:
            print(f"  [~] {wmsg}")
    if issues:
        print("VALIDATION ISSUES (fix and re-run dtlab-pack):")
        for i in issues:
            print(f"  [!!] {i}")
        return 1
    print("All 7 deliverables present and valid. Upload the zip to the LMS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
