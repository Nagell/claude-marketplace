"""Builders for synthetic transcripts. Never real transcripts."""
import json
import os
import shutil
import sys
import tempfile
import unittest

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
FIXTURES = os.path.join(SKILL_DIR, "tests", "fixtures")

import prices  # noqa: E402

T0 = "2026-11-20T10:00:{:02d}.000Z"


def ts(sec):
    m, s = divmod(sec, 60)
    return f"2026-11-20T10:{m:02d}:{s:02d}.000Z"


def usage(inp=10, out=5, read=0, w5=0, w1=0, dict_=True):
    u = {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": read,
         "cache_creation_input_tokens": w5 + w1}
    if dict_:
        u["cache_creation"] = {"ephemeral_5m_input_tokens": w5, "ephemeral_1h_input_tokens": w1}
    return u


def asst(mid, sec, model="claude-opus-5-5", skill=None, u=None, content=None, effort="medium", **extra):
    e = {"type": "assistant", "timestamp": ts(sec), "effort": effort,
         "message": {"id": mid, "model": model, "usage": u or usage(),
                     "content": content if content is not None else [{"type": "text", "text": "ok"}]}}
    if skill:
        e["attributionSkill"] = skill
    e.update(extra)
    return e


def agent_call(mid, sec, tool_id, skill=None, **kw):
    return asst(mid, sec, skill=skill, content=[{"type": "tool_use", "id": tool_id, "name": "Agent", "input": {}}], **kw)


def skill_call(mid, sec, name):
    return asst(mid, sec, content=[{"type": "tool_use", "id": "s" + mid, "name": "Skill", "input": {"skill": name}}])


def human(sec, text="do it", origin=True):
    e = {"type": "user", "timestamp": ts(sec), "message": {"role": "user", "content": text}}
    if origin:
        e["origin"] = {"kind": "human"}
    return e


def skill_load(sec, name="x"):
    """The meta line Claude Code writes when a skill is invoked."""
    return {"type": "user", "timestamp": ts(sec), "isMeta": True,
            "message": {"role": "user", "content": [{"type": "text", "text": f"Base directory for this skill: /s/{name}"}]}}


def notification(sec):
    return {"type": "user", "timestamp": ts(sec), "origin": {"kind": "task-notification"},
            "message": {"role": "user", "content": "<task-notification>done</task-notification>"}}


def command(sec, name):
    return {"type": "user", "timestamp": ts(sec),
            "message": {"role": "user", "content": f"<command-name>/{name}</command-name>\n<command-args></command-args>"}}


def write_jsonl(path, entries, tail=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")
        if tail:
            fh.write(tail)


class TempHome(unittest.TestCase):
    """A temp projects dir with helpers to add sessions and agents."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="usage-test.")
        self.projects = os.path.join(self.tmp, "projects")
        self.table = prices.PriceTable(prices.SEED_PATH, None)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def session(self, sid, entries, project="-home-u-proj", tail=None):
        path = os.path.join(self.projects, project, sid + ".jsonl")
        write_jsonl(path, entries, tail)
        return path

    def agent(self, sid, aid, entries, meta=None, project="-home-u-proj"):
        path = os.path.join(self.projects, project, sid, "subagents", f"agent-{aid}.jsonl")
        write_jsonl(path, entries)
        if meta is not None:
            with open(path[:-len(".jsonl")] + ".meta.json", "w", encoding="utf-8") as fh:
                json.dump(meta, fh)
        return path
