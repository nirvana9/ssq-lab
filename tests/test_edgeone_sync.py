from __future__ import annotations

import runpy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.sync_edgeone_data import merge_draws, render_data_module, write_bundle


def draw(issue: str, date: str, red: list[int], blue: int, sales: str = ""):
    return {
        "issue": issue,
        "draw_date": date,
        "red": red,
        "blue": blue,
        "sales": sales,
        "poolmoney": "",
        "prizegrades": [],
        "source": "cwl.gov.cn",
    }


class EdgeOneSyncTests(unittest.TestCase):
    def test_merge_updates_duplicate_issue_and_keeps_sorted_unique_history(self):
        old = [
            draw("2026122", "2026-10-25", [1, 2, 3, 4, 5, 6], 7, "old"),
            draw("2026123", "2026-10-27", [2, 4, 6, 8, 10, 12], 9, "old"),
        ]
        new = [
            draw("2026123", "2026-10-27", [2, 4, 6, 8, 10, 12], 9, "updated"),
            draw("2026124", "2026-10-29", [3, 5, 7, 9, 11, 13], 10, "new"),
        ]

        merged = merge_draws(old, new)

        self.assertEqual([row["issue"] for row in merged], ["2026122", "2026123", "2026124"])
        self.assertEqual(merged[1]["sales"], "updated")
        self.assertEqual(len({row["issue"] for row in merged}), 3)

    def test_rendered_module_can_be_imported_with_unicode_metadata(self):
        payload = {
            "schema_version": 1,
            "source": "cwl.gov.cn",
            "updated_at": "2026-10-30T12:00:00+00:00",
            "latest_issue": "2026124",
            "draws": [draw("2026124", "2026-10-29", [3, 5, 7, 9, 11, 13], 10)],
        }
        source = render_data_module(payload)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draws_data.py"
            path.write_text(source, encoding="utf-8")
            result = runpy.run_path(str(path))["DRAW_DATA"]
        self.assertEqual(result, payload)

    def test_empty_payload_does_not_overwrite_existing_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draws_data.py"
            path.write_text("DRAW_DATA = {'sentinel': 'keep'}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                write_bundle({"schema_version": 1, "draws": []}, path)
            self.assertEqual(path.read_text(encoding="utf-8"), "DRAW_DATA = {'sentinel': 'keep'}\n")


if __name__ == "__main__":
    unittest.main()
