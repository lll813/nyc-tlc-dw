-- ODS 层：贴源、按 pickup 年月分区、保留来源文件，异常时间戳单独落 rejected
-- 这里不做业务清洗（清洗放 DWD），只做"可追溯的规范化"

COPY (
    SELECT
        CAST(VendorID AS SMALLINT)                    AS vendor_id,
        tpep_pickup_datetime                           AS pickup_ts,
        tpep_dropoff_datetime                          AS dropoff_ts,
        CAST(passenger_count AS TINYINT)               AS passenger_count,
        CAST(trip_distance AS DOUBLE)                  AS trip_distance,
        CAST(RatecodeID AS SMALLINT)                   AS ratecode_id,
        store_and_fwd_flag,
        CAST(PULocationID AS SMALLINT)                 AS pu_location_id,
        CAST(DOLocationID AS SMALLINT)                 AS do_location_id,
        CAST(payment_type AS TINYINT)                  AS payment_type,
        CAST(fare_amount AS DOUBLE)                    AS fare_amount,
        CAST(extra AS DOUBLE)                          AS extra,
        CAST(mta_tax AS DOUBLE)                        AS mta_tax,
        CAST(tip_amount AS DOUBLE)                     AS tip_amount,
        CAST(tolls_amount AS DOUBLE)                   AS tolls_amount,
        CAST(improvement_surcharge AS DOUBLE)          AS improvement_surcharge,
        CAST(total_amount AS DOUBLE)                   AS total_amount,
        CAST(congestion_surcharge AS DOUBLE)           AS congestion_surcharge,
        CAST(COALESCE(airport_fee, 0) AS DOUBLE)       AS airport_fee,
        CAST(COALESCE(cbd_congestion_fee, 0) AS DOUBLE) AS cbd_congestion_fee,
        filename                                       AS source_file,
        CAST(now() AS TIMESTAMP)                       AS ingest_ts,
        CAST(strftime(tpep_pickup_datetime, '%Y') AS SMALLINT) AS pickup_year,
        CAST(strftime(tpep_pickup_datetime, '%m') AS TINYINT)  AS pickup_month
    FROM read_parquet('{{RAW_GLOB}}', union_by_name = true, filename = true)
    WHERE tpep_pickup_datetime >= TIMESTAMP '{{START_TS}}'
      AND tpep_pickup_datetime <  TIMESTAMP '{{END_TS}}'
) TO '{{ODS_DIR}}' (
    FORMAT PARQUET,
    PARTITION_BY (pickup_year, pickup_month),
    COMPRESSION ZSTD,
    OVERWRITE_OR_IGNORE
);

COPY (
    SELECT
        VendorID                    AS vendor_id,
        tpep_pickup_datetime        AS pickup_ts,
        tpep_dropoff_datetime       AS dropoff_ts,
        PULocationID                AS pu_location_id,
        DOLocationID                AS do_location_id,
        total_amount,
        filename                    AS source_file,
        CASE
            WHEN tpep_pickup_datetime IS NULL THEN 'pickup_null'
            WHEN tpep_pickup_datetime <  TIMESTAMP '{{START_TS}}' THEN 'pickup_before_range'
            ELSE 'pickup_after_range'
        END                         AS reject_reason
    FROM read_parquet('{{RAW_GLOB}}', union_by_name = true, filename = true)
    WHERE tpep_pickup_datetime IS NULL
       OR tpep_pickup_datetime <  TIMESTAMP '{{START_TS}}'
       OR tpep_pickup_datetime >= TIMESTAMP '{{END_TS}}'
) TO '{{REJECTED_FILE}}' (FORMAT PARQUET, COMPRESSION ZSTD);

CREATE OR REPLACE VIEW ods_trips AS
SELECT *
FROM read_parquet('{{ODS_GLOB}}', hive_partitioning = true, union_by_name = true);
