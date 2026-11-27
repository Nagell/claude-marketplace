#!/usr/bin/env python3
"""Read Claude Code transcripts on demand: skill runs, their agents, deduped requests and cost.

Reads ~/.claude/projects/<project>/<session>.jsonl and <session>/subagents/agent-<id>.jsonl
(+ .meta.json). Never writes. Stdlib only, Python 3.9+.

    python3 scan.py --days 30 [--projects-dir DIR] [--prices FILE] [--override FILE]
"""
import argparse
import collections
import datetime as dt
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices  # noqa: E402

def config_dir():
    """Claude Code's config folder: CLAUDE_CONFIG_DIR when set, else ~/.claude."""
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


PROJECTS_DIR = os.path.join(config_dir(), "projects")
SYNTHETIC = "<synthetic>"
LONG_PROMPT = 100_000
NO_SKILL = None
NOT_TYPED_PREFIXES = ("<task-notification>", "<local-command", "<bash-")
BUILTIN_COMMANDS = {
    "add-dir", "agents", "bug", "clear", "compact", "config", "context", "cost", "doctor", "exit",
    "export", "fast", "feedback", "help", "hooks", "ide", "keybindings", "login", "logout", "mcp",
    "memory", "model", "permissions", "plugin", "plugins", "pr-comments", "privacy-settings",
    "quit", "release-notes", "reload-plugins", "reload-skills", "rename", "resume", "rewind",
    "sandbox", "status", "statusline", "terminal-setup", "theme", "upgrade", "usage", "vim",
}
TOKEN_FIELDS = ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")


# ---------- parsing ----------

def parse_ts(value):
    if not isinstance(value, str):
        return None
    try:
        t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def read_jsonl(path):
    """Parsed lines and the count of lines that could not be parsed."""
    entries, skipped = [], 0
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                if not raw.strip():
                    continue
                try:
                    obj = json.loads(raw)
                except ValueError:
                    skipped += 1
                    continue
                if isinstance(obj, dict):
                    entries.append(obj)
                else:
                    skipped += 1
    except OSError:
        skipped += 1
    return entries, skipped


def first_ts(entries):
    for e in entries:
        t = parse_ts(e.get("timestamp"))
        if t:
            return t
    return None


def content_of(e):
    msg = e.get("message")
    return msg.get("content") if isinstance(msg, dict) else None


def is_typed_prompt(e):
    if e.get("type") != "user" or e.get("isCompactSummary"):
        return False
    origin = e.get("origin")
    if isinstance(origin, dict):
        return origin.get("kind") == "human"
    if "origin" in e and origin is not None:
        return False
    c = content_of(e)
    if not isinstance(c, str) or e.get("isMeta") or e.get("toolUseResult") is not None:
        return False
    return not c.lstrip().startswith(NOT_TYPED_PREFIXES)


def command_name(e):
    c = content_of(e)
    if e.get("type") != "user" or not isinstance(c, str) or "<command-name>" not in c:
        return None
    name = c.split("<command-name>", 1)[1].split("</command-name>", 1)[0].strip()
    return name.lstrip("/") or None


def is_skill_load(e):
    if e.get("type") != "user" or not e.get("isMeta"):
        return False
    return "Base directory for this skill" in json.dumps(content_of(e) or "")


def tool_uses(e):
    c = content_of(e)
    if not isinstance(c, list):
        return []
    return [b for b in c if isinstance(b, dict) and b.get("type") == "tool_use"]


def final_text(entries):
    """Text of the last assistant line that has text."""
    for e in reversed(entries):
        if e.get("type") != "assistant":
            continue
        c = content_of(e)
        if isinstance(c, str) and c.strip():
            return c
        if isinstance(c, list):
            texts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"]
            if any(t.strip() for t in texts):
                return "\n".join(texts)
    return ""


def report_text(entries):
    """Content of the agent's last Write to a .txt or .md file: review-mr agents write their report there."""
    for e in reversed(entries):
        for b in reversed(tool_uses(e)):
            inp = b.get("input") if isinstance(b.get("input"), dict) else {}
            path = str(inp.get("file_path") or "")
            if b.get("name") == "Write" and path.endswith((".txt", ".md")) and isinstance(inp.get("content"), str):
                return inp["content"]
    return ""


