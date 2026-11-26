import json
import os
import re
import shutil
import threading

from helpers import SKILL_DIR, TempHome
import bench
import models

CASE = os.path.join(SKILL_DIR, "references", "bench", "review-hooks-browser")
REVIEW_MR = os.path.join(os.path.dirname(SKILL_DIR), "review-mr", "references")
BACK = {"{snap}": "<reviews worktree path>", "{head_sha}": "<sha>", "{primary}": "<primary repo path>",
        "{diff}": "<diff path>", "{target_branch}": "<target_branch>", "{base_sha}": "<base_sha>",
        "{title}": "<title>", "{description}": "<the file refs --description-out wrote>",
        "{run_tmp}": "<run temp dir>", "{slice_files}": "<the slice's files, with their line counts>",
        "{lenses}": '<lens text, or "none">', "{conventions}": "<find_conventions.py entries for the slice: path, lines, changed>",
        "{report}": "<report path>"}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class Case(TempHome):
    def test_snapshot_size(self):
        files = bench.snapshot_files(os.path.join(CASE, "snap"))
        self.assertEqual((len(files), sum(f["lines"] for f in files)), (20, 2905))

    def test_brief_template_matches_review_mr(self):
        text = read(os.path.join(CASE, "setups", "review-mr-v1", "slice-brief.md"))
        text = re.sub(r"^\{/?drop\}\n", "", text, flags=re.M)
        for k, v in BACK.items():
            text = text.replace(k, v)
        self.assertEqual(text, read(os.path.join(REVIEW_MR, "agent-brief.md")))

    def test_slices_under_hard_limit(self):
        setup = json.loads(read(os.path.join(CASE, "setups", "review-mr-v1.json")))
        slices = bench.cut_slices(bench.snapshot_files(os.path.join(CASE, "snap")), setup["size_rule"])
        self.assertTrue(all(s["load"] < 700 for s in slices))
        self.assertEqual(sum(len(s["files"]) for s in slices), 20)

    def test_results_only_setup_runs(self):
        data = json.loads(read(os.path.join(CASE, "results.json")))
        self.assertEqual(data["skill"], "review-mr")
        for r in data["runs"]:  # only setup runs; history B to I stays in RESULTS.md
            self.assertTrue(r["setup_id"].startswith("review-mr-v1-"))
            self.assertIn(r["status"], ("complete", "incomplete"))

    def test_answer_key_items_complete(self):
        key = read(os.path.join(CASE, "answer-key.md"))
        items = re.split(r"^### ", key, flags=re.M)[1:]
        self.assertEqual(len(items), 14)
        for item in items:
            self.assertRegex(item, r"^[HSD]\d \((high|medium|low)\)")
            self.assertIn("Mechanism:", item)
            self.assertIn("```diff", item)
            loc = re.search(r"`(snap/[^`:]+):(\d+)`", item)
            lines = read(os.path.join(CASE, loc.group(1))).split("\n")
            self.assertLessEqual(int(loc.group(2)), len(lines))
            self.assertRegex(item, r"Fix: `[0-9a-f]{7}`")

    def test_no_session_paths_in_case(self):
        for root, _, files in os.walk(CASE):
            for f in files:
                text = read(os.path.join(root, f))
                self.assertNotRegex(text, r"/tmp/claude-\d+/-home|scratchpad/exp2|\.claude/projects/-", f)

    def test_templates_have_placeholders(self):
        chk = read(os.path.join(CASE, "checker-brief.md"))
        for k in ("{snap}", "{reports}", "{key}", "{report_count}"):
            self.assertIn(k, chk)
        self.assertIn("Opus 5.5 at medium", chk)
        self.assertIn("{reports}", read(os.path.join(CASE, "refuter-brief.md")))


