import datetime as dt
import json
import os

from helpers import FIXTURES, TempHome, asst, human, skill_load, usage
import models
import prices
import report

NOW = dt.datetime(2026, 11, 21, tzinfo=dt.timezone.utc)


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


def bench_title(title):
    return {"type": "custom-title", "customTitle": title, "sessionId": "x"}


class Usage(TempHome):
    def runs(self, skill, model, effort, n, start, inp=1000):
        out = []
        for i in range(n):
            sec = start + i * 10
            out += [human(sec), skill_load(sec),
                    asst(f"{skill}-{start}-{i}", sec + 1, model=model, effort=effort, skill=skill, u=usage(inp=inp, out=0))]
        return out

    def test_model_effort_and_cost_per_run_for_two_skills(self):
        entries = (self.runs("a", "claude-opus-5-5", "medium", 2, 0) + self.runs("a", "claude-haiku-5-5", "max", 1, 100)
                   + self.runs("b", "claude-sonnet-5-5", "high", 2, 200))
        self.session("s1", entries)
        out = models.usage(projects_dir=self.projects, table=self.table, now=NOW)
        by = {s["skill"]: s for s in out["skills"]}
        self.assertEqual((by["a"]["model"], by["a"]["effort"]), ("claude-opus-5-5", "medium"))
        self.assertEqual((by["b"]["model"], by["b"]["effort"]), ("claude-sonnet-5-5", "high"))
        self.assertEqual(by["b"]["runs"], 2)
        self.assertAlmostEqual(by["b"]["cost_per_run"]["mean"], 1000 * 2.0 / 1e6)
        self.assertEqual(by["a"]["runs"], 3)

    def test_bench_session_left_out_of_both_modes(self):
        self.session("s1", self.runs("a", "claude-opus-5-5", "medium", 1, 0))
        self.session("s2", [bench_title("bench-review-hooks-browser-J")] + self.runs("bench", "claude-haiku-5-5", "max", 3, 50))
        self.assertEqual([s["skill"] for s in models.usage(projects_dir=self.projects, table=self.table, now=NOW)["skills"]],
                         ["a"])
        rep = report.report(projects_dir=self.projects, scratch_root=self.tmp, table=self.table, now=NOW)
        self.assertEqual([s["skill"] for s in rep["skills"]], ["a"])

    def test_other_custom_title_counts(self):
        self.session("s2", [bench_title("benchmark notes")] + self.runs("a", "claude-opus-5-5", "medium", 1, 0))
        out = models.usage(projects_dir=self.projects, table=self.table, now=NOW)
        self.assertEqual([s["skill"] for s in out["skills"]], ["a"])


