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

SETTINGS_PATH = os.path.join(scan.config_dir(), "settings.json")
DEFAULT_RETENTION = 30
TARGET_RETENTION = 180


def default_scratch_root():
    getuid = getattr(os, "getuid", None)
    return f"/tmp/claude-{getuid()}" if getuid else os.path.join(tempfile.gettempdir(), "claude")


# ---------- review-mr run.json ----------

def load_run_json(scratch_root, project, session):
    """The session's run.json and an error string; (None, None) when there is none."""
    path = os.path.join(scratch_root, project, session, "scratchpad", "run.json")
    if not os.path.exists(path):
        return None, None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return None, f"{path}: {exc}"
    if not isinstance(data, dict) or not isinstance(data.get("agents"), list):
        return None, f"{path}: no agents list"
    return data, None


def _str(v):
    return v if isinstance(v, str) and v else None


def clean_run_json(data):
    """Valid agent and finding entries, and how many were skipped. Written by a model, so check each field."""
    agents, findings, skipped = [], [], 0
    for e in data.get("agents") or []:
        aid = e.get("agent_id") if isinstance(e, dict) else None
        if not isinstance(aid, (str, int)) or isinstance(aid, bool) or aid == "":
            skipped += 1
            continue
        agents.append({"agent_id": str(aid), "role": _str(e.get("role")) or "unknown", "slice": _str(e.get("slice")),
                       "model": _str(e.get("model")), "effort": _str(e.get("effort"))})
    for f in data.get("findings") or [] if isinstance(data.get("findings"), list) else []:
        dups = f.get("duplicates", []) if isinstance(f, dict) else None
        if not isinstance(f, dict) or not isinstance(dups, list) or not all(isinstance(d, str) for d in dups) \
                or not isinstance(f.get("survived"), bool) or (f.get("source") is not None and not _str(f.get("source"))):
            skipped += 1
            continue
        findings.append({"source": _str(f.get("source")), "duplicates": dups, "survived": f["survived"]})
    return agents, findings, skipped


def apply_run_json(run, agents, findings, skipped):
    """Label agents by role and slice, add Codex agents, count surviving findings per role."""
    by_id = {e["agent_id"]: e for e in agents}
    matched = set()
    for a in run["agents"]:
        entry = by_id.get(a["agent_id"])
        if not entry:
            continue
        matched.add(a["agent_id"])
        a["role"] = entry["role"] if entry["role"] != "unknown" else a["role"]
        a["slice"] = entry["slice"]
        a["label"] = " ".join(x for x in (a["role"], entry["slice"]) if x)
        a["requested_model"] = entry["model"] or a.get("requested_model")
        a["requested_effort"] = entry["effort"] or a.get("requested_effort")
        a["source"] = "run.json"
    for entry in agents:
        if entry["model"] == "codex" and entry["agent_id"] not in matched:
            role = entry["role"] if entry["role"] != "unknown" else "codex"
            run["agents"].append({
                "agent_id": entry["agent_id"], "role": role, "slice": entry["slice"],
                "label": " ".join(x for x in (role, entry["slice"]) if x),
                "requested_model": "codex", "requested_effort": entry["effort"], "model": "codex",
                "cost": None, "requests": 0, "unpriced_requests": 0, "source": "run.json",
                "note": "Codex task: no Claude transcript",
            })
    # a finding's source and duplicates name a slice or a role
    name_role = {}
    for entry in agents:
        if entry["slice"]:
            name_role[entry["slice"]] = entry["role"]
        name_role.setdefault(entry["role"], entry["role"])
    unique, repeated = collections.Counter(), collections.Counter()
    for f in findings:
        if not f["survived"]:
            continue
        if f["source"]:
            unique[name_role.get(f["source"], f["source"])] += 1
        for d in f["duplicates"]:
            repeated[name_role.get(d, d)] += 1
    run["findings_by_role"] = {r: {"unique": unique[r], "repeated": repeated[r]}
                               for r in sorted(set(unique) | set(repeated))}
    run["run_json"] = True
    if skipped:
        run["run_json_skipped_entries"] = skipped


def label_agents(runs, scratch_root):
    review_runs = with_json = 0
    errors = []
    sessions = collections.OrderedDict()
    for run in runs:
        for a in run["agents"]:
            a["role"] = a.get("agent_type") or "unknown"
            a["label"] = a["role"]
            a["source"] = "meta"
        run["run_json"] = False
        if run["skill_display"] == "review-mr":
            review_runs += 1
            sessions.setdefault((run["project"], run["session"]), []).append(run)
    for (project, session), session_runs in sessions.items():
        data, error = load_run_json(scratch_root, project, session)
        if error:
            errors.append(error)
        if data is None:
            continue
        agents, findings, skipped = clean_run_json(data)
        # one run.json per session: give it to the review run whose agents it lists, else to the latest one
        ids = {e["agent_id"] for e in agents}
        owners = [r for r in session_runs if any(a["agent_id"] in ids for a in r["agents"])]
        target = owners[-1] if owners else max(session_runs, key=lambda r: r["start"] or "")
        apply_run_json(target, agents, findings, skipped)
        with_json += 1
    out = {"review_runs": review_runs, "with_run_json": with_json,
           "note": "one run.json per session, the latest review's; a reboot or /base:cleanup removes older ones"}
    if errors:
        out["errors"] = errors
    return out


