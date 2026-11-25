#!/usr/bin/env python3
"""Numbers for the models mode: usage per skill, price check, external data and ranking inputs.

    python3 models.py --usage [--days 30] [--top 5]
    python3 models.py --prices [--write] [--page FILE]
    AA_API_KEY=... python3 models.py --external
    python3 models.py --rank <case>
    python3 models.py --rules FILE [--write] [--claude-md FILE ...] [--review-skill FILE]

Prints JSON. Only --write writes: with --prices only ~/.claude/usage/prices.json; with --rules only the
`## Models` sections of the CLAUDE.md files and review-mr's role table. Raw external fetches
go to ~/.claude/model-bench/external/<date>/. Stdlib only, Python 3.9+.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices  # noqa: E402
import report as report_mod  # noqa: E402
import scan  # noqa: E402

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_PATH = os.path.join(SKILL_DIR, "sources.json")
BENCH_DIR = os.path.join(SKILL_DIR, "references", "bench")
EXTERNAL_DIR = os.path.join(scan.config_dir(), "model-bench", "external")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
USER_AGENT = "Mozilla/5.0 (usage-skill)"


# ---------- usage ----------

def usage(days=30, top=5, projects_dir=scan.PROJECTS_DIR, table=None, now=None):
    """Per top skill: the model and effort with the most requests, and cost per run."""
    data = report_mod.report(days, top, 1, projects_dir, None, table, now)
    out = []
    for s in data["skills"]:
        t = s["trends"]
        counts = collections.Counter()
        for key, v in t["per_model_effort"].items():
            counts[key.replace("main session: ", "", 1)] += v["requests"]
        model, effort = (None, None)
        if counts:
            model, _, effort = counts.most_common(1)[0][0].partition(" / ")
        out.append({"skill": s["skill"], "runs": t["runs"], "model": model, "effort": effort,
                    "cost_per_run": t["cost_per_run"], "per_model_effort": t["per_model_effort"]})
    return {"estimate": True, "window": data["window"], "skills": out, "warnings": data["warnings"],
            "unpriced_models": data["unpriced_models"]}


# ---------- prices ----------

_PRICE = re.compile(r"\$([0-9.]+)\s*/\s*MTok")
_COLUMNS = ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")


def model_id(display):
    """'Claude Opus 4.1' -> 'claude-opus-4-1'."""
    name = display.strip().lower().replace(".", "-")
    name = re.sub(r"\s+", "-", name)
    return name if name.startswith("claude-") else "claude-" + name


def parse_pricing(md):
    """Model rows of the first table under '## Model pricing'. Returns ({id: entry}, footnotes)."""
    start = md.find("## Model pricing")
    if start < 0:
        raise ValueError("no '## Model pricing' section")
    section = md[start:]
    nxt = section.find("\n## ", 5)
    section = section if nxt < 0 else section[:nxt]
    models, footnotes = {}, []
    for line in section.splitlines():
        line = line.strip()
        if line.startswith("*<sup>") or line.startswith("<sup>"):
            footnotes.append(re.sub(r"</?sup>|\*", "", line).strip())
            continue
        if not line.startswith("|") or ":----" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 6 or cells[0] == "Model":
            continue
        name = cells[0]
        notes = re.findall(r"\(([^()]*(?:\([^()]*\)[^()]*)*)\)", name)
        base = re.sub(r"\s*\(.*\)\s*$", "", name)
        vals = []
        for c in cells[1:]:
            m = _PRICE.search(c)
            if not m:
                break
            vals.append(float(m.group(1)))
        if len(vals) != 5:
            continue
        entry = dict(zip(_COLUMNS, vals))
        mid = model_id(base)
        note = " ".join(notes).lower()
        over = re.search(r"over ([0-9,]+) tokens", note)
        if over:
            models.setdefault(mid, {})["long_prompt"] = dict(entry, threshold=int(over.group(1).replace(",", "")))
            continue
        row = models.setdefault(mid, {})
        row.update(entry)
        row["display"] = base
        if "[retired" in note or note.startswith("retired"):
            row["retired"] = True
    return models, footnotes


def _strip(entry):
    out = {f: entry[f] for f in prices.FIELDS if f in entry}
    if "long_prompt" in entry:
        out["long_prompt"] = {k: v for k, v in entry["long_prompt"].items()}
    return out


def diff_prices(page_models, table):
    """Added and changed models (page wins), retired flags, and table models missing from the page."""
    added, changed, retired = [], [], []
    for mid, entry in sorted(page_models.items()):
        if entry.get("retired"):
            retired.append(mid)
        new = _strip(entry)
        old = table.models.get(mid)
        if old is None:
            added.append({"model": mid, "new": new, "retired": bool(entry.get("retired"))})
            continue
        fields = {}
        for f in prices.FIELDS:
            if old.get(f) != new.get(f):
                fields[f] = {"old": old.get(f), "new": new.get(f)}
        if (old.get("long_prompt") or None) != (new.get("long_prompt") or None):
            fields["long_prompt"] = {"old": old.get("long_prompt"), "new": new.get("long_prompt")}
        if fields:
            changed.append({"model": mid, "fields": fields, "new": new, "retired": bool(entry.get("retired"))})
    missing = sorted(m for m in table.models if m not in page_models)
    return {"added": added, "changed": changed, "retired": retired, "not_on_page": missing}


def write_override(entries, path=prices.OVERRIDE_PATH, version=None):
    """Merge {model: entry} into the override file with an atomic replace. Other keys are kept."""
    data = {"models": {}}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or not isinstance(data.get("models"), dict):
            raise ValueError(f"{path}: no 'models' object")
    data["models"].update(entries)
    data["version"] = version or dt.date.today().isoformat()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".prices.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return sorted(entries)


def load_sources(path=SOURCES_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def source(sources, sid):
    return next(s for s in sources["sources"] if s["id"] == sid)


def check_prices(table, md):
    page, footnotes = parse_pricing(md)
    out = diff_prices(page, table)
    out.update(page_models=len(page), footnotes=footnotes, prices=table.versions())
    return out


# ---------- fetching ----------

def fetch(url, headers=None, timeout=30):
    """(status, body text). status is None when the source did not answer."""
    req = urllib.request.Request(url, headers=dict({"User-Agent": USER_AGENT}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return None, str(exc)


def save_raw(name, body, root=EXTERNAL_DIR, day=None):
    folder = os.path.join(root, day or dt.date.today().isoformat())
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return {"path": path, "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest()}


# ---------- external ----------

def flight_text(html):
    """The Next.js flight chunks of a page, joined. The pages are JavaScript rendered."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html)
    return "".join(json.loads('"' + c + '"') for c in chunks)


