"""FastAPI 查询服务：把 ADS 表暴露成 HTTP API，并托管 dashboard.html。

运行：
    python scripts/serve.py
    # http://127.0.0.1:8000
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

import duckdb
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, HTMLResponse

from config import DB_PATH, OUTPUT

app = FastAPI(title="NYC TLC Data Warehouse API", version="1.0")


def q(sql: str, params: list | None = None) -> list[dict]:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        df = con.execute(sql, params or []).fetchdf()
        return json.loads(df.to_json(orient="records", date_format="iso"))
    finally:
        con.close()


@app.get("/", response_class=HTMLResponse)
def index():
    path = OUTPUT / "dashboard.html"
    if path.exists():
        return FileResponse(path)
    return HTMLResponse("<h3>dashboard.html 尚未生成，请先运行 python run_all.py</h3>")


@app.get("/api/kpi")
def kpi():
    return {row["metric"]: row["value"] for row in q("SELECT metric, value FROM ads_kpi_summary")}


@app.get("/api/daily")
def daily(start: str | None = None, end: str | None = None):
    sql = "SELECT * FROM ads_daily_kpi WHERE 1=1"
    params: list = []
    if start:
        sql += " AND date >= ?"
        params.append(start)
    if end:
        sql += " AND date <= ?"
        params.append(end)
    return q(sql + " ORDER BY date", params)


@app.get("/api/monthly")
def monthly():
    return q("SELECT * FROM ads_monthly_kpi ORDER BY year_month")


@app.get("/api/zones")
def zones(month: str | None = Query(default=None, description="YYYY-MM，默认最新月")):
    if not month:
        month = q("SELECT max(year_month) AS m FROM ads_zone_rank")[0]["m"]
    return q("SELECT * FROM ads_zone_rank WHERE year_month = ? ORDER BY revenue DESC", [month])


@app.get("/api/hourly")
def hourly():
    return q("SELECT * FROM ads_hourly_heatmap ORDER BY weekday, pickup_hour")


@app.get("/api/tip-zones")
def tip_zones(limit: int = 20):
    return q("SELECT * FROM ads_tip_zone ORDER BY card_tip_rate DESC LIMIT ?", [limit])


@app.get("/api/quality")
def quality():
    return q("SELECT * FROM dq_result")


@app.get("/api/forecast")
def forecast(limit: int = 120):
    return q(
        "SELECT * FROM (SELECT * FROM ads_demand_forecast ORDER BY date DESC LIMIT ?) "
        "ORDER BY date",
        [limit],
    )


@app.get("/api/benchmark")
def benchmark():
    return json.loads((OUTPUT / "benchmark.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("serve:app", host="127.0.0.1", port=8000, reload=False)
