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

    def test_status_reports_empty_data_without_database(self):
        result = self.module.status()
        self.assertEqual(result["draw_count"], 0)
        self.assertIsNone(result["latest"])
        self.assertEqual(result["source"], "中国福利彩票发行管理中心（cwl.gov.cn）")


if __name__ == "__main__":
    unittest.main()