def embedded(text, start_pattern, need):
    dec = json.JSONDecoder()
    out = []
    for m in re.finditer(start_pattern, text):
        try:
            obj, _ = dec.raw_decode(text, m.start())
        except ValueError:
            continue
        if isinstance(obj, dict) and all(k in obj for k in need):
            out.append(obj)
    return out


def effort_of(name):
    m = re.search(r"\(([A-Za-z]+)\)\s*$", name or "")
    e = m.group(1).lower() if m else None
    return e if e in EFFORTS else None


def row(vendor, model, effort, metric, value, url, date, source_id, **extra):
    r = {"vendor": vendor, "model": model, "effort": effort, "metric": metric, "value": value, "url": url,
         "date": date, "source": source_id, "tag": "anthropic" if vendor == "anthropic" else "reference"}
    r.update(extra)
    return r


def _ratio(cost, score):
    return round(cost / score, 4) if cost is not None and score else None


def rows_from_api(data, url, date):
    out = []
    for m in data.get("data") or []:
        vendor = ((m.get("model_creator") or {}).get("name") or "").lower().replace(" ", "-")
        score = (m.get("evaluations") or {}).get("artificial_analysis_intelligence_index")
        cost = (m.get("artificial_analysis_intelligence_index_cost") or {}).get("total_cost")
        args = (vendor, m.get("slug"), effort_of(m.get("name")))
        out.append(row(*args, "intelligence_index", score, url, date, "aa-models-api"))
        out.append(row(*args, "cost_to_run_index_usd", cost, url, date, "aa-models-api"))
        out.append(row(*args, "cost_per_index_point", _ratio(cost, score), url, date, "aa-models-api"))
    return out


