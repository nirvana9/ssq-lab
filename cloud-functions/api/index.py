from __future__ import annotations

import csv
import io
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Makers packages Python files under cloud-functions together. Add this directory
# explicitly so auxiliary modules can be imported regardless of worker cwd.
FUNCTIONS_DIR = Path(__file__).resolve().parents[1]
if str(FUNCTIONS_DIR) not in sys.path:
    sys.path.insert(0, str(FUNCTIONS_DIR))

from analysis import backtest as run_backtest
from analysis import generate_picks
from analysis import summarize
from draws_data import DRAW_DATA

app = FastAPI(
    title="SSQ Lab Makers API",
    version="2.0.0",
    description="EdgeOne Makers read-only API for SSQ Lab",
)


class PickPayload(BaseModel):
    count: int = Field(default=5, ge=1, le=50)
    mode: str = Field(default="random", pattern="^(random|balanced|hot|cold)$")
    window: int = Field(default=50, ge=10, le=5000)
    sum_min: int = Field(default=70, ge=21, le=183)
    sum_max: int = Field(default=150, ge=21, le=183)
    use_filters: bool = True
    avoid_latest: bool = False
    seed: int | None = None


def load_draws() -> list[dict[str, Any]]:
    """Return the immutable draw bundle sorted by issue number."""
    records = DRAW_DATA.get("draws") or []
    return sorted(records, key=lambda row: str(row.get("issue", "")))


def status() -> dict[str, Any]:
    rows = load_draws()
    latest = rows[-1] if rows else None
    return {
        "ok": True,
        "version": app.version,
        "draw_count": len(rows),
        "latest": latest,
        "last_sync": DRAW_DATA.get("updated_at"),
        "last_sync_mode": "github-actions",
        "last_sync_count": len(rows),
        "source": "中国福利彩票发行管理中心（cwl.gov.cn）",
        "source_url": "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/",
    }


@app.get("/status")
def get_status() -> dict[str, Any]:
    return status()


@app.get("/draws")
def get_draws(
    limit: int = Query(default=100, ge=1, le=10000),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> dict[str, Any]:
    rows = load_draws()
    if order == "desc":
        rows = list(reversed(rows))
    rows = rows[:limit]
    return {"count": len(rows), "draws": rows}


@app.post("/sync")
def refresh_published_data(mode: str = Query(default="incremental", pattern="^(incremental|full)$")) -> dict[str, Any]:
    """Refresh the function's in-memory view; external sync is done by GitHub Actions."""
    current = status()
    return {
        "ok": True,
        "mode": mode,
        "fetched": 0,
        "upserted": 0,
        "latest": current["latest"],
        "last_sync": current["last_sync"],
        "message": "已重新读取当前部署的数据版本；开奖数据由 GitHub Actions 定时同步。新数据会在下一次部署后显示。",
    }


@app.get("/analysis")
def get_analysis(window: int = Query(default=30, ge=1, le=5000)) -> dict[str, Any]:
    return summarize(load_draws(), window=window)


@app.get("/backtest")
def get_backtest(
    window: int = Query(default=50, ge=10, le=1000),
    warmup: int = Query(default=100, ge=30, le=3000),
) -> dict[str, Any]:
    return run_backtest(load_draws(), window=window, warmup=warmup)


@app.post("/picks")
def get_picks(payload: PickPayload) -> dict[str, Any]:
    rows = load_draws()
    if not rows:
        raise HTTPException(status_code=409, detail="当前部署版本尚无历史开奖数据；请先运行 GitHub Actions 数据同步工作流。")
    if payload.sum_min > payload.sum_max:
        raise HTTPException(status_code=422, detail="和值下限不能大于上限。")
    result = generate_picks(
        rows,
        count=payload.count,
        mode=payload.mode,
        window=payload.window,
        sum_min=payload.sum_min,
        sum_max=payload.sum_max,
        use_filters=payload.use_filters,
        avoid_latest=payload.avoid_latest,
        seed=payload.seed,
    )
    if len(result) < payload.count:
        return {
            "picks": result,
            "requested": payload.count,
            "warning": f"当前筛选条件较严格，只生成了 {len(result)} 注；可放宽和值或结构筛选。",
        }
    return {"picks": result, "requested": payload.count, "warning": None}


@app.post("/import")
def reject_cloud_import() -> None:
    raise HTTPException(
        status_code=405,
        detail="EdgeOne 云端版本使用只读历史数据；CSV 导入请在本地版（FastAPI + SQLite）中使用。",
    )


@app.get("/export.csv")
def export_csv() -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["issue", "draw_date", "red1", "red2", "red3", "red4", "red5", "red6", "blue", "sales", "poolmoney"])
    for row in load_draws():
        writer.writerow([
            row["issue"],
            row["draw_date"],
            *row["red"],
            row["blue"],
            row.get("sales", ""),
            row.get("poolmoney", ""),
        ])
    content = "\ufeff" + buffer.getvalue()
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=ssq-history.csv"},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
