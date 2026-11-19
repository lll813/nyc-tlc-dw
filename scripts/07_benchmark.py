"""Step 7: 性能实验 —— 分区裁剪、列裁剪、CSV vs Parquet、线程数、倾斜与加盐。

所有数字都是本机实测（i7-12700H / 16 GB / DuckDB 2.0 / 3 GB 内存上限）。
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_PATH, DWD, RAW
from scripts.common import connect, json_dump, scalar, table, timer

BENCH = ROOT / "data" / "bench"
RESULTS: list[dict] = []


def timed(con, name: str, sql: str, repeat: int = 3, note: str = "") -> float:
    times = []
    rows = None
    for _ in range(repeat):
        t0 = time.perf_counter()
        res = con.execute(sql).fetchall()
        times.append(time.perf_counter() - t0)
        rows = len(res)
    med = statistics.median(times)
    best = min(times)
    RESULTS.append({"name": name, "seconds_median": round(med, 3), "seconds_best": round(best, 3), "rows": rows, "note": note})
    print(f"  {name:32s} median={med:7.3f}s best={best:7.3f}s rows={rows}", flush=True)
    return med


def main() -> None:
    BENCH.mkdir(parents=True, exist_ok=True)
    con = connect()
    raw_glob = (RAW / "yellow_tripdata_*.parquet").as_posix()
    one_raw = (RAW / "yellow_tripdata_2025-01.parquet").as_posix()

    with timer("benchmark basics"):
        timed(con, "raw_full_scan_sum", f"SELECT round(sum(total_amount),2) FROM read_parquet('{raw_glob}', union_by_name=true)", 3,
              "36 个月原始 Parquet 全量，真实读金额列")
        timed(con, "raw_one_month_sum", f"SELECT round(sum(total_amount),2) FROM read_parquet('{one_raw}')", 3,
              "单月 Parquet，模拟分区裁剪")
        timed(con, "dwd_full_scan_sum", "SELECT round(sum(total_amount),2) FROM dwd_trip_detail", 3, "DWD 全量金额列")
        timed(con, "dwd_one_month_sum", "SELECT round(sum(total_amount),2) FROM dwd_trip_detail WHERE pickup_year=2025 AND pickup_month=1", 3,
              "分区裁剪到 1 个月")
        timed(con, "dwd_groupby_zone", "SELECT pu_location_id, count(*), round(sum(total_amount),2) FROM dwd_trip_detail GROUP BY 1", 3,
              "按 zone 聚合全量")
        timed(con, "dwd_groupby_date", "SELECT pickup_date, count(*), round(sum(total_amount),2) FROM dwd_trip_detail GROUP BY 1 ORDER BY 1", 3,
              "按天聚合全量")

    with timer("column pruning"):
        timed(con, "column_1", "SELECT sum(total_amount) FROM dwd_trip_detail", 3, "只读 1 列")
        timed(con, "column_6", "SELECT sum(total_amount), sum(tip_amount), sum(fare_amount), sum(tolls_amount), sum(duration_min), sum(trip_distance) FROM dwd_trip_detail", 3,
              "读 6 列")

    with timer("threads scaling"):
        for n in (1, 2, 4, 8):
            con.execute(f"SET threads={n}")
            timed(con, f"threads_{n}_groupby_zone", "SELECT pu_location_id, count(*), round(sum(total_amount),2) FROM dwd_trip_detail GROUP BY 1", 2,
                  f"threads={n}")
        con.execute("SET threads=4")

    with timer("CSV vs Parquet"):
        csv_path = BENCH / "dwd_2025_01.csv"
        if not csv_path.exists():
            con.execute(
                f"COPY (SELECT * FROM dwd_trip_detail WHERE pickup_year=2025 AND pickup_month=1) "
                f"TO '{csv_path.as_posix()}' (HEADER, DELIMITER ',')"
            )
        csv_gb = csv_path.stat().st_size / 1024**3
        pq_gb = sum(f.stat().st_size for f in (DWD / "pickup_year=2025" / "pickup_month=1").glob("*.parquet")) / 1024**3
        timed(con, "csv_one_month_agg", f"SELECT count(*), round(sum(total_amount),2) FROM read_csv_auto('{csv_path.as_posix()}')", 2,
              f"CSV {csv_gb:.2f} GB")
        timed(con, "parquet_one_month_agg", "SELECT count(*), round(sum(total_amount),2) FROM dwd_trip_detail WHERE pickup_year=2025 AND pickup_month=1", 2,
              f"Parquet {pq_gb:.2f} GB")
        # 实验完删掉 1.2 GB CSV，避免占盘；需要复现时脚本会自动重建
        csv_path.unlink(missing_ok=True)

    with timer("skew"):
        top = table(
            con,
            "SELECT pu_location_id, count(*) c FROM dwd_trip_detail GROUP BY 1 ORDER BY c DESC LIMIT 10",
        )
        total = scalar(con, "SELECT count(*) FROM dwd_trip_detail")
        RESULTS.append({"name": "skew_top_zones", "top": top, "total": total, "top1_share": round(top[0][1] / total, 4)})
        print("  top zones:", top[:5], "top1_share=", round(top[0][1] / total, 4))

        timed(con, "skew_naive_groupby", "SELECT pickup_date, pu_location_id, count(*), round(sum(total_amount),2) FROM dwd_trip_detail WHERE pickup_year=2025 GROUP BY 1,2", 2,
              "普通两列 group by")
        timed(con, "skew_salted_groupby", """
            WITH s AS (
                SELECT pickup_date, pu_location_id, total_amount, hash(pickup_ts) % 8 AS salt
                FROM dwd_trip_detail WHERE pickup_year=2025
            ), stage1 AS (
                SELECT pickup_date, pu_location_id, salt, count(*) c, sum(total_amount) amt
                FROM s GROUP BY 1,2,3
            )
            SELECT pickup_date, pu_location_id, sum(c), round(sum(amt),2)
            FROM stage1 GROUP BY 1,2
        """, 2, "加盐两阶段聚合")

    result = {
        "machine": "i7-12700H / 16GB / Windows / DuckDB 2.0 / 3GB memory_limit / 4 threads",
        "results": RESULTS,
        "csv_gb": locals().get("csv_gb"),
        "parquet_gb": locals().get("pq_gb"),
        "db_size_gb": round(DB_PATH.stat().st_size / 1024**3, 2) if DB_PATH.exists() else None,
    }
    json_dump(result, ROOT / "output" / "benchmark.json")

    # Markdown 表
    lines = [
        "| 实验 | 中位耗时(s) | 最快(s) | 说明 |",
        "|---|---:|---:|---|",
    ]
    for r in RESULTS:
        if "seconds_median" in r:
            lines.append(f"| {r['name']} | {r['seconds_median']:.3f} | {r['seconds_best']:.3f} | {r['note']} |")
    (ROOT / "output" / "benchmark.md").write_text("\n".join(lines), encoding="utf-8")
    print("\nwrote output/benchmark.json + benchmark.md")
    con.close()


if __name__ == "__main__":
    main()