def rows_from_models_page(html, url, date, with_scores=True):
    seen = {}
    for o in embedded(flight_text(html), r'\{"id":"', ("slug", "effort", "intelligenceIndex", "creator")):
        seen[(o["slug"], (o.get("effort") or {}).get("slug"))] = o
    out = []
    for (slug, effort), o in sorted(seen.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        args = ((o.get("creator") or {}).get("slug"), slug, effort)
        cost = (o.get("intelligenceIndexCost") or {}).get("total")
        score = o.get("intelligenceIndex")
        if with_scores:
            out.append(row(*args, "intelligence_index", score, url, date, "aa-models-page"))
            out.append(row(*args, "cost_to_run_index_usd", cost, url, date, "aa-models-page"))
            out.append(row(*args, "cost_per_index_point", _ratio(cost, score), url, date, "aa-models-page"))
        out.append(row(*args, "time_per_task_s", o.get("intelligenceIndexTimePerTask"), url, date, "aa-models-page"))
    return out


def rows_from_coding_page(html, url, date):
    out = []
    for o in embedded(flight_text(html), r'\{"id":"[0-9a-f]{32}","isDefault"', ("agentName", "model", "mean")):
        model = o.get("model") or {}
        vendor = o.get("provider")
        name = (model.get("release") or {}).get("shortName") or model.get("name")
        args = (vendor, model_id(name) if vendor == "anthropic" else name, (model.get("effort") or {}).get("slug"))
        mean = o.get("mean") or {}
        agent = {"agent": o.get("agentName")}
        out.append(row(*args, "coding_agent_index", o.get("indexScore"), url, date, "aa-coding-agents", **agent))
        out.append(row(*args, "cost_per_task_usd", mean.get("costUsd"), url, date, "aa-coding-agents", **agent))
        out.append(row(*args, "wall_time_per_task_s", mean.get("agentWallTimeSec"), url, date, "aa-coding-agents",
                       **agent))
    return out


def rows_from_tbench(html, url, date):
    out = []
    for o in embedded(flight_text(html), r'\{"id":"[0-9a-f-]{36}","leaderboard_id"', ("metadata", "metrics")):
        meta, metrics = o["metadata"], o["metrics"]
        org = ((meta.get("model_org") or {}).get("label") or "").lower()
        label = (meta.get("model_display") or {}).get("label")
        vendor = "anthropic" if org == "anthropic" else org
        args = (vendor, model_id(label) if vendor == "anthropic" else label, meta.get("reasoning_effort"))
        agent = {"agent": (meta.get("agent_display") or {}).get("label")}
        d = meta.get("date") or date
        out.append(row(*args, "terminal_bench_accuracy_pct", metrics.get("accuracy"), url, d, "tbench-leaderboard",
                       **agent))
        out.append(row(*args, "total_cost_usd", metrics.get("total_cost_usd"), url, d, "tbench-leaderboard", **agent))
    return out


def effort_coverage(rows):
    """Per Anthropic model on Artificial Analysis: efforts listed, and 'Effort not listed' for the others."""
    listed = collections.defaultdict(set)
    for r in rows:
        if r["tag"] == "anthropic" and r["source"].startswith("aa-models") and r["effort"]:
            listed[r["model"]].add(r["effort"])
    out = {}
    for model, eff in sorted(listed.items()):
        missing = [e for e in EFFORTS if e not in eff]
        out[model] = {"listed": [e for e in EFFORTS if e in eff], "not_listed": missing,
                      "note": f"Effort not listed: {', '.join(missing)} (no external data)" if missing else None}
    return out


def external(key=None, sources=None, fetcher=fetch, raw_root=EXTERNAL_DIR, day=None):
    """Rows from every registry source. A failing source is named in `skipped` and the run continues."""
    sources = sources or load_sources()
    day = day or dt.date.today().isoformat()
    rows, skipped, raw, notes = [], [], [], []
    by_id = {s["id"]: s for s in sources["sources"]}
    path = "page"

    def get(sid, headers=None):
        s = by_id.get(sid)
        if not s:
            return None
        status, body = fetcher(s["url"], headers)
        if status != 200:
            skipped.append({"source": sid, "url": s["url"], "status": status,
                            "reason": "did not answer" if status is None else f"HTTP {status}"})
            return None
        ext = "json" if sid.endswith("api") else ("md" if s["url"].endswith(".md") else "html")
        raw.append(dict(save_raw(f"{sid}.{ext}", body, raw_root, day), source=sid))
        return body

    api_ok = False
    if key and "aa-models-api" in by_id:
        url, data, page_no = by_id["aa-models-api"]["url"], {"data": []}, 1
        while True:
            status, body = fetcher(f"{url}?page={page_no}" if page_no > 1 else url, {"x-api-key": key})
            if status != 200:
                skipped.append({"source": "aa-models-api", "url": url, "status": status,
                                "reason": "did not answer" if status is None else f"HTTP {status}"})
                break
            raw.append(dict(save_raw(f"aa-models-api-{page_no}.json", body, raw_root, day), source="aa-models-api"))
            part = json.loads(body)
            data["data"].extend(part.get("data") or [])
            if not (part.get("pagination") or {}).get("has_more") or page_no >= 10:
                api_ok = True
                break
            page_no += 1
        if api_ok:
            rows.extend(rows_from_api(data, url, day))
            path = "free API"
        tiers = []
        for pro in sources.get("pro_endpoints", []):
            status, _ = fetcher(pro, {"x-api-key": key})
            tiers.append({"url": pro, "status": status,
                          "result": "free tier" if status == 403 else ("available" if status == 200 else
                                                                      f"HTTP {status}")})
        notes.append({"pro_endpoints": tiers})
    elif not key:
        notes.append("no AA_API_KEY: scores and cost to run read from the page")

    body = get("aa-models-page")
    if body is not None:
        rows.extend(rows_from_models_page(body, by_id["aa-models-page"]["url"], day, with_scores=not api_ok))
    body = get("aa-coding-agents")
    if body is not None:
        rows.extend(rows_from_coding_page(body, by_id["aa-coding-agents"]["url"], day))
    body = get("tbench-leaderboard")
    if body is not None:
        rows.extend(rows_from_tbench(body, by_id["tbench-leaderboard"]["url"], day))
    return {"path": path, "rows": rows, "effort_coverage": effort_coverage(rows), "skipped": skipped,
            "raw": raw, "notes": notes, "attribution": "Data: Artificial Analysis (artificialanalysis.ai)"}


# ---------- ranking ----------

def token_price(table, model):
    e = table.lookup(model)
    return {"input": e["input"], "output": e["output"]} if e else None


def rank(results, ext_rows=None, table=None):
    """Local rows ranked within each setup by cost per caught key bug, then slowest-agent time.
    External rows (Anthropic only) in a separate group by cost per index point, never ranked against local."""
    table = table or prices.PriceTable()
    groups = collections.defaultdict(list)
    local_pairs = set()
    for r in results.get("runs", []):
        caught = r.get("caught_strict")
        cost = r.get("cost_with_refuter") if r.get("cost_with_refuter") is not None else r.get("cost")
        groups[r.get("setup_id")].append({
            "run": r.get("id"), "model": r.get("model"), "effort": r.get("effort"),
            "cost_per_caught_key_bug": round(cost / caught, 4) if cost is not None and caught else None,
            "slowest_agent_min": r.get("slowest_agent_min"), "caught_strict": caught,
            "not_comparable": r.get("not_comparable"), "token_price": token_price(table, r.get("model"))})
        local_pairs.add((r.get("model"), r.get("effort")))
    big = float("inf")
    local = []
    for setup, rows in sorted(groups.items(), key=lambda kv: str(kv[0])):
        rows.sort(key=lambda x: (x["cost_per_caught_key_bug"] if x["cost_per_caught_key_bug"] is not None else big,
                                 x["slowest_agent_min"] if x["slowest_agent_min"] is not None else big))
        for i, x in enumerate(rows, 1):
            x["rank"] = i
        local.append({"setup_id": setup, "rows": rows})
    ext = collections.defaultdict(dict)
    for r in ext_rows or []:
        if r["tag"] != "anthropic" or r["source"] not in ("aa-models-api", "aa-models-page"):
            continue
        if (r["model"], r["effort"]) in local_pairs:
            continue
        ext[(r["model"], r["effort"])][r["metric"]] = r["value"]
    external_rows = [{"model": m, "effort": e, "cost per index point": v.get("cost_per_index_point"),
                      "time per task (s)": v.get("time_per_task_s"), "token_price": token_price(table, m)}
                     for (m, e), v in ext.items()]
    external_rows.sort(key=lambda x: x["cost per index point"] if x["cost per index point"] is not None else big)
    return {"local": local, "external": {"label": "cost per index point (Artificial Analysis, whole index run, "
                                                  "not per task)", "rows": external_rows}}


# ---------- rule list ----------

CLAUDE_FAMILIES = ("opus", "sonnet", "haiku", "fable", "mythos")
SLICE_ROLES_EXCLUDED = ("refuters", "thread validation")


def parse_lines(text):
    """'- Task: Model effort (note)' lines. Lines that name no Claude model are dropped (other vendors are reference only)."""
    keep, dropped = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        task, _, rest = line[2:].partition(":")
        word = rest.strip().split(" ", 1)[0].lower()
        (keep if word in CLAUDE_FAMILIES else dropped).append(line)
    return keep, dropped


def replace_section(text, lines):
    section = "## Models\n\n" + "\n".join(lines) + "\n"
    m = re.search(r"^## Models[ \t]*\n.*?(?=^## |\Z)", text, re.M | re.S)
    if m:
        tail = text[m.end():]
        return text[:m.start()] + section + ("\n" if tail else "") + tail
    return text.rstrip("\n") + "\n\n" + section


def alias_effort(rest):
    """'Haiku 5.5 max (about 7 agents)' -> 'haiku, max'."""
    m = re.match(r"\s*(Opus|Sonnet|Haiku|Fable|Mythos)\s+[0-9.]+\s+(low|medium|high|xhigh|max)\b", rest, re.I)
    return f"{m.group(1).lower()}, {m.group(2).lower()}" if m else None


def update_role_table(text, lines):
    """Rows of review-mr's step-4 role table that the `- Review` lines cover; other rows unchanged."""
    by_task = {l[2:].partition(":")[0].strip(): alias_effort(l[2:].partition(":")[2]) for l in lines}
    out = []
    in_table = False
    for row in text.split("\n"):
        if row.startswith("| role"):
            in_table = True
            out.append(row)
            continue
        if in_table and not row.startswith("|"):
            in_table = False
        if in_table and not row.startswith("| --"):
            cells = row.split("|")[1:-1]
            role = cells[0].strip()
            refuter = role.startswith(SLICE_ROLES_EXCLUDED)
            main = by_task.get("Review refuters" if refuter else "Review slices")
            fast = by_task.get("Review refuters" if refuter else "Review with --fast")
            vals = [cells[0], main or cells[1].strip(), fast or cells[2].strip()]
            row = "|" + "|".join([vals[0]] + [" " + v.ljust(len(c) - 1) for v, c in zip(vals[1:], cells[1:])]) + "|"
        out.append(row)
    return "\n".join(out)


def apply_models(proposal, claude_mds, review_skill, write=False):
    """One diff over the `## Models` sections and review-mr's role table; files change only with write=True."""
    import difflib
    lines, dropped = parse_lines(proposal)
    diff, new_texts = [], {}
    targets = [(p, lambda t: replace_section(t, lines)) for p in claude_mds]
    if any(l.startswith("- Review") for l in lines):
        targets.append((review_skill, lambda t: update_role_table(t, [l for l in lines if l.startswith("- Review")])))
    for path, fn in targets:
        old = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                old = fh.read()
        new = fn(old)
        if new != old:
            new_texts[path] = new
            diff += difflib.unified_diff(old.splitlines(True), new.splitlines(True), path, path)
    if write:
        for path, new in new_texts.items():
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".models.")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(new)
            os.replace(tmp, path)
    return {"lines": lines, "dropped": dropped, "diff": "".join(diff), "changed": sorted(new_texts),
            "written": bool(write and new_texts)}


