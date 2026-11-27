#!/usr/bin/env python3
"""Local benchmark: plan runs for new models, estimate cost, run them under a cap, store results.

    python3 bench.py plan <case> [--setup <id>] [--models id,...] [--external FILE] [--usage FILE] [--effort E]
    python3 bench.py run <case> --plan FILE --cap <usd> [--resume <id>]
    python3 bench.py status <case> [--claude-md FILE ...]

Prints JSON. Only `run` writes: run outputs to ~/.claude/model-bench/<case>/runs/, and the result to the
case's results.json and RESULTS.md, only in a repo checkout. Stdlib only, Python 3.9+.
"""
import argparse
import concurrent.futures
import datetime as dt
import glob
import hashlib
import json
import math
import os
import re
import shutil
import string
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices  # noqa: E402
import scan  # noqa: E402

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH_DIR = os.path.join(SKILL_DIR, "references", "bench")
OUT_ROOT = os.path.join(scan.config_dir(), "model-bench")
GAP_S = 300
REPEAT_WITHIN = 2
MIN_BUDGET = 0.01  # the smallest --max-budget-usd a call gets; below it a role cannot start
EFFORTS = ("low", "medium", "high", "xhigh", "max")
AGENT_TIMEOUT_S = 2 * 3600  # one agent call; the slowest stored agent took about 30 minutes


# ---------- case and setups ----------

def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def all_files(folder):
    """Every file under folder, hidden ones included, in path order."""
    return sorted(os.path.join(root, f) for root, _, files in os.walk(folder) for f in files)


def tree_hash(folder):
    h = hashlib.sha256()
    for p in all_files(folder):
        h.update(os.path.relpath(p, folder).encode())
        h.update(sha(p).encode())
    return h.hexdigest()


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def setups(case_dir):
    """{setup_id: (setup dict, setup file path)} for every setups/*.json."""
    out = {}
    for path in sorted(glob.glob(os.path.join(case_dir, "setups", "*.json"))):
        s = load_json(path)
        out[setup_id(s, path)] = (s, path)
    return out


def setup_id(setup, path):
    brief = os.path.join(os.path.dirname(path), setup["brief_template"])
    return f"{setup['name']}-v{setup['version']}-{sha(brief)[:8]}-{sha(path)[:8]}"


def case_hashes(case_dir):
    return {"checker_brief_hash": sha(os.path.join(case_dir, "checker-brief.md"))[:12],
            "key_hash": sha(os.path.join(case_dir, "answer-key.md"))[:12],
            "snapshot_hash": tree_hash(os.path.join(case_dir, "snap"))[:12]}


def brief_hashes(case_dir, setup, setup_path):
    """The briefs a setup id does not hash: the run-it template and the refuter brief."""
    out = {"refuter_brief_hash": sha(os.path.join(case_dir, setup["refuter"]["brief"]))[:12]}
    if setup.get("run_it_template"):
        out["run_it_brief_hash"] = sha(os.path.join(os.path.dirname(setup_path), setup["run_it_template"]))[:12]
    return out


def comparability(results, case_dir):
    """Marks each run whose own hashes differ from the current ones (checker brief, key, snapshot,
    run-it and refuter brief), or whose setup changed or is gone. `case_not_comparable` lists the
    case-level reasons found on any run."""
    now = case_hashes(case_dir)
    current = setups(case_dir)
    by_version = {sid.rsplit("-", 2)[0]: sid for sid in current}
    case_reasons, marked = set(), []
    for r in results.get("runs", []):
        reasons = [k.replace("_hash", "") for k, v in now.items() if r.get(k) not in (None, v)]
        case_reasons.update(reasons)
        sid = r.get("setup_id") or ""
        if sid in current:
            reasons += [k.replace("_hash", "") for k, v in brief_hashes(case_dir, *current[sid]).items()
                        if r.get(k) not in (None, v)]
        else:
            reasons.append("setup changed" if sid.rsplit("-", 2)[0] in by_version else "setup missing")
        if reasons:
            marked.append({"run": r.get("id"), "setup_id": sid, "reasons": reasons})
    return {"case_not_comparable": sorted(case_reasons), "runs_not_comparable": marked}


# ---------- slices ----------

def snapshot_files(snap):
    out = []
    for p in all_files(snap):
        if os.sep + ".git" + os.sep in p:
            continue
        with open(p, encoding="utf-8", errors="replace") as fh:
            n = fh.read().count("\n")
        out.append({"path": os.path.relpath(p, snap), "lines": n})
    return out


def cut_slices(files, rule):
    """Whole files in path order, packed to the target; a file above the hard limit is its own slice,
    above split_above it splits into ranges of about the hard limit."""
    target, hard, split = rule["target_lines"], rule["hard_limit"], rule["split_above"]
    slices, cur, load = [], [], 0
    for f in files:
        n = f["lines"]
        if n > hard:
            if cur:
                slices.append(cur)
                cur, load = [], 0
            if n > split:
                for start in range(1, n + 1, hard):
                    slices.append([dict(f, range=[start, min(n, start + hard - 1)])])
            else:
                slices.append([f])
            continue
        if cur and load + n > target:
            slices.append(cur)
            cur, load = [], 0
        cur.append(f)
        load += n
    if cur:
        slices.append(cur)
    return [{"slice": i, "files": s, "load": sum(x["lines"] if "range" not in x else x["range"][1] - x["range"][0] + 1
                                                    for x in s)}
            for i, s in enumerate(slices, 1)]


