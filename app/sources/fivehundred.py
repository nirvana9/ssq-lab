from __future__ import annotations

import html
import re
import time
from datetime import datetime
from typing import Any

import requests

from .cwl import SourceError

BASE_URL = "https://datachart.500.com/ssq/history/newinc/history.php"
HISTORY_URL = "https://datachart.500.com/ssq/history/history.shtml"
SOURCE = "datachart.500.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": HISTORY_URL,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

ROW_RE = re.compile(r'<tr class="t_tr1"[^>]*>(.*?)</tr>', re.S | re.I)
TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def _clean_cell(raw: str) -> str:
    value = COMMENT_RE.sub("", raw)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value).replace(",", "").replace("\xa0", "").strip()
    return value


def _short_issue(value: str | int) -> str:
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 7 and digits.startswith("20"):
        digits = digits[2:]
    if len(digits) != 5:
        raise ValueError(f"invalid 500.com issue: {value!r}")
    return digits


def parse_history_html(source_html: str) -> list[dict[str, Any]]:
    """Parse 500.com 16-column history rows into SSQ Lab's normalized format."""
    records: dict[str, dict[str, Any]] = {}
    for match in ROW_RE.finditer(source_html or ""):
        cells = [_clean_cell(cell) for cell in TD_RE.findall(match.group(1))]
        if len(cells) < 16:
            continue
        try:
            short_issue = _short_issue(cells[0])
            issue = f"20{short_issue}"
            red = sorted(int(cells[index]) for index in range(1, 7))
            blue = int(cells[7])
            draw_date = cells[15].replace("/", "-")
            datetime.strptime(draw_date, "%Y-%m-%d")
            if int(draw_date[:4]) % 100 != int(short_issue[:2]):
                continue
            if len(set(red)) != 6 or any(number < 1 or number > 33 for number in red):
                continue
            if not 1 <= blue <= 16:
                continue
            sales = str(int(cells[14] or "0"))
            poolmoney = str(int(cells[9] or "0"))
            prizes = [
                {"level": 1, "count": int(cells[10] or "0"), "amount": int(cells[11] or "0")},
                {"level": 2, "count": int(cells[12] or "0"), "amount": int(cells[13] or "0")},
            ]
        except (TypeError, ValueError, IndexError):
            continue
        records[issue] = {
            "issue": issue,
            "draw_date": draw_date,
            "red": red,
            "blue": blue,
            "sales": sales,
            "poolmoney": poolmoney,
            "prizegrades": prizes,
            "source": SOURCE,
        }
    return [records[issue] for issue in sorted(records)]


class FiveHundredProvider:
    """Fallback history provider using 500.com's public HTML history endpoint."""

    def __init__(self, timeout: int = 25, chunk_size: int = 300, delay: float = 0.8):
        self.timeout = timeout
        self.chunk_size = chunk_size
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _fetch_html(self, start: str | None = None, end: str | None = None) -> str:
        params: dict[str, str] = {}
        if start:
            params["start"] = _short_issue(start)
        if end:
            params["end"] = _short_issue(end)
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = self.session.get(BASE_URL, params=params, timeout=self.timeout)
                response.raise_for_status()
                response.encoding = "gbk"
                return response.text
            except requests.RequestException as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(attempt * 2)
        raise SourceError(f"500.com 历史接口请求失败：{last_error}")

    def fetch_recent(self) -> list[dict[str, Any]]:
        rows = parse_history_html(self._fetch_html())
        if not rows:
            raise SourceError("500.com 最近开奖页面没有返回可识别记录。")
        return rows

    def fetch_range(self, start: str, end: str) -> list[dict[str, Any]]:
        first = int(_short_issue(start))
        last = int(_short_issue(end))
        if first > last:
            return []
        merged: dict[str, dict[str, Any]] = {}
        chunk_count = (last - first) // self.chunk_size + 1
        chunk_index = 0
        cursor = first
        while cursor <= last:
            chunk_end = min(cursor + self.chunk_size - 1, last)
            chunk_index += 1
            start_issue = f"{cursor:05d}"
            end_issue = f"{chunk_end:05d}"
            print(f"500.com 历史抓取 [{chunk_index}/{chunk_count}] {start_issue}–{end_issue}", flush=True)
            rows = parse_history_html(self._fetch_html(start_issue, end_issue))
            for row in rows:
                merged[row["issue"]] = row
            cursor = chunk_end + 1
            if cursor <= last:
                time.sleep(self.delay)
        if not merged:
            raise SourceError("500.com 全量历史接口未返回有效开奖记录。")
        return [merged[issue] for issue in sorted(merged)]

    def fetch(self, mode: str = "incremental", latest_date: str | None = None) -> list[dict[str, Any]]:
        recent = self.fetch_recent()
        if mode != "full":
            return recent
        latest_issue = max(row["issue"] for row in recent)
        return self.fetch_range("03001", latest_issue[2:])
