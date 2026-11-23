import json
import os
import unittest

from helpers import FIXTURES, TempHome, usage
import prices


class PriceTests(TempHome):
    def cost(self, model, **kw):
        return prices.request_cost(self.table, model, prices.token_classes(usage(**kw)))

    def test_haiku_under_threshold_base_tier(self):
        # 80k prompt: 80k cache read at 0.01, 1k output at 0.50
        self.assertAlmostEqual(self.cost("claude-haiku-5-5", inp=0, out=1000, read=80_000), (800 + 500) / 1e6)

    def test_haiku_over_threshold_long_tier(self):
        # 2k input + 3k write + 115k read = 120k prompt -> long tier
        tk = prices.token_classes(usage(inp=2000, out=0, read=115_000, w5=3000))
        self.assertEqual(prices.prompt_size(tk), 120_000)
        expected = (2000 * 0.50 + 3000 * 0.625 + 115_000 * 0.05) / 1e6
        self.assertAlmostEqual(prices.request_cost(self.table, "claude-haiku-5-5", tk), expected)

    def test_one_hour_write(self):
        self.assertAlmostEqual(self.cost("claude-opus-5-5", inp=0, out=0, w1=1_000_000), 8.0)

    def test_hand_computed_opus(self):
        # 1000 in * 4 + 500 out * 20 + 2000 w5 * 5 + 10000 read * 0.2
        self.assertAlmostEqual(self.cost("claude-opus-5-5", inp=1000, out=500, w5=2000, read=10_000),
                               (4000 + 10_000 + 10_000 + 2000) / 1e6)

    def test_missing_cache_creation_dict_counts_as_5m(self):
        tk = prices.token_classes(usage(w5=4000, dict_=False))
        self.assertEqual((tk["cache_write_5m"], tk["cache_write_1h"]), (4000, 0))

    def test_dated_id_matches_undated(self):
        self.assertIs(self.table.lookup("claude-haiku-4-5-20251001"), self.table.lookup("claude-haiku-4-5"))

    def test_unpriced_model_is_none(self):
        self.assertIsNone(self.cost("claude-unknown-9"))

    def test_seed_has_five_prices_per_model(self):
        for model, entry in self.table.models.items():
            for f in prices.FIELDS:
                self.assertIsInstance(entry[f], (int, float), model)


class OverrideTests(TempHome):
    def write_override(self, data):
        path = os.path.join(self.tmp, "override.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(data if isinstance(data, str) else json.dumps(data))
        return path

    def test_partial_override_merges_per_model(self):
        over = self.write_override({"version": "user-1", "models": {"claude-haiku-5-5": {
            "input": 1.0, "output": 1.0, "cache_write_5m": 1.0, "cache_write_1h": 1.0, "cache_read": 1.0}}})
        t = prices.PriceTable(prices.SEED_PATH, over)
        tk = prices.token_classes(usage(inp=1_000_000, out=0))
        self.assertAlmostEqual(prices.request_cost(t, "claude-haiku-5-5", tk), 1.0)
        self.assertAlmostEqual(prices.request_cost(t, "claude-opus-5-5", tk), 4.0)
        self.assertEqual(t.versions(), {"seed": "2026-11-21", "override": "user-1"})

    def test_invalid_override_reported_seed_used(self):
        t = prices.PriceTable(prices.SEED_PATH, self.write_override("{not json"))
        self.assertIsNone(t.versions()["override"])
        self.assertIn("override_error", t.versions())
        self.assertEqual(t.models, self.table.models)

    def test_override_with_bad_entry_rejected(self):
        t = prices.PriceTable(prices.SEED_PATH, self.write_override({"models": {"x": {"input": "a"}}}))
        self.assertIn("override_error", t.versions())


class RunDRegression(unittest.TestCase):
    def test_matches_cost_py(self):
        with open(os.path.join(FIXTURES, "run_d.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        table = prices.PriceTable(prices.SEED_PATH, None)
        for agent in data["agents"]:
            # cost.py priced <synthetic> error lines at 0; the scanner skips them
            got = sum(prices.request_cost(table, r["model"], prices.token_classes(r["usage"]))
                      for r in agent["requests"] if r["model"] != "<synthetic>")
            self.assertAlmostEqual(got, agent["expected_usd"], places=5, msg=agent["agent"])


if __name__ == "__main__":
    unittest.main()