# ---------- prices and estimates ----------

def effective_price(table, model, over_share=0.0):
    e = table.lookup(model)
    if e is None:
        return None
    base = sum(e[f] for f in prices.FIELDS)
    lp = e.get("long_prompt")
    if lp and over_share:
        return (1 - over_share) * base + over_share * sum(lp[f] for f in prices.FIELDS)
    return base


def estimate(model, runs, table):
    """Cost of the closest stored run (nearest price, then latest): reviewers scaled by token price at that
    run's share of prompts over 100k, refuter and checker unchanged. Effort is not counted."""
    best = None
    for r in runs:
        share = r.get("over_100k_share") or 0.0
        new = effective_price(table, model, share)
        old = effective_price(table, r.get("model"), share)
        if not old or new is None or r.get("cost") is None:
            continue
        key = (abs(math.log(new / old)), -(dt.date.fromisoformat(r["date"]).toordinal() if r.get("date") else 0))
        if best is None or key < best[0]:
            best = (key, r, new / old)
    if best is None:
        return None
    _, r, ratio = best
    refuter = (r.get("cost_with_refuter") or r["cost"]) - r["cost"]
    checker = r.get("checker_cost") or 0.0
    return {"usd": round(r["cost"] * ratio + refuter + checker, 2), "reviewers": round(r["cost"] * ratio, 2),
            "refuter": round(refuter, 2), "checker": round(checker, 2), "from_run": r.get("id"),
            "price_ratio": round(ratio, 4), "basis": "token price only; effort not counted"}


def is_complete(r):
    return r.get("status", "complete") != "incomplete"


def history_runs(case_dir, results):
    """Runs with no setup id in results.json, else the cost rows of RESULTS.md's history (latest first)."""
    runs = [r for r in results.get("runs", []) if not r.get("setup_id") and is_complete(r)]
    if runs:
        return runs
    path = os.path.join(case_dir, "RESULTS.md")
    if not os.path.exists(path):
        return []
    out, date = [], None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            d = re.search(r"^## .*\(added (\d{4}-\d{2}-\d{2})\)", line)
            if d:
                date = d.group(1)
            m = re.match(r"\| ([A-Z]) \| ([^|]+) \|.*?\| \$(\d+\.\d+)(?:, \$(\d+\.\d+) with refuter)?", line)
            name = model_from_name(m.group(2)) if m else None
            if name:
                cost = float(m.group(3))
                out.append({"id": m.group(1), "model": name[0], "effort": name[1], "cost": cost,
                            "cost_with_refuter": float(m.group(4)) if m.group(4) else cost, "date": date})
    return out[::-1]


# ---------- current model and plan ----------

def model_from_name(text):
    """'Haiku 5.5 max (about 7 agents)' -> ('claude-haiku-5-5', 'max')."""
    m = re.match(r"\s*(Opus|Sonnet|Haiku|Fable|Mythos)\s+([0-9.]+)\s+(low|medium|high|xhigh|max)\b", text, re.I)
    if not m:
        return None
    return f"claude-{m.group(1).lower()}-{m.group(2).replace('.', '-')}", m.group(3).lower()