class Prices(TempHome):
    def table_with(self, change):
        path = os.path.join(self.tmp, "seed.json")
        with open(prices.SEED_PATH, encoding="utf-8") as fh:
            seed = json.load(fh)
        change(seed["models"])
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(seed, fh)
        return prices.PriceTable(path, None)

    def test_parse_saved_page(self):
        page, notes = models.parse_pricing(fixture("pricing.md"))
        self.assertEqual(page["claude-opus-4-1"]["retired"], True)
        self.assertEqual(page["claude-opus-4-1"]["display"], "Claude Opus 4.1")
        self.assertNotIn("retired", page["claude-opus-5-5"])
        self.assertEqual(page["claude-haiku-5-5"]["long_prompt"]["threshold"], 100000)
        self.assertEqual(page["claude-haiku-5-5"]["long_prompt"]["output"], 2.5)
        self.assertEqual(page["claude-haiku-5-5"]["input"], 0.1)
        self.assertTrue(any("0.05x" in n for n in notes))

    def test_added_changed_retired(self):
        def change(m):
            del m["claude-opus-4-8"]
            m["claude-sonnet-5-5"]["output"] = 12.0
        out = models.check_prices(self.table_with(change), fixture("pricing.md"))
        self.assertIn("claude-opus-4-8", [a["model"] for a in out["added"]])
        ch = {c["model"]: c for c in out["changed"]}
        self.assertEqual(ch["claude-sonnet-5-5"]["fields"], {"output": {"old": 12.0, "new": 10.0}})
        self.assertIn("claude-opus-4-1", out["retired"])
        self.assertNotIn("claude-haiku-5-5", ch)

    def test_write_only_changed_model_keeps_other_keys(self):
        path = os.path.join(self.tmp, "home", "usage", "prices.json")
        os.makedirs(os.path.dirname(path))
        other = {"input": 1.0, "output": 2.0, "cache_write_5m": 1.0, "cache_write_1h": 1.0, "cache_read": 0.1}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"version": "old", "note": "mine", "models": {"claude-x": other}}, fh)
        def change(m):
            m["claude-sonnet-5-5"]["output"] = 12.0
        out = models.check_prices(self.table_with(change), fixture("pricing.md"))
        written = models.write_override({c["model"]: c["new"] for c in out["added"] + out["changed"]}, path, "v2")
        self.assertEqual(written, ["claude-mythos-5", "claude-opus-4", "claude-sonnet-4", "claude-sonnet-5-5"])
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["note"], "mine")
        self.assertEqual(data["models"]["claude-x"], other)
        self.assertEqual(data["models"]["claude-sonnet-5-5"]["output"], 10.0)
        self.assertEqual(data["version"], "v2")
        self.assertEqual(os.listdir(os.path.dirname(path)), ["prices.json"])

    def test_declined_leaves_file_unchanged(self):
        path = os.path.join(self.tmp, "prices.json")
        models.check_prices(self.table, fixture("pricing.md"))
        self.assertFalse(os.path.exists(path))


class External(TempHome):
    URLS = {
        "https://artificialanalysis.ai/models": "aa_models_page.html",
        "https://artificialanalysis.ai/agents/coding": "aa_coding_page.html",
        "https://www.tbench.ai/leaderboard": "tbench_page.html",
        "https://artificialanalysis.ai/api/v2/language/models/free": "aa_free.json",
    }

    def fetcher(self, dead=()):
        calls = []

        def f(url, headers=None):
            calls.append((url, headers))
            if url in dead:
                return None, "connection refused"
            if url in self.URLS:
                if url.endswith("/free") and not (headers or {}).get("x-api-key"):
                    return 401, "{}"
                return 200, fixture(self.URLS[url])
            if "/api/v2/" in url:
                return 403, '{"error":"tier"}'
            return 404, ""
        f.calls = calls
        return f

    def ext(self, key=None, dead=()):
        f = self.fetcher(dead)
        return models.external(key, None, f, os.path.join(self.tmp, "raw"), "2026-11-25"), f

    def test_free_key(self):
        out, f = self.ext("k")
        self.assertEqual(out["path"], "free API")
        tiers = out["notes"][0]["pro_endpoints"]
        self.assertEqual([t["result"] for t in tiers], ["free tier", "free tier"])
        self.assertEqual(out["skipped"], [])
        opus = [r for r in out["rows"] if r["model"] == "claude-opus-5-5" and r["metric"] == "cost_per_index_point"]
        self.assertAlmostEqual(opus[0]["value"], round(8909.7 / 59.1, 4))
        self.assertEqual(opus[0]["source"], "aa-models-api")
        # time per task still comes from the page
        self.assertTrue(any(r["metric"] == "time_per_task_s" for r in out["rows"]))
        self.assertFalse(any(r["source"] == "aa-models-page" and r["metric"] == "intelligence_index" for r in out["rows"]))

    def test_no_key_uses_page(self):
        out, f = self.ext(None)
        self.assertEqual(out["path"], "page")
        self.assertIn("no AA_API_KEY", out["notes"][0])
        self.assertFalse(any("/api/v2/" in u for u, _ in f.calls))
        sonnet = [r for r in out["rows"] if r["model"] == "claude-sonnet-5-5" and r["metric"] == "intelligence_index"]
        self.assertEqual(sorted(r["effort"] for r in sonnet), ["high", "max"])

    def test_effort_not_listed(self):
        out, _ = self.ext(None)
        cov = out["effort_coverage"]["claude-haiku-5-5"]
        self.assertEqual(cov["listed"], ["max"])
        self.assertTrue(cov["note"].startswith("Effort not listed: low, medium, high, xhigh"))

    def test_gpt_is_reference(self):
        out, _ = self.ext("k")
        gpt = [r for r in out["rows"] if r["model"] in ("gpt-6", "GPT-6")]
        self.assertTrue(gpt)
        self.assertEqual({r["tag"] for r in gpt}, {"reference"})

    def test_raw_saved_with_hash(self):
        out, _ = self.ext(None)
        self.assertEqual(len(out["raw"]), 3)
        for r in out["raw"]:
            self.assertTrue(os.path.exists(r["path"]))
            self.assertIn(os.path.join("raw", "2026-11-25"), r["path"])
            self.assertEqual(len(r["sha256"]), 64)

    def test_dead_source_named_and_skipped(self):
        out, _ = self.ext(None, dead=("https://www.tbench.ai/leaderboard",))
        self.assertEqual([s["source"] for s in out["skipped"]], ["tbench-leaderboard"])
        self.assertFalse(any(r["source"] == "tbench-leaderboard" for r in out["rows"]))
        self.assertTrue(any(r["source"] == "aa-coding-agents" for r in out["rows"]))

    def test_registry_fields(self):
        src = models.load_sources()
        for s in src["sources"]:
            for k in ("id", "url", "contributes", "read", "stability", "verified"):
                self.assertTrue(s.get(k), (s["id"], k))
        self.assertIn("https://platform.claude.com/docs/en/about-claude/pricing.md", [s["url"] for s in src["sources"]])