class CaseCopy(TempHome):
    """A temp copy of the case with synthetic results."""

    def setUp(self):
        super().setUp()
        self.case = os.path.join(self.tmp, "review-hooks-browser")
        shutil.copytree(CASE, self.case, ignore=shutil.ignore_patterns("snap"))
        os.makedirs(os.path.join(self.case, "snap"))
        with open(os.path.join(self.case, "snap", "a.sh"), "w") as fh:
            fh.write("echo hi\n")
        self.sid = sorted(bench.setups(self.case))[0]

    def results(self, runs):
        h = bench.case_hashes(self.case)
        for r in runs:
            r.setdefault("setup_id", self.sid)
            for k, v in h.items():
                r.setdefault(k, v)
        with open(os.path.join(self.case, "results.json"), "w") as fh:
            json.dump({"skill": "review-mr", "runs": runs}, fh)

    def haiku_run(self, **kw):
        r = {"id": "J", "model": "claude-haiku-5-5", "effort": "max", "caught_strict": 12, "cost": 4.0,
             "cost_with_refuter": 7.0, "over_100k_share": 0.0, "date": "2026-11-25", "slowest_agent_min": 20}
        r.update(kw)
        return r

    def double_haiku(self):
        """A fixture model priced at twice Haiku 5.5, both tiers."""
        h = self.table.models["claude-haiku-5-5"]
        new = {k: v * 2 for k, v in h.items() if k != "long_prompt"}
        new["long_prompt"] = {k: (v * 2 if k != "threshold" else v) for k, v in h["long_prompt"].items()}
        self.table.models["claude-haiku-6"] = new


def aa(model, effort, value):
    return models.row("anthropic", model, effort, "cost_per_index_point", value, "u", "d", "aa-models-page")


class Plan(CaseCopy):
    def test_new_model_two_picks_and_estimate(self):
        self.results([self.haiku_run()])
        self.double_haiku()
        ext = [aa("claude-haiku-6", "max", 9.0), aa("claude-haiku-6", "high", 5.0), aa("claude-haiku-5-5", "max", 9.0)]
        out = bench.plan(self.case, None, ["claude-haiku-6", "claude-haiku-5-5"], ext, "medium", self.table)
        self.assertEqual(out["setup_id"], self.sid)
        self.assertEqual([(p["model"], p["effort"]) for p in out["picks"]],
                         [("claude-haiku-6", "high"), ("claude-haiku-6", "medium")])
        # reviewers $4 scaled x2 plus a $3 refuter unchanged
        self.assertEqual(out["picks"][0]["estimate"]["usd"], 11.0)
        self.assertEqual(out["total_estimate_usd"], 22.0)

    def test_equal_picks_collapse(self):
        self.results([self.haiku_run()])
        self.double_haiku()
        out = bench.plan(self.case, None, ["claude-haiku-6"], [aa("claude-haiku-6", "high", 5.0)], "high", self.table)
        self.assertEqual(len(out["picks"]), 1)
        self.assertEqual(len(out["picks"][0]["why"]), 2)

    def test_no_new_model(self):
        self.results([self.haiku_run()])
        out = bench.plan(self.case, None, ["claude-haiku-5-5"], [aa("claude-haiku-5-5", "max", 9.0)], "max", self.table)
        self.assertEqual(out["picks"], [])

    def test_estimate_falls_back_to_history_run_i(self):
        self.results([])
        out = bench.plan(self.case, None, ["claude-haiku-5-5"], None, None, self.table, fixed_effort="max")
        est = out["picks"][0]["estimate"]
        self.assertEqual((est["from_run"], est["usd"], est["from_history"]), ("I", 11.59, True))

    def test_history_run_in_results_json_wins(self):
        self.results([self.haiku_run(id="X", cost=2.0, cost_with_refuter=3.0, setup_id=None)])
        out = bench.plan(self.case, self.sid, ["claude-haiku-5-5"], None, "max", self.table)
        self.assertEqual(out["picks"][0]["estimate"]["from_run"], "X")

    def test_no_estimate_without_any_history(self):
        self.results([])
        with open(os.path.join(self.case, "RESULTS.md"), "w") as fh:
            fh.write("# x\n")
        the_plan = bench.plan(self.case, self.sid, ["claude-haiku-5-5"], None, "max", self.table)
        self.assertIsNone(the_plan["picks"][0]["estimate"])
        out = bench.run(self.case, the_plan, 10.0, lambda *a: None, os.path.join(self.tmp, "out"), lambda c, e: None)
        self.assertEqual(out["not_run"][0]["reason"], "no estimate")

    def test_gpt_reference_never_planned(self):
        self.results([self.haiku_run()])
        ext = [models.row("openai", "gpt-6", "high", "cost_per_index_point", 1.0, "u", "d", "aa-models-page")]
        out = bench.plan(self.case, None, None, ext, "high", self.table)
        self.assertEqual(out["picks"], [])


