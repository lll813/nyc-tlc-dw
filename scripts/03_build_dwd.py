"""Step 3: DWD —— 按月清洗、去重、维表补全、天气关联，按年月分区落 Parquet。

为什么按月循环：1.2 亿行做全局 row_number() 会落大量临时文件（实测 20 分钟只写出 20%）。
按月循环后每个分区只有 ~350 万行，窗口排序可完全在内存完成，总耗时反而更短。
"""
from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DWD, END_TS, MONTHS, SQL_DIR, START_TS
from scripts.common import connect, json_dump, one_row, run_sql_file, scalar, table, timer

FILTER_SQL = """
SELECT
    count(*) AS ods_rows,
    sum(CASE WHEN dropoff_ts <= pickup_ts THEN 1 ELSE 0 END) AS bad_time_order,
    sum(CASE WHEN dropoff_ts > pickup_ts
              AND date_diff('second', pickup_ts, dropoff_ts) NOT BETWEEN 60 AND 14400
             THEN 1 ELSE 0 END) AS bad_duration,
    sum(CASE WHEN trip_distance NOT BETWEEN 0 AND 200 THEN 1 ELSE 0 END) AS bad_distance,
    sum(CASE WHEN fare_amount NOT BETWEEN 0 AND 1000 OR total_amount NOT BETWEEN 0 AND 2000
             THEN 1 ELSE 0 END) AS bad_amount,
    sum(CASE WHEN tip_amount NOT BETWEEN 0 AND 500 OR tolls_amount NOT BETWEEN 0 AND 200
             THEN 1 ELSE 0 END) AS bad_tip_toll,
    sum(CASE WHEN pu_location_id NOT BETWEEN 1 AND 265 OR do_location_id NOT BETWEEN 1 AND 265
             THEN 1 ELSE 0 END) AS bad_zone,
    sum(CASE WHEN payment_type NOT BETWEEN 0 AND 6 THEN 1 ELSE 0 END) AS bad_payment,
    sum(CASE WHEN ratecode_id IS NOT NULL AND ratecode_id NOT IN (0,1,2,3,4,5,6,99)
             THEN 1 ELSE 0 END) AS bad_ratecode,
    sum(CASE WHEN passenger_count IS NOT NULL AND passenger_count NOT BETWEEN 0 AND 8
             THEN 1 ELSE 0 END) AS bad_passenger,
    sum(CASE WHEN pickup_ts >= TIMESTAMP '{start}'
              AND pickup_ts <  TIMESTAMP '{end}'
              AND dropoff_ts > pickup_ts
              AND date_diff('second', pickup_ts, dropoff_ts) BETWEEN 60 AND 14400
              AND trip_distance BETWEEN 0 AND 200
              AND fare_amount BETWEEN 0 AND 1000
              AND total_amount BETWEEN 0 AND 2000
              AND tip_amount BETWEEN 0 AND 500
              AND tolls_amount BETWEEN 0 AND 200
              AND pu_location_id BETWEEN 1 AND 265
              AND do_location_id BETWEEN 1 AND 265
              AND payment_type BETWEEN 0 AND 6
              AND (ratecode_id IS NULL OR ratecode_id IN (0,1,2,3,4,5,6,99))
              AND (passenger_count IS NULL OR passenger_count BETWEEN 0 AND 8)
             THEN 1 ELSE 0 END) AS filtered_rows
FROM ods_trips
""".format(start=START_TS, end=END_TS)


def main() -> None:
    if DWD.exists():
        print(f"[clean] {DWD}")
        shutil.rmtree(DWD)
    DWD.mkdir(parents=True, exist_ok=True)

    con = connect()
    with timer("DWD filter funnel (one scan)"):
        funnel = one_row(con, FILTER_SQL)
        print("  ", funnel)

    t_all = time.perf_counter()
    with timer("DWD per-month rewrite"):
        for year, month in MONTHS:
            out = DWD / f"pickup_year={year}" / f"pickup_month={month}" / "data.parquet"
            out.parent.mkdir(parents=True, exist_ok=True)
            t0 = time.perf_counter()
            run_sql_file(
                con,
                SQL_DIR / "03_dwd.sql",
                YEAR=year,
                MONTH=month,
                OUT_FILE=out.as_posix(),
            )
            size_mb = out.stat().st_size / 1024**2
            print(
                f"  {year}-{month:02d}  {size_mb:6.1f} MB  {time.perf_counter()-t0:5.1f}s",
                flush=True,
            )
        print(f"  total {time.perf_counter()-t_all:.1f}s")

    con.execute(
        "CREATE OR REPLACE VIEW dwd_trip_detail AS "
        f"SELECT * FROM read_parquet('{(DWD / '**' / '*.parquet').as_posix()}', "
        "hive_partitioning = true, union_by_name = true)"
    )

    with timer("verify DWD"):
        dwd_rows = scalar(con, "SELECT count(*) FROM dwd_trip_detail")
        parts = scalar(con, "SELECT count(DISTINCT (pickup_year, pickup_month)) FROM dwd_trip_detail")
        by_year = table(
            con,
            "SELECT pickup_year, count(*) AS rows, count(DISTINCT pickup_month) AS months, "
            "round(sum(total_amount)/1e6, 2) AS revenue_musd "
            "FROM dwd_trip_detail GROUP BY 1 ORDER BY 1",
        )
        null_dims = one_row(
            con,
            "SELECT sum(CASE WHEN pu_borough IS NULL THEN 1 ELSE 0 END) AS null_pu_zone, "
            "sum(CASE WHEN payment_name IS NULL THEN 1 ELSE 0 END) AS null_payment, "
            "sum(CASE WHEN temp_mean_c IS NULL THEN 1 ELSE 0 END) AS null_weather FROM dwd_trip_detail",
        )
        dedup_rows = funnel["filtered_rows"] - dwd_rows
        dedup_rate = dedup_rows / funnel["filtered_rows"] if funnel["filtered_rows"] else 0

    audit = {
        "funnel": funnel,
        "dwd_rows": dwd_rows,
        "dedup_removed": dedup_rows,
        "dedup_rate": round(dedup_rate, 6),
        "partitions": parts,
        "by_year": by_year,
        "null_dims": null_dims,
        "size_gb": round(sum(f.stat().st_size for f in DWD.rglob("*.parquet")) / 1024**3, 2),
    }
    json_dump(audit, ROOT / "output" / "dwd_audit.json")

    print(f"\n  ODS       {funnel['ods_rows']:>12,}")
    print(f"  filtered  {funnel['filtered_rows']:>12,}")
    print(f"  DWD       {dwd_rows:>12,}")
    print(f"  dedup     {dedup_rows:>12,}  ({dedup_rate:.4%})")
    print(f"  partitions {parts}, size {audit['size_gb']} GB")
    for row in by_year:
        print("  ", row)
    print("  null dims", null_dims)
    con.close()


if __name__ == "__main__":
    main()
