from __future__ import annotations

import sys
from typing import Any

from .cwl import CwlProvider, SourceError, normalize_record
from .github_mirror import GitHubMirrorProvider
from .sichuan_fucai import SichuanFucaiProvider


def _normalize_draw(row: dict[str, Any]) -> dict[str, Any]:
    return normalize_record({
        "issue": row.get("issue"),
        "date": row.get("draw_date") or row.get("date"),
        "red": row.get("red"),
        "blue": row.get("blue"),
        "sales": row.get("sales"),
        "poolmoney": row.get("poolmoney"),
        "prizegrades": row.get("prizegrades") or [],
        "source": row.get("source") or "cwl.gov.cn",
    })


def merge_draws(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge validated draw records by issue; incoming records take precedence."""
    merged: dict[str, dict[str, Any]] = {}
    for row in existing:
        normalized = _normalize_draw(row)
        merged[normalized["issue"]] = normalized
    for row in incoming:
        normalized = _normalize_draw(row)
        merged[normalized["issue"]] = normalized
    return [merged[issue] for issue in sorted(merged)]


def fetch_with_fallback(
    mode: str = "incremental",
    latest_date: str | None = None,
    existing: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Fetch official history first; fall back to a validated mirror + official recent page."""
    existing = existing or []
    try:
        official_rows = CwlProvider().fetch(mode=mode, latest_date=latest_date)
        return merge_draws(existing, official_rows)
    except SourceError as official_error:
        print(
            f"中国福彩网官方接口暂不可用：{official_error}；改用 GitHub 历史镜像并用四川省福彩官网核对近期数据。",
            file=sys.stderr,
        )

    try:
        mirror_rows = GitHubMirrorProvider().fetch()
        base_rows = merge_draws(existing, mirror_rows)
    except SourceError as mirror_error:
        raise SourceError(
            f"中国福彩网官方源失败：{official_error}；GitHub 历史镜像也失败：{mirror_error}"
        ) from mirror_error

    try:
        recent_rows = SichuanFucaiProvider().fetch(existing_draws=base_rows)
        return merge_draws(base_rows, recent_rows)
    except SourceError as recent_error:
        print(
            f"四川省福彩近期页面暂不可用，保留已校验的历史镜像：{recent_error}",
            file=sys.stderr,
        )
        return base_rows
