import datetime as dt
import json
import os

from helpers import TempHome, agent_call, asst, human, skill_load, usage
import report

NOW = dt.datetime(2026, 11, 21, tzinfo=dt.timezone.utc)
RM = "base:review-mr"


class ReportBase(TempHome):
    def setUp(self):
        super().setUp()
        self.scratch = os.path.join(self.tmp, "scratch")
        self.runs_root = os.path.join(self.tmp, "review-runs")

    def report(self, **kw):
        return report.report(projects_dir=self.projects, scratch_root=self.scratch, table=self.table, now=NOW,
                             runs_root=self.runs_root, **kw)

    def skill_runs(self, skill, n, sid="s1", cost_tokens=None, start=0):
        """n runs of one skill in one session, each with one request."""
        entries = []
        for i in range(n):
            sec = start + i * 10
            inp = (cost_tokens or [1000] * n)[i]
            entries += [human(sec), skill_load(sec), asst(f"{sid}-{skill}-{i}", sec + 1, skill=skill, u=usage(inp=inp, out=0))]
        return entries


class TopSkills(ReportBase):
    def test_default_top_five(self):
        entries = []
        for k in range(7):
            entries += self.skill_runs(f"skill-{k}", 1, cost_tokens=[1000 * (k + 1)], start=k * 100)
        self.session("s1", entries)
        out = self.report()
        self.assertEqual([s["skill"] for s in out["skills"]], [f"skill-{k}" for k in (6, 5, 4, 3, 2)])
        self.assertEqual(out["skills_in_window"], 7)

    def test_fewer_skills_than_limit(self):
        self.session("s1", self.skill_runs("a", 1) + self.skill_runs("b", 1, start=100) + self.skill_runs("c", 1, start=200))
        out = self.report()
        self.assertEqual(len(out["skills"]), 3)
        self.assertEqual(out["skills_in_window"], 3)

    def test_custom_run_count_and_outlier_also_recent(self):
        # five runs; the most expensive is the latest, so it is read once with both reasons
        self.session("s1", self.skill_runs("x", 5, cost_tokens=[100, 200, 300, 400, 9000]))
        runs = self.report(n_runs=3)["skills"][0]["runs"]
        self.assertEqual(len(runs), 3)
        self.assertIn("most_expensive", runs[0]["picked_because"])
        self.assertIn("recent", runs[0]["picked_because"])

    def test_old_expensive_run_added_as_outlier(self):
        self.session("s1", self.skill_runs("x", 5, cost_tokens=[9000, 200, 300, 400, 500]))
        runs = self.report(n_runs=2)["skills"][0]["runs"]
        self.assertEqual(len(runs), 3)
        self.assertIn("most_expensive", runs[-1]["picked_because"])
        self.assertNotIn("recent", runs[-1]["picked_because"])

    def test_unfinished_na_skips_outlier(self):
        self.session("s1", self.skill_runs("x", 2))
        skill = self.report()["skills"][0]
        self.assertTrue(all("most_unfinished" not in r["picked_because"] for r in skill["runs"]))
        self.assertTrue(skill["notes"])

    def test_trends(self):
        entries = self.skill_runs("x", 2)
        entries.append(asst("big", 30, skill="x", u=usage(inp=120_000, out=0)))
        self.session("s1", entries)
        t = self.report()["skills"][0]["trends"]
        self.assertEqual(t["runs"], 2)
        self.assertAlmostEqual(t["over_100k_share"], 1 / 3, places=3)
        self.assertEqual(list(t["per_month"]), ["2026-11"])
        self.assertIn("main session: claude-opus-5-5 / medium", t["per_model_effort"])

    def test_model_switch_inside_a_run(self):
        self.session("s1", [human(0), skill_load(0), asst("m1", 1, skill="x"),
                            asst("m2", 2, skill="x", model="claude-sonnet-5-5")])
        run = self.report()["skills"][0]["runs"][0]
        self.assertEqual(run["model_switch"], ["claude-opus-5-5 / medium", "claude-sonnet-5-5 / medium"])


