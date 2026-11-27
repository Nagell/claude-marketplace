import datetime as dt
import json
import os
import subprocess
import sys

from helpers import SKILL_DIR, TempHome, agent_call, asst, command, human, notification, skill_call, skill_load, usage
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
        self.session("s1", [human(0), asst("m1", 1, skill=RM, u=usage(out=1)), asst("m1", 2, skill=RM, u=usage(out=335)),
                            asst("m1", 3, skill=RM, u=usage(out=20))])
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
        data = self.scan()
        self.assertEqual((data["skipped_lines"], data["no_skill"]["requests"]), (1, 1))

    def test_bench_session_lines_not_counted(self):
        title = {"type": "custom-title", "customTitle": "bench-x-J", "sessionId": "b"}
        self.session("b1", [title, human(0), asst("m1", 1)], tail='{"type": "assistant", "mess')
        data = self.scan()
        self.assertEqual(data["skipped_lines"], 0)
        self.assertEqual(data["warnings"], ["only benchmark sessions in the window, all left out"])

    def test_wrong_typed_fields_skip_the_line(self):
        bad_tokens = asst("m2", 2, u={"input_tokens": "10", "output_tokens": 5})
        bad_model = asst("m3", 3, model=["x"])
        naive = asst("m4", 4)
        naive["timestamp"] = "2026-11-20T10:00:04"
        self.session("s1", [human(0), asst("m1", 1), bad_tokens, bad_model, naive])
        data = self.scan()
        self.assertEqual((data["skipped_lines"], data["no_skill"]["requests"]), (2, 2))

    def test_missing_projects_dir_warns(self):
        data = scan.scan(30, os.path.join(self.tmp, "nope"), self.table, NOW)
        self.assertTrue(any("does not exist" in w for w in data["warnings"]))

    def test_api_errors_counted_in_window_only(self):
        old = asst("e1", 1, model="<synthetic>", u=usage(0, 0))
        old["timestamp"] = "2026-01-01T00:00:00.000Z"
        self.session("s1", [old, human(0), asst("e2", 1, model="<synthetic>", u=usage(0, 0)), asst("m1", 2)])
        self.assertEqual(self.scan()["api_errors"], 1)

    def test_config_dir_from_env(self):
        old = os.environ.get("CLAUDE_CONFIG_DIR")
        os.environ["CLAUDE_CONFIG_DIR"] = self.tmp
        try:
            self.assertEqual(scan.config_dir(), self.tmp)
        finally:
            if old is None:
                del os.environ["CLAUDE_CONFIG_DIR"]
            else:
                os.environ["CLAUDE_CONFIG_DIR"] = old

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
        self.session("s1", [human(0), skill_load(0), asst("m1", 1, skill=RM),
                            human(10), skill_load(10), asst("m2", 11, skill=RM)])
        self.assertEqual(len(self.runs(self.scan())), 2)

    def test_reply_typed_during_run_keeps_one_run(self):
        # an interactive skill: the user answers, the same skill carries on without a new invocation
        self.session("s1", [human(0), skill_load(0), asst("m1", 1, skill=RM), human(10, "yes"), asst("m2", 11, skill=RM)])
        runs = self.runs(self.scan())
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["total"]["requests"], 2)

    def test_answer_to_a_question_stays_in_run(self):
        # Claude Code drops attributionSkill on the turns that answer a reply
        ask = asst("m1", 1, skill=RM, content=[{"type": "text", "text": "Which option do you want?"}])
        self.session("s1", [human(0), skill_load(0), ask, human(10, "the first"), asst("m2", 11), asst("m3", 12)])
        data = self.scan()
        self.assertEqual(self.runs(data)[0]["total"]["requests"], 3)
        self.assertEqual(data["no_skill"]["requests"], 0)

    def test_new_prompt_after_a_statement_is_no_skill(self):
        done = asst("m1", 1, skill=RM, content=[{"type": "text", "text": "All done."}])
        self.session("s1", [human(0), skill_load(0), done, human(10, "something else"), asst("m2", 11)])
        self.assertEqual(self.scan()["no_skill"]["requests"], 1)

    def test_compaction_summary_does_not_close_run(self):
        summary = dict(human(5, "This session is being continued", origin=False), isCompactSummary=True)
        self.session("s1", [human(0), asst("m1", 1, skill=RM), summary, asst("m2", 6)])
        self.assertEqual(self.runs(self.scan())[0]["total"]["requests"], 2)

    def test_resumed_session_agents_join_the_original_run(self):
        history = [human(0), skill_load(0), asst("m1", 1, skill=RM), agent_call("m2", 2, "tu1", skill=RM)]
        self.session("a-parent", history)
        self.session("b-child", history + [human(30), asst("m3", 31)])
        self.agent("b-child", "a1", [asst("am", 3)], {"toolUseId": "tu1", "spawnDepth": 1})
        runs = self.runs(self.scan())
        self.assertEqual(len(runs), 1)
        self.assertEqual((runs[0]["own"]["requests"], len(runs[0]["agents"])), (2, 1))

    def test_unknown_command_needs_skill_load(self):
        self.session("s1", [command(0, "mystery"), asst("m1", 1)])
        self.assertEqual(self.scan()["runs"], [])

    def test_nested_skill_stays_in_parent_run(self):
        self.session("s1", [human(0), asst("m1", 1, skill=RM), asst("m2", 2, skill="base:writing-style-guide"),
                            agent_call("m3", 3, "tu1", skill="base:writing-style-guide"), asst("m4", 4, skill=RM)])
        self.agent("s1", "a1", [asst("am", 5)], {"toolUseId": "tu1", "spawnDepth": 1})
        data = self.scan()
        self.assertEqual([r["skill"] for r in data["runs"]], [RM])
        run = data["runs"][0]
        self.assertEqual(run["nested_skills"], ["base:writing-style-guide"])
        self.assertEqual((run["total"]["requests"], len(run["agents"])), (5, 1))

    def test_resumed_session_with_same_first_timestamp(self):
        parent = [human(0), asst("m1", 1, skill=RM)]
        self.session("z-parent", parent)
        self.session("a-child", parent + [human(20), asst("m2", 21)])
        data = self.scan()
        self.assertEqual([(r["session"], r["total"]["requests"]) for r in data["runs"]], [("z-parent", 1)])
        self.assertEqual(data["no_skill"]["requests"], 1)

    def test_id_less_requests_in_two_files_both_count(self):
        for sid in ("s1", "s2"):
            line = asst(None, 1)
            del line["message"]["id"]
            self.session(sid, [human(0), line])
        self.assertEqual(self.scan()["no_skill"]["requests"], 2)

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

    def test_review_mr_clean_run_counts_zero(self):
        self.make("all good")
        run = self.runs(self.scan())[0]
        self.assertEqual((run["agents"][0]["unfinished"], run["total"]["unfinished"]), (0, 0))

    def test_other_skill_is_na(self):
        self.session("s1", [human(0), agent_call("m1", 1, "tu1", skill="base:grilling")])
        self.agent("s1", "a1", [asst("am", 2, content=[{"type": "text", "text": "Unfinished: x.py"}])],
                   {"toolUseId": "tu1", "spawnDepth": 1})
        run = self.runs(self.scan(), "base:grilling")[0]
        self.assertIsNone(run["agents"][0]["unfinished"])
        self.assertIsNone(run["total"]["unfinished"])

    def test_unfinished_read_from_report_write(self):
        self.session("s1", [human(0), agent_call("m1", 1, "tu1", skill=RM)])
        write = {"type": "tool_use", "id": "w1", "name": "Write",
                 "input": {"file_path": "/s/wave1-slice-1.txt", "content": "Unfinished: a.py\n| ledger |\nLeftovers: none"}}
        self.agent("s1", "a1", [asst("am1", 2, content=[write]), asst("am2", 3, content=[{"type": "text", "text": "/s/wave1-slice-1.txt"}])],
                   {"toolUseId": "tu1", "spawnDepth": 1})
        self.assertEqual(self.runs(self.scan())[0]["agents"][0]["unfinished"], 1)

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