class Run(CaseCopy):
    def fake_agent(self, costs):
        calls = []

        def agent(prompt, model, effort, budget, name, cwd, case_dir):
            calls.append({"name": name, "budget": budget, "model": model})
            role = name.rsplit("-", 1)[-1]
            cost = costs.get(role, 0.0)
            if role == "checker":
                return {"cost": 0.0, "minutes": 1.0, "result": "SCORE caught_strict=10 partial=2 missed=2 real_extra=0 false=0"}
            return {"cost": cost, "minutes": 2.0, "result": "ok", "requests": 1, "over_100k": 0}
        agent.calls = calls
        return agent

    def test_cap_stops_third_run_and_passes_remaining_cap(self):
        self.results([])
        picks = [{"model": m, "effort": "high", "estimate": {"usd": e}}
                 for m, e in (("claude-a", 5.0), ("claude-b", 3.0), ("claude-c", 5.0))]
        stored = []
        # each run spends its estimate: $5 on its one slice agent, nothing else
        agent = self.fake_agent({"1": 5.0})
        costs = iter([5.0, 3.0])

        def agent2(prompt, model, effort, budget, name, cwd, case_dir):
            if name.endswith("slice-1"):
                agent.calls.append({"name": name, "budget": budget})
                return {"cost": next(costs), "minutes": 2.0, "result": "ok", "requests": 1, "over_100k": 0}
            return agent(prompt, model, effort, budget, name, cwd, case_dir)

        out = bench.run(self.case, {"setup_id": self.sid, "picks": picks}, 10.0, agent2,
                        os.path.join(self.tmp, "out"), lambda c, e: stored.append(e))
        self.assertEqual([r["entry"]["model"] for r in out["runs"]], ["claude-a", "claude-b"])
        self.assertIn("above the remaining cap", out["not_run"][0]["reason"])
        slice_calls = [c for c in agent.calls if c["name"].endswith("slice-1")]
        # each reviewer call may use the whole phase cap (no refuter estimate here, so the remaining cap)
        self.assertEqual([c["budget"] for c in slice_calls], [10.0, 5.0])
        self.assertEqual(out["remaining_cap"], 2.0)
        self.assertEqual(stored[0]["caught_strict"], 10)
        self.assertEqual(stored[0]["caught_with_partials"], 11.0)
        self.assertEqual(stored[0]["setup_id"], self.sid)
        self.assertEqual(stored[0]["status"], "complete")

    def test_reviewers_start_together_within_the_cap(self):
        for i in range(3):
            with open(os.path.join(self.case, "snap", f"b{i}.md"), "w") as fh:
                fh.write("x\n" * 300)
        self.results([])
        n = len(bench.cut_slices(bench.snapshot_files(os.path.join(self.case, "snap")),
                                 bench.setups(self.case)[self.sid][0]["size_rule"])) + 1
        barrier = threading.Barrier(n, timeout=5)
        calls, stored = [], []

        def agent(prompt, model, effort, budget, name, cwd, case_dir):
            calls.append((name, budget))
            if "-slice-" in name or name.endswith("runit"):
                barrier.wait()  # raises unless all reviewer calls run at the same time
            res = "SCORE caught_strict=9 partial=0 missed=5" if name.endswith("checker") else "ok"
            return {"cost": 0.1, "minutes": 3.0 if name.endswith("slice-1") else 1.0, "result": res}
        picks = [{"model": "m", "effort": "max", "estimate": {"usd": 6.0, "reviewers": 4.0, "refuter": 2.0}}]
        bench.run(self.case, {"setup_id": self.sid, "picks": picks}, 8.0, agent,
                  os.path.join(self.tmp, "out"), lambda c, e: stored.append(e))
        reviewer_budgets = [b for name, b in calls if "-slice-" in name or name.endswith("runit")]
        self.assertEqual(len(reviewer_budgets), n)
        self.assertEqual(set(reviewer_budgets), {6.0})  # phase cap: $8 minus the $2 refuter estimate
        e = stored[0]
        self.assertEqual(e["status"], "complete")
        self.assertEqual(e["phase_minutes"], {"reviewers": 3.0, "refuter": 1.0, "checker": 1.0})
        self.assertEqual(e["run_minutes"], 5.0)

    def test_phase_over_its_cap_stops_before_refuter(self):
        self.results([])
        stored = []
        agent = self.fake_agent({"1": 4.0, "runit": 3.0})
        picks = [{"model": "m", "effort": "max", "estimate": {"usd": 6.0, "reviewers": 4.0, "refuter": 2.0}}]
        bench.run(self.case, {"setup_id": self.sid, "picks": picks}, 8.0, agent,
                  os.path.join(self.tmp, "out"), lambda c, e: stored.append(e))
        self.assertTrue(stored[0]["reason"].startswith("reviewer phase spent $7.00, above its cap $6.00"))
        self.assertFalse(any(c["name"].endswith("refuter") for c in agent.calls))

    def test_resume_reruns_only_unfinished_roles(self):
        prior = {"id": "M", "model": "m", "effort": "max", "status": "incomplete", "reason": "x", "cost": 5.0,
                 "cost_with_refuter": 5.0, "roles": {"slice-1": False, "runit": True, "refuter": False, "checker": False},
                 "phase_minutes": {"reviewers": 20.0}, "date": "2026-11-25"}
        self.results([prior])
        out_dir = os.path.join(self.tmp, "out")
        os.makedirs(os.path.join(out_dir, "review-hooks-browser", "runs"))
        with open(os.path.join(out_dir, "review-hooks-browser", "runs", "M-runit.md"), "w") as fh:
            fh.write("old run-it report")
        agent, prompts, stored = self.fake_agent({"1": 1.0, "refuter": 2.0}), {}, []

        def spy(prompt, model, effort, budget, name, cwd, case_dir):
            prompts[name.rsplit("-", 1)[-1]] = prompt
            return agent(prompt, model, effort, budget, name, cwd, case_dir)
        picks = [{"model": "m", "effort": "max", "estimate": {"usd": 8.0, "reviewers": 6.0, "refuter": 2.0}}]
        out = bench.run(self.case, {"setup_id": self.sid, "picks": picks}, 7.0, spy, out_dir,
                        lambda c, e: stored.append(e), resume="M")
        self.assertEqual([c["name"].rsplit("-", 1)[-1] for c in agent.calls], ["1", "refuter", "checker"])
        self.assertIn("run-tmp/M-runit.md", prompts["refuter"])  # the refuter cannot read model-bench
        e = stored[0]
        self.assertEqual((e["id"], e["status"], e["cost"], e["cost_with_refuter"]), ("M", "complete", 6.0, 8.0))
        self.assertEqual(e["resumed"], "resumed: slice-1 rerun")
        self.assertEqual(e["phase_minutes"]["reviewers"], 20.0)
        self.assertEqual(len(out["runs"]), 1)

    def test_error_logs_incomplete_run(self):
        self.results([])
        stored = []

        def agent(prompt, model, effort, budget, name, cwd, case_dir):
            err = "error_max_budget_usd" if name.endswith("runit") else None
            return {"cost": 1.5, "minutes": 2.0, "result": "x", "error": err}
        picks = [{"model": "claude-haiku-5-5", "effort": "max", "estimate": {"usd": 5.0}}]
        out = bench.run(self.case, {"setup_id": self.sid, "picks": picks}, 10.0, agent,
                        os.path.join(self.tmp, "out"), lambda c, e: stored.append(e))
        e = stored[0]
        self.assertEqual((e["status"], e["cost"], e["cost_with_refuter"]), ("incomplete", 3.0, 3.0))
        self.assertIn("runit stopped", e["reason"])
        self.assertEqual(e["roles"], {"slice-1": True, "runit": False, "refuter": False, "checker": False})
        self.assertEqual(out["runs"][0]["status"], "incomplete")
        # never ranked, never the baseline, and the model is planned again
        results = {"runs": stored}
        self.assertIsNone(bench.current_model(results, self.sid))
        self.results(stored)
        self.assertEqual(len(bench.plan(self.case, self.sid, ["claude-haiku-5-5"], None, "max", self.table)["picks"]), 1)

    def test_cap_reached_before_refuter(self):
        self.results([])
        stored = []
        agent = self.fake_agent({"1": 5.0, "runit": 5.0})
        picks = [{"model": "claude-haiku-5-5", "effort": "max", "estimate": {"usd": 5.0}}]
        bench.run(self.case, {"setup_id": self.sid, "picks": picks}, 10.0, agent,
                  os.path.join(self.tmp, "out"), lambda c, e: stored.append(e))
        self.assertTrue(stored[0]["reason"].startswith("cap reached before refuter could start"))
        self.assertFalse(any(c["name"].endswith("refuter") for c in agent.calls))

    def test_incomplete_line_in_results_md(self):
        self.results([])
        orig = bench.is_repo_checkout
        bench.is_repo_checkout = lambda c: True
        try:
            bench.store(self.case, {"id": "J", "setup_id": self.sid, "model": "m", "effort": "max",
                                    "status": "incomplete", "reason": "cap reached before refuter could start",
                                    "cost": 3.0, "cost_with_refuter": 3.0, "date": "2026-11-25",
                                    "roles": {"slice-1": True, "refuter": False}})
        finally:
            bench.is_repo_checkout = orig
        self.assertIn("| J | " + self.sid + " | m max | incomplete: cap reached before refuter could start; "
                      "finished: slice-1 | $3.00 ($3.00) | n/a | 2026-11-25 |", read(os.path.join(self.case, "RESULTS.md")))

    def test_replies_saved_as_reports(self):
        self.results([])
        prompts = []
        agent = self.fake_agent({})

        def spy(prompt, *rest):
            prompts.append(prompt)
            return agent(prompt, *rest)
        out_dir = os.path.join(self.tmp, "out")
        bench.run(self.case, {"setup_id": self.sid, "picks": [{"model": "m", "effort": "max", "estimate": {"usd": 1.0}}]},
                  10.0, spy, out_dir, lambda c, e: None)
        self.assertEqual(read(os.path.join(out_dir, "review-hooks-browser", "runs", "J-slice-1.md")), "ok")

    def test_report_file_kept_from_temp_folder(self):
        self.results([])
        out_dir = os.path.join(self.tmp, "out")

        def agent(prompt, model, effort, budget, name, cwd, case_dir):
            m = re.search(r"(\S*run-tmp/J-slice-1\.md)", prompt)
            if m:
                with open(m.group(1).strip("`"), "w") as fh:
                    fh.write("file report")
            res = "SCORE caught_strict=1 partial=0 missed=13" if name.endswith("checker") else "reply"
            return {"cost": 0.0, "minutes": 1.0, "result": res}
        bench.run(self.case, {"setup_id": self.sid, "picks": [{"model": "m", "effort": "max", "estimate": {"usd": 1.0}}]},
                  10.0, agent, out_dir, lambda c, e: None)
        runs = os.path.join(out_dir, "review-hooks-browser", "runs")
        self.assertEqual(read(os.path.join(runs, "J-slice-1.md")), "file report")
        self.assertEqual(read(os.path.join(runs, "J-runit.md")), "reply")

    def test_rerun_reply_replaces_old_report(self):
        path = os.path.join(self.tmp, "r.md")
        with open(path, "w") as fh:
            fh.write("old stub")
        bench.save_reply(path, "new reply", os.path.join(self.tmp, "missing.md"))
        self.assertEqual(read(path), "new reply")

    def test_stored_run_never_planned_again(self):
        self.results([self.haiku_run()])
        picks = [{"model": "claude-haiku-5-5", "effort": "high", "estimate": {"usd": 1.0}}]
        out = bench.run(self.case, {"setup_id": self.sid, "picks": picks}, 10.0, self.fake_agent({}),
                        os.path.join(self.tmp, "out"), lambda c, e: None)
        self.assertEqual(out["runs"], [])
        self.assertIn("already has a result", out["not_run"][0]["reason"])

    def test_temp_folder_is_a_git_snapshot_and_removed(self):
        folder = bench.prepare_folder(self.case, self.tmp)
        self.assertTrue(os.path.exists(os.path.join(folder["snap"], "a.sh")))
        self.assertFalse(os.path.exists(os.path.join(folder["root"], "answer-key.md")))
        self.assertIn("+echo hi", read(folder["diff"]))
        shutil.rmtree(folder["root"])

    def test_store_refuses_installed_copy(self):
        with self.assertRaises(RuntimeError):
            bench.store(self.case, {"id": "J"})  # temp copy is not a repo checkout