def asks_user(e):
    """True when an assistant line ends its turn by asking the user something."""
    c = content_of(e)
    if isinstance(c, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "AskUserQuestion" for b in c):
            return True
        text = "\n".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    elif isinstance(c, str):
        text = c
    else:
        return False
    return text.rstrip().endswith("?")


def count_unfinished(text):
    return sum(1 for line in text.splitlines() if line.lstrip().startswith("Unfinished:"))


# ---------- requests and dedupe ----------

class Counters:
    def __init__(self):
        self.skipped_lines = 0
        self.api_errors = 0
        self.unpriced = collections.Counter()


def collect_requests(entries, seen, table, counters, key="", since=None):
    """Deduped requests of one file, in order: {id: request}. Ids in `seen` (earlier files) are dropped.

    Each request keeps the largest value per usage field over its lines.
    """
    reqs = collections.OrderedDict()
    anon = 0
    for idx, e in enumerate(entries):
        if e.get("type") != "assistant":
            continue
        msg = e.get("message")
        if not isinstance(msg, dict):
            counters.skipped_lines += 1
            continue
        model = msg.get("model")
        if model is not None and not isinstance(model, str):
            counters.skipped_lines += 1
            continue
        if model == SYNTHETIC:
            mid = msg.get("id")
            if mid and (mid in seen or mid in reqs):
                continue
            t = parse_ts(e.get("timestamp"))
            if since is None or (t and t >= since):
                counters.api_errors += 1
            if mid:
                reqs[mid] = None  # placeholder so later lines of the same error are not counted again
            continue
        usage = msg.get("usage")
        if not isinstance(usage, dict):
            counters.skipped_lines += 1
            continue
        mid = msg.get("id")
        if not mid:
            anon += 1
            mid = f"__{key}#line{idx}_{anon}"
        if mid in seen:
            continue
        tokens = prices.token_classes(usage)
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in tokens.values()):
            counters.skipped_lines += 1
            continue
        r = reqs.get(mid)
        if r is None:
            reqs[mid] = {
                "id": mid, "line": idx, "model": model, "effort": e.get("effort"),
                "ts": parse_ts(e.get("timestamp")), "tokens": tokens,
                "skill": e.get("attributionSkill"), "speed": usage.get("speed"),
            }
        else:
            for f in TOKEN_FIELDS:
                r["tokens"][f] = max(r["tokens"][f], tokens[f])
    out = collections.OrderedDict()
    for mid, r in reqs.items():
        seen.add(mid)
        if r is None:
            continue
        r["prompt"] = prices.prompt_size(r["tokens"])
        r["cost"] = prices.request_cost(table, r["model"], r["tokens"], r["speed"])
        if r["cost"] is None and (since is None or (r["ts"] and r["ts"] >= since)):
            counters.unpriced[r["model"] or "unknown"] += 1
        out[mid] = r
    return out


def empty_totals():
    return {"requests": 0, "tokens": {f: 0 for f in TOKEN_FIELDS}, "cost": 0.0,
            "unpriced_requests": 0, "largest_prompt": 0, "over_100k": 0, "fast_requests": 0, "by_model": {}}


def add_request(tot, r):
    tot["requests"] += 1
    for f in TOKEN_FIELDS:
        tot["tokens"][f] += r["tokens"][f]
    if r["cost"] is None:
        tot["unpriced_requests"] += 1
    else:
        tot["cost"] += r["cost"]
    tot["largest_prompt"] = max(tot["largest_prompt"], r["prompt"])
    if r["prompt"] > LONG_PROMPT:
        tot["over_100k"] += 1
    if r.get("speed") == "fast":
        tot["fast_requests"] += 1
    m = tot["by_model"].setdefault(f"{r['model']} / {r.get('effort') or '?'}", {"requests": 0, "cost": 0.0})
    m["requests"] += 1
    m["cost"] += r["cost"] or 0.0


def merge_totals(a, b):
    a["requests"] += b["requests"]
    for f in TOKEN_FIELDS:
        a["tokens"][f] += b["tokens"][f]
    a["cost"] += b["cost"]
    a["unpriced_requests"] += b["unpriced_requests"]
    a["largest_prompt"] = max(a["largest_prompt"], b["largest_prompt"])
    a["over_100k"] += b["over_100k"]
    a["fast_requests"] += b.get("fast_requests", 0)
    for k, v in b.get("by_model", {}).items():
        m = a["by_model"].setdefault(k, {"requests": 0, "cost": 0.0})
        m["requests"] += v["requests"]
        m["cost"] += v["cost"]


