"""Step 6: 数据质量 —— 18 条规则，PASS / WARN / FAIL 三级，落 JSON + DuckDB 表。

设计原则：
- 每条规则都有明确 SQL、观测值、阈值、责任层；
- 对 TLC 已知的"分项与总额口径不一致"标 WARN，不阻断主流程（收入以 total_amount 为准）；
- 结果可被 Airflow/调度器读取，用于阻断下游。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DQ_THRESHOLDS, OUTPUT
from scripts.common import connect, one_row, scalar, timer

CHECKS_SQL = """
SELECT
    count(*) AS rows,
    sum(CASE WHEN dropoff_ts <= pickup_ts OR duration_min < 1 OR duration_min > 240 THEN 1 ELSE 0 END) AS bad_duration,
    sum(CASE WHEN trip_distance < 0 OR trip_distance > 200 THEN 1 ELSE 0 END) AS bad_distance,
    sum(CASE WHEN fare_amount < 0 OR total_amount < 0 THEN 1 ELSE 0 END) AS bad_amount,
    sum(CASE WHEN pu_location_id NOT BETWEEN 1 AND 265 OR do_location_id NOT BETWEEN 1 AND 265 THEN 1 ELSE 0 END) AS bad_zone,
    sum(CASE WHEN pu_borough IS NULL THEN 1 ELSE 0 END) AS null_pu_zone,
    sum(CASE WHEN payment_name IS NULL THEN 1 ELSE 0 END) AS null_payment,
    sum(CASE WHEN temp_mean_c IS NULL THEN 1 ELSE 0 END) AS null_weather,
    sum(CASE WHEN abs(total_amount - revenue_parts) <= 0.011 THEN 1 ELSE 0 END) AS revenue_match,
    round(sum(total_amount), 2) AS revenue