def models_section(text):
    m = re.search(r"^## Models\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return None
    out = {}
    for line in m.group(1).splitlines():
        lm = re.match(r"-\s*([^:]+):\s*(.+)", line.strip())
        if lm:
            out[lm.group(1).strip()] = lm.group(2).strip()
    return out


def current_model(results, sid, claude_md_texts=(), task="Review slices"):
    """The `## Models` line for the task (later files win), else the best-ranked stored result in the setup."""
    line = None
    for text in claude_md_texts:
        sec = models_section(text or "")
        if sec and task in sec:
            line = sec[task]
    if line and model_from_name(line):
        model, effort = model_from_name(line)
        stored = [r for r in results.get("runs", []) if r.get("setup_id") == sid and is_complete(r)
                  and r.get("model") == model and r.get("effort") == effort]
        best = max(stored, key=lambda r: r.get("caught_strict") or 0) if stored else None
        return {"model": model, "effort": effort, "source": "models line",
                "caught_strict": best.get("caught_strict") if best else None, "run": best.get("id") if best else None}
    ranked = ranked_runs([r for r in results.get("runs", []) if r.get("setup_id") == sid and is_complete(r)])
    if not ranked:
        return None
    r = ranked[0]
    out = {"model": r["model"], "effort": r["effort"], "source": "best stored result",
           "caught_strict": r.get("caught_strict"), "run": r.get("id")}
    if line:
        out["note"] = f"`## Models` line not read, best stored result used: {line}"
    return out


def cost_per_caught(r):
    cost = r.get("cost_with_refuter") if r.get("cost_with_refuter") is not None else r.get("cost")
    caught = r.get("caught_strict")
    return cost / caught if cost is not None and caught else float("inf")


def ranked_runs(runs):
    return sorted(runs, key=lambda r: (cost_per_caught(r), r.get("slowest_agent_min") or float("inf")))


def propose_repeat(new_caught, current):
    if not current or current.get("caught_strict") is None or new_caught is None:
        return False
    return abs(current["caught_strict"] - new_caught) <= REPEAT_WITHIN


def aa_pick(model, ext_rows):
    rows = [r for r in ext_rows or [] if r.get("tag") == "anthropic" and r.get("model") == model
            and r.get("metric") == "cost_per_index_point" and r.get("value") is not None and r.get("effort")]
    return min(rows, key=lambda r: r["value"])["effort"] if rows else None


def plan(case_dir, sid=None, models=None, ext_rows=None, usage_effort=None, table=None, claude_md_texts=(),
         fixed_effort=None):
    """Models without a complete result in the setup, at most 2 efforts each, with an estimate per run."""
    table = table or prices.PriceTable()
    results = load_json(os.path.join(case_dir, "results.json"))
    all_setups = setups(case_dir)
    runs = results.get("runs", [])
    if sid is None:
        cur_any = None
        for s in all_setups:
            cur_any = current_model(results, s, claude_md_texts)
            if cur_any and cur_any.get("run"):
                sid = s
                break
        sid = sid or (sorted(all_setups)[-1] if all_setups else None)
    in_setup = [r for r in runs if r.get("setup_id") == sid and is_complete(r)]
    history = history_runs(case_dir, results)
    done = {r.get("model") for r in in_setup}
    if models is None:
        models = sorted({r["model"] for r in ext_rows or [] if r.get("tag") == "anthropic"
                         and r.get("source", "").startswith("aa-models") and table.lookup(r["model"])})
    picks, no_effort = [], []
    for m in models:
        if m in done:
            continue
        efforts = [{"effort": fixed_effort, "why": ["fixed by --effort"]}] if fixed_effort else []
        for why, e in () if fixed_effort else (("lowest AA cost per index point", aa_pick(m, ext_rows)),
                       ("most used effort of the case's skill", usage_effort)):
            if not e:
                continue
            hit = next((x for x in efforts if x["effort"] == e), None)
            if hit:
                hit["why"].append(why)
            else:
                efforts.append({"effort": e, "why": [why]})
        if not efforts:
            no_effort.append(m)
        for x in efforts[:2]:
            est = estimate(m, in_setup, table)
            if est is None:
                est = estimate(m, history, table)
                if est:
                    est["from_history"] = True
            picks.append({"model": m, "effort": x["effort"], "why": x["why"], "estimate": est})
    total = sum(p["estimate"]["usd"] for p in picks if p["estimate"])
    return {"case": os.path.basename(case_dir), "skill": results.get("skill"), "setup_id": sid,
            "current": current_model(results, sid, claude_md_texts), "picks": picks,
            "total_estimate_usd": round(total, 2), "unestimated": [p["model"] for p in picks if not p["estimate"]],
            "no_effort": no_effort,
            "stored_in_setup": [{"id": r.get("id"), "model": r.get("model"), "effort": r.get("effort")} for r in in_setup],
            "incomplete_in_setup": [{"id": r.get("id"), "model": r.get("model"), "effort": r.get("effort"),
                                     "reason": r.get("reason")} for r in runs
                                    if r.get("setup_id") == sid and not is_complete(r)],
            "comparability": comparability(results, case_dir)}


# ---------- runner ----------

def active_minutes(paths):
    """Active wall time of one agent's transcripts: gaps over 5 minutes left out."""
    times = []
    for p in paths:
        entries, _ = scan.read_jsonl(p)
        times += [t.timestamp() for t in (scan.parse_ts(e.get("timestamp")) for e in entries) if t]
    times.sort()
    return round(sum(b - a for a, b in zip(times, times[1:]) if b - a <= GAP_S) / 60, 2)


def project_slug(path):
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def deny_rules(case_dir):
    """Every place a key copy can sit: this checkout, any repo checkout's case folder, the installed plugin copy,
    and ~/.claude/model-bench/."""
    return [f"Read(/{case_dir}/**)", "Read(//**/skills/usage/references/bench/**)",
            f"Read(/{scan.config_dir()}/plugins/**/references/bench/**)", f"Read(/{OUT_ROOT}/**)",
            "Bash(*references/bench*)", "Bash(*model-bench*)", "Bash(*answer-key*)"]


def trim_flags(settings_path=None):
    """No MCP servers and no plugin but base, so the start context is close to a real review subagent's.
    Every other plugin enabled in the user's settings is switched off for this call only."""
    path = settings_path or os.path.join(scan.config_dir(), "settings.json")
    enabled = {}
    if os.path.exists(path):
        try:
            enabled = load_json(path).get("enabledPlugins") or {}
        except (OSError, ValueError, AttributeError) as exc:
            sys.stderr.write(f"warning: {path} unreadable ({exc}); other plugins stay on for the benchmark calls\n")
    off = {k: False for k, v in enabled.items() if v and k.split("@")[0] != "base"}
    return ["--strict-mcp-config", "--settings", json.dumps({"enabledPlugins": off})]


TOOLS = "Read,Grep,Glob,Bash"


def agent_cmd(prompt, model, effort, budget, name, case_dir, settings_path=None):
    """dontAsk denies every tool not allowed up front, so the tools are allowed too; the deny rules still win."""
    return ["claude", "-p", "--model", model, "--effort", effort, "--output-format", "json",
            "--tools", TOOLS, "--allowedTools", TOOLS, "--permission-mode", "dontAsk", *trim_flags(settings_path),
            *(["--disallowedTools", *deny_rules(case_dir)] if case_dir else []), "-n", name,
            "--max-budget-usd", f"{max(budget, MIN_BUDGET):.2f}", prompt]


def call_error(out):
    """The error of a `claude -p` result, or None. A usage-limit stop comes back as is_error with subtype
    "success", so the result text is the reason then."""
    if not out.get("is_error"):
        return None
    sub = out.get("subtype")
    if sub and sub != "success":
        return sub
    return (out.get("result") or "error").strip()[:200]


def claude_agent(prompt, model, effort, budget, name, cwd, case_dir):
    """One `claude -p` call. Returns cost and minutes from its transcript, the CLI's cost as a cross-check."""
    cmd = agent_cmd(prompt, model, effort, budget, name, case_dir)
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=AGENT_TIMEOUT_S)
        out = json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        out = {"is_error": True, "result": f"timed out after {AGENT_TIMEOUT_S} s"}
    except ValueError:
        out = {"is_error": True, "result": proc.stderr[-500:]}
    sid = out.get("session_id")
    path = os.path.join(scan.PROJECTS_DIR, project_slug(os.path.realpath(cwd)), f"{sid}.jsonl") if sid else None
    cost = minutes = s = None
    if path and os.path.exists(path):
        s, _ = scan.summarize_agent(path)
        cost = s["cost"]
        minutes = active_minutes([path] + glob.glob(os.path.join(path[:-6], "subagents", "**", "*.jsonl"),
                                                   recursive=True))
    error = call_error(out)
    if cost is None:  # no transcript at the computed path: the CLI's own figure, else the call counts as failed
        cost = out.get("total_cost_usd")
        if cost is None and not error:
            error = "no cost: no transcript and no CLI cost"
    return {"cost": cost, "cli_cost": out.get("total_cost_usd"), "minutes": minutes, "result": out.get("result"),
            "error": error, "transcript": path,
            "over_100k": s["over_100k"] if s else None, "requests": s["requests"] if s else None}