def iso(t):
    return t.isoformat().replace("+00:00", "Z") if t else None


# ---------- agents ----------

def read_meta(agent_path):
    meta_path = agent_path[: -len(".jsonl")] + ".meta.json"
    try:
        with open(meta_path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def agent_id_of(path):
    base = os.path.basename(path)
    return base[len("agent-"): -len(".jsonl")] if base.startswith("agent-") else base


def _summarize(path, entries, reqs, meta, since=None):
    tot = empty_totals()
    models, efforts = collections.Counter(), collections.Counter()
    times = []
    for r in reqs.values():
        if since and (r["ts"] is None or r["ts"] < since):
            continue
        add_request(tot, r)
        models[r["model"]] += 1
        if r["effort"]:
            efforts[r["effort"]] += 1
    for e in entries:
        t = parse_ts(e.get("timestamp"))
        if t:
            times.append(t)
    tot["cost"] = round(tot["cost"], 6)
    return {
        "agent_id": agent_id_of(path),
        "path": path,
        "agent_type": meta.get("agentType"),
        "description": meta.get("description"),
        "requested_model": meta.get("model"),
        "requested_effort": meta.get("effort"),
        "model": models.most_common(1)[0][0] if models else None,
        "effort": efforts.most_common(1)[0][0] if efforts else None,
        **tot,
        "duration_s": round((max(times) - min(times)).total_seconds(), 1) if times else None,
        "start": iso(min(times)) if times else None,
        "unfinished": count_unfinished(final_text(entries) + "\n" + report_text(entries)),
        "finished": meta.get("finished"),
        "spawn_depth": meta.get("spawnDepth"),
        "parent_agent_id": meta.get("parentAgentId"),
        "tool_use_id": meta.get("toolUseId"),
        "skill_attribution": collections.Counter(
            e.get("attributionSkill") for e in entries
            if e.get("type") == "assistant" and e.get("attributionSkill")).most_common(1),
    }


def summarize_agent(path, table=None, seen=None, counters=None, since=None):
    """Deduped requests, token classes, prompt sizes and cost of one agent transcript."""
    table = table or prices.PriceTable()
    counters = counters or Counters()
    entries, skipped = read_jsonl(path)
    counters.skipped_lines += skipped
    reqs = collect_requests(entries, set() if seen is None else seen, table, counters, path, since)
    out = _summarize(path, entries, reqs, read_meta(path), since)
    out["skipped_lines"] = skipped
    return out, entries


# ---------- runs ----------

def detect_runs(entries, reqs, session_key):
    """Runs of one session file and the run of each request id and each Agent tool_use id.

    A skill loaded inside an open run (openspec-grill loading grilling) stays in that run, listed under
    `nested`. After a typed prompt, the last run reopens when the skill was not invoked again (a skill
    command, a skill-load line or a Skill tool_use) and either the next line carries the same
    `attributionSkill` or the run's last turn asked the user something: Claude Code drops the attribution
    on the turns that answer a reply, so an interactive skill would otherwise lose them to "no skill".
    """
    has_attr = any(e.get("type") == "assistant" and e.get("attributionSkill") for e in entries)
    runs, req_run, tool_run = [], {}, {}
    cur = last = None
    invoked = asked = follow = False
    line_req = {r["line"]: mid for mid, r in reqs.items()}
    pending_cmd = None

    def start(skill, t):
        nonlocal cur
        cur = {"run_id": f"{session_key}#{len(runs) + 1}", "skill": skill, "start": t, "end": t, "nested": []}
        runs.append(cur)

    def enter(skill, t):
        nonlocal cur
        if cur is None:
            if last is not None and last["skill"] == skill and not invoked:
                cur = last
            else:
                start(skill, t)
        elif cur["skill"] != skill and skill not in cur["nested"]:
            cur["nested"].append(skill)

    for idx, e in enumerate(entries):
        t = parse_ts(e.get("timestamp"))
        if is_typed_prompt(e):
            follow = bool(cur) and asked
            if cur:
                cur["end"] = t or cur["end"]
                last = cur
            cur = None
            asked = False
            name = command_name(e)
            # a plugin skill (name with ":") starts at once; an unknown command only when a skill-load line follows
            is_skill_cmd = bool(name) and ":" in name
            invoked = is_skill_cmd
            pending_cmd = None
            if name and not has_attr:
                if is_skill_cmd:
                    start(name, t)
                elif name not in BUILTIN_COMMANDS:
                    pending_cmd = name
            continue
        if is_skill_load(e):
            invoked = True
            if pending_cmd:
                start(pending_cmd, t)
                pending_cmd = None
        if e.get("type") != "assistant":
            continue
        skill_calls = []
        for b in tool_uses(e):
            if b.get("name") == "Skill":
                inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                name = inp.get("skill") or inp.get("command") or inp.get("name")
                if name:
                    skill_calls.append(str(name).lstrip("/"))
        attributed = has_attr and e.get("attributionSkill")
        if cur is None and follow and not invoked and last is not None and not skill_calls and not attributed:
            cur = last
        if has_attr:
            skill = e.get("attributionSkill")
            if skill:
                enter(skill, t)
            if skill_calls:
                invoked = True
        else:
            if skill_calls:
                pending_cmd = None
            for name in skill_calls:
                if cur is None:
                    start(name, t)
                elif cur["skill"] != name and name not in cur["nested"]:
                    cur["nested"].append(name)
        if cur and t:
            cur["end"] = t
        asked = bool(cur) and asks_user(e)
        run = cur["run_id"] if cur else None
        mid = line_req.get(idx)
        if mid:
            req_run[mid] = run
        for b in tool_uses(e):
            if b.get("name") in ("Agent", "Task") and b.get("id"):
                tool_run[b["id"]] = run
    return runs, req_run, tool_run


def skill_display(name):
    return name.split(":", 1)[1] if name and ":" in name else name


# ---------- scan ----------

def is_bench_session(entries):
    """A session named `bench-...` (claude -p -n bench-...) is a benchmark run, not normal usage."""
    for e in entries:
        if e.get("type") == "custom-title" and str(e.get("customTitle") or "").startswith("bench-"):
            return True
    return False


def find_sessions(projects_dir, since_epoch):
    out = []
    for path in glob.glob(os.path.join(projects_dir, "*", "*.jsonl")):
        session_dir = path[: -len(".jsonl")]
        agents = [a for a in glob.glob(os.path.join(session_dir, "subagents", "**", "agent-*.jsonl"), recursive=True)
                  if os.path.getmtime(a) >= since_epoch]
        if os.path.getmtime(path) >= since_epoch or agents:
            out.append((path, agents))
    return out


def scan(days=30, projects_dir=PROJECTS_DIR, table=None, now=None):
    table = table or prices.PriceTable()
    now = now or dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(days=days)
    counters = Counters()
    seen = set()
    loaded = []
    bench_sessions = 0
    for path, agents in find_sessions(projects_dir, since.timestamp()):
        entries, skipped = read_jsonl(path)
        if is_bench_session(entries):
            bench_sessions += 1
            continue
        counters.skipped_lines += skipped
        loaded.append((first_ts(entries) or now, len(entries), path, entries, agents))
    # a resumed session copies its parent's history, so on equal first timestamps the shorter file is the parent
    loaded.sort(key=lambda x: (x[0], x[1], x[2]))

    runs_out, no_skill = [], empty_totals()
    files_read = 0
    warnings = []
    if not os.path.isdir(projects_dir):
        warnings.append(f"{projects_dir} does not exist")
    all_runs = collections.OrderedDict()
    tool_owner = {}  # Agent tool_use id -> run, first file wins (a resumed session copies its parent's ids)
    for _, _, path, entries, agent_paths in loaded:
        files_read += 1
        project = os.path.basename(os.path.dirname(path))
        session = os.path.basename(path)[: -len(".jsonl")]
        reqs = collect_requests(entries, seen, table, counters, path, since)
        runs, req_run, tool_run = detect_runs(entries, reqs, session)
        for r in runs:
            all_runs[r["run_id"]] = dict(r, project=project, session=session, own=empty_totals(), agents=[])
        for tid, rid in tool_run.items():
            tool_owner.setdefault(tid, rid)
        for mid, r in reqs.items():
            if r["ts"] is None or r["ts"] < since:
                continue
            run = all_runs.get(req_run.get(mid))
            add_request(run["own"] if run else no_skill, r)

        # agents: parents first, so a nested agent finds its parent's run
        summaries = []
        for ap in agent_paths:
            files_read += 1
            s, a_entries = summarize_agent(ap, table, seen, counters, since)
            summaries.append((s, a_entries))
        summaries.sort(key=lambda x: (x[0]["spawn_depth"] if isinstance(x[0]["spawn_depth"], int) else 1,
                                      x[0]["start"] or ""))
        agent_run = {}
        for s, a_entries in summaries:
            run_id = tool_owner.get(s["tool_use_id"]) if s["tool_use_id"] in tool_owner else None
            if run_id is None and s["parent_agent_id"]:
                run_id = agent_run.get(s["parent_agent_id"])
            if run_id is None and s["tool_use_id"] not in tool_owner:
                run_id = _run_by_time(runs, s)
            agent_run[s["agent_id"]] = run_id
            for e in a_entries:
                for b in tool_uses(e):
                    if b.get("name") in ("Agent", "Task") and b.get("id"):
                        tool_owner.setdefault(b["id"], run_id)
            del s["skill_attribution"]
            if run_id and run_id in all_runs:
                all_runs[run_id]["agents"].append(s)
            elif s["requests"]:
                merge_totals(no_skill, s)

    for run in all_runs.values():
        total = empty_totals()
        merge_totals(total, run["own"])
        for a in run["agents"]:
            merge_totals(total, a)
        if not total["requests"]:
            continue
        total["cost"] = round(total["cost"], 6)
        run["own"]["cost"] = round(run["own"]["cost"], 6)
        runs_out.append({
            "run_id": run["run_id"], "skill": run["skill"], "skill_display": skill_display(run["skill"]),
            "project": run["project"], "session": run["session"],
            "start": iso(run["start"]), "end": iso(run["end"]), "nested_skills": run["nested"],
            "total": total, "own": run["own"], "agents": run["agents"],
        })

    # Unfinished: is review-mr's convention (its agents write it into their report); n/a for other skills
    uses = {r["skill"]: skill_display(r["skill"]) == "review-mr" for r in runs_out}
    for r in runs_out:
        r["unfinished_convention"] = uses[r["skill"]]
        for a in r["agents"]:
            if not uses[r["skill"]]:
                a["unfinished"] = None
        r["total"]["unfinished"] = (sum(a["unfinished"] for a in r["agents"]) if uses[r["skill"]] else None)

    no_skill["cost"] = round(no_skill["cost"], 6)
    runs_out.sort(key=lambda r: r["start"] or "")
    return {
        "estimate": True,
        "window": {"days": days, "since": iso(since), "until": iso(now)},
        "prices": table.versions(),
        "files_read": files_read,
        "skipped_lines": counters.skipped_lines,
        "api_errors": counters.api_errors,
        "unpriced_models": dict(counters.unpriced),
        "warnings": warnings + ([] if files_read else
                                ["only benchmark sessions in the window, all left out" if bench_sessions
                                 else "no transcript files in the window"]),
        "runs": runs_out,
        "no_skill": no_skill,
    }


def _run_by_time(runs, s):
    """Fallback for an agent without a matching tool_use: its own attribution, then its start time."""
    start = parse_ts(s["start"])
    attr = s["skill_attribution"][0][0] if s["skill_attribution"] else None
    candidates = [r for r in runs if start and r["start"] and r["start"] <= start <= (r["end"] or start)]
    if attr:
        for r in candidates:
            if r["skill"] == attr:
                return r["run_id"]
        same = [r for r in runs if r["skill"] == attr and r["start"]]
        if same and start:
            before = [r for r in same if r["start"] <= start]
            pick = max(before, key=lambda r: r["start"]) if before else min(same, key=lambda r: r["start"])
            return pick["run_id"]
    return candidates[-1]["run_id"] if candidates else None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--projects-dir", default=PROJECTS_DIR)
    p.add_argument("--prices", default=prices.SEED_PATH, help="seed price table")
    p.add_argument("--override", default=prices.OVERRIDE_PATH, help="user price override")
    a = p.parse_args(argv)
    table = prices.PriceTable(a.prices, a.override)
    json.dump(scan(a.days, a.projects_dir, table), sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