# ---------- aggregation ----------

def role_costs(run):
    out = collections.defaultdict(lambda: {"agents": 0, "cost": 0.0, "unpriced": 0})
    for a in run["agents"]:
        r = out[a["role"]]
        r["agents"] += 1
        if a.get("cost") is None or a.get("unpriced_requests"):
            r["unpriced"] += 1
        if a.get("cost") is not None:
            r["cost"] += a["cost"]
    return out


def trends(skill_runs):
    costs = [r["total"]["cost"] for r in skill_runs]
    by_role = collections.defaultdict(lambda: {"agents": 0, "cost": 0.0})
    by_model = collections.defaultdict(lambda: {"requests": 0, "cost": 0.0})
    by_month = collections.defaultdict(lambda: {"runs": 0, "cost": 0.0})
    reqs = over = unpriced = 0
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
        unpriced += r["total"]["unpriced_requests"]
        month = (r["start"] or "")[:7] or "unknown"
        by_month[month]["runs"] += 1
        by_month[month]["cost"] += r["total"]["cost"]

    def rounded(d):
        return {k: {kk: (round(vv, 6) if isinstance(vv, float) else vv) for kk, vv in v.items()}
                for k, v in sorted(d.items())}

    return {
        "runs": len(skill_runs),
        "cost_total": round(sum(costs), 4),
        "cost_per_run": {"mean": round(statistics.mean(costs), 4), "median": round(statistics.median(costs), 4),
                         "max": round(max(costs), 4)},
        "per_role": rounded(by_role),
        "per_model_effort": rounded(by_model),
        "over_100k_share": round(over / reqs, 4) if reqs else 0.0,
        "unpriced_requests": unpriced,
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
        notes.append("no most-Unfinished outlier: only review-mr agents use the Unfinished: convention")
    mark(max(skill_runs, key=lambda r: r["total"]["largest_prompt"]), "largest_prompt")
    return [dict(run_detail(run), picked_because=why) for run, why in picked.values()], notes


def run_detail(run):
    return {
        "run_id": run["run_id"], "start": run["start"], "end": run["end"], "session": run["session"],
        "project": run["project"], "cost": run["total"]["cost"], "requests": run["total"]["requests"],
        "unpriced_requests": run["total"]["unpriced_requests"], "nested_skills": run.get("nested_skills"),
        "largest_prompt": run["total"]["largest_prompt"], "over_100k": run["total"]["over_100k"],
        "unfinished": run["total"]["unfinished"], "run_json": run["run_json"],
        "findings_by_role": run.get("findings_by_role"),
        "role_costs": {k: {"agents": v["agents"], "cost": round(v["cost"], 6), "unpriced": v["unpriced"]}
                       for k, v in sorted(role_costs(run).items())},
        "agents": [{k: a.get(k) for k in (
            "agent_id", "label", "role", "slice", "description", "requested_model", "requested_effort",
            "model", "effort", "requests", "unpriced_requests", "tokens", "cost", "largest_prompt", "over_100k",
            "duration_s",
            "unfinished", "finished", "path", "note")} for a in run["agents"]],
    }


def report(days=30, top=5, n_runs=5, projects_dir=scan.PROJECTS_DIR, scratch_root=None, table=None, now=None):
    data = scan.scan(days, projects_dir, table, now)
    runs = data["runs"]
    coverage = label_agents(runs, scratch_root or default_scratch_root())
    # group by the name without the plugin prefix, so a skill whose plugin was renamed stays one row
    by_skill = collections.defaultdict(list)
    for r in runs:
        by_skill[r["skill_display"]].append(r)
    ranked = sorted(by_skill.items(), key=lambda kv: -sum(r["total"]["cost"] for r in kv[1]))
    skills = []
    for skill, skill_runs in ranked[:top]:
        picked, notes = pick_runs(skill_runs, n_runs)
        missing = sum(r["total"]["unpriced_requests"] for r in skill_runs)
        if missing:
            notes.append(f"{missing} requests on models without a price count as $0, so this skill's cost and rank are too low")
        names = sorted({r["skill"] for r in skill_runs})
        skills.append({"skill": names[-1], "skill_display": skill, "full_names": names, "trends": trends(skill_runs),
                       "runs": picked, "notes": notes})
    return {
        "estimate": True,
        "window": data["window"], "prices": data["prices"],
        "files_read": data["files_read"], "skipped_lines": data["skipped_lines"],
        "api_errors": data["api_errors"], "unpriced_models": data["unpriced_models"], "warnings": data["warnings"],
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
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    return data


def managed_settings_files():
    """Managed (organisation) settings files Claude Code reads, highest precedence first."""
    if sys.platform == "darwin":
        roots = ["/Library/Application Support/ClaudeCode"]
    elif sys.platform == "win32":
        roots = [r"C:\Program Files\ClaudeCode"]
    else:
        roots = ["/etc/claude-code"]
        if os.environ.get("WSL_DISTRO_NAME"):
            roots.append("/mnt/c/Program Files/ClaudeCode")
    files = []
    for root in roots:
        files += sorted(glob.glob(os.path.join(root, "managed-settings.d", "*.json")), reverse=True)
        files.append(os.path.join(root, "managed-settings.json"))
    return files


def setting_source(settings_path, project_dir=None, managed=None):
    """Where cleanupPeriodDays comes from, by Claude Code's precedence: managed, project local, project, user.

    Returns (value, source, path) for the first file that sets it, or (None, None, None).
    """
    layers = [("managed", f) for f in (managed_settings_files() if managed is None else managed)]
    if project_dir:
        layers += [("project local", os.path.join(project_dir, ".claude", "settings.local.json")),
                   ("project", os.path.join(project_dir, ".claude", "settings.json"))]
    layers.append(("user", settings_path))
    for source, path in layers:
        if not os.path.exists(path):
            continue
        data = read_settings(path)  # a user file that cannot be read raises; the caller reports it
        if "cleanupPeriodDays" in data:
            return data["cleanupPeriodDays"], source, path
    return None, None, None


def retention(settings_path=SETTINGS_PATH, projects_dir=scan.PROJECTS_DIR, project_dir=None, managed=None):
    try:
        value, source, source_path = setting_source(settings_path, project_dir, managed)
    except (OSError, ValueError) as exc:
        return {"error": f"a settings file is unreadable: {exc}", "offer": False}
    whole = isinstance(value, (int, float)) and not isinstance(value, bool) and float(value).is_integer()
    valid = whole and value >= 1
    effective = int(value) if valid else DEFAULT_RETENTION
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
    if value is None:
        note = "unset: Claude Code's default of 30 days applies"
    elif not valid:
        note = (f"{value!r} is not a valid value: Claude Code reports a settings error for it (whole number, "
                "minimum 1). Counted as 30 here; set 1 or more")
    else:
        note = None
    if source in ("managed", "project", "project local"):
        note = ((note + "; ") if note else "") + (
            f"set in {source} settings ({source_path}), which override your user settings, so a change there "
            "would have no effect")
    note_estimate = "average per day that had transcript writes; the 180-day figure assumes you use Claude Code daily"
    return {
        "cleanupPeriodDays": value,
        "source": source or "unset",
        "source_file": source_path,
        "effective_days": effective,
        "note": note,
        "bytes_on_disk": total,
        "active_days": len(per_day),
        "avg_bytes_per_active_day": int(avg),
        "estimate_bytes_at_180_days": int(avg * TARGET_RETENTION),
        "estimate_note": note_estimate,
        "checked_file": os.path.abspath(settings_path),
        "offer": effective < TARGET_RETENTION and source in (None, "user"),
    }


def set_retention(days, settings_path=SETTINGS_PATH):
    """Set cleanupPeriodDays, keeping every other key; atomic replace."""
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise ValueError("cleanupPeriodDays must be a whole number of 1 or more")
    settings_path = os.path.realpath(settings_path)  # write through a symlink, keep the link
    data = read_settings(settings_path)
    data["cleanupPeriodDays"] = days
    folder = os.path.dirname(settings_path)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".settings.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        if os.path.exists(settings_path):
            os.chmod(tmp, os.stat(settings_path).st_mode & 0o777)
        os.replace(tmp, settings_path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return {"cleanupPeriodDays": days, "written": settings_path}


def positive_int(text):
    n = int(text)
    if n < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return n


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--days", type=positive_int, default=30)
    p.add_argument("--top", type=positive_int, default=5)
    p.add_argument("--runs", type=positive_int, default=5)
    p.add_argument("--projects-dir", default=scan.PROJECTS_DIR)
    p.add_argument("--scratch-root", default=None, help="Claude scratch root (default /tmp/claude-<uid>)")
    p.add_argument("--settings", default=SETTINGS_PATH)
    p.add_argument("--prices", default=prices.SEED_PATH)
    p.add_argument("--override", default=prices.OVERRIDE_PATH)
    p.add_argument("--retention", action="store_true", help="print the retention check")
    p.add_argument("--set-retention", type=positive_int, metavar="DAYS", help="write cleanupPeriodDays")
    a = p.parse_args(argv)
    if a.set_retention is not None:
        try:
            out = set_retention(a.set_retention, a.settings)
        except (OSError, ValueError) as exc:
            json.dump({"error": f"{a.settings}: {exc}", "written": None}, sys.stdout, indent=1)
            sys.stdout.write("\n")
            sys.exit(1)
    elif a.retention:
        out = retention(a.settings, a.projects_dir, os.getcwd())
    else:
        out = report(a.days, a.top, a.runs, a.projects_dir, a.scratch_root, prices.PriceTable(a.prices, a.override))
    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
