import datetime as dt
import json
import os
import subprocess
import sys

from helpers import SKILL_DIR, TempHome, agent_call, asst, command, human, notification, skill_call, ts, usage
import scan

NOW = dt.datetime(2026, 11, 21, tzinfo=dt.timezone.utc)
RM = "base:review-mr"


class ScanBase(TempHome):
    def scan(self, days=30):
        return scan.scan(days, self.projects, self.table, NOW)

    def runs(self, data, skill=RM):
        return [r for r in data["runs"] if r["skill"] == skill]


class Dedupe(ScanBase):
    def test_split_response_counts_once(self):
        self.session("s1", [human(0), asst("m1", 1, skill=RM), asst("m1", 2, skill=RM), asst("m1", 3, skill=RM)])
        run = self.runs(self.scan())[0]
        self.assertEqual(run["total"]["requests"], 1)
        self.assertEqual(run["total"]["tokens"]["input"], 10)

    def test_growing_first_line_takes_largest(self):
        self.session("s1", [human(0), asst("m1", 1, skill=RM, u=usage(out=1)), asst("m1", 2, skill=RM, u=usage(out=335))])
        self.assertEqual(self.runs(self.scan())[0]["total"]["tokens"]["output"], 335)

    def test_shared_ids_count_once_in_earlier_file(self):
        self.session("a-early", [human(0), asst("m1", 1, skill=RM), asst("m2", 2, skill=RM)])
        self.session("b-late", [asst("m1", 1, skill=RM), human(30), asst("m3", 31, skill=RM)])
        data = self.scan()
        by_session = {r["session"]: r["total"]["requests"] for r in data["runs"]}
        self.assertEqual(by_session, {"a-early": 2, "b-late": 1})

    def test_synthetic_is_api_error_not_unpriced(self):
        self.session("s1", [human(0), asst("e1", 1, model="<synthetic>", u=usage(0, 0)),
                            asst("e2", 2, model="<synthetic>", u=usage(0, 0)), asst("m1", 3)])
        data = self.scan()
        self.assertEqual(data["api_errors"], 2)
        self.assertEqual(data["unpriced_models"], {})

    def test_unpriced_model_listed(self):
        self.session("s1", [human(0), asst("m1", 1, model="claude-new-9")])
        data = self.scan()
        self.assertEqual(data["unpriced_models"], {"claude-new-9": 1})
        self.assertEqual(data["no_skill"]["unpriced_requests"], 1)
        self.assertEqual(data["no_skill"]["tokens"]["input"], 10)

    def test_truncated_last_line_skipped(self):
        self.session("s1", [human(0), asst("m1", 1)], tail='{"type": "assistant", "mess')
        self.assertEqual(self.scan()["skipped_lines"], 1)

    def test_old_file_not_opened(self):
        path = self.session("old", [human(0), asst("m1", 1, skill=RM)])
        old = (NOW - dt.timedelta(days=60)).timestamp()
        os.utime(path, (old, old))
        data = self.scan()
        self.assertEqual(data["files_read"], 0)

    def test_token_classes_kept_apart(self):
        self.session("s1", [human(0), asst("m1", 1, skill=RM, u=usage(inp=10, read=1000, w5=5, w1=7))])
        tk = self.runs(self.scan())[0]["total"]["tokens"]
        self.assertEqual(tk, {"input": 10, "cache_write_5m": 5, "cache_write_1h": 7, "cache_read": 1000, "output": 5})


