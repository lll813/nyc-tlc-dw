-- Hive / Spark SQL 外部表 DDL
-- 用途：把 Parquet 湖挂到 Hive Metastore / Spark catalog，证明分区与 schema 可平移。
-- 路径按实际环境替换；本项目本地路径为 data/ods/trips、data/dwd/trip_detail。

CREATE DATABASE IF NOT EXISTS tlc;
USE tlc;

-- ODS：贴源，按 pickup_year / pickup_month 分区
CREATE EXTERNAL TABLE IF NOT EXISTS ods_trips (
    vendor_id             SMALLINT,
    pickup_ts             TIMESTAMP,
    dropoff_ts            TIMESTAMP,
    passenger_count       TINYINT,
    trip_distance         DOUBLE,
    ratecode_id           SMALLINT,
    store_and_fwd_flag    STRING,
    pu_location_id        SMALLINT,
    do_location_id        SMALLINT,
    payment_type          TINYINT,
    fare_amount           DOUBLE,
    extra                 DOUBLE,
    mta_tax               DOUBLE,
    tip_amount            DOUBLE,
    tolls_amount          DOUBLE,
    improvement_surcharge DOUBLE,
    total_amount          DOUBLE,
    congestion_surcharge  DOUBLE,
    airport_fee           DOUBLE,
    cbd_congestion_fee    DOUBLE,
    source_file           STRING,
    ingest_ts             TIMESTAMP
)
PARTITIONED BY (pickup_year SMALLINT, pickup_month TINYINT)
STORED AS PARQUET
LOCATION 'hdfs:///warehouse/tlc/ods/trips';

MSCK REPAIR TABLE ods_trips;

-- DWD：清洗后的行程明细
CREATE EXTERNAL TABLE IF NOT EXISTS dwd_trip_detail (
    vendor_id             SMALLINT,
    pickup_ts             TIMESTAMP,
    dropoff_ts            TIMESTAMP,
    passenger_count       TINYINT,
    trip_distance         DOUBLE,
    ratecode_id           SMALLINT,
    store_and_fwd_flag    STRING,
    pu_location_id        SMALLINT,
    do_location_id        SMALLINT,
    payment_type          TINYINT,
    fare_amount           DOUBLE,
    extra                 DOUBLE,
    mta_tax               DOUBLE,
    tip_amount            DOUBLE,
    tolls_amount          DOUBLE,
    improvement_surcharge DOUBLE,
    total_amount          DOUBLE,
    congestion_surcharge  DOUBLE,
    airport_fee           DOUBLE,
    cbd_congestion_fee    DOUBLE,
    source_file           STRING,
    ingest_ts             TIMESTAMP,
    pickup_date           DATE,
    pickup_hour           TINYINT,
    pickup_weekday        TINYINT,
    is_weekend            BOOLEAN,
    is_night              BOOLEAN,
    is_airport_pickup     BOOLEAN,
    duration_min          DOUBLE,
    speed_mph             DOUBLE,
    tip_rate              DOUBLE,
    revenue_parts         DOUBLE,
    revenue_diff          DOUBLE,
    pu_borough            STRING,
    pu_zone               STRING,
    pu_service_zone       STRING,
    do_borough            STRING,
    do_zone               STRING,
    do_service_zone       STRING,
    payment_name          STRING,
    ratecode_name         STRING,
    temp_mean_c           DOUBLE,
    precip_mm             DOUBLE,
    snow_mm               DOUBLE,
    wind_max_kmh          DOUBLE,
    is_rain               BOOLEAN,
    is_snow               BOOLEAN
)
PARTITIONED BY (pickup_year SMALLINT, pickup_month TINYINT)
STORED AS PARQUET
LOCATION 'hdfs:///warehouse/tlc/dwd/trip_detail';

MSCK REPAIR TABLE dwd_trip_detail;

-- 示例：分区裁剪 + 窗口函数
SELECT pickup_date,
       pu_borough,
       count(*) AS trips,
       round(sum(total_amount), 2) AS revenue,
       row_number() OVER (PARTITION BY pickup_date ORDER BY sum(total_amount) DESC) AS rn
FROM dwd_trip_detail
WHERE pickup_year = 2025 AND pickup_month = 12
GROUP BY pickup_date, pu_borough
ORDER BY pickup_date, revenue DESC
LIMIT 20;
