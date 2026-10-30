from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.sources.fivehundred import parse_history_html


SAMPLE_HTML = """
<table>
<tr class="t_tr1">
  <td>26124</td><td>03</td><td>11</td><td>17</td><td>22</td><td>23</td><td>29</td>
  <td>09</td><td>&nbsp;</td><td>1,075,698,427</td><td>8</td><td>6,656,899</td>
  <td>220</td><td>75,313</td><td>346,568,144</td><td>2026-10-29</td>
</tr>
</table>
"""


class FiveHundredParserTests(unittest.TestCase):
    def test_maps_short_issue_and_parses_real_draw_fields(self):
        rows = parse_history_html(SAMPLE_HTML)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["issue"], "2026124")
        self.assertEqual(rows[0]["draw_date"], "2026-10-29")
        self.assertEqual(rows[0]["red"], [3, 11, 17, 22, 23, 29])
        self.assertEqual(rows[0]["blue"], 9)
        self.assertEqual(rows[0]["sales"], "346568144")
        self.assertEqual(rows[0]["poolmoney"], "1075698427")
        self.assertEqual(rows[0]["source"], "datachart.500.com")

    def test_rejects_rows_with_invalid_ball_values(self):
        invalid = SAMPLE_HTML.replace("<td>33</td>", "<td>39</td>")
        rows = parse_history_html(invalid)
        self.assertEqual(rows, [])

    def test_empty_or_unrelated_html_returns_no_records(self):
        self.assertEqual(parse_history_html("<html><body>blocked</body></html>"), [])


if __name__ == "__main__":
    unittest.main()