def work_path(run_tmp, report):
    """Agents cannot read or write under model-bench (deny rules), so they work on a copy in the run's temp folder."""
    return os.path.join(run_tmp, os.path.basename(report))


def save_reply(report, result, work=None):
    """Keeps the agent's report file from the temp folder, or else its reply, as the report."""
    if work and os.path.exists(work):
        shutil.copyfile(work, report)
    elif report and result:  # a rerun replaces the earlier attempt's reply
        with open(report, "w", encoding="utf-8") as fh:
            fh.write(result)


DENIED = re.compile(r"report (is |was )?not (saved|written)|could(n't| not) (save|write)|"
                    r"write[^\n]{0,120}(was )?(denied|refused)|(denied|refused)[^\n]{0,60}\bwrite", re.I)


LEDGER = re.compile(r"coverage ledger|promises versus behaviou?r|^\|.*\|[ \t]*$", re.I | re.M)


def report_problem(report):
    """Why the saved report is not a finished one, or None. A finished report has its ledger (the
    heading or a table row); without it, a reply saying the write was denied, a path-only reply or a
    header-only file never reaches the refuter as a report. A denial quoted inside a ledger row is fine."""
    if not os.path.exists(report):
        return "report write denied"
    with open(report, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if LEDGER.search(text):
        return None
    return "report write denied" if DENIED.search(text[:600]) else "report not saved: no ledger"


def render(template_path, values):
    with open(template_path, encoding="utf-8") as fh:
        text = fh.read()
    text = re.sub(r"\{drop\}.*?\{/drop\}\n?", "", text, flags=re.S)
    for k, v in values.items():
        text = text.replace("{" + k + "}", str(v))
    return text


def prepare_folder(case_dir, parent=None):
    """A fresh temp folder with the snapshot as a git repo: an empty base commit, then the snapshot as head."""
    tmp = tempfile.mkdtemp(prefix="bench.", dir=parent)
    snap = os.path.join(tmp, "snap")
    shutil.copytree(os.path.join(case_dir, "snap"), snap)
    git = ["git", "-C", snap, "-c", "user.name=bench", "-c", "user.email=bench@localhost", "-c", "commit.gpgsign=false"]
    subprocess.run(git[:3] + ["init", "-q"], check=True)
    subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "base"], check=True)
    base = subprocess.run(git[:3] + ["rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(git[:3] + ["add", "-A"], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "snapshot"], check=True)
    head = subprocess.run(git[:3] + ["rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    diff = os.path.join(tmp, "snapshot.diff")
    with open(diff, "w", encoding="utf-8") as fh:
        subprocess.run(git[:3] + ["diff", base, head], stdout=fh, check=True)
    run_tmp = os.path.join(tmp, "run-tmp")
    os.makedirs(run_tmp)
    return {"root": tmp, "snap": snap, "base": base, "head": head, "diff": diff, "run_tmp": run_tmp}


def is_repo_checkout(case_dir):
    if os.path.realpath(case_dir).startswith(os.path.realpath(os.path.join(scan.config_dir(), "plugins"))):
        return False
    return subprocess.run(["git", "-C", case_dir, "rev-parse", "--is-inside-work-tree"],
                          capture_output=True, text=True).stdout.strip() == "true"


def next_run_id(results):
    used = {r.get("id") for r in results.get("runs", [])}
    for c in string.ascii_uppercase[9:]:  # runs B to I are history
        if c not in used:
            return c
    return f"R{len(used) + 1}"


def parse_score(text):
    m = re.search(r"SCORE caught_strict=(\d+) partial=(\d+) missed=(\d+)", text or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def phase_times(agents):
    """Slowest agent per phase and the run's wall time: phases run one after another, agents in a phase at once."""
    phases = {}
    for a in agents:
        if a.get("minutes") is not None:
            phases[a["phase"]] = max(phases.get(a["phase"], 0.0), a["minutes"])
    return {"phase_minutes": phases, "run_minutes": round(sum(phases.values()), 2) if phases else None}


def call(agent, *args):
    """One agent call; an exception (an odd transcript, say) marks only this call failed."""
    try:
        return agent(*args)
    except Exception as exc:  # noqa: BLE001 - every other call of the phase has spent already
        return {"cost": None, "minutes": None, "result": None, "error": f"{type(exc).__name__}: {exc}"}


def run_pick(case_dir, setup, setup_path, sid, pick, budget_left, agent, run_id, out_dir, prior=None):
    """All agents of one planned pick, then the refuter and the checker. Returns the result entry.
    With prior (an incomplete entry of the same run), only the roles it did not finish run again;
    the finished ones' reports and costs are reused. The refuter's is reused only when no reviewer reruns."""
    prior_roles = (prior or {}).get("roles", {})
    prior_done = {k for k, v in prior_roles.items() if v and k not in ("refuter", "checker")}
    name = os.path.basename(case_dir)
    folder = prepare_folder(case_dir)
    spent = reviewers = 0.0
    agents, reports, reason, values, todo, roles = [], [], None, {}, [], []
    try:
        sdir = os.path.dirname(setup_path)
        slices = cut_slices(snapshot_files(folder["snap"]), setup["size_rule"])
        common = {"snap": folder["snap"], "head_sha": folder["head"], "primary": folder["snap"],
                  "diff": folder["diff"], "target_branch": "base", "base_sha": folder["base"],
                  "title": f"Benchmark snapshot {name}", "description": "none", "run_tmp": folder["run_tmp"],
                  "lenses": "none", "conventions": "none"}
        jobs = []
        for s in slices:
            files = ", ".join(f"{f['path']} (lines {f['range'][0]}-{f['range'][1]} of {f['lines']})" if "range" in f
                              else f"{f['path']} ({f['lines']} lines)" for f in s["files"])
            report = os.path.join(out_dir, f"{run_id}-slice-{s['slice']}.md")
            jobs.append((f"slice-{s['slice']}", render(os.path.join(sdir, setup["brief_template"]),
                                                       dict(common, slice_files=files, report=work_path(folder["run_tmp"], report))), report,
                         s["load"]))
        mean_load = sum(s["load"] for s in slices) / len(slices) if slices else 1
        for extra in setup.get("extra_agents", []):
            if extra["role"] == "run-it":
                report = os.path.join(out_dir, f"{run_id}-runit.md")
                runnable = ", ".join(f["path"] for f in snapshot_files(folder["snap"])
                                     if f["path"].endswith((".sh", ".json")) or "/scripts/" in f["path"])
                jobs.append(("runit", render(os.path.join(sdir, setup["run_it_template"]),
                                             dict(common, runnable=runnable, report=work_path(folder["run_tmp"], report))), report, mean_load))
        roles = [j[0] for j in jobs] + ["refuter", "checker"]
        reports = [j[2] for j in jobs if j[0] in prior_done]
        todo = [j for j in jobs if j[0] not in prior_done]
        refute_report = os.path.join(out_dir, f"{run_id}-refute.md")
        if prior_roles.get("refuter") and not todo and os.path.exists(refute_report):
            prior_done.add("refuter")
        est = pick.get("estimate") or {}
        rev_est = est.get("reviewers", est.get("usd") or 0.0) * len(todo) / max(len(jobs), 1)
        ref_est = 0.0 if "refuter" in prior_done else est.get("refuter", 0.0)
        chk_est = est.get("checker", 0.0)
        # phase 1: every slice owner and the run-it agent at once; each call may use the whole phase cap
        # (the cap minus the refuter's and checker's estimates), and the run stops after the phase if the
        # total passed it, so parallel calls can pass the cap by up to the estimate's error
        phase_cap = budget_left - ref_est - chk_est
        if todo and phase_cap < max(rev_est, MIN_BUDGET):
            reason = (f"cap ${budget_left:.2f} does not cover the reviewer phase estimate ${rev_est:.2f} "
                      f"plus the refuter's and the checker's")
        elif todo:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(todo)) as pool:
                futs = [(role, report, pool.submit(call, agent, prompt, pick["model"], pick["effort"], phase_cap,
                                                   f"bench-{name}-{run_id}-{role}", folder["snap"], case_dir))
                        for role, prompt, report, _ in todo]
                for role, report, fut in futs:
                    r = fut.result()
                    spent += r.get("cost") or 0.0
                    save_reply(report, r.get("result"), work_path(folder["run_tmp"], report))
                    problem = None if r.get("error") else report_problem(report)
                    if problem:
                        r = dict(r, error=problem)
                    agents.append(dict(r, role=role, phase="reviewers"))
                    reports.append(report)
                    if r.get("error") and not reason:
                        reason = f"{role} stopped: {r['error']}"
            reviewers = spent
            if not reason and spent > phase_cap:
                reason = f"reviewer phase spent ${spent:.2f}, above its cap ${phase_cap:.2f}"
        # phase 2: the refuter, only on full reports (reused ones included)
        bad = [os.path.basename(x) for x in reports if report_problem(x)]
        if not reason and bad:
            reason = f"reports not saved: {', '.join(bad)}"
        values = {"snap": folder["snap"], "reports": ", ".join(reports), "report_count": len(reports),
                  "key": os.path.join(case_dir, "answer-key.md")}  # the checker reads the kept copies
        if not reason and "refuter" not in prior_done and budget_left - spent - chk_est < max(ref_est, MIN_BUDGET):
            reason = f"cap reached before refuter could start (remaining ${budget_left - spent:.2f}, estimate ${ref_est:.2f})"
        if not reason and "refuter" not in prior_done:
            ref = setup["refuter"]
            work = [work_path(folder["run_tmp"], x) for x in reports]
            for src, dst in zip(reports, work):
                if os.path.exists(src) and not os.path.exists(dst):
                    shutil.copyfile(src, dst)
            prompt = render(os.path.join(case_dir, ref["brief"]), dict(values, key="", reports=", ".join(work))) + \
                f"\n\nReport path: {work_path(folder['run_tmp'], refute_report)}"
            r = call(agent, prompt, ref["model"], ref["effort"], budget_left - spent, f"bench-{name}-{run_id}-refuter",
                     folder["snap"], case_dir)
            spent += r.get("cost") or 0.0
            save_reply(refute_report, r.get("result"), work_path(folder["run_tmp"], refute_report))
            agents.append(dict(r, role="refuter", phase="refuter"))
            if r.get("error"):
                reason = f"refuter stopped: {r['error']}"
    finally:
        shutil.rmtree(folder["root"], ignore_errors=True)

    base_rev = (prior or {}).get("cost") or 0.0

    def merged(entry, total):
        """Per-role cost of each finished role's good attempt; cost fields count only those (the clean run),
        spent_total counts every call of every attempt. A resumed run adds the prior part: the reused roles'
        costs and its slowest reviewer."""
        entry.update(phase_times(agents))
        role_costs = {a["role"]: round(a.get("cost") or 0.0, 4) for a in agents if not a.get("error")}
        reused = {k: v for k, v in (prior or {}).get("role_costs", {}).items() if k in prior_done}
        entry["role_costs"] = dict(reused, **role_costs)
        entry["spent_total"] = round(total + ((prior or {}).get("spent_total") or 0.0), 4)
        if entry["status"] == "incomplete":
            rc = entry["role_costs"]
            entry["cost"] = round(sum(v for k, v in rc.items() if k not in ("refuter", "checker")), 4)
            entry["cost_with_refuter"] = round(sum(v for k, v in rc.items() if k != "checker"), 4)
        elif prior:
            add_all = sum(reused.values()) if prior.get("role_costs") else base_rev
            add_rev = sum(v for k, v in reused.items() if k != "refuter") if prior.get("role_costs") else base_rev
            entry["cost"] = round(entry["cost"] + add_rev, 4)
            entry["cost_with_refuter"] = round(entry["cost_with_refuter"] + add_all, 4)
        if prior:
            old = (prior.get("phase_minutes") or {}).get("reviewers")
            if old is not None:
                entry["phase_minutes"]["reviewers"] = max(old, entry["phase_minutes"].get("reviewers", 0.0))
                entry["run_minutes"] = round(sum(entry["phase_minutes"].values()), 2)
                if entry.get("status") == "complete":
                    entry["slowest_agent_min"] = max(old, entry.get("slowest_agent_min") or 0.0)
            rerun = ", ".join(j[0] for j in todo) or "no reviewer"
            entry["resumed"] = f"resumed: {rerun} rerun" + ("; refuter reused" if "refuter" in prior_done else "")
        entry.update(case_hashes(case_dir))
        entry.update(brief_hashes(case_dir, setup, setup_path))
        return entry

    def incomplete(total):
        finished = {a["role"] for a in agents if not a.get("error")} | prior_done
        entry = {"id": run_id, "model": pick["model"], "effort": pick["effort"], "setup_id": sid,
                 "status": "incomplete", "reason": reason, "caught_strict": None, "caught_with_partials": None,
                 "roles": {role: role in finished for role in roles}, "date": dt.date.today().isoformat()}
        return merged(entry, total), total, agents
    if not reason and budget_left - spent < MIN_BUDGET:
        reason = "cap reached before checker could start"
    if reason:
        return incomplete(spent)
    # the checker needs the key, so it runs outside the agent folder and is not part of the run's cost
    chk = setup["checker"]
    check_report = os.path.join(out_dir, f"{run_id}-check.md")
    check_dir = tempfile.mkdtemp(prefix="bench-check.")
    try:
        c = call(agent, render(os.path.join(case_dir, chk["brief"]), values) + f"\n\nReport path: {check_report}",
                 chk["model"], chk["effort"], budget_left - spent, f"bench-{name}-{run_id}-checker", check_dir, None)
    finally:
        shutil.rmtree(check_dir, ignore_errors=True)
    checker_cost = c.get("cost") or 0.0
    if c.get("error"):
        agents.append(dict(c, role="checker", phase="checker"))
        reason = f"checker stopped: {c['error']}"
        return incomplete(spent + checker_cost)
    text = c.get("result") or ""
    if os.path.exists(check_report):
        with open(check_report, encoding="utf-8") as fh:
            text = fh.read()
    strict, partial = parse_score(text)
    if strict is None:
        agents.append(dict(c, role="checker", phase="checker", error="no SCORE line"))
        reason = "checker gave no SCORE line"
        return incomplete(spent + checker_cost)
    reqs = sum(a.get("requests") or 0 for a in agents)
    over = sum(a.get("over_100k") or 0 for a in agents)
    entry = {"id": run_id, "model": pick["model"], "effort": pick["effort"], "setup_id": sid, "status": "complete",
             "caught_strict": strict, "caught_with_partials": strict + partial / 2,
             "cost": round(reviewers, 4), "cost_with_refuter": round(spent, 4),
             "slowest_agent_min": max((a["minutes"] for a in agents if a.get("minutes") is not None), default=None),
             "walltime_method": "active time, gaps over 5 min left out", "over_100k_share":
                 round(over / reqs, 4) if reqs else None,
             "checker": f"{chk['model']} {chk['effort']}", "date": dt.date.today().isoformat()}
    agents.append(dict(c, role="checker", phase="checker"))
    entry["checker_cost"] = round(checker_cost, 4)
    return merged(entry, spent + checker_cost), spent + checker_cost, agents


def store(case_dir, entry):
    if not is_repo_checkout(case_dir):
        raise RuntimeError(f"{case_dir} is not a repo checkout; results are written only there")
    path = os.path.join(case_dir, "results.json")
    md = os.path.join(case_dir, "RESULTS.md")
    with open(md, encoding="utf-8") as fh:
        lines = [l for l in fh.read().split("\n") if not l.startswith(f"| {entry['id']} | {entry['setup_id']} |")]
    head = next((i for i, l in enumerate(lines) if l.startswith("| Run | Setup | Model")), None)
    if head is None:  # checked before results.json changes, so the two files stay in step
        raise RuntimeError(f"{md} has no '| Run | Setup | Model' table; nothing stored")
    data = load_json(path)
    data["runs"] = [r for r in data.get("runs", []) if r.get("id") != entry["id"]] + [entry]
    prices.write_atomic(path, json.dumps(data, indent=1) + "\n")
    end = head + 2
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    def f(v, fmt="{}"):
        return "n/a" if v is None else fmt.format(v)
    note = f"; {entry['resumed']}" if entry.get("resumed") else ""
    spent = (f"; spent ${entry['spent_total']:.2f} with broken attempts"
             if entry.get("spent_total") and entry["spent_total"] - entry["cost_with_refuter"] - (entry.get("checker_cost") or 0) > 0.005
             else "")
    if entry.get("status") == "incomplete":
        done = ", ".join(k for k, v in entry["roles"].items() if v) or "none"
        lines.insert(end, f"| {entry['id']} | {entry['setup_id']} | {entry['model']} {entry['effort']} | "
                          f"incomplete: {entry['reason']}; finished: {done}{note} | "
                          f"${entry['cost']:.2f} (${entry['cost_with_refuter']:.2f}) | n/a | {entry['date']} |")
        with open(md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        return
    lines.insert(end, f"| {entry['id']} | {entry['setup_id']} | {entry['model']} {entry['effort']} | "
                      f"{f(entry['caught_strict'])} / {f(entry['caught_with_partials'])}{note} | "
                      f"${entry['cost']:.2f} (${entry['cost_with_refuter']:.2f}){spent} | "
                      f"{f(entry['slowest_agent_min'], '{:.1f} min')} | {entry['date']} |")
    with open(md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def run(case_dir, the_plan, cap, agent=claude_agent, out_root=OUT_ROOT, store_fn=store, claude_md_texts=(),
        resume=None):
    """Runs each pick once while its estimate fits the remaining cap; every call gets the remaining cap as budget."""
    if store_fn is store and not is_repo_checkout(case_dir):  # checked before any call spends
        raise RuntimeError(f"{case_dir} is not a repo checkout; results are written only there. "
                           "Pass the case folder of a marketplace checkout.")
    results = load_json(os.path.join(case_dir, "results.json"))
    all_setups = setups(case_dir)
    sid = the_plan["setup_id"]
    if sid not in all_setups:
        raise RuntimeError(f"setup {sid} not found or changed; plan again")
    setup, setup_path = all_setups[sid]
    current = current_model(results, sid, claude_md_texts)
    out_dir = os.path.join(out_root, os.path.basename(case_dir), "runs")
    os.makedirs(out_dir, exist_ok=True)
    remaining = float(cap)
    done, stopped = [], []
    prior = None
    if resume:
        prior = next((r for r in results.get("runs", []) if r.get("id") == resume), None)
        if not prior or is_complete(prior) or prior.get("setup_id") != sid:
            raise RuntimeError(f"run {resume} is not an incomplete run of setup {sid}")
        if not any((p["model"], p["effort"]) == (prior["model"], prior["effort"]) for p in the_plan["picks"]):
            raise RuntimeError(f"the plan has no pick for run {resume} ({prior['model']} {prior['effort']}); "
                               "plan with --models and --effort for it")
    for pick in the_plan["picks"]:
        if prior and (pick["model"], pick["effort"]) != (prior["model"], prior["effort"]):
            continue
        stored = {(r.get("model"), r.get("effort"), r.get("setup_id")) for r in results.get("runs", []) if is_complete(r)}
        if (pick["model"], pick["effort"], sid) in stored:
            stopped.append({"pick": pick, "reason": "already has a result in this setup"})
            continue
        est = (pick.get("estimate") or {}).get("usd")
        if prior and est is not None:  # only the unfinished part runs again
            roles = prior.get("roles") or {}
            reviewers_done = all(v for k, v in roles.items() if k not in ("refuter", "checker"))
            refuter = (prior.get("role_costs") or {}).get("refuter", 0.0) if roles.get("refuter") and reviewers_done else 0.0
            est = est - (prior.get("cost") or 0.0) - refuter
        if est is None or est > remaining:
            stopped.append({"pick": pick, "reason": "no estimate" if est is None else
                            f"estimate ${est:.2f} is above the remaining cap ${remaining:.2f}"})
            continue
        run_id = prior["id"] if prior else next_run_id(results)
        entry, spent, agents = run_pick(case_dir, setup, setup_path, sid, pick, remaining, agent, run_id, out_dir, prior)
        remaining -= spent
        store_fn(case_dir, entry)
        results["runs"] = [r for r in results.get("runs", []) if r.get("id") != run_id] + [entry]
        done.append({"entry": entry, "spent": round(spent, 4), "remaining_cap": round(remaining, 4),
                     "status": entry["status"], "repeat_proposed": propose_repeat(entry["caught_strict"], current),
                     "agents": [{k: a.get(k) for k in ("role", "cost", "cli_cost", "minutes", "error")} for a in agents]})
    return {"runs": done, "not_run": stopped, "remaining_cap": round(remaining, 4), "current": current}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("action", choices=("plan", "run", "status"))
    p.add_argument("case")
    p.add_argument("--setup")
    p.add_argument("--models", help="comma-separated model ids (default: Anthropic models in --external)")
    p.add_argument("--external", help="output of models.py --external")
    p.add_argument("--usage", help="output of models.py --usage, for the case skill's most used effort")
    p.add_argument("--effort", help="with plan: one fixed effort per model instead of the AA and usage picks")
    p.add_argument("--plan", help="with run: output of bench.py plan")
    p.add_argument("--cap", type=float)
    p.add_argument("--resume", help="with run: id of an incomplete run; reruns only its unfinished agents")
    p.add_argument("--claude-md", action="append", default=[], help="CLAUDE.md files with a ## Models section, in order")
    a = p.parse_args(argv)
    case_dir = os.path.join(BENCH_DIR, a.case) if not os.path.isdir(a.case) else os.path.abspath(a.case)
    texts = []
    for path in a.claude_md:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                texts.append(fh.read())
    if a.action == "plan":
        ext = load_json(a.external)["rows"] if a.external else None
        effort = None
        if a.usage:
            skill = load_json(os.path.join(case_dir, "results.json")).get("skill")
            effort = next((s["effort"] for s in load_json(a.usage)["skills"] if scan.skill_display(s["skill"]) == skill),
                          None)
            effort = effort if effort in EFFORTS else None  # a placeholder such as "?" never reaches --effort
        models = a.models.split(",") if a.models else None
        out = plan(case_dir, a.setup, models, ext, effort, claude_md_texts=texts, fixed_effort=a.effort)
    elif a.action == "run":
        if a.cap is None or not a.plan:
            p.error("run needs --plan and --cap")
        out = run(case_dir, load_json(a.plan), a.cap, claude_md_texts=texts, resume=a.resume)
    else:
        results = load_json(os.path.join(case_dir, "results.json"))
        out = {"setups": sorted(setups(case_dir)), "comparability": comparability(results, case_dir),
               "slices": {sid: [{"slice": s["slice"], "load": s["load"], "files": len(s["files"])}
                                for s in cut_slices(snapshot_files(os.path.join(case_dir, "snap")), st["size_rule"])]
                          for sid, (st, _) in setups(case_dir).items()}}
    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
