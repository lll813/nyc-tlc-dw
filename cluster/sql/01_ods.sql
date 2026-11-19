-- Spark SQL on YARN：先验证 HDFS 上的 ODS 外部表与分区发现
CREATE DATABASE IF NOT EXISTS tlc;
USE tlc;

DROP TABLE IF EXISTS ods_trips;

CREATE EXTERNAL TABLE ods_trips (
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
PARTITIONED BY (pickup_year INT, pickup_month INT)
STORED AS PARQUET
LOCATION 'hdfs://namenode:9000/tlc/ods/trips';

MSCK REPAIR TABLE ods_trips;

SELECT pickup_year, pickup_month, count(*) AS rows
FROM ods_trips
GROUP BY pickup_year, pickup_month;
