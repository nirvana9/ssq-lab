#!/usr/bin/env python3
"""Fetch and atomically publish the read-only draw bundle for EdgeOne Makers."""
from __future__ import annotations

import argparse
import json
import os
import runpy
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.sources.cwl import CwlProvider, SourceError, normalize_record
from app.sources.fivehundred import FiveHundredProvider

DEFAULT_OUTPUT = ROOT / "cloud-functions" / "draws_data.py"


def _normalize_draw(row: dict[str, Any]) -> dict[str, Any]:
    """Validate a normalized draw again before it enters the deploy bundle."""
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
    """Merge by issue; incoming records replace older versions of the same issue."""
    merged: dict[str, dict[str, Any]] = {}
    for row in existing:
        normalized = _normalize_draw(row)
        merged[normalized["issue"]] = normalized
    for row in incoming:
        normalized = _normalize_draw(row)
        merged[normalized["issue"]] = normalized
    return [merged[issue] for issue in sorted(merged)]


def render_data_module(payload: dict[str, Any]) -> str:
    """Render data as a Python module so Makers bundles it with function code."""
    draws = payload.get("draws")
    if not isinstance(draws, list) or not draws:
        raise ValueError("refusing to render an empty draw dataset")
    issues = [str(row.get("issue", "")) for row in draws]
    if any(not issue for issue in issues) or len(set(issues)) != len(issues):
        raise ValueError("draw dataset contains an empty or duplicate issue")
    if issues != sorted(issues):
        raise ValueError("draw dataset must be sorted by issue")
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (
        '"""Generated, read-only lottery history bundle for EdgeOne Makers. '
        'Do not hand-edit draw records."""\n\n'
        "import json\n\n"
        f"DRAW_DATA = json.loads({serialized!r})\n"
    )


def write_bundle(payload: dict[str, Any], output: Path = DEFAULT_OUTPUT) -> None:
    """Atomically replace the module; invalid/empty data leaves the old file intact."""
    source = render_data_module(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=str(output.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(source)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def load_existing_bundle(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "source": "cwl.gov.cn",
                "source_label": "中国福利彩票发行管理中心（cwl.gov.cn）",
                "updated_at": None, "latest_issue": None, "draws": []}
    namespace = runpy.run_path(str(path))
    payload = namespace.get("DRAW_DATA")
    if not isinstance(payload, dict) or not isinstance(payload.get("draws"), list):
        raise ValueError(f"existing bundle has an invalid format: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="同步 SSQ 历史数据到 EdgeOne Makers 部署包")
    parser.add_argument("--full", action="store_true", help="从 2003-01-01 开始全量同步")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="生成的 Python 数据模块路径")
    args = parser.parse_args()

    try:
        existing_payload = load_existing_bundle(args.output)
        existing = existing_payload.get("draws") or []
        mode = "full" if args.full or not existing else "incremental"
        latest_date = existing[-1].get("draw_date") if existing else None
        print(f"数据同步模式：{mode}")
        try:
            incoming = CwlProvider().fetch(mode=mode, latest_date=latest_date)
        except SourceError as official_error:
            print(
                f"中国福彩网官方接口暂不可用：{official_error}；切换到 500.com 历史数据备用源。",
                file=sys.stderr,
            )
            try:
                incoming = FiveHundredProvider().fetch(mode=mode, latest_date=latest_date)
            except SourceError as fallback_error:
                raise SourceError(
                    f"官方源失败：{official_error}；500.com 备用源也失败：{fallback_error}"
                ) from fallback_error
        if not incoming:
            raise SourceError("数据源未返回可校验的开奖记录；保留现有数据。")

        merged = merge_draws(existing, incoming)
        if merged == existing:
            print(f"数据未变化：本地仍为 {len(existing)} 期，最新期号 {existing[-1]['issue'] if existing else '无'}。")
            return 0

        sources = sorted({row.get("source", "cwl.gov.cn") for row in merged})
        labels = {
            "cwl.gov.cn": "中国福利彩票官方接口",
            "datachart.500.com": "500彩票网历史数据（第三方）",
        }
        payload = {
            "schema_version": 1,
            "source": sources[0] if len(sources) == 1 else "mixed",
            "sources": sources,
            "source_label": " + ".join(labels.get(source, source) for source in sources),
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "latest_issue": merged[-1]["issue"],
            "draws": merged,
        }
        write_bundle(payload, args.output)
        print(
            f"数据更新完成：本次抓取 {len(incoming)} 期，合并后 {len(merged)} 期，"
            f"最新期号 {payload['latest_issue']}。"
        )
        return 0
    except (SourceError, ValueError, OSError) as exc:
        print(f"数据同步失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
