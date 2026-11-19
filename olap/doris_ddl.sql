-- Apache Doris 2.x serving 层：Unique Key 模型，支持按天 upsert
-- 与 ClickHouse 版本二选一即可；本机不装 Doris，文件用于展示建表与选型。

CREATE DATABASE IF NOT EXISTS tlc;
USE tlc;

CREATE TABLE IF NOT EXISTS ads_daily_kpi (
    date              DATE        NOT NULL,
    trips             BIGINT      NOT NULL,
    revenue           DECIMAL(18, 2),
    avg_fare          DECIMAL(10, 2),
    avg_miles         DOUBLE,
    avg_duration_min  DOUBLE,
    avg_speed_mph     DOUBLE,
    airport_share     DOUBLE,
    card_share        DOUBLE,
    card_tip_rate     DOUBLE,
    active_zones      INT
)
UNIQUE KEY(date)
DISTRIBUTED BY HASH(date) BUCKETS 4
PROPERTIES (
    "replication_allocation" = "tag.location.default: 1",
    "enable_unique_key_merge_on_write" = "true"
);

CREATE TABLE IF NOT EXISTS ads_zone_rank (
    year_month     VARCHAR(7) NOT NULL,
    pu_location_id INT        NOT NULL,
    pu_zone        VARCHAR(80),
    pu_borough     VARCHAR(40),
    trips          BIGINT,
    revenue        DECIMAL(18, 2),
    avg_fare       DECIMAL(10, 2),
    avg_speed_mph  DOUBLE
)
UNIQUE KEY(year_month, pu_location_id)
PARTITION BY RANGE(year_month) ()
DISTRIBUTED BY HASH(pu_location_id) BUCKETS 4
PROPERTIES ("replication_allocation" = "tag.location.default: 1");

-- 导入：Stream Load / Broker Load 把 Parquet 落到 ADS 表
-- curl --location-trusted -u root: -H "format: parquet" -T ads_daily_kpi.parquet \
--   http://doris-fe:8030/api/tlc/ads_daily_kpi/_stream_load
