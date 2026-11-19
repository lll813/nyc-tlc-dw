"""Step 1: 构建维度层（zone / payment / ratecode / vendor / date / weather）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DIM, END_TS, RAW, SQL_DIR, START_TS
from scripts.common import connect, run_sql_file, scalar, table, timer


def main() -> None:
    DIM.mkdir(parents=True, exist_ok=True)
    con = connect()
    with timer("build dimensions"):
        run_sql_file(
            con,
            SQL_DIR / "01_dim.sql",
            ZONE_CSV=(RAW / "taxi_zone_lookup.csv").as_posix(),
            WEATHER_CSV=(RAW / "weather_daily.csv").as_posix(),
            START_DATE=START_TS[:10],
            END_DATE=END_TS[:10].replace("2026-01-01", "2025-12-31"),
            DIM_DIR=DIM.as_posix(),
        )
    for name in ("dim_zone", "dim_payment", "dim_ratecode", "dim_vendor", "dim_date", "dim_weather"):
        n = scalar(con, f"SELECT count(*) FROM {name}")
        print(f"  {name:14s} {n:>8,} rows")
    print("\nzone sample:")
    for row in table(con, "SELECT location_id, borough, zone, service_zone FROM dim_zone ORDER BY location_id LIMIT 5"):
        print(" ", row)
    con.close()


if __name__ == "__main__":
    main()
