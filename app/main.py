from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import analysis, database
from .sources.cwl import SourceError, normalize_record
from .sources.manager import fetch_with_fallback

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app = FastAPI(title="SSQ Lab", version="2.0.0", description="双色球历史数据分析与回测工具")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ImportPayload(BaseModel):
    draws: list[dict[str, Any]]
    replace: bool = False


class PickPayload(BaseModel):
    count: int = Field(default=5, ge=1, le=50)
    mode: str = Field(default="random", pattern="^(random|balanced|hot|cold)$")
    window: int = Field(default=50, ge=10, le=5000)
    sum_min: int = Field(default=70, ge=21, le=183)
    sum_max: int = Field(default=150, ge=21, le=183)
    use_filters: bool = True
    avoid_latest: bool = False
    seed: int | None = None


@app.on_event("startup")
def startup() -> None:
    database.init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
def status() -> dict[str, Any]:
    latest = database.latest_draw()
    return {
        "ok": True,
        "version": app.version,
        "draw_count": database.count_draws(),
        "latest": latest,
        "last_sync": database.get_meta("last_sync"),
        "last_sync_mode": database.get_meta("last_sync_mode"),
        "last_sync_count": database.get_meta("last_sync_count"),
        "source": database.get_meta("source_label") or "中国福利彩票发行管理中心（cwl.gov.cn）",
        "sources": json.loads(database.get_meta("sources") or "[]"),
        "source_url": "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/",
    }


@app.get("/api/draws")
def draws(limit: int = Query(default=100, ge=1, le=10000), order: str = "desc") -> dict[str, Any]:
    rows = database.list_draws(limit=limit, newest_first=(order.lower() != "asc"))
    return {"count": len(rows), "draws": rows}


@app.post("/api/sync")
def sync(mode: str = Query(default="incremental", pattern="^(incremental|full)$")) -> dict[str, Any]:
    existing = database.list_draws()
    latest_date = existing[-1]["draw_date"] if existing else None
    try:
        rows = fetch_with_fallback(mode=mode, latest_date=latest_date, existing=existing)
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
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        database.set_meta("last_sync", now)
        database.set_meta("last_sync_mode", mode)
        database.set_meta("last_sync_count", str(len(changed_rows)))
        database.set_meta("source_label", source_label)
        database.set_meta("sources", json.dumps(sources, ensure_ascii=False))
        return {"ok": True, "mode": mode, "fetched": len(changed_rows), "upserted": changed,
                "latest": database.latest_draw(), "last_sync": now, "source": source_label,
                "message": f"同步完成：新增/修正 {len(changed_rows)} 期，数据库共 {database.count_draws()} 期。"}
    except SourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"同步失败：{exc}") from exc


@app.get("/api/analysis")
def get_analysis(window: int = Query(default=30, ge=1, le=5000)) -> dict[str, Any]:
    rows = database.list_draws()
    return analysis.summarize(rows, window=window)


@app.get("/api/backtest")
def get_backtest(window: int = Query(default=50, ge=10, le=1000),
                 warmup: int = Query(default=100, ge=30, le=3000)) -> dict[str, Any]:
    rows = database.list_draws()
    return analysis.backtest(rows, window=window, warmup=warmup)


@app.post("/api/picks")
def picks(payload: PickPayload) -> dict[str, Any]:
    rows = database.list_draws()
    if not rows:
        raise HTTPException(status_code=409, detail="尚无历史开奖数据，请先同步或导入数据。")
    if payload.sum_min > payload.sum_max:
        raise HTTPException(status_code=422, detail="和值下限不能大于上限。")
    result = analysis.generate_picks(
        rows, count=payload.count, mode=payload.mode, window=payload.window,
        sum_min=payload.sum_min, sum_max=payload.sum_max,
        use_filters=payload.use_filters, avoid_latest=payload.avoid_latest,
        seed=payload.seed,
    )
    if len(result) < payload.count:
        return {"picks": result, "requested": payload.count,
                "warning": f"当前筛选条件较严格，只生成了 {len(result)} 注；可放宽和值或结构筛选。"}
    return {"picks": result, "requested": payload.count, "warning": None}


@app.post("/api/import")
def import_data(payload: ImportPayload) -> dict[str, Any]:
    normalized = []
    errors = []
    for index, item in enumerate(payload.draws, start=1):
        try:
            normalized.append(normalize_record(item))
        except SourceError as exc:
            errors.append({"row": index, "error": str(exc)})
    if errors:
        raise HTTPException(status_code=422, detail={"message": "导入数据校验失败，未写入任何记录。", "errors": errors[:20]})
    changed = database.import_draws(normalized, replace=payload.replace)
    return {"ok": True, "received": len(normalized), "upserted": changed,
            "draw_count": database.count_draws()}


@app.get("/api/export.csv")
def export_csv() -> StreamingResponse:
    rows = database.list_draws()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["issue", "draw_date", "red1", "red2", "red3", "red4", "red5", "red6", "blue", "sales", "poolmoney"])
    for row in rows:
        writer.writerow([row["issue"], row["draw_date"], *row["red"], row["blue"], row.get("sales", ""), row.get("poolmoney", "")])
    content = "\ufeff" + buffer.getvalue()
    return StreamingResponse(iter([content]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=ssq-history.csv"})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}
