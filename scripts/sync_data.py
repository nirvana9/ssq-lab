#!/usr/bin/env python3
"""Synchronize SSQ results from the China Welfare Lottery public endpoint."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import database  # noqa: E402
from app.sources.cwl import CwlProvider, SourceError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="同步双色球历史开奖数据")
    parser.add_argument("--full", action="store_true", help="尝试全量同步（从 2003-01-01 开始查询）")
    args = parser.parse_args()
    database.init_db()
    latest = database.latest_draw()
    mode = "full" if args.full or not latest else "incremental"
    print(f"同步模式：{mode}")
    try:
        rows = CwlProvider().fetch(mode=mode, latest_date=latest["draw_date"] if latest else None)
        changed = database.upsert_draws(rows)
        print(f"获取 {len(rows)} 期，写入/更新 {changed} 条。")
        print(f"本地共 {database.count_draws()} 期。最新：{database.latest_draw()['issue']}")
        return 0
    except SourceError as exc:
        print(f"同步失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