class RunJson(ReportBase):
    def build(self, run_json=True, extra_agents=(), findings=None):
        sid = "s1"
        entries = [human(0)]
        names = [("a1", "slice-owner", "slice-1"), ("a2", "slice-owner", "slice-2"),
                 ("a3", "slice-owner", "slice-3"), ("a4", "refuter", None)]
        for i, (aid, _, _) in enumerate(names):
            entries.append(agent_call(f"c{i}", 1 + i, f"tu{i}", skill=RM))
        self.session(sid, entries)
        for i, (aid, _, _) in enumerate(names):
            self.agent(sid, aid, [asst(f"am{i}", 10 + i, model="claude-haiku-5-5")],
                       {"agentType": "general-purpose", "toolUseId": f"tu{i}", "spawnDepth": 1})
        if run_json:
            agents = [{"agent_id": aid, "role": role, **({"slice": sl} if sl else {}), "model": "haiku", "effort": "max"}
                      for aid, role, sl in names] + list(extra_agents)
            data = {"agents": agents, "findings": findings if findings is not None else [
                {"id": "slice-2-1", "source": "slice-2", "duplicates": [], "survived": True},
                {"id": "slice-2-2", "source": "slice-2", "duplicates": ["runit"], "survived": True},
                {"id": "slice-1-1", "source": "slice-1", "duplicates": [], "survived": False}]}
            path = os.path.join(self.scratch, "-home-u-proj", sid, "scratchpad", "run.json")
            os.makedirs(os.path.dirname(path))
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
        out = self.report()
        return out, out["skills"][0]["runs"][0]

    def test_labels_cost_and_unique_findings(self):
        out, run = self.build()
        labels = sorted(a["label"] for a in run["agents"])
        self.assertEqual(labels, ["refuter", "slice-owner slice-1", "slice-owner slice-2", "slice-owner slice-3"])
        self.assertEqual(run["role_costs"]["slice-owner"]["agents"], 3)
        self.assertGreater(run["role_costs"]["refuter"]["cost"], 0)
        self.assertEqual(run["findings_by_role"]["slice-owner"], {"unique": 2, "repeated": 0})
        self.assertEqual((out["review_run_json"]["review_runs"], out["review_run_json"]["with_run_json"]), (1, 1))
        a = next(a for a in run["agents"] if a["label"] == "refuter")
        self.assertEqual((a["requested_model"], a["model"]), ("haiku", "claude-haiku-5-5"))

    def test_repeated_finding(self):
        _, run = self.build()
        self.assertEqual(run["findings_by_role"]["runit"], {"unique": 0, "repeated": 1})

    def test_no_run_json_keeps_meta_labels(self):
        out, run = self.build(run_json=False)
        self.assertEqual({a["label"] for a in run["agents"]}, {"general-purpose"})
        self.assertGreater(run["cost"], 0)
        self.assertEqual((out["review_run_json"]["review_runs"], out["review_run_json"]["with_run_json"]), (1, 0))

    def write_run_json(self, data, sid="s1"):
        path = os.path.join(self.scratch, "-home-u-proj", sid, "scratchpad", "run.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(data if isinstance(data, str) else json.dumps(data))

    def test_malformed_entries_skipped_not_fatal(self):
        self.write_run_json({"agents": [{"agent_id": "a1", "slice": "slice-1"}, {"agent_id": "a2", "role": "x", "slice": 3},
                                        "junk", {"role": "refuter"}],
                             "findings": [{"source": "slice-1", "duplicates": "refuter", "survived": True},
                                          {"source": "slice-1", "duplicates": [], "survived": "false"},
                                          {"source": "slice-1", "duplicates": [], "survived": True}]})
        _, run = self.build(run_json=False)
        self.assertEqual(run["findings_by_role"], {"unknown": {"unique": 1, "repeated": 0}})

    def test_broken_run_json_reported(self):
        self.write_run_json("{not json")
        out, _ = self.build(run_json=False)
        self.assertEqual(out["review_run_json"]["with_run_json"], 0)
        self.assertIn("run.json", out["review_run_json"]["errors"][0])

    def test_run_json_goes_to_the_run_it_lists(self):
        entries = [human(0), skill_load(0), agent_call("c1", 1, "tu1", skill=RM),
                   human(100), skill_load(100), asst("late", 101, skill=RM)]
        self.session("s1", entries)
        self.agent("s1", "a1", [asst("am1", 2, model="claude-haiku-5-5")], {"toolUseId": "tu1", "spawnDepth": 1})
        self.write_run_json({"agents": [{"agent_id": "a1", "role": "slice-owner", "slice": "slice-1"}]})
        runs = self.report()["skills"][0]["runs"]
        with_json = [r for r in runs if r["run_json"]]
        self.assertEqual(len(with_json), 1)
        self.assertEqual(with_json[0]["agents"][0]["label"], "slice-owner slice-1")

    def test_codex_agent_has_no_cost(self):
        _, run = self.build(extra_agents=[{"agent_id": "job-1", "role": "slice-owner", "slice": "slice-4", "model": "codex"},
                                          {"agent_id": "job-2", "model": "codex"}])
        codex = next(a for a in run["agents"] if a["model"] == "codex")
        self.assertIsNone(codex["cost"])
        self.assertEqual(run["role_costs"]["slice-owner"]["unpriced"], 1)
        self.assertEqual(run["role_costs"]["codex"]["unpriced"], 1)


class RunFolders(ReportBase):
    """review-mr runs labelled from their own folders under the runs root, the scratchpad as fallback."""

    def three_runs(self):
        # run 1 at 10:00:00 spawns a1, run 2 at 10:01:40 spawns a2, run 3 at 10:03:20 spawns no agent
        entries = [human(0), skill_load(0), agent_call("c1", 1, "tu1", skill=RM),
                   human(100), skill_load(100), agent_call("c2", 101, "tu2", skill=RM),
                   human(200), skill_load(200), asst("r3", 201, skill=RM)]
        self.session("s1", entries)
        self.agent("s1", "a1", [asst("am1", 2, model="claude-haiku-5-5")], {"toolUseId": "tu1", "spawnDepth": 1})
        self.agent("s1", "a2", [asst("am2", 102, model="claude-haiku-5-5")], {"toolUseId": "tu2", "spawnDepth": 1})

    def write_folder(self, name, data):
        path = os.path.join(self.runs_root, "-home-u-proj", "s1", name, "run.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def write_scratch(self, data):
        path = os.path.join(self.scratch, "-home-u-proj", "s1", "scratchpad", "run.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def runs(self, out):
        return sorted(out["skills"][0]["runs"], key=lambda r: r["start"])

    def labels(self, run):
        return sorted(a["label"] for a in run["agents"])

    def test_two_runs_in_one_session_each_get_their_folder(self):
        self.three_runs()
        self.write_folder("20261120T100005Z-gitlab-1", {"agents": [{"agent_id": "a1", "role": "slice-owner", "slice": "slice-1"}]})
        self.write_folder("20261120T100145Z-gitlab-2", {"agents": [{"agent_id": "a2", "role": "refuter"}]})
        out = self.report()
        r1, r2, r3 = self.runs(out)
        self.assertEqual(self.labels(r1), ["slice-owner slice-1"])
        self.assertEqual(self.labels(r2), ["refuter"])
        self.assertFalse(r3["run_json"])
        self.assertEqual(out["review_run_json"]["with_run_json"], 2)
        self.assertEqual(out["review_run_json"]["runs_root"], self.runs_root)

    def test_run_without_agents_matched_by_folder_time(self):
        self.three_runs()
        self.write_folder("20261120T100330Z-gitlab-3", {"agents": [], "findings": [
            {"source": "slice-1", "duplicates": [], "survived": True}]})
        r1, r2, r3 = self.runs(self.report())
        self.assertEqual((r1["run_json"], r2["run_json"], r3["run_json"]), (False, False, True))
        self.assertEqual(r3["findings_by_role"], {"slice-1": {"unique": 1, "repeated": 0}})

    def test_folder_before_every_run_is_reported_not_guessed(self):
        self.three_runs()
        self.write_folder("20261120T095900Z-gitlab-0", {"agents": []})
        out = self.report()
        self.assertEqual(out["review_run_json"]["with_run_json"], 0)
        self.assertIn("no review run in this session matches", out["review_run_json"]["errors"][0])

    def test_older_run_falls_back_to_the_scratchpad(self):
        self.three_runs()
        self.write_folder("20261120T100145Z-gitlab-2", {"agents": [{"agent_id": "a2", "role": "refuter"}]})
        self.write_scratch({"agents": [{"agent_id": "a1", "role": "slice-owner", "slice": "slice-1"}]})
        r1, r2, _ = self.runs(self.report())
        self.assertEqual(self.labels(r1), ["slice-owner slice-1"])
        self.assertEqual(self.labels(r2), ["refuter"])

    def test_scratchpad_never_relabels_a_run_its_folder_labelled(self):
        self.three_runs()
        self.write_folder("20261120T100005Z-gitlab-1", {"agents": [{"agent_id": "a1", "role": "slice-owner", "slice": "slice-1"}]})
        self.write_scratch({"agents": [{"agent_id": "a1", "role": "contract"}]})
        out = self.report()
        r1, r2, r3 = self.runs(out)
        self.assertEqual(self.labels(r1), ["slice-owner slice-1"])
        self.assertEqual((r2["run_json"], r3["run_json"]), (False, False))
        self.assertEqual(out["review_run_json"]["with_run_json"], 1)

    def test_second_folder_of_a_labelled_run_is_reported_not_given_to_an_earlier_run(self):
        self.three_runs()
        self.write_folder("20261120T100145Z-gitlab-2", {"agents": [{"agent_id": "a2", "role": "refuter"}]})
        self.write_folder("20261120T100150Z-gitlab-2", {"agents": []})
        out = self.report()
        r1, r2, _ = self.runs(out)
        self.assertEqual(self.labels(r2), ["refuter"])
        self.assertFalse(r1["run_json"])
        self.assertEqual(out["review_run_json"]["with_run_json"], 1)
        self.assertIn("a second folder for run", out["review_run_json"]["errors"][0])

    def test_folder_with_agents_beats_an_earlier_empty_folder_of_the_same_run(self):
        self.three_runs()
        self.write_folder("20261120T100145Z-gitlab-2", {"agents": []})
        self.write_folder("20261120T100400Z-gitlab-2", {"agents": [{"agent_id": "a2", "role": "refuter"}]})
        out = self.report()
        _, r2, r3 = self.runs(out)
        self.assertEqual(self.labels(r2), ["refuter"])
        self.assertFalse(r3["run_json"])
        self.assertIn("a second folder for run", out["review_run_json"]["errors"][0])

    def test_folder_older_than_the_window_is_skipped_silently(self):
        self.three_runs()
        self.write_folder("20261001T090000Z-gitlab-0", {"agents": []})
        out = self.report()
        self.assertEqual(out["review_run_json"]["with_run_json"], 0)
        self.assertNotIn("errors", out["review_run_json"])

    def test_neither_folder_nor_scratchpad_keeps_meta_labels(self):
        self.three_runs()
        out = self.report()
        self.assertEqual(out["review_run_json"]["with_run_json"], 0)
        self.assertEqual({a["label"] for r in self.runs(out) for a in r["agents"]}, {"unknown"})

    def test_default_runs_root_follows_xdg_data_home(self):
        old = os.environ.get("XDG_DATA_HOME")
        os.environ["XDG_DATA_HOME"] = "/x/data"
        try:
            self.assertEqual(report.default_runs_root(), "/x/data/review-runs")
            del os.environ["XDG_DATA_HOME"]
            self.assertEqual(report.default_runs_root(), os.path.join(os.path.expanduser("~"), ".local", "share", "review-runs"))
        finally:
            if old is not None:
                os.environ["XDG_DATA_HOME"] = old


class Renamed(ReportBase):
    def test_renamed_plugin_is_one_skill(self):
        self.session("s1", [human(0), skill_load(0), asst("m1", 1, skill="base-setup:setup-zsh"),
                            human(10), skill_load(10), asst("m2", 11, skill="base:setup-zsh")])
        skills = self.report()["skills"]
        self.assertEqual(len(skills), 1)
        self.assertEqual((skills[0]["skill_display"], skills[0]["older_names"]), ("base:setup-zsh", ["base-setup:setup-zsh"]))
        self.assertEqual(skills[0]["trends"]["runs"], 2)


class Unpriced(ReportBase):
    def test_unpriced_skill_flagged(self):
        self.session("s1", [human(0), skill_load(0), asst("m1", 1, skill="cheap", model="claude-new-9", u=usage(inp=10**6)),
                            human(10), skill_load(10), asst("m2", 11, skill="known")])
        out = self.report()
        cheap = next(s for s in out["skills"] if s["skill"] == "cheap")
        self.assertEqual(cheap["trends"]["unpriced_requests"], 1)
        self.assertTrue(any("without a price" in n for n in cheap["notes"]))


class Retention(TempHome):
    def setUp(self):
        super().setUp()
        self._real_retention = report.retention
        report_mod = report

        def isolated(settings_path, projects_dir, project_dir=None, managed=()):
            return self._real_retention(settings_path, projects_dir, project_dir, managed)
        report_mod.retention = isolated

    def tearDown(self):
        report.retention = self._real_retention
        super().tearDown()

    def write(self, rel, data):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return path

    def test_managed_setting_wins_and_no_offer(self):
        managed = self.write("etc/managed-settings.json", {"cleanupPeriodDays": 14})
        r = self._real_retention(self.settings({"cleanupPeriodDays": 90}), self.projects, None, [managed])
        self.assertEqual((r["source"], r["effective_days"], r["offer"]), ("managed", 14, False))
        self.assertIn("override your user settings", r["note"])

    def test_project_setting_wins_over_user(self):
        self.write("proj/.claude/settings.json", {"cleanupPeriodDays": 60})
        r = self._real_retention(self.settings({"cleanupPeriodDays": 90}), self.projects, os.path.join(self.tmp, "proj"), [])
        self.assertEqual((r["source"], r["effective_days"], r["offer"]), ("project", 60, False))

    def test_user_setting_used_when_nothing_overrides(self):
        r = self._real_retention(self.settings({"cleanupPeriodDays": 90}), self.projects, os.path.join(self.tmp, "proj"), [])
        self.assertEqual((r["source"], r["offer"]), ("user", True))

    def test_managed_paths_listed(self):
        self.assertTrue(all(f.endswith(".json") for f in report.managed_settings_files()))

    def settings(self, data=None):
        path = os.path.join(self.tmp, "settings.json")
        if data is not None:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
        return path

    def test_unset_offers(self):
        self.session("s1", [human(0)])
        r = report.retention(self.settings(), self.projects)
        self.assertEqual((r["cleanupPeriodDays"], r["effective_days"], r["offer"]), (None, 30, True))
        self.assertGreater(r["estimate_bytes_at_180_days"], 0)

    def test_float_whole_number_accepted(self):
        r = report.retention(self.settings({"cleanupPeriodDays": 180.0}), self.projects)
        self.assertEqual((r["effective_days"], r["offer"]), (180, False))

    def test_non_object_settings_not_replaced(self):
        path = os.path.join(self.tmp, "settings.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("[1, 2]")
        self.assertIn("error", report.retention(path, self.projects))
        with self.assertRaises(ValueError):
            report.set_retention(180, path)
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "[1, 2]")

    def test_set_retention_rejects_below_one(self):
        path = self.settings({"model": "opus"})
        for bad in (0, -5):
            with self.assertRaises(ValueError):
                report.set_retention(bad, path)
        with self.assertRaises(SystemExit):
            report.main(["--set-retention", "0", "--settings", path])

    def test_cli_rejects_negative_top(self):
        with self.assertRaises(SystemExit):
            report.main(["--top", "-1"])

    def test_zero_is_invalid_and_offers(self):
        # Claude Code rejects 0 (minimum 1), so the default of 30 applies
        r = report.retention(self.settings({"cleanupPeriodDays": 0}), self.projects)
        self.assertEqual((r["effective_days"], r["offer"]), (30, True))
        self.assertIn("not a valid value", r["note"])

    def test_malformed_settings_reported(self):
        path = os.path.join(self.tmp, "settings.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('{"a": 1,}')
        r = report.retention(path, self.projects)
        self.assertFalse(r["offer"])
        self.assertIn("unreadable", r["error"])
        with self.assertRaises(ValueError):
            report.set_retention(180, path)

    def test_write_keeps_symlink(self):
        real = self.settings({"model": "opus"})
        link = os.path.join(self.tmp, "link.json")
        os.symlink(real, link)
        report.set_retention(180, link)
        self.assertTrue(os.path.islink(link))
        with open(real, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), {"model": "opus", "cleanupPeriodDays": 180})

    def test_under_180_offers(self):
        self.assertTrue(report.retention(self.settings({"cleanupPeriodDays": 90}), self.projects)["offer"])

    def test_180_or_more_no_offer(self):
        for v in (180, 365):
            self.assertFalse(report.retention(self.settings({"cleanupPeriodDays": v}), self.projects)["offer"])

    def test_write_keeps_other_keys(self):
        keep = {"env": {"A": "1"}, "permissions": {"allow": ["Bash(ls)"]}, "model": "opus"}
        path = self.settings(keep)
        report.set_retention(180, path)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data, dict(keep, cleanupPeriodDays=180))
        self.assertEqual([f for f in os.listdir(self.tmp) if f.endswith(".tmp")], [])

    def test_write_creates_missing_file(self):
        path = os.path.join(self.tmp, "new", "settings.json")
        report.set_retention(180, path)
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), {"cleanupPeriodDays": 180})


if __name__ == "__main__":
    import unittest
    unittest.main()
