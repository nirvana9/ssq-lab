#!/usr/bin/env python3
"""Synchronize SSQ results from the China Welfare Lottery public endpoint."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import database  # noqa: E402
from app.sources.cwl import SourceError  # noqa: E402
from app.sources.manager import fetch_with_fallback  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="同步双色球历史开奖数据")
    parser.add_argument("--full", action="store_true", help="尝试全量同步（从 2003-01-01 开始查询）")
    args = parser.parse_args()
    database.init_db()
    existing = database.list_draws()
    latest = existing[-1] if existing else None
    mode = "full" if args.full or not latest else "incremental"
    print(f"同步模式：{mode}")
    try:
        rows = fetch_with_fallback(
            mode=mode,
            latest_date=latest["draw_date"] if latest else None,
            existing=existing,
        )
        old_by_issue = {row["issue"]: row for row in existing}
        changed_rows = [row for row in rows if old_by_issue.get(row["issue"]) != row]
        changed = database.upsert_draws(changed_rows)
        sources = sorted({row.get("source", "cwl.gov.cn") for row in rows})
        labels = {
            "cwl.gov.cn": "中国福利彩票官方接口",
            "github.com/wangdaodao/DoubleColorBall": "GitHub 历史数据镜像（MIT 许可）",
            "scflcp.com.cn": "四川省福利彩票发行中心官方页面",
        }
        source_label = " + ".join(labels.get(source, source) for source in sources)
        database.set_meta("last_sync", __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"))
        database.set_meta("last_sync_mode", mode)
        database.set_meta("last_sync_count", str(len(changed_rows)))
        database.set_meta("source_label", source_label)
        database.set_meta("sources", __import__("json").dumps(sources, ensure_ascii=False))
        print(f"新增/修正 {len(changed_rows)} 期，数据库写入/更新 {changed} 条。")
        print(f"本地共 {database.count_draws()} 期。最新：{database.latest_draw()['issue']}。数据源：{source_label}")
        return 0
    except SourceError as exc:
        print(f"同步失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
