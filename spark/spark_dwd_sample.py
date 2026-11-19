"""Spark SQL 对照实验：用 Spark 4.3 处理 1 个月 ODS，验证「同一套 SQL 能平移」。

本机：JDK 21 + Spark 4.3.0 + Python 3.13，local[2] / driver 2g。
完整 36 个月由 DuckDB 跑（单机更快）；Spark 只跑 2023-01 做技术栈验证与倾斜实验。

运行：
    powershell -File spark/run_spark.ps1
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

ROOT = Path(__file__).resolve().parents[1]
ODS_ONE = ROOT / "data" / "ods" / "trips" / "pickup_year=2023" / "pickup_month=1"
DIM = ROOT / "data" / "dim"
OUT = ROOT / "data" / "spark" / "dwd_sample"


def main() -> None:
    spark = (
        SparkSession.builder.appName("nyc-tlc-dwd-sample")
        .master("local[2]")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    print("Spark", spark.version, "Java", spark.sparkContext._jvm.System.getProperty("java.version"))

    zones = spark.read.parquet((DIM / "dim_zone.parquet").as_posix())
    payments = spark.read.parquet((DIM / "dim_payment.parquet").as_posix())
    ratecodes = spark.read.parquet((DIM / "dim_ratecode.parquet").as_posix())
    weather = spark.read.parquet((DIM / "dim_weather.parquet").as_posix())

    t0 = time.perf_counter()
    # Windows + winutils 对目录 list 可能返回 AccessDenied；直接给文件名，绕过 Hadoop 列目录
    ods = spark.read.parquet((ODS_ONE / "data_0.parquet").as_posix())
    base = (
        ods.filter(
            (F.col("dropoff_ts") > F.col("pickup_ts"))
            & (F.col("trip_distance").between(0, 200))
            & (F.col("fare_amount").between(0, 1000))
            & (F.col("total_amount").between(0, 2000))
            & (F.col("pu_location_id").between(1, 265))
            & (F.col("do_location_id").between(1, 265))
            & (F.col("payment_type").between(0, 6))
        )
        .withColumn(
            "duration_min",
            (F.unix_timestamp("dropoff_ts") - F.unix_timestamp("pickup_ts")) / 60.0,
        )
        .filter(F.col("duration_min").between(1, 240))
        .withColumn("pickup_date", F.to_date("pickup_ts"))
        .withColumn("pickup_hour", F.hour("pickup_ts"))
        .withColumn("is_airport_pickup", F.col("pu_location_id").isin(1, 132, 138))
        .withColumn(
            "trip_key",
            F.xxhash64("vendor_id", "pickup_ts", "dropoff_ts", "pu_location_id", "do_location_id", "total_amount"),
        )
    )
    w = Window.partitionBy("trip_key").orderBy("source_file", "pickup_ts")
    dedup = base.withColumn("rn", F.row_number().over(w)).filter("rn = 1").drop("rn", "trip_key")

    dwd = (
        dedup.join(
            F.broadcast(
                zones.select(
                    F.col("location_id").alias("pu_location_id"),
                    F.col("borough").alias("pu_borough"),
                    F.col("zone").alias("pu_zone"),
                    F.col("service_zone").alias("pu_service_zone"),
                )
            ),
            "pu_location_id",
            "left",
        )
        .join(
            F.broadcast(
                zones.select(
                    F.col("location_id").alias("do_location_id"),
                    F.col("borough").alias("do_borough"),
                )
            ),
            "do_location_id",
            "left",
        )
        .join(F.broadcast(payments), "payment_type", "left")
        .join(F.broadcast(ratecodes), "ratecode_id", "left")
        .join(
            F.broadcast(weather.select("date", "temp_mean_c", "precip_mm", "snow_mm")),
            F.col("pickup_date") == F.col("date"),
            "left",
        )
        .drop("date")
        .withColumn("pickup_year", F.lit(2023))
        .withColumn("pickup_month", F.lit(1))
    )
    dwd.cache()
    n = dwd.count()
    print(f"Spark DWD rows = {n:,}, build {time.perf_counter()-t0:.1f}s")

    # 说明：Windows + DSH 沙箱下 Spark 写 Parquet 会触发 winutils chmod 被 ACL 拒绝，
    # 因此这里只做内存计算与结果验证；正式落盘由 DuckDB 版本完成（见 data/dwd）。
    dwd.createOrReplaceTempView("dwd_sample")

    # 1) 普通聚合：区域 × 小时
    t1 = time.perf_counter()
    direct = spark.sql(
        """
        SELECT pu_location_id, pickup_hour, count(*) AS trips, round(sum(total_amount), 2) AS revenue
        FROM dwd_sample GROUP BY 1, 2 ORDER BY 1, 2
        """
    )
    direct_count = direct.count()
    t_direct = time.perf_counter() - t1

    # 2) 加盐两阶段聚合：先按 (zone, hour, salt) 局部聚合，再按 (zone, hour) 汇总
    t2 = time.perf_counter()
    salted = spark.sql(
        """
        WITH s AS (
            SELECT pu_location_id, pickup_hour, total_amount,
                   pmod(hash(pickup_ts), 8) AS salt
            FROM dwd_sample
        ),
        stage1 AS (
            SELECT pu_location_id, pickup_hour, salt, count(*) AS c, sum(total_amount) AS s
            FROM s GROUP BY 1, 2, 3
        )
        SELECT pu_location_id, pickup_hour, sum(c) AS trips, round(sum(s), 2) AS revenue
        FROM stage1 GROUP BY 1, 2 ORDER BY 1, 2
        """
    )
    salted_count = salted.count()
    t_salted = time.perf_counter() - t2

    print(f"direct rows={direct_count:,} time={t_direct:.2f}s")
    print(f"salted rows={salted_count:,} time={t_salted:.2f}s")
    print("top zones:")
    top_rows = spark.sql(
        """
        SELECT pu_location_id, pu_zone, sum(trips) AS trips, round(sum(revenue), 2) AS revenue
        FROM (
            SELECT pu_location_id, pu_zone, count(*) AS trips, sum(total_amount) AS revenue
            FROM dwd_sample GROUP BY 1, 2
        ) GROUP BY 1, 2 ORDER BY revenue DESC LIMIT 10
        """
    ).collect()
    for row in top_rows:
        print(" ", row)

    import json

    audit = {
        "spark_version": spark.version,
        "java_version": "21.0.2",
        "mode": "local[2] / driver 2g",
        "sample": "2023-01 ODS",
        "dwd_rows": n,
        "build_seconds": round(time.perf_counter() - t0, 2),
        "direct_seconds": round(t_direct, 3),
        "salted_seconds": round(t_salted, 3),
        "speedup_pct": round((t_direct - t_salted) / t_direct * 100, 1),
        "direct_rows": direct_count,
        "salted_rows": salted_count,
        "top_zones": [
            {"pu_location_id": r["pu_location_id"], "pu_zone": r["pu_zone"], "trips": r["trips"], "revenue": r["revenue"]}
            for r in top_rows
        ],
    }
    (ROOT / "output" / "spark_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote output/spark_audit.json")

    spark.stop()


if __name__ == "__main__":
    main()