class Runs(ScanBase):
    def test_run_with_nine_agents(self):
        entries = [human(0), asst("m0", 1, skill=RM)]
        for i in range(9):
            entries.append(agent_call(f"c{i}", 2 + i, f"tu{i}", skill=RM))
        self.session("s1", entries)
        for i in range(9):
            self.agent("s1", f"a{i}", [asst(f"am{i}", 3 + i)], {"agentType": "general-purpose", "toolUseId": f"tu{i}",
                                                              "spawnDepth": 1, "description": f"slice {i}"})
        runs = self.runs(self.scan())
        self.assertEqual(len(runs), 1)
        self.assertEqual(len(runs[0]["agents"]), 9)
        self.assertEqual(runs[0]["total"]["requests"], 1 + 9 + 9)

    def test_same_skill_twice(self):
        self.session("s1", [human(0), asst("m1", 1, skill=RM), human(10), asst("m2", 11, skill=RM)])
        self.assertEqual(len(self.runs(self.scan())), 2)

    def test_gaps_in_attribution_stay_in_run(self):
        self.session("s1", [human(0), asst("m1", 1, skill=RM), asst("m2", 2), asst("m3", 3, skill=RM)])
        data = self.scan()
        self.assertEqual(self.runs(data)[0]["total"]["requests"], 3)
        self.assertEqual(data["no_skill"]["requests"], 0)

    def test_notification_does_not_end_run(self):
        self.session("s1", [human(0), agent_call("m1", 1, "tu1", skill=RM), notification(5),
                            asst("m2", 6), agent_call("m3", 7, "tu2")])
        self.agent("s1", "late", [asst("am", 8)], {"toolUseId": "tu2", "spawnDepth": 1, "agentType": "x"})
        run = self.runs(self.scan())[0]
        self.assertEqual(run["total"]["requests"], 4)
        self.assertEqual([a["agent_id"] for a in run["agents"]], ["late"])

    def test_requests_outside_skill_are_no_skill(self):
        self.session("s1", [human(0), asst("m1", 1), human(5), asst("m2", 6, skill=RM)])
        data = self.scan()
        self.assertEqual(data["no_skill"]["requests"], 1)
        self.assertEqual(self.runs(data)[0]["total"]["requests"], 1)

    def test_fallback_without_attribution(self):
        self.session("s1", [human(0, origin=False), skill_call("m1", 1, "base:review-mr"), asst("m2", 2),
                            human(10, origin=False), asst("m3", 11)])
        data = self.scan()
        self.assertEqual(self.runs(data)[0]["total"]["requests"], 2)
        self.assertEqual(data["no_skill"]["requests"], 1)

    def test_fallback_skill_command_starts_run(self):
        self.session("s1", [command(0, "base:cleanup"), asst("m1", 1)])
        self.assertEqual(len(self.runs(self.scan(), "base:cleanup")), 1)

    def test_clear_starts_no_run(self):
        self.session("s1", [command(0, "clear"), asst("m1", 1)])
        data = self.scan()
        self.assertEqual(data["runs"], [])
        self.assertEqual(data["no_skill"]["requests"], 1)

    def test_typed_prompt_fallback_content_rules(self):
        self.assertTrue(scan.is_typed_prompt(human(0, origin=False)))
        self.assertFalse(scan.is_typed_prompt(human(0, "<task-notification>x", origin=False)))
        self.assertFalse(scan.is_typed_prompt(human(0, "<local-command-stdout>x", origin=False)))
        self.assertFalse(scan.is_typed_prompt(dict(human(0, origin=False), isMeta=True)))
        tool_result = {"type": "user", "message": {"content": [{"type": "tool_result"}]}}
        self.assertFalse(scan.is_typed_prompt(tool_result))

    def test_nested_agent_lands_in_parent_run(self):
        self.session("s1", [human(0), agent_call("m1", 1, "tu1", skill=RM), human(50), asst("m9", 51)])
        self.agent("s1", "parent", [agent_call("p1", 2, "tu-nested")], {"toolUseId": "tu1", "spawnDepth": 1})
        self.agent("s1", "child", [asst("c1", 3)], {"toolUseId": "tu-nested", "spawnDepth": 2, "parentAgentId": "parent"})
        run = self.runs(self.scan())[0]
        self.assertEqual(sorted(a["agent_id"] for a in run["agents"]), ["child", "parent"])

    def test_nested_agent_by_parent_id_only(self):
        self.session("s1", [human(0), agent_call("m1", 1, "tu1", skill=RM)])
        self.agent("s1", "parent", [asst("p1", 2)], {"toolUseId": "tu1", "spawnDepth": 1})
        self.agent("s1", "child", [asst("c1", 3)], {"spawnDepth": 2, "parentAgentId": "parent"})
        run = self.runs(self.scan())[0]
        self.assertEqual(len(run["agents"]), 2)

    def test_agent_without_meta(self):
        self.session("s1", [human(0), asst("m1", 1, skill=RM)])
        self.agent("s1", "nometa", [asst("am", 2, skill=RM)])
        run = self.runs(self.scan())[0]
        a = run["agents"][0]
        self.assertEqual((a["agent_type"], a["requested_model"], a["requested_effort"]), (None, None, None))
        self.assertEqual(a["requests"], 1)


class AgentDetails(ScanBase):
    def make(self, final_text, read=140_000):
        self.session("s1", [human(0), agent_call("m1", 1, "tu1", skill=RM)])
        return self.agent("s1", "a1", [
            asst("am1", 2, model="claude-haiku-5-5", effort="max", u=usage(read=read)),
            asst("am2", 62, model="claude-haiku-5-5", effort="max",
                 content=[{"type": "text", "text": final_text}]),
        ], {"agentType": "general-purpose", "description": "slice 1", "toolUseId": "tu1", "spawnDepth": 1,
            "model": "haiku", "effort": "max", "finished": True})

    def test_overwhelmed_agent(self):
        self.make("Unfinished: a.py b.py\n| ledger |")
        a = self.runs(self.scan())[0]["agents"][0]
        self.assertEqual(a["unfinished"], 1)
        self.assertEqual(a["largest_prompt"], 140_010)
        self.assertEqual(a["over_100k"], 1)
        self.assertEqual((a["model"], a["effort"], a["finished"], a["duration_s"]), ("claude-haiku-5-5", "max", True, 60.0))

    def test_convention_not_used_is_na(self):
        self.make("all good")
        run = self.runs(self.scan())[0]
        self.assertIsNone(run["agents"][0]["unfinished"])
        self.assertIsNone(run["total"]["unfinished"])

    def test_summarize_agent_matches_scan(self):
        path = self.make("done")
        from_scan = self.runs(self.scan())[0]["agents"][0]
        alone, _ = scan.summarize_agent(path, self.table)
        for k in ("requests", "tokens", "cost", "largest_prompt", "over_100k"):
            self.assertEqual(alone[k], from_scan[k], k)

    def test_cli_prints_json(self):
        self.make("done")
        out = subprocess.run([sys.executable, os.path.join(SKILL_DIR, "scripts", "scan.py"), "--days", "36500",
                              "--projects-dir", self.projects, "--override", os.path.join(self.tmp, "none.json")],
                             capture_output=True, text=True, check=True)
        self.assertIn("runs", json.loads(out.stdout))


if __name__ == "__main__":
    import unittest
    unittest.main()