FROM dwd_trip_detail
"""


def add(checks: list[dict], name: str, layer: str, rule: str, observed, threshold, status: str, severity: str, detail: str = "") -> None:
    checks.append(
        {
            "check": name,
            "layer": layer,
            "rule": rule,
            "observed": observed,
            "threshold": threshold,
            "status": status,
            "severity": severity,
            "detail": detail,
        }
    )


def main() -> None:
    con = connect()
    checks: list[dict] = []
    t = timer("quality checks")
    t.__enter__()
    try:
        # ODS / 接入层
        raw_rows = scalar(con, "SELECT count(*) FROM read_parquet('" + (ROOT / "data" / "raw" / "yellow_tripdata_*.parquet").as_posix() + "', union_by_name=true)")
        ods_rows = scalar(con, "SELECT count(*) FROM ods_trips")
        rejected = scalar(con, "SELECT count(*) FROM read_parquet('" + (ROOT / "data" / "ods" / "_rejected" / "rejected.parquet").as_posix() + "')")
        reject_rate = rejected / raw_rows if raw_rows else 0
        add(checks, "ods_reject_rate", "ODS", "异常 pickup 时间戳占比", round(reject_rate, 6), DQ_THRESHOLDS["reject_rate_max"],
            "PASS" if reject_rate <= DQ_THRESHOLDS["reject_rate_max"] else "FAIL", "FAIL",
            f"raw={raw_rows:,}, ods={ods_rows:,}, rejected={rejected:,}")
        parts = scalar(con, "SELECT count(DISTINCT (pickup_year, pickup_month)) FROM ods_trips")
        add(checks, "ods_partitions", "ODS", "按月分区数 = 36", parts, 36,
            "PASS" if parts == 36 else "FAIL", "FAIL")
        add(checks, "ods_rows_positive", "ODS", "ODS 行数 > 1 亿", f"{ods_rows:,}", 100_000_000,
            "PASS" if ods_rows > 100_000_000 else "FAIL", "FAIL")

        # DWD 规则（一次扫描）
        r = one_row(con, CHECKS_SQL)
        n = r["rows"]
        add(checks, "dwd_rows_positive", "DWD", "DWD 行数 > 1 亿", f"{n:,}", 100_000_000,
            "PASS" if n > 100_000_000 else "FAIL", "FAIL")
        weather_days = scalar(con, "SELECT count(*) FROM dim_weather")
        add(checks, "dim_weather_days", "DIM", "天气维表覆盖 1096 天", weather_days, 1096,
            "PASS" if weather_days == 1096 else "FAIL", "FAIL")
        for key, label, severity in [
            ("bad_duration", "时长/时间顺序合法", "FAIL"),
            ("bad_distance", "里程在 0~200 英里", "FAIL"),
            ("bad_amount", "金额非负", "FAIL"),
            ("bad_zone", "zone id 在 1~265", "FAIL"),
        ]:
            add(checks, f"dwd_{key}", "DWD", label, r[key], 0,
                "PASS" if r[key] == 0 else "FAIL", severity, f"rows={n:,}")

        for key, label, threshold in [
            ("null_pu_zone", "上车 zone 维度覆盖率", DQ_THRESHOLDS["zone_coverage_min"]),
            ("null_payment", "支付方式维度覆盖率", DQ_THRESHOLDS["payment_coverage_min"]),
            ("null_weather", "天气维度覆盖率", 0.99),
        ]:
            rate = 1 - (r[key] / n if n else 0)
            add(checks, f"dwd_{key}", "DWD", label, round(rate, 6), threshold,
                "PASS" if rate >= threshold else "FAIL", "FAIL", f"null={r[key]:,}")

        rev_rate = r["revenue_match"] / n if n else 0
        add(checks, "dwd_revenue_reconcile", "DWD", "分项之和 ≈ total_amount（±$0.01）", round(rev_rate, 6), DQ_THRESHOLDS["revenue_match_min"],
            "PASS" if rev_rate >= DQ_THRESHOLDS["revenue_match_min"] else "WARN", "WARN",
            "TLC 不同 Vendor 的分项口径不一致，收入以 total_amount 为准；此规则只观测不阻断")

        audit = json.loads((OUTPUT / "dwd_audit.json").read_text(encoding="utf-8"))
        dedup_rate = audit.get("dedup_rate", 0)
        add(checks, "dwd_dedup_rate", "DWD", "自然键重复率（月分区内去重前）", dedup_rate, DQ_THRESHOLDS["dup_rate_max"],
            "PASS" if dedup_rate <= DQ_THRESHOLDS["dup_rate_max"] else "FAIL", "FAIL",
            f"removed={audit.get('dedup_removed', 0):,}")

        # ADS 对账
        daily_days = scalar(con, "SELECT count(*) FROM ads_daily_kpi")
        add(checks, "ads_daily_days", "ADS", "日粒度覆盖 1096 天", daily_days, 1096,
            "PASS" if daily_days == 1096 else "FAIL", "FAIL")
        months = scalar(con, "SELECT count(*) FROM ads_monthly_kpi")
        add(checks, "ads_month_count", "ADS", "月粒度覆盖 36 个月", months, 36,
            "PASS" if months == 36 else "FAIL", "FAIL")

        ads_trips = scalar(con, "SELECT sum(trips) FROM ads_daily_kpi")
        add(checks, "ads_trip_reconcile", "ADS", "ADS 行程数 = DWD 行数", f"{ads_trips:,} vs {n:,}", "equal",
            "PASS" if ads_trips == n else "FAIL", "FAIL")
        ads_rev = scalar(con, "SELECT sum(revenue) FROM ads_daily_kpi")
        diff = abs(float(ads_rev) - float(r["revenue"])) / max(float(r["revenue"]), 1)
        add(checks, "ads_revenue_reconcile", "ADS", "ADS 收入 = DWD 收入（误差 < 0.1%）", round(diff, 8), 0.001,
            "PASS" if diff < 0.001 else "FAIL", "FAIL", f"ads={ads_rev:,.2f}, dwd={r['revenue']:,.2f}")
    finally:
        t.__exit__(None, None, None)

    fail = sum(1 for c in checks if c["status"] == "FAIL")
    warn = sum(1 for c in checks if c["status"] == "WARN")
    overall = "FAIL" if fail else ("WARN" if warn else "PASS")
    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall": overall,
        "summary": {"total": len(checks), "pass": len(checks) - fail - warn, "warn": warn, "fail": fail},
        "checks": checks,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "quality_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    con.execute("DROP TABLE IF EXISTS dq_result")
    con.execute(
        "CREATE TABLE dq_result (check_name VARCHAR, layer VARCHAR, rule VARCHAR, observed VARCHAR, "
        "threshold VARCHAR, status VARCHAR, severity VARCHAR, detail VARCHAR)"
    )
    con.executemany(
        "INSERT INTO dq_result VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (c["check"], c["layer"], c["rule"], str(c["observed"]), str(c["threshold"]), c["status"], c["severity"], c["detail"])
            for c in checks
        ],
    )
    con.close()

    print(f"\noverall={overall}  pass={result['summary']['pass']}  warn={warn}  fail={fail}")
    for c in checks:
        print(f"  [{c['status']:4s}] {c['layer']:3s} {c['check']:28s} observed={c['observed']}  {c['rule']}")


if __name__ == "__main__":
    main()
