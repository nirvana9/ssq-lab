from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.sources.cwl import SourceError
from app.sources.manager import fetch_with_fallback, merge_draws


def draw(issue: str, date: str, red: list[int], blue: int, source: str):
    return {
        "issue": issue, "draw_date": date, "red": red, "blue": blue,
        "sales": "", "poolmoney": "", "prizegrades": [], "source": source,
    }


class SourceManagerTests(unittest.TestCase):
    def test_fallback_merges_full_history_and_recent_official_records(self):
        old = draw("2026123", "2026-10-27", [4, 5, 20, 21, 26, 30], 12,
                   "github.com/wangdaodao/DoubleColorBall")
        latest = draw("2026124", "2026-10-29", [3, 11, 17, 22, 23, 29], 9,
                      "scflcp.com.cn")
        with patch("app.sources.manager.CwlProvider.fetch", side_effect=SourceError("403")):
            with patch("app.sources.manager.GitHubMirrorProvider.fetch", return_value=[old]):
                with patch("app.sources.manager.SichuanFucaiProvider.fetch", return_value=[old, latest]):
                    rows = fetch_with_fallback("incremental", "2026-10-27", existing=[old])

        self.assertEqual([row["issue"] for row in rows], ["2026123", "2026124"])
        self.assertEqual(rows[-1]["source"], "scflcp.com.cn")

    def test_fallback_keeps_history_when_recent_official_page_is_unavailable(self):
        old = draw("2026123", "2026-10-27", [4, 5, 20, 21, 26, 30], 12,
                   "github.com/wangdaodao/DoubleColorBall")
        with patch("app.sources.manager.CwlProvider.fetch", side_effect=SourceError("403")):
            with patch("app.sources.manager.GitHubMirrorProvider.fetch", return_value=[old]):
                with patch("app.sources.manager.SichuanFucaiProvider.fetch", side_effect=SourceError("timeout")):
                    rows = fetch_with_fallback("incremental", "2026-10-27", existing=[])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["issue"], "2026123")

    def test_merge_deduplicates_and_validates_issue_numbers(self):
        old = draw("2026123", "2026-10-27", [4, 5, 20, 21, 26, 30], 12, "old")
        updated = draw("2026123", "2026-10-27", [4, 5, 20, 21, 26, 30], 12, "new")
        merged = merge_draws([old], [updated])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source"], "new")


if __name__ == "__main__":
    unittest.main()