class Repeat(CaseCopy):
    def test_one_behind_repeats_seven_behind_does_not(self):
        cur = {"caught_strict": 13}
        self.assertTrue(bench.propose_repeat(12, cur))
        self.assertFalse(bench.propose_repeat(6, cur))

    def test_current_from_models_line(self):
        self.results([self.haiku_run(), self.haiku_run(id="K", model="claude-sonnet-5-5", effort="high",
                                                        caught_strict=13, cost_with_refuter=50.0)])
        md = "# x\n\n## Models\n\n- Coding: Opus 5.5 medium\n- Review slices: Sonnet 5.5 high (about 7 agents)\n\n## Other\n"
        cur = bench.current_model(bench.load_json(os.path.join(self.case, "results.json")), self.sid, [md])
        self.assertEqual((cur["model"], cur["effort"], cur["source"], cur["caught_strict"]),
                         ("claude-sonnet-5-5", "high", "models line", 13))

    def test_current_from_results_without_line(self):
        self.results([self.haiku_run(), self.haiku_run(id="K", model="claude-sonnet-5-5", effort="high",
                                                        caught_strict=13, cost_with_refuter=50.0)])
        cur = bench.current_model(bench.load_json(os.path.join(self.case, "results.json")), self.sid, ["# no section\n"])
        self.assertEqual((cur["model"], cur["source"]), ("claude-haiku-5-5", "best stored result"))

    def test_changed_checker_brief_marks_case(self):
        self.results([self.haiku_run()])
        with open(os.path.join(self.case, "checker-brief.md"), "a") as fh:
            fh.write("\nchanged\n")
        out = bench.comparability(bench.load_json(os.path.join(self.case, "results.json")), self.case)
        self.assertEqual(out["case_not_comparable"], ["checker_brief"])

    def test_changed_brief_marks_setup(self):
        self.results([self.haiku_run()])
        with open(os.path.join(self.case, "setups", "review-mr-v1", "slice-brief.md"), "a") as fh:
            fh.write("\nchanged\n")
        out = bench.comparability(bench.load_json(os.path.join(self.case, "results.json")), self.case)
        self.assertEqual(out["case_not_comparable"], [])
        self.assertEqual(out["runs_not_comparable"][0]["reasons"], ["setup changed"])


