"""Step 2: ODS —— 36 个月原始 Parquet → 按 pickup 年月分区的规范化 Parquet。"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import END_TS, ODS, REJECTED, RAW, SQL_DIR, START_TS
from scripts.common import connect, json_dump, run_sql_file, scalar, table, timer


def main() -> None:
    if ODS.exists():
        print(f"[clean] {ODS}")
        shutil.rmtree(ODS)
    ODS.mkdir(parents=True, exist_ok=True)
    REJECTED.mkdir(parents=True, exist_ok=True)
    rejected_file = REJECTED / "rejected.parquet"
    if rejected_file.exists():
        rejected_file.unlink()

    con = connect()
    raw_glob = (RAW / "yellow_tripdata_*.parquet").as_posix()

    with timer("count raw rows"):
        raw_rows = scalar(
            con,
            f"SELECT count(*) FROM read_parquet('{raw_glob}', union_by_name = true)",
        )
        print(f"  raw rows = {raw_rows:,}")

    with timer("ODS rewrite + partition"):
        run_sql_file(
            con,
            SQL_DIR / "02_ods.sql",
            RAW_GLOB=raw_glob,
            START_TS=START_TS,
            END_TS=END_TS,
            ODS_DIR=ODS.as_posix(),
            ODS_GLOB=(ODS / "**" / "*.parquet").as_posix(),
            REJECTED_FILE=rejected_file.as_posix(),
        )

    with timer("verify"):
        ods_rows = scalar(con, "SELECT count(*) FROM ods_trips")
        rejected_rows = scalar(con, f"SELECT count(*) FROM read_parquet('{rejected_file.as_posix()}')") if rejected_file.exists() else 0
        by_year = table(
            con,
            "SELECT pickup_year, count(*) AS rows, count(DISTINCT pickup_month) AS months "
            "FROM ods_trips GROUP BY 1 ORDER BY 1",
        )
        by_reason = table(
            con,
            f"SELECT reject_reason, count(*) FROM read_parquet('{rejected_file.as_posix()}') GROUP BY 1 ORDER BY 2 DESC"
            if rejected_file.exists()
            else "SELECT 'none' AS reject_reason, 0",
        )
        parts = scalar(
            con,
            f"SELECT count(DISTINCT (pickup_year, pickup_month)) FROM read_parquet('{(ODS / '**' / '*.parquet').as_posix()}', hive_partitioning=true)",
        )

    audit = {
        "raw_rows": raw_rows,
        "ods_rows": ods_rows,
        "rejected_rows": rejected_rows,
        "reject_rate": round(rejected_rows / raw_rows, 6) if raw_rows else 0,
        "partitions": parts,
        "by_year": by_year,
        "reject_reasons": by_reason,
        "raw_files": len(list(RAW.glob("yellow_tripdata_*.parquet"))),
    }
    json_dump(audit, ROOT / "output" / "ods_audit.json")

    print(f"\n  raw       {raw_rows:>12,}")
    print(f"  ODS       {ods_rows:>12,}")
    print(f"  rejected  {rejected_rows:>12,}  ({audit['reject_rate']:.4%})")
    print(f"  partitions {parts}")
    for row in by_year:
        print("  ", row)
    for row in by_reason:
        print("  reject", row)
    con.close()


if __name__ == "__main__":
    main()
