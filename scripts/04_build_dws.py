"""Step 4: DWS —— 日期 × zone / hour / payment / borough / weather 预聚合。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import SQL_DIR
from scripts.common import connect, json_dump, run_sql_file, scalar, table, timer


def main() -> None:
    con = connect()
    dws_dir = ROOT / "data" / "dws"
    dws_dir.mkdir(parents=True, exist_ok=True)

    with timer("build DWS tables"):
        run_sql_file(con, SQL_DIR / "04_dws.sql", DWS_DIR=dws_dir.as_posix())

    result = {}
    for name in (
        "dws_zone_day",
        "dws_hour_day",
        "dws_payment_day",
        "dws_borough_day",
        "dws_zone_hour",
        "dws_weather_day",
    ):
        n = scalar(con, f"SELECT count(*) FROM {name}")
        result[name] = n
        print(f"  {name:18s} {n:>10,} rows")

    sample = table(con, "SELECT * FROM dws_zone_day ORDER BY revenue DESC LIMIT 3")
    print("\ntop revenue zone-days:")
    for row in sample:
        print("  ", row)

    json_dump(result, ROOT / "output" / "dws_audit.json")
    con.close()


if __name__ == "__main__":
    main()
