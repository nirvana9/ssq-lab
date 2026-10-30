from __future__ import annotations

import re
import time
from html.parser import HTMLParser
from typing import Any

import requests

from .cwl import SourceError, normalize_record

URL = "https://www.scflcp.com.cn/ssq"
SOURCE = "scflcp.com.cn"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self.parts.append(value)


DRAW_RE = re.compile(
    r"开奖结果\s*开奖时间\s*[:：]\s*(20\d{2}-\d{2}-\d{2})\s+((?:\d{1,2}\s+){6}\d{1,2})",
    re.S,
)
SALES_RE = re.compile(r"本期销售金额\s*[:：]\s*([\d,]+)")
POOL_RE = re.compile(r"下期一等奖奖池累计金额\s*[:：]\s*([\d,]+)")


def parse_sichuan_html(
    source_html: str,
    existing_draws: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parse recent results from Sichuan Welfare Lottery's official website.

    The page displays recent draw dates and numbers. Existing history is used
    to map known dates to issue numbers and to assign the next sequence number
    to any newer draw dates.
    """
    extractor = _TextExtractor()
    extractor.feed(source_html or "")
    text = re.sub(r"\s+", " ", " ".join(extractor.parts)).strip()
    matches = list(DRAW_RE.finditer(text))
    if not matches:
        return []

    issue_by_date: dict[str, str] = {}
    max_sequence_by_year: dict[str, int] = {}
    for row in existing_draws:
        issue = str(row.get("issue", ""))
        date = str(row.get("draw_date", ""))
        if re.fullmatch(r"20\d{5}", issue):
            issue_by_date[date] = issue
            year = issue[:4]
            max_sequence_by_year[year] = max(max_sequence_by_year.get(year, 0), int(issue[4:]))

    if not issue_by_date:
        raise ValueError("existing history is required to map official recent draws to issue numbers")

    raw_records = []
    for index, match in enumerate(matches):
        draw_date = match.group(1)
        numbers = [int(value) for value in re.findall(r"\d+", match.group(2))]
        if len(numbers) != 7:
            continue
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        segment = text[match.end():next_start]
        sales_match = SALES_RE.search(segment)
        pool_match = POOL_RE.search(segment)
        raw_records.append({
            "draw_date": draw_date,
            "red": sorted(numbers[:6]),
            "blue": numbers[6],
            "sales": re.sub(r"\D", "", sales_match.group(1)) if sales_match else "",
            "poolmoney": re.sub(r"\D", "", pool_match.group(1)) if pool_match else "",
        })

    # Some page layouts render all ten draw cards first and the detailed
    # sales/pool blocks afterward. In that case, align those lists by page order.
    sales_values = [re.sub(r"\\D", "", value) for value in SALES_RE.findall(text)]
    pool_values = [re.sub(r"\\D", "", value) for value in POOL_RE.findall(text)]
    for index, record in enumerate(raw_records):
        if not record["sales"] and index < len(sales_values):
            record["sales"] = sales_values[index]
        if not record["poolmoney"] and index < len(pool_values):
            record["poolmoney"] = pool_values[index]

    raw_records.sort(key=lambda row: row["draw_date"])
    result: dict[str, dict[str, Any]] = {}
    for record in raw_records:
        draw_date = record["draw_date"]
        year = draw_date[:4]
        issue = issue_by_date.get(draw_date)
        if issue is None:
            sequence = max_sequence_by_year.get(year, 0) + 1
            max_sequence_by_year[year] = sequence
            issue = f"{year}{sequence:03d}"
            issue_by_date[draw_date] = issue

        row = normalize_record({
            "issue": issue,
            "date": draw_date,
            "red": record["red"],
            "blue": record["blue"],
            "sales": record["sales"],
            "poolmoney": record["poolmoney"],
            "prizegrades": [],
            "source": SOURCE,
        })
        previous = next((item for item in existing_draws if item.get("issue") == issue), None)
        if previous and (previous.get("red") != row["red"] or int(previous.get("blue", 0)) != row["blue"]):
            raise SourceError(f"四川福彩页面与历史镜像号码不一致：{issue}，停止覆盖以便人工核对。")
        result[issue] = row

    return [result[issue] for issue in sorted(result)]


class SichuanFucaiProvider:
    """Fetch recent draw records from the Sichuan Welfare Lottery official site."""

    def __init__(self, timeout: int = 25):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def fetch(self, existing_draws: list[dict[str, Any]]) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = self.session.get(URL, timeout=self.timeout)
                response.raise_for_status()
                response.encoding = response.apparent_encoding or "utf-8"
                rows = parse_sichuan_html(response.text, existing_draws)
                if not rows:
                    raise SourceError("四川省福彩页面没有返回可识别的近期开奖记录。")
                return rows
            except (requests.RequestException, ValueError, SourceError) as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(attempt)
        raise SourceError(f"四川省福彩官方页面抓取失败：{last_error}")
