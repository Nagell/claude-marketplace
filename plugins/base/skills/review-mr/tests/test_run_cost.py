import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_cost  # noqa: E402

# A stand-in for the usage skill's scanner (add-usage-skill): dedupe by
# message.id, prompt = input + cache write + cache read, 5x above 100k.
STUB_SCAN = '''
import json

def summarize_agent(path):
    seen, reqs = set(), []
    for line in open(path, encoding="utf-8"):
        msg = json.loads(line).get("message") or {}
        if not msg.get("id") or msg["id"] in seen:
            continue
        seen.add(msg["id"])
        u = msg.get("usage", {})
        prompt = (u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                  + u.get("cache_read_input_tokens", 0))
        reqs.append((prompt, u.get("output_tokens", 0)))
    usd = sum((p + o) * 1e-6 * (5 if p > 100_000 else 1) for p, o in reqs)
    return {"requests": len(reqs), "requests_over_100k": sum(p > 100_000 for p, _ in reqs),
            "first_prompt": reqs[0][0] if reqs else 0,
            "max_prompt": max((p for p, _ in reqs), default=0),
            "usd": round(usd, 6), "price_table_version": "stub"}
'''


def line(msg_id: str, model: str, prompt: int, out: int = 10) -> str:
    return json.dumps({"type": "assistant", "message": {
        "id": msg_id, "model": model,
        "usage": {"input_tokens": 5, "cache_creation_input_tokens": 0,
                  "cache_read_input_tokens": prompt - 5, "output_tokens": out}}})


@pytest.fixture
def scanner_dir(tmp_path):
    d = tmp_path / "usage" / "scripts"
    d.mkdir(parents=True)
    (d / "scan.py").write_text(STUB_SCAN, encoding="utf-8")
    return d


@pytest.fixture
def run_file(tmp_path):
    tdir = tmp_path / "subagents"
    tdir.mkdir()
    # one response split over three lines with one message.id, then a long prompt
    (tdir / "agent-a1.jsonl").write_text("\n".join([
        json.dumps({"type": "user", "message": {"role": "user", "content": "go"}}),
        line("m1", "claude-haiku-5-5-20261001", 40_000),
        line("m1", "claude-haiku-5-5-20261001", 40_000),
        line("m1", "claude-haiku-5-5-20261001", 40_000),
        line("m2", "claude-haiku-5-5-20261001", 120_000),
    ]) + "\n", encoding="utf-8")
    (tdir / "agent-r1.jsonl").write_text(line("m9", "claude-opus-5-5", 20_000) + "\n",
                                         encoding="utf-8")
    run = {"session_id": "s", "transcript_dir": str(tdir), "agents": [
        {"agent_id": "a1", "role": "slice-owner", "model": "haiku", "effort": "max"},
        {"agent_id": "r1", "role": "refuter", "model": "opus", "effort": "medium"},
        {"agent_id": "job-7", "role": "slice-owner", "model": "codex", "effort": "high"},
    ]}
    p = tmp_path / "run.json"
    p.write_text(json.dumps(run), encoding="utf-8")
    return p


def stub_module(scanner_dir: Path):
    spec = importlib.util.spec_from_file_location("stub_scan", scanner_dir / "scan.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_costs_come_from_the_scanner(run_file, scanner_dir):
    run = json.loads(run_file.read_text())
    out = run_cost.fill(run, run_cost.load_scanner(scanner_dir))
    stub = stub_module(scanner_dir)
    tdir = Path(run["transcript_dir"])
    a1, r1, codex = out["agents"]
    assert a1["cost"] == stub.summarize_agent(str(tdir / "agent-a1.jsonl"))
    assert r1["cost"] == stub.summarize_agent(str(tdir / "agent-r1.jsonl"))
    assert a1["cost"]["requests"] == 2  # split response counted once
    assert a1["cost"]["requests_over_100k"] == 1  # one above, one below 100k
    assert codex["cost"] is None and codex["cost_reason"] == "no Claude transcript"
    total = out["cost_total"]
    assert total["requests"] == 3 and total["requests_over_100k"] == 1
    assert total["agents_priced"] == 2
    assert total["usd"] == round(a1["cost"]["usd"] + r1["cost"]["usd"], 4)


def test_resolved_model_per_agent(run_file, scanner_dir):
    out = run_cost.fill(json.loads(run_file.read_text()), run_cost.load_scanner(scanner_dir))
    assert out["agents"][0]["resolved_model"] == "claude-haiku-5-5-20261001"
    assert out["agents"][1]["resolved_model"] == "claude-opus-5-5"


def test_missing_scanner(run_file, tmp_path):
    assert run_cost.load_scanner(tmp_path / "nowhere") is None
    out = run_cost.fill(json.loads(run_file.read_text()), None)
    a1, r1, codex = out["agents"]
    assert a1["cost"] is None and a1["cost_reason"] == "usage scanner not found"
    assert r1["cost_reason"] == "usage scanner not found"
    assert a1["resolved_model"] == "claude-haiku-5-5-20261001"
    assert codex["cost_reason"] == "no Claude transcript"
    assert out["cost_total"]["reason"] == "usage scanner not found"


def test_missing_transcript(tmp_path, scanner_dir):
    run = {"transcript_dir": str(tmp_path), "agents": [{"agent_id": "zz", "model": "haiku"}]}
    out = run_cost.fill(run, run_cost.load_scanner(scanner_dir))
    assert out["agents"][0]["cost_reason"] == "transcript not found"


def test_cli_writes_run_json(run_file, scanner_dir):
    proc = subprocess.run([sys.executable, str(SCRIPTS / "run_cost.py"), "--run", str(run_file),
                           "--scanner-dir", str(scanner_dir)],
                          capture_output=True, text=True, check=True)
    assert "2 agents priced, 3 requests" in proc.stdout
    saved = json.loads(run_file.read_text())
    assert saved["agents"][0]["cost"]["requests"] == 2


def test_cli_without_scanner(run_file, tmp_path):
    proc = subprocess.run([sys.executable, str(SCRIPTS / "run_cost.py"), "--run", str(run_file),
                           "--scanner-dir", str(tmp_path / "none")],
                          capture_output=True, text=True, check=True)
    assert "usage scanner not found" in proc.stdout
