#!/usr/bin/env python3
"""Fill the cost of each agent in a review's run.json from its transcript.

For every entry in ``agents`` the transcript is
``<transcript_dir>/agent-<agent_id>.jsonl``. It is summarised with
``summarize_agent(path)`` from the ``usage`` skill's scanner
(``plugins/base/skills/usage/scripts/scan.py``). The scanner does the dedupe by
``message.id``, the token classes, the prompt sizes and the per-request price
on its tier; this script has no price table or token parsing of its own, so
its numbers match the ``usage`` report.

Writes back, per agent, ``cost`` (the summary, or null) with ``cost_reason``
when null, and ``resolved_model`` (the ``message.model`` the transcript
shows). Adds ``cost_total`` with requests, requests over 100k, their share and
USD. Null reasons:
  - "usage scanner not found": the scanner cannot be imported
  - "no Claude transcript": a Codex task
  - "transcript not found": no file at the expected path
  - "usage scanner failed: <error>": the scanner raised on this transcript
When no agent is priced, ``cost_total.reason`` is the most common of these.
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import sys
from pathlib import Path
from typing import Callable

DEFAULT_SCANNER_DIR = Path(__file__).resolve().parent.parent.parent / "usage" / "scripts"

Summarize = Callable[[str], dict]


def load_scanner(folder: Path) -> Summarize | None:
    path = folder / "scan.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("usage_scan", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    # registered and left on sys.path, so dataclasses and later imports in the scanner work
    sys.modules[spec.name] = module
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    try:
        spec.loader.exec_module(module)
    except Exception:  # a broken scanner is the same as a missing one here
        sys.modules.pop(spec.name, None)
        return None
    return getattr(module, "summarize_agent", None)


def resolved_model(path: Path) -> str | None:
    """The first ``message.model`` in the transcript, so alias drift shows up."""
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                model = (json.loads(line).get("message") or {}).get("model")
            except (ValueError, AttributeError):
                continue
            if model and model != "<synthetic>":
                return model
    return None


def fill(run: dict, summarize: Summarize | None) -> dict:
    tdir = Path(str(run.get("transcript_dir", ""))).expanduser()
    total = {"agents_priced": 0, "requests": 0, "requests_over_100k": 0, "usd": 0.0}
    for agent in run.get("agents", []):
        agent["cost"] = None
        agent.pop("cost_reason", None)
        if agent.get("model") == "codex" or agent.get("engine") == "codex":
            agent["cost_reason"] = "no Claude transcript"
            continue
        path = tdir / f"agent-{agent.get('agent_id')}.jsonl"
        if not path.is_file():
            agent["cost_reason"] = "transcript not found"
            continue
        agent["resolved_model"] = resolved_model(path)
        if summarize is None:
            agent["cost_reason"] = "usage scanner not found"
            continue
        try:
            cost = summarize(str(path))
        except Exception as e:  # one bad transcript must not stop the others
            agent["cost_reason"] = f"usage scanner failed: {e}"
            continue
        agent["cost"] = cost
        total["agents_priced"] += 1
        total["requests"] += int(cost.get("requests") or 0)
        total["requests_over_100k"] += int(cost.get("requests_over_100k") or 0)
        total["usd"] += float(cost.get("usd") or 0.0)
    total["usd"] = round(total["usd"], 4)
    total["over_100k_share"] = (round(total["requests_over_100k"] / total["requests"], 3)
                                if total["requests"] else None)
    reasons = collections.Counter(a["cost_reason"] for a in run.get("agents", [])
                                  if a.get("cost_reason"))
    if summarize is None:
        total["reason"] = "usage scanner not found"
    elif total["agents_priced"] == 0 and reasons:
        total["reason"] = reasons.most_common(1)[0][0]
    run["cost_total"] = total
    return run


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="the review's run.json, updated in place")
    ap.add_argument("--scanner-dir", default=str(DEFAULT_SCANNER_DIR),
                    help="folder holding the usage skill's scan.py")
    a = ap.parse_args()
    path = Path(a.run)
    run = fill(json.loads(path.read_text(encoding="utf-8")), load_scanner(Path(a.scanner_dir)))
    path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    t = run["cost_total"]
    share = "n/a" if t["over_100k_share"] is None else f"{t['over_100k_share']:.0%}"
    note = f" ({t['reason']})" if t.get("reason") else ""
    print(f"{t['agents_priced']} agents priced, {t['requests']} requests, "
          f"{share} over 100k, ${t['usd']:.2f}{note}")


if __name__ == "__main__":
    main()
