from __future__ import annotations

import time
from typing import Any

import requests

from .cwl import SourceError, normalize_record

REPOSITORY = "wangdaodao/DoubleColorBall"
RAW_BASE = f"https://raw.githubusercontent.com/{REPOSITORY}/main/data"
SOURCE = f"github.com/{REPOSITORY}"
HEADERS = {
    "User-Agent": "SSQ-Lab-data-sync/1.0 (+https://github.com/nirvana9/ssq-lab)",
    "Accept": "application/json",
}


def parse_year_payload(payload: dict[str, Any], expected_year: int) -> list[dict[str, Any]]:
    if int(payload.get("year", -1)) != expected_year:
        raise ValueError(f"year file mismatch: expected {expected_year}")
    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError(f"{expected_year} year file has no data array")
    if int(payload.get("count", -1)) != len(data):
        raise ValueError(f"{expected_year} year file count does not match its data length")

    rows = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError(f"{expected_year} year file contains a non-object record")
        row = normalize_record({
            "issue": item.get("code"),
            "date": item.get("date"),
            "red": item.get("red"),
            "blue": item.get("blue"),
            "sales": "",
            "poolmoney": "",
            "prizegrades": [],
            "source": SOURCE,
        })
        if int(row["issue"][:4]) != expected_year:
            raise ValueError(f"issue {row['issue']} is in the wrong year file")
        rows.append(row)

    rows.sort(key=lambda row: row["issue"])
    if rows and payload.get("latestIssue") and rows[-1]["issue"] != str(payload["latestIssue"]):
        raise ValueError(f"{expected_year} latestIssue metadata does not match its final record")
    return rows


class GitHubMirrorProvider:
    """Download yearly historical data from the MIT-licensed public mirror repository."""

    def __init__(self, timeout: int = 25, delay: float = 0.05):
        self.timeout = timeout
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _get_json(self, url: str) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = self.session.get(f"{url}?t={int(time.time())}", timeout=self.timeout)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("response root is not a JSON object")
                return payload
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(attempt)
        raise SourceError(f"GitHub 历史数据镜像请求失败：{url}: {last_error}")

    def fetch(self) -> list[dict[str, Any]]:
        index = self._get_json(f"{RAW_BASE}/index.json")
        year_entries = index.get("years")
        if not isinstance(year_entries, list) or not year_entries:
            raise SourceError("GitHub 历史数据镜像 index.json 缺少 years 列表。")

        all_rows: dict[str, dict[str, Any]] = {}
        for position, entry in enumerate(year_entries, start=1):
            try:
                year = int(entry["year"])
            except (KeyError, TypeError, ValueError) as exc:
                raise SourceError(f"GitHub 历史数据镜像年份目录格式异常：{entry!r}") from exc
            if position > 1:
                time.sleep(self.delay)
            payload = self._get_json(f"{RAW_BASE}/{year}.json")
            try:
                rows = parse_year_payload(payload, expected_year=year)
            except (TypeError, ValueError) as exc:
                raise SourceError(f"GitHub 历史数据镜像 {year}.json 校验失败：{exc}") from exc
            if len(rows) != int(entry.get("count", -1)):
                raise SourceError(f"GitHub 历史数据镜像 {year} 年期数与 index.json 不一致。")
            for row in rows:
                all_rows[row["issue"]] = row

        expected_total = int(index.get("totalCount", -1))
        if expected_total != len(all_rows):
            raise SourceError(
                f"GitHub 历史数据镜像总期数不一致：index={expected_total}, actual={len(all_rows)}"
            )
        if not all_rows:
            raise SourceError("GitHub 历史数据镜像没有返回任何开奖记录。")
        return [all_rows[issue] for issue in sorted(all_rows)]