class Call(TempHome):
    def test_usage_limit_is_the_reason_not_success(self):
        out = {"is_error": True, "subtype": "success", "result": "You've hit your 5-hour limit · resets 8:20am"}
        self.assertEqual(bench.call_error(out), "You've hit your 5-hour limit · resets 8:20am")
        self.assertEqual(bench.call_error({"is_error": True, "subtype": "error_max_budget_usd"}), "error_max_budget_usd")
        self.assertIsNone(bench.call_error({"is_error": False, "subtype": "success", "result": "ok"}))

    def test_tools_allowed_in_dont_ask_mode(self):
        cmd = bench.agent_cmd("p", "m", "max", 1.0, "n", "/case", "/nonexistent/x.json")
        self.assertEqual(cmd[cmd.index("--allowedTools") + 1], "Read,Grep,Glob,Bash")
        self.assertIn("Read(//case/**)", cmd)


class Trim(TempHome):
    def test_only_base_plugin_and_no_mcp(self):
        path = os.path.join(self.tmp, "settings.json")
        with open(path, "w") as fh:
            json.dump({"enabledPlugins": {"base@m": True, "extras@m": True, "ctx@x": True, "old@x": False}}, fh)
        flags = bench.trim_flags(path)
        self.assertEqual(flags[0], "--strict-mcp-config")
        self.assertEqual(json.loads(flags[2]), {"enabledPlugins": {"extras@m": False, "ctx@x": False}})

    def test_missing_settings(self):
        self.assertEqual(json.loads(bench.trim_flags("/nonexistent/x.json")[2]), {"enabledPlugins": {}})
