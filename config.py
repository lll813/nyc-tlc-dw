"""NYC TLC 出行数仓 —— 全局配置。

所有路径都相对于项目根目录，换机器只改这里。
DuckDB 放在项目 lib/ 下，免安装；生产环境可换成 Spark/Doris。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIB = ROOT / "lib"
# 免安装 DuckDB：优先使用项目自带 wheel
if LIB.exists() and str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

DATA = ROOT / "data"
RAW = DATA / "raw"
DIM = DATA / "dim"
ODS = DATA / "ods" / "trips"
REJECTED = DATA / "ods" / "_rejected"
DWD = DATA / "dwd" / "trip_detail"
DB_DIR = ROOT / "db"
DB_PATH = DB_DIR / "nyc_tlc.duckdb"
OUTPUT = ROOT / "output"
SQL_DIR = ROOT / "sql"
DOCS = ROOT / "docs"

# 数据集覆盖范围：2023-01-01 ~ 2025-12-31，36 个月
START_YEAR = 2023
END_YEAR = 2025
START_TS = "2023-01-01 00:00:00"
END_TS = "2026-01-01 00:00:00"

# 三座机场的 taxi zone id（JFK / LaGuardia / Newark）
AIRPORT_ZONES = (1, 132, 138)

# 资源限制：16 GB 内存的笔记本，给系统留足余量
DUCKDB_MEMORY_LIMIT = "3GB"
DUCKDB_THREADS = 4
TEMP_DIR = ROOT / "db" / "tmp"

# 数据质量阈值
DQ_THRESHOLDS = {
    "reject_rate_max": 0.02,
    "dup_rate_max": 0.005,
    "zone_coverage_min": 0.995,
    "payment_coverage_min": 0.999,
    "revenue_match_min": 0.999,
    "missing_days_max": 0,
}

MONTHS = [(y, m) for y in range(START_YEAR, END_YEAR + 1) for m in range(1, 13)]
