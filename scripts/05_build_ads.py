"""Step 5: ADS —— 每日/月度 KPI、区域榜、热力图、机场、小费、支付、预测特征。"""
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
    ads_dir = ROOT / "data" / "ads"
    ads_dir.mkdir(parents=True, exist_ok=True)

    with timer("build ADS tables"):
        run_sql_file(con, SQL_DIR / "05_ads.sql", ADS_DIR=ads_dir.as_posix())

    result = {}
    for name in (
        "ads_daily_kpi",
        "ads_monthly_kpi",
        "ads_zone_rank",
        "ads_hourly_heatmap",
        "ads_airport_daily",
        "ads_tip_zone",
        "ads_payment_mix",
        "ads_borough_hour",
        "ads_demand_forecast",
        "ads_kpi_summary",
    ):
        n = scalar(con, f"SELECT count(*) FROM {name}")
        result[name] = n
        print(f"  {name:22s} {n:>8,} rows")

    print("\nKPI summary:")
    for row in table(con, "SELECT metric, value FROM ads_kpi_summary"):
        print("  ", row)
    print("\nTop 5 zone by revenue (2025-12):")
    for row in table(
        con,
        "SELECT pu_zone, pu_borough, trips, revenue FROM ads_zone_rank "
        "WHERE year_month='2025-12' ORDER BY revenue DESC LIMIT 5",
    ):
        print("  ", row)

    json_dump(result, ROOT / "output" / "ads_audit.json")
    con.close()


if __name__ == "__main__":
    main()
