from __future__ import annotations

import datetime as dt
import re
import time
from typing import Any

import requests

HOME_URL = "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/"
API_URL = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": HOME_URL,
    "X-Requested-With": "XMLHttpRequest",
}


class SourceError(RuntimeError):
    pass


def _date_only(value: Any) -> str:
    text = str(value or "").strip()
    match = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
    if not match:
        raise SourceError(f"开奖日期无法识别：{text!r}")
    return match.group(1)


def _split_red(value: Any) -> list[int]:
    if isinstance(value, (list, tuple)):
        nums = [int(x) for x in value]
    else:
        nums = [int(x) for x in re.findall(r"\d+", str(value or ""))]
    if len(nums) != 6:
        raise SourceError(f"红球数量不是 6 个：{value!r}")
    nums.sort()
    if len(set(nums)) != 6 or any(n < 1 or n > 33 for n in nums):
        raise SourceError(f"红球号码非法：{value!r}")
    return nums


def normalize_record(item: dict[str, Any]) -> dict[str, Any]:
    issue = str(item.get("code") or item.get("issue") or "").strip()
    if not re.fullmatch(r"20\d{5}", issue):
        raise SourceError(f"期号格式非法：{issue!r}")
    red = _split_red(item.get("red"))
    blue_match = re.search(r"\d+", str(item.get("blue") or ""))
    if not blue_match:
        raise SourceError(f"蓝球无法识别：{item.get('blue')!r}")
    blue = int(blue_match.group())
    if not 1 <= blue <= 16:
        raise SourceError(f"蓝球超出 01–16：{blue}")
    draw_date = _date_only(item.get("date"))
    if draw_date[:4] != issue[:4]:
        raise SourceError(f"期号年份与开奖日期不一致：{issue} / {draw_date}")
    return {
        "issue": issue,
        "draw_date": draw_date,
        "red": red,
        "blue": blue,
        "sales": str(item.get("sales") or ""),
        "poolmoney": str(item.get("poolmoney") or ""),
        "prizegrades": item.get("prizegrades") or [],
        "source": str(item.get("source") or "cwl.gov.cn"),
    }


class CwlProvider:
    """Fetches SSQ results from the China Welfare Lottery public endpoint."""

    def __init__(self, timeout: int = 30, page_size: int = 100, delay: float = 0.45):
        self.timeout = timeout
        self.page_size = page_size
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def bootstrap(self) -> None:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.session.get(HOME_URL, timeout=self.timeout, allow_redirects=True)
                response.raise_for_status()
                return
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(1.0 * (attempt + 1))
        raise SourceError(f"访问中国福彩网首页获取会话失败：{last_error}")

    def _request_page(self, page: int, day_start: str, day_end: str) -> dict[str, Any]:
        params = {
            "name": "ssq",
            "issueCount": "",
            "issueStart": "",
            "issueEnd": "",
            "dayStart": day_start,
            "dayEnd": day_end,
            "pageNo": str(page),
            "pageSize": str(self.page_size),
            "week": "",
            "systemType": "PC",
        }
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.session.get(API_URL, params=params, timeout=self.timeout, allow_redirects=True)
                response.raise_for_status()
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise SourceError(f"官方接口返回的不是 JSON（HTTP {response.status_code}）") from exc
                if not isinstance(payload, dict):
                    raise SourceError("官方接口 JSON 格式异常")
                result = payload.get("result")
                if not isinstance(result, list):
                    raise SourceError(f"官方接口未返回开奖列表：{payload.get('message') or payload}")
                if not result and page == 1:
                    raise SourceError(
                        "官方接口返回空数据。可能是会话 Cookie、反爬策略或接口参数发生变化；"
                        "请稍后重试，或使用 CSV 导入。"
                    )
                return payload
            except (requests.RequestException, SourceError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1.2 * (attempt + 1))
        raise SourceError(f"请求官方开奖接口失败（第 {page} 页）：{last_error}")

    def fetch(self, mode: str = "incremental", latest_date: str | None = None) -> list[dict[str, Any]]:
        today = dt.date.today()
        if mode == "full":
            # The public endpoint accepts date-range queries; start from the lottery's first year.
            day_start = "2003-01-01"
        else:
            if latest_date:
                try:
                    start = dt.date.fromisoformat(latest_date) - dt.timedelta(days=45)
                except ValueError:
                    start = today - dt.timedelta(days=120)
            else:
                start = today - dt.timedelta(days=120)
            day_start = start.isoformat()
        day_end = today.isoformat()

        self.bootstrap()
        first = self._request_page(1, day_start, day_end)
        raw_items = list(first.get("result") or [])
        try:
            page_count = int(first.get("pageCount") or first.get("totalPage") or 1)
        except (TypeError, ValueError):
            page_count = 1
        page_count = max(1, min(page_count, 100))
        for page in range(2, page_count + 1):
            time.sleep(self.delay)
            payload = self._request_page(page, day_start, day_end)
            page_items = payload.get("result") or []
            if not page_items:
                break
            raw_items.extend(page_items)

        normalized: dict[str, dict[str, Any]] = {}
        for item in raw_items:
            row = normalize_record(item)
            normalized[row["issue"]] = row
        if not normalized:
            raise SourceError("官方接口没有返回可用的双色球开奖记录，未修改本地数据库。")
        return sorted(normalized.values(), key=lambda x: x["issue"])
