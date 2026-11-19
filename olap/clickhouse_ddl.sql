-- ClickHouse  serving 层：把 ADS 指标落到 OLAP，供 BI/接口低延迟查询
-- 适用：JD 中 Doris / ClickHouse / StarRocks 的选型与 POC
-- 导入：clickhouse-client --query "CREATE DATABASE IF NOT EXISTS tlc"
--       clickhouse-client --database tlc --multiquery < clickhouse_ddl.sql

CREATE DATABASE IF NOT EXISTS tlc;

CREATE TABLE IF NOT EXISTS tlc.ads_daily_kpi
(
    date              Date,
    trips             UInt64,
    revenue           Decimal(18, 2),
    avg_fare          Decimal(10, 2),
    avg_miles         Float64,
    avg_duration_min  Float64,
    avg_speed_mph     Float64,
    airport_share     Float64,
    card_share        Float64,
    card_tip_rate     Float64,
    active_zones      UInt16
)
ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(date)
ORDER BY date;

CREATE TABLE IF NOT EXISTS tlc.ads_zone_rank
(
    year_month     String,
    pu_location_id UInt16,
    pu_zone        String,
    pu_borough     String,
    trips          UInt64,
    revenue        Decimal(18, 2),
    avg_fare       Decimal(10, 2),
    avg_speed_mph  Float64
)
ENGINE = ReplacingMergeTree
PARTITION BY year_month
ORDER BY (year_month, pu_location_id);

-- 导入 Parquet（ClickHouse 22.6+ 支持 file 表函数）
-- INSERT INTO tlc.ads_daily_kpi
-- SELECT * FROM file('/data/ads/ads_daily_kpi.parquet', 'Parquet');

-- 典型查询：2025 年每月收入 Top 5 区域
SELECT year_month, pu_zone, revenue
FROM tlc.ads_zone_rank
WHERE year_month LIKE '2025-%'
ORDER BY year_month, revenue DESC
LIMIT 5 BY year_month;

-- 选型话术：
-- ClickHouse：写入吞吐高、单表聚合快、适合 ADS 宽表；不适合高频 update/delete。
-- Doris：MySQL 协议、Unique Key 支持 upsert、物化视图/湖仓联邦更成熟。
-- StarRocks：CBO 与多表 join 更强，适合 ADS 层多表关联。
