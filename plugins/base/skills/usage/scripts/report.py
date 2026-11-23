#!/usr/bin/env python3
"""Top skills by spend, trends, recent runs and outliers, and the transcript retention check.

    python3 report.py [--days 30] [--top 5] [--runs 5] [--scratch-root DIR]
    python3 report.py --retention
    python3 report.py --set-retention 180

Prints JSON. Only --set-retention writes, and only ~/.claude/settings.json. Stdlib only, Python 3.9+.
"""
import argparse
import collections
import datetime as dt
import glob
import json
import os
import statistics
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices  # noqa: E402
import scan  # noqa: E402

SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
DEFAULT_RETENTION = 30
TARGET_RETENTION = 180


def default_scratch_root():
    getuid = getattr(os, "getuid", None)
    return f"/tmp/claude-{getuid()}" if getuid else os.path.join(tempfile.gettempdir(), "claude")


# ---------- review-mr run.json ----------

def load_run_json(scratch_root, project, session):
    path = os.path.join(scratch_root, project, session, "scratchpad", "run.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("agents"), list):
        return None
    return data


def apply_run_json(run, data):
    """Label agents by role and slice, add Codex agents, count surviving findings per role."""
    by_id = {}
    for entry in data.get("agents", []):
        if isinstance(entry, dict) and entry.get("agent_id"):
            by_id[str(entry["agent_id"])] = entry
    matched = set()
    for a in run["agents"]:
        entry = by_id.get(a["agent_id"])
        if not entry:
            continue
        matched.add(a["agent_id"])
        a["role"] = entry.get("role") or a["role"]
        a["slice"] = entry.get("slice")
        a["label"] = " ".join(x for x in (a["role"], entry.get("slice")) if x)
        a["requested_model"] = entry.get("model", a.get("requested_model"))
        a["requested_effort"] = entry.get("effort", a.get("requested_effort"))
        a["source"] = "run.json"
    for entry in data.get("agents", []):
        if isinstance(entry, dict) and entry.get("model") == "codex" and str(entry.get("agent_id")) not in matched:
            run["agents"].append({
                "agent_id": entry.get("agent_id"), "role": entry.get("role"), "slice": entry.get("slice"),
                "label": " ".join(x for x in (entry.get("role"), entry.get("slice")) if x),
                "requested_model": "codex", "requested_effort": entry.get("effort"), "model": "codex",
                "cost": None, "requests": 0, "source": "run.json", "note": "Codex task: no Claude transcript",
            })
    # a finding's source and duplicates name a slice or a role
    name_role = {}
    for entry in data.get("agents", []):
        if isinstance(entry, dict):
            if entry.get("slice"):
                name_role[entry["slice"]] = entry.get("role")
            if entry.get("role"):
                name_role.setdefault(entry["role"], entry["role"])
    unique, repeated = collections.Counter(), collections.Counter()
    for f in data.get("findings") or []:
        if not isinstance(f, dict) or not f.get("survived"):
            continue
        if f.get("source"):
            unique[name_role.get(f["source"], f["source"])] += 1
        for d in f.get("duplicates") or []:
            repeated[name_role.get(d, d)] += 1
    run["findings_by_role"] = {r: {"unique": unique[r], "repeated": repeated[r]}
                               for r in sorted(set(unique) | set(repeated))}
    run["run_json"] = True


def label_agents(runs, scratch_root):
    review_runs = with_json = 0
    for run in runs:
        for a in run["agents"]:
            a["role"] = a.get("agent_type") or "unknown"
            a["label"] = a["role"]
            a["source"] = "meta"
        run["run_json"] = False
        if run["skill_display"] != "review-mr":
            continue
        review_runs += 1
        data = load_run_json(scratch_root, run["project"], run["session"])
        if data is None:
            continue
        # one run.json per session: the latest review run's; earlier runs keep meta labels
        latest = max((r for r in runs if r["session"] == run["session"] and r["skill_display"] == "review-mr"),
                     key=lambda r: r["start"] or "")
        if latest is run:
            apply_run_json(run, data)
            with_json += 1
    return {"review_runs": review_runs, "with_run_json": with_json}


# ---------- aggregation ----------

def role_costs(run):
    out = collections.defaultdict(lambda: {"agents": 0, "cost": 0.0, "unpriced": 0})
    for a in run["agents"]:
        r = out[a["role"]]
        r["agents"] += 1
        if a.get("cost") is None:
            r["unpriced"] += 1
        else:
            r["cost"] += a["cost"]
    return out


def trends(skill_runs):
    costs = [r["total"]["cost"] for r in skill_runs]
    by_role = collections.defaultdict(lambda: {"agents": 0, "cost": 0.0})
    by_model = collections.defaultdict(lambda: {"requests": 0, "cost": 0.0})
    by_month = collections.defaultdict(lambda: {"runs": 0, "cost": 0.0})
    reqs = over = 0
    for r in skill_runs:
        for role, v in role_costs(r).items():
            by_role[role]["agents"] += v["agents"]
            by_role[role]["cost"] += v["cost"]
        for a in r["agents"]:
            if a.get("model") == "codex":
                continue
            key = f"{a.get('model')} / {a.get('effort') or '?'}"
            by_model[key]["requests"] += a.get("requests", 0)
            by_model[key]["cost"] += a.get("cost") or 0.0
        if r["own"]["requests"]:
            by_model["main session"]["requests"] += r["own"]["requests"]
            by_model["main session"]["cost"] += r["own"]["cost"]
        reqs += r["total"]["requests"]
        over += r["total"]["over_100k"]
        month = (r["start"] or "")[:7] or "unknown"
        by_month[month]["runs"] += 1
        by_month[month]["cost"] += r["total"]["cost"]

    def rounded(d):
        return {k: {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()}
                for k, v in sorted(d.items())}

    return {
        "runs": len(skill_runs),
        "cost_total": round(sum(costs), 4),
        "cost_per_run": {"mean": round(statistics.mean(costs), 4), "median": round(statistics.median(costs), 4),
                         "max": round(max(costs), 4)},
        "per_role": rounded(by_role),
        "per_model_effort": rounded(by_model),
        "over_100k_share": round(over / reqs, 4) if reqs else 0.0,
        "per_month": rounded(by_month),
    }


def pick_runs(skill_runs, n_recent):
    """Last N runs plus outliers; a run picked twice is listed once with both reasons."""
    picked = collections.OrderedDict()

    def mark(run, why):
        picked.setdefault(run["run_id"], (run, []))[1].append(why)

    for r in sorted(skill_runs, key=lambda r: r["start"] or "", reverse=True)[:n_recent]:
        mark(r, "recent")
    mark(max(skill_runs, key=lambda r: r["total"]["cost"]), "most_expensive")
    notes = []
    if skill_runs[0]["unfinished_convention"]:
        top = max(skill_runs, key=lambda r: r["total"]["unfinished"] or 0)
        if top["total"]["unfinished"]:
            mark(top, "most_unfinished")
    else:
        notes.append("no most-Unfinished outlier: this skill's agents never use the Unfinished: convention")
    mark(max(skill_runs, key=lambda r: r["total"]["largest_prompt"]), "largest_prompt")
    return [dict(run_detail(run), picked_because=why) for run, why in picked.values()], notes


def run_detail(run):
    return {
        "run_id": run["run_id"], "start": run["start"], "end": run["end"], "session": run["session"],
        "project": run["project"], "cost": run["total"]["cost"], "requests": run["total"]["requests"],
        "largest_prompt": run["total"]["largest_prompt"], "over_100k": run["total"]["over_100k"],
        "unfinished": run["total"]["unfinished"], "run_json": run["run_json"],
        "findings_by_role": run.get("findings_by_role"),
        "role_costs": {k: {"agents": v["agents"], "cost": round(v["cost"], 4), "unpriced": v["unpriced"]}
                       for k, v in sorted(role_costs(run).items())},
        "agents": [{k: a.get(k) for k in (
            "agent_id", "label", "role", "slice", "description", "requested_model", "requested_effort",
            "model", "effort", "requests", "tokens", "cost", "largest_prompt", "over_100k", "duration_s",
            "unfinished", "finished", "path", "note")} for a in run["agents"]],
    }


def report(days=30, top=5, n_runs=5, projects_dir=scan.PROJECTS_DIR, scratch_root=None, table=None, now=None):
    data = scan.scan(days, projects_dir, table, now)
    runs = data["runs"]
    coverage = label_agents(runs, scratch_root or default_scratch_root())
    by_skill = collections.defaultdict(list)
    for r in runs:
        by_skill[r["skill"]].append(r)
    ranked = sorted(by_skill.items(), key=lambda kv: -sum(r["total"]["cost"] for r in kv[1]))
    skills = []
    for skill, skill_runs in ranked[:top]:
        picked, notes = pick_runs(skill_runs, n_runs)
        skills.append({"skill": skill, "skill_display": scan.skill_display(skill), "trends": trends(skill_runs),
                       "runs": picked, "notes": notes})
    return {
        "estimate": True,
        "window": data["window"], "prices": data["prices"],
        "files_read": data["files_read"], "skipped_lines": data["skipped_lines"],
        "api_errors": data["api_errors"], "unpriced_models": data["unpriced_models"],
        "skills_in_window": len(by_skill), "top_requested": top,
        "spend_total": round(sum(r["total"]["cost"] for r in runs) + data["no_skill"]["cost"], 4),
        "spend_no_skill": data["no_skill"]["cost"],
        "review_run_json": coverage,
        "skills": skills,
    }


# ---------- retention ----------

def read_settings(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    return data if isinstance(data, dict) else {}


def retention(settings_path=SETTINGS_PATH, projects_dir=scan.PROJECTS_DIR):
    value = read_settings(settings_path).get("cleanupPeriodDays")
    effective = DEFAULT_RETENTION if value is None else value
    per_day = collections.Counter()
    total = 0
    for path in glob.glob(os.path.join(projects_dir, "**", "*.jsonl"), recursive=True):
        try:
            st = os.stat(path)
        except OSError:
            continue
        per_day[dt.date.fromtimestamp(st.st_mtime).isoformat()] += st.st_size
        total += st.st_size
    avg = total / len(per_day) if per_day else 0
    offer = isinstance(effective, int) and 1 <= effective < TARGET_RETENTION
    return {
        "cleanupPeriodDays": value,
        "effective_days": effective,
        "note": ("unset: Claude Code's default of 30 days applies" if value is None
                 else "0: no sweep" if value == 0 else None),
        "bytes_on_disk": total,
        "active_days": len(per_day),
        "avg_bytes_per_active_day": int(avg),
        "estimate_bytes_at_180_days": int(avg * TARGET_RETENTION),
        "offer": offer,
    }


def set_retention(days, settings_path=SETTINGS_PATH):
    """Set cleanupPeriodDays, keeping every other key; atomic replace."""
    data = read_settings(settings_path)
    data["cleanupPeriodDays"] = days
    folder = os.path.dirname(os.path.abspath(settings_path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".settings.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        if os.path.exists(settings_path):
            os.chmod(tmp, os.stat(settings_path).st_mode & 0o777)
        os.replace(tmp, settings_path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return {"cleanupPeriodDays": days, "written": settings_path}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--runs", type=int, default=5)
    p.add_argument("--projects-dir", default=scan.PROJECTS_DIR)
    p.add_argument("--scratch-root", default=None, help="Claude scratch root (default /tmp/claude-<uid>)")
    p.add_argument("--settings", default=SETTINGS_PATH)
    p.add_argument("--prices", default=prices.SEED_PATH)
    p.add_argument("--override", default=prices.OVERRIDE_PATH)
    p.add_argument("--retention", action="store_true", help="print the retention check")
    p.add_argument("--set-retention", type=int, metavar="DAYS", help="write cleanupPeriodDays")
    a = p.parse_args(argv)
    if a.set_retention is not None:
        out = set_retention(a.set_retention, a.settings)
    elif a.retention:
        out = retention(a.settings, a.projects_dir)
    else:
        out = report(a.days, a.top, a.runs, a.projects_dir, a.scratch_root, prices.PriceTable(a.prices, a.override))
    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
