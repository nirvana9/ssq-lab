from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.sources.sichuan_fucai import parse_sichuan_html


SAMPLE_HTML = """
<html><body>
<div>开奖结果</div><div>开奖时间：2026-10-29</div>
<div>03 11 17 22 23 29 09</div>
<div>本期销售金额：346568144 元</div>
<div>下期一等奖奖池累计金额：1075698427 元</div>
<div>开奖结果</div><div>开奖时间：2026-10-27</div>
<div>04 05 20 21 26 30 12</div>
<div>本期销售金额：334118378 元</div>
<div>下期一等奖奖池累计金额：1079246630 元</div>
</body></html>
"""


class SichuanFucaiParserTests(unittest.TestCase):
    def test_maps_latest_official_draws_using_existing_issue_history(self):
        existing = [{
            "issue": "2026123", "draw_date": "2026-10-27",
            "red": [4, 5, 20, 21, 26, 30], "blue": 12,
            "sales": "", "poolmoney": "", "prizegrades": [],
            "source": "github.com/wangdaodao/DoubleColorBall",
        }]
        rows = parse_sichuan_html(SAMPLE_HTML, existing)

        self.assertEqual([row["issue"] for row in rows], ["2026123", "2026124"])
        latest = rows[-1]
        self.assertEqual(latest["draw_date"], "2026-10-29")
        self.assertEqual(latest["red"], [3, 11, 17, 22, 23, 29])
        self.assertEqual(latest["blue"], 9)
        self.assertEqual(latest["sales"], "346568144")
        self.assertEqual(latest["poolmoney"], "1075698427")
        self.assertEqual(latest["source"], "scflcp.com.cn")

    def test_rejects_page_without_draw_records(self):
        self.assertEqual(parse_sichuan_html("<html>maintenance</html>", []), [])


if __name__ == "__main__":
    unittest.main()
