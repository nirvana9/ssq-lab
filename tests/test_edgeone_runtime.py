from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOUD_FUNCTIONS = ROOT / "cloud-functions"
sys.path.insert(0, str(CLOUD_FUNCTIONS))


class EdgeOneDataTests(unittest.TestCase):
    def test_bundled_data_has_explicit_schema_and_no_fake_draws(self):
        from draws_data import DRAW_DATA

        self.assertEqual(DRAW_DATA["schema_version"], 1)
        self.assertEqual(DRAW_DATA["source"], "cwl.gov.cn")
        self.assertIn("updated_at", DRAW_DATA)
        self.assertIn("latest_issue", DRAW_DATA)
        self.assertIsInstance(DRAW_DATA["draws"], list)

    def test_empty_history_summary_is_safe(self):
        from analysis import summarize

        result = summarize([], window=30)
        self.assertEqual(result["count"], 0)
        self.assertIsNone(result["latest"])
        self.assertEqual(result["red_frequency"], {})
        self.assertEqual(result["blue_frequency"], {})


class EdgeOneApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = CLOUD_FUNCTIONS / "api" / "index.py"
        spec = importlib.util.spec_from_file_location("ssq_makers_api", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to load Makers API module")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_api_uses_relative_paths_under_api_function_prefix(self):
        paths = {route.path for route in self.module.app.routes if hasattr(route, "path")}
        self.assertTrue({"/status", "/draws", "/sync", "/analysis", "/backtest", "/picks", "/export.csv"}.issubset(paths))
        self.assertNotIn("/api/status", paths)

    def test_status_reports_bundled_data_without_database(self):
        from draws_data import DRAW_DATA

        result = self.module.status()
        self.assertEqual(result["draw_count"], len(DRAW_DATA["draws"]))
        self.assertEqual(result["latest"], DRAW_DATA["draws"][-1] if DRAW_DATA["draws"] else None)
        self.assertEqual(result["source"], DRAW_DATA["source_label"])

    def test_history_bundle_is_sorted_unique_and_legal(self):
        from draws_data import DRAW_DATA

        rows = DRAW_DATA["draws"]
        issues = [row["issue"] for row in rows]
        self.assertEqual(issues, sorted(issues))
        self.assertEqual(len(issues), len(set(issues)))
        for row in rows:
            self.assertEqual(len(row["red"]), 6)
            self.assertEqual(len(set(row["red"])), 6)
            self.assertTrue(all(1 <= n <= 33 for n in row["red"]))
            self.assertTrue(1 <= row["blue"] <= 16)
            self.assertEqual(row["issue"][:4], row["draw_date"][:4])

    def test_read_only_api_supports_analysis_picks_and_backtest(self):
        from draws_data import DRAW_DATA

        if not DRAW_DATA["draws"]:
            self.skipTest("No published draw data yet")
        latest = DRAW_DATA["draws"][-1]
        listed = self.module.get_draws(limit=5, order="desc")
        self.assertEqual(listed["draws"][0]["issue"], latest["issue"])

        stats = self.module.get_analysis(window=30)
        self.assertEqual(stats["count"], len(DRAW_DATA["draws"]))
        self.assertEqual(stats["window"], 30)

        picks = self.module.get_picks(self.module.PickPayload(
            count=2, mode="random", window=50, sum_min=21, sum_max=183,
            use_filters=False,
        ))
        self.assertEqual(len(picks["picks"]), 2)
        for pick in picks["picks"]:
            self.assertEqual(len(pick["red"]), 6)
            self.assertTrue(1 <= pick["blue"] <= 16)

        backtest = self.module.get_backtest(window=50, warmup=100)
        self.assertEqual(len(backtest["results"]), 4)
        self.assertGreater(backtest["sample_count"], 0)


if __name__ == "__main__":
    unittest.main()
