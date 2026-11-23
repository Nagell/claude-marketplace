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

    def report(self, **kw):
        return report.report(projects_dir=self.projects, scratch_root=self.scratch, table=self.table, now=NOW, **kw)

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
        self.assertIn("main session", t["per_model_effort"])


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
        self.assertEqual(out["review_run_json"], {"review_runs": 1, "with_run_json": 1})
        a = next(a for a in run["agents"] if a["label"] == "refuter")
        self.assertEqual((a["requested_model"], a["model"]), ("haiku", "claude-haiku-5-5"))

    def test_repeated_finding(self):
        _, run = self.build()
        self.assertEqual(run["findings_by_role"]["runit"], {"unique": 0, "repeated": 1})

    def test_no_run_json_keeps_meta_labels(self):
        out, run = self.build(run_json=False)
        self.assertEqual({a["label"] for a in run["agents"]}, {"general-purpose"})
        self.assertGreater(run["cost"], 0)
        self.assertEqual(out["review_run_json"], {"review_runs": 1, "with_run_json": 0})

    def test_codex_agent_has_no_cost(self):
        _, run = self.build(extra_agents=[{"agent_id": "job-1", "role": "slice-owner", "slice": "slice-4", "model": "codex"},
                                          {"agent_id": "job-2", "model": "codex"}])
        codex = next(a for a in run["agents"] if a["model"] == "codex")
        self.assertIsNone(codex["cost"])
        self.assertEqual(run["role_costs"]["slice-owner"]["unpriced"], 1)
        self.assertEqual(run["role_costs"]["codex"]["unpriced"], 1)


class Retention(TempHome):
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
