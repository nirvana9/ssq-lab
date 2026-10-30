from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.sources.github_mirror import parse_year_payload


class GitHubMirrorTests(unittest.TestCase):
    def test_normalizes_upstream_year_data_to_ssq_lab_schema(self):
        payload = {
            "year": 2026,
            "count": 1,
            "latestIssue": "2026123",
            "data": [{
                "code": "2026123",
                "date": "2026-10-27",
                "red": [4, 5, 20, 21, 26, 30],
                "blue": 12,
                "sum": 106,
            }],
        }
        rows = parse_year_payload(payload, expected_year=2026)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["issue"], "2026123")
        self.assertEqual(rows[0]["red"], [4, 5, 20, 21, 26, 30])
        self.assertEqual(rows[0]["blue"], 12)
        self.assertEqual(rows[0]["source"], "github.com/wangdaodao/DoubleColorBall")

    def test_rejects_inconsistent_year_count(self):
        payload = {"year": 2026, "count": 2, "data": []}
        with self.assertRaises(ValueError):
            parse_year_payload(payload, expected_year=2026)


if __name__ == "__main__":
    unittest.main()