class Ranking(TempHome):
    def results(self):
        return {"skill": "review-mr", "runs": [
            # A: cheaper tokens (Haiku) but more cost per caught key bug
            {"id": "J", "model": "claude-haiku-5-5", "effort": "max", "setup_id": "s1", "caught_strict": 4,
             "cost_with_refuter": 12.0, "slowest_agent_min": 20},
            {"id": "K", "model": "claude-sonnet-5-5", "effort": "high", "setup_id": "s1", "caught_strict": 12,
             "cost_with_refuter": 12.0, "slowest_agent_min": 30},
            {"id": "L", "model": "claude-opus-5-5", "effort": "medium", "setup_id": "s2", "caught_strict": 14,
             "cost_with_refuter": 1.0, "slowest_agent_min": 5},
        ]}

    def test_cheaper_tokens_rank_lower(self):
        out = models.rank(self.results(), None, self.table)
        s1 = next(g for g in out["local"] if g["setup_id"] == "s1")["rows"]
        self.assertEqual([r["run"] for r in s1], ["K", "J"])
        self.assertEqual(s1[1]["token_price"]["output"], 0.5)

    def test_setups_not_ranked_together(self):
        out = models.rank(self.results(), None, self.table)
        self.assertEqual(sorted(g["setup_id"] for g in out["local"]), ["s1", "s2"])
        s2 = next(g for g in out["local"] if g["setup_id"] == "s2")["rows"]
        self.assertEqual([(r["run"], r["rank"]) for r in s2], [("L", 1)])

    def test_external_label_and_group(self):
        rows = [models.row("anthropic", "claude-sonnet-5-5", "max", "cost_per_index_point", 145.9, "u", "d", "aa-models-page"),
                models.row("anthropic", "claude-haiku-5-5", "max", "cost_per_index_point", 9.3, "u", "d", "aa-models-page"),
                models.row("openai", "gpt-6", "high", "cost_per_index_point", 1.0, "u", "d", "aa-models-page")]
        out = models.rank(self.results(), rows, self.table)
        self.assertIn("cost per index point", out["external"]["label"])
        ext = out["external"]["rows"]
        # haiku max has a local result, so only sonnet max is external; GPT never appears
        self.assertEqual([(r["model"], r["effort"]) for r in ext], [("claude-sonnet-5-5", "max")])
        self.assertIn("cost per index point", ext[0])
