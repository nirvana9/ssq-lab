import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.analysis import backtest, generate_picks, prize_tier, summarize
from app.sources.cwl import SourceError, normalize_record


def make_draws(count=180):
    rows = []
    for i in range(count):
        # Deterministic synthetic fixtures used only in unit tests, never shipped as real draw data.
        start = (i * 7) % 28 + 1
        red = sorted({((start + j * 3 - 1) % 33) + 1 for j in range(6)})
        while len(red) < 6:
            red.append((red[-1] % 33) + 1)
            red = sorted(set(red))
        rows.append({"issue": f"2026{i+1:03d}", "draw_date": f"2026-{(i//28)+1:02d}-{(i%28)+1:02d}",
                     "red": red, "blue": (i % 16) + 1, "sales": "", "poolmoney": "",
                     "prizegrades": [], "source": "test-fixture"})
    return rows


class DataValidationTests(unittest.TestCase):
    def test_normalize_valid_record(self):
        row = normalize_record({"code": "2026123", "date": "2026-10-27(二)",
                                "red": "04,05,20,21,26,30", "blue": "12"})
        self.assertEqual(row["red"], [4, 5, 20, 21, 26, 30])
        self.assertEqual(row["blue"], 12)

    def test_reject_duplicate_red_ball(self):
        with self.assertRaises(SourceError):
            normalize_record({"code": "2026123", "date": "2026-10-27", "red": "1,1,2,3,4,5", "blue": "1"})


class AnalysisTests(unittest.TestCase):
    def test_summary_has_all_ball_slots(self):
        result = summarize(make_draws(60), 30)
        self.assertEqual(result["count"], 60)
        self.assertEqual(len(result["red_frequency"]), 33)
        self.assertEqual(len(result["blue_frequency"]), 16)

    def test_pick_generation_respects_ranges(self):
        picks = generate_picks(make_draws(), count=8, mode="balanced", seed=42)
        self.assertEqual(len(picks), 8)
        for pick in picks:
            self.assertEqual(len(pick["red"]), 6)
            self.assertEqual(len(set(pick["red"])), 6)
            self.assertTrue(all(1 <= n <= 33 for n in pick["red"]))
            self.assertTrue(1 <= pick["blue"] <= 16)

    def test_prize_tier_rules(self):
        self.assertEqual(prize_tier(6, True), 1)
        self.assertEqual(prize_tier(5, True), 3)
        self.assertEqual(prize_tier(3, True), 5)
        self.assertEqual(prize_tier(0, True), 6)
        self.assertIsNone(prize_tier(2, False))

    def test_backtest_walk_forward_runs(self):
        result = backtest(make_draws(180), window=50, warmup=100)
        self.assertEqual(result["sample_count"], 80)
        self.assertEqual(len(result["results"]), 4)
        self.assertTrue(all(row["tested"] == 80 for row in result["results"]))


if __name__ == "__main__":
    unittest.main()