def load_results(case, bench_dir=BENCH_DIR):
    with open(os.path.join(bench_dir, case, "results.json"), encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--usage", action="store_true")
    g.add_argument("--prices", action="store_true")
    g.add_argument("--external", action="store_true")
    g.add_argument("--rank", metavar="CASE")
    g.add_argument("--rules", metavar="FILE", help="proposed ## Models lines; prints the diff, --write applies it")
    p.add_argument("--days", type=report_mod.positive_int, default=30)
    p.add_argument("--top", type=report_mod.positive_int, default=5)
    p.add_argument("--projects-dir", default=scan.PROJECTS_DIR)
    p.add_argument("--page", help="read the pricing page from this file instead of fetching it")
    p.add_argument("--write", action="store_true", help="with --prices or --rules: apply the change")
    p.add_argument("--override", default=prices.OVERRIDE_PATH)
    p.add_argument("--external-json", help="with --rank: output of --external")
    p.add_argument("--claude-md", action="append", help="with --rules: CLAUDE.md files (default: ~/.claude/CLAUDE.md and "
                                                       "plugins/base/CLAUDE.md of this checkout)")
    p.add_argument("--review-skill", default=os.path.join(os.path.dirname(SKILL_DIR), "review-mr", "SKILL.md"))
    a = p.parse_args(argv)
    table = prices.PriceTable(prices.SEED_PATH, a.override)
    if a.usage:
        out = usage(a.days, a.top, a.projects_dir, table)
    elif a.prices:
        if a.page:
            with open(a.page, encoding="utf-8") as fh:
                md = fh.read()
        else:
            status, md = fetch(source(load_sources(), "anthropic-pricing")["url"])
            if status != 200:
                json.dump({"error": f"pricing page: {status}"}, sys.stdout)
                sys.stdout.write("\n")
                sys.exit(1)
        out = check_prices(table, md)
        if a.write:
            out["written"] = write_override({c["model"]: c["new"] for c in out["added"] + out["changed"]},
                                            a.override)
    elif a.external:
        out = external(os.environ.get("AA_API_KEY") or None)
    elif a.rules:
        with open(a.rules, encoding="utf-8") as fh:
            proposal = fh.read()
        mds = a.claude_md or [os.path.join(scan.config_dir(), "CLAUDE.md"),
                              os.path.join(os.path.dirname(os.path.dirname(SKILL_DIR)), "CLAUDE.md")]
        out = apply_models(proposal, mds, a.review_skill, a.write)
    else:
        ext = None
        if a.external_json:
            with open(a.external_json, encoding="utf-8") as fh:
                ext = json.load(fh)["rows"]
        out = rank(load_results(a.rank), ext, table)
    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
