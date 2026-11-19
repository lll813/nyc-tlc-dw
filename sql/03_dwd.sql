-- DWD 层：清洗、去重、维度补全、天气关联
-- 粒度：一行 = 一次黄色出租车行程
-- 分区：pickup_year / pickup_month（由 Python 按月循环写入，避免对 1.2 亿行做全局窗口排序）
--
-- 清洗规则（全部可在 docs/metric_dict.md 查到）：
--   1) dropoff > pickup，行程时长 1~240 分钟
--   2) 里程 0~200 英里
--   3) 车费 0~1000 美元，总金额 0~2000 美元，小费/过路费非负
--   4) 上/下车 zone 必须在 1~265
--   5) payment_type 0~6，ratecode 0~6 或 99
--   6) 乘客数 NULL 或 0~8
--   7) 用 hash(自然键) 在「月分区内」去重，保留 source_file 排序第一条
--
-- 注意：TLC 的 total_amount 与分项之和并非 100% 可对账（不同 Vendor 口径不同），
-- 本项目以 total_amount 作为收入口径，分项差额只做质量观测，不做过滤。

COPY (
    WITH base AS (
        SELECT
            o.*,
            date_diff('second', o.pickup_ts, o.dropoff_ts) / 60.0 AS duration_min,
            CAST(o.pickup_ts AS DATE)                            AS pickup_date,
            CAST(hour(o.pickup_ts) AS TINYINT)                   AS pickup_hour,
            CAST(dayofweek(o.pickup_ts) AS TINYINT)              AS pickup_weekday, -- 0=Sunday
            CASE WHEN dayofweek(o.pickup_ts) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend,
            CASE WHEN hour(o.pickup_ts) >= 22 OR hour(o.pickup_ts) < 6 THEN TRUE ELSE FALSE END AS is_night,
            CASE WHEN o.pu_location_id IN (1, 132, 138) THEN TRUE ELSE FALSE END AS is_airport_pickup,
            o.fare_amount + o.extra + o.mta_tax + o.tip_amount + o.tolls_amount
                + o.improvement_surcharge + COALESCE(o.congestion_surcharge, 0)
                + COALESCE(o.airport_fee, 0) + COALESCE(o.cbd_congestion_fee, 0) AS revenue_parts,
            hash(
                o.vendor_id, o.pickup_ts, o.dropoff_ts, o.pu_location_id,
                o.do_location_id, o.total_amount, o.trip_distance
            ) AS trip_key
        FROM ods_trips o
        WHERE o.pickup_year = {{YEAR}}
          AND o.pickup_month = {{MONTH}}
          AND o.dropoff_ts > o.pickup_ts
          AND date_diff('second', o.pickup_ts, o.dropoff_ts) BETWEEN 60 AND 14400
          AND o.trip_distance BETWEEN 0 AND 200
          AND o.fare_amount BETWEEN 0 AND 1000
          AND o.total_amount BETWEEN 0 AND 2000
          AND o.tip_amount BETWEEN 0 AND 500
          AND o.tolls_amount BETWEEN 0 AND 200
          AND o.pu_location_id BETWEEN 1 AND 265
          AND o.do_location_id BETWEEN 1 AND 265
          AND o.payment_type BETWEEN 0 AND 6
          AND (o.ratecode_id IS NULL OR o.ratecode_id IN (0, 1, 2, 3, 4, 5, 6, 99))
          AND (o.passenger_count IS NULL OR o.passenger_count BETWEEN 0 AND 8)
    ),
    dedup AS (
        SELECT * EXCLUDE (trip_key)
        FROM base
        QUALIFY row_number() OVER (PARTITION BY trip_key ORDER BY source_file, pickup_ts) = 1
    )
    SELECT
        d.vendor_id,
        d.pickup_ts,
        d.dropoff_ts,
        d.passenger_count,
        d.trip_distance,
        d.ratecode_id,
        d.store_and_fwd_flag,
        d.pu_location_id,
        d.do_location_id,
        d.payment_type,
        d.fare_amount,
        d.extra,
        d.mta_tax,
        d.tip_amount,
        d.tolls_amount,
        d.improvement_surcharge,
        d.total_amount,
        d.congestion_surcharge,
        d.airport_fee,
        d.cbd_congestion_fee,
        regexp_extract(d.source_file, '[^/\\]+$')             AS source_file,
        d.ingest_ts,
        d.pickup_date,
        d.pickup_hour,
        d.pickup_weekday,
        d.is_weekend,
        d.is_night,
        d.is_airport_pickup,
        CAST(d.duration_min AS DOUBLE)                        AS duration_min,
        CAST(CASE WHEN d.duration_min > 0
                  THEN least(d.trip_distance / (d.duration_min / 60.0), 120)
                  ELSE 0 END AS DOUBLE)                       AS speed_mph,
        CAST(CASE WHEN d.fare_amount > 0
                  THEN least(d.tip_amount / d.fare_amount, 2.0)
                  ELSE 0 END AS DOUBLE)                       AS tip_rate,
        CAST(d.revenue_parts AS DOUBLE)                       AS revenue_parts,
        CAST(d.total_amount - d.revenue_parts AS DOUBLE)      AS revenue_diff,
        z.borough                                             AS pu_borough,
        z.zone                                                AS pu_zone,
        z.service_zone                                        AS pu_service_zone,
        dz.borough                                            AS do_borough,
        dz.zone                                               AS do_zone,
        dz.service_zone                                       AS do_service_zone,
        p.payment_name,
        r.ratecode_name,
        w.temp_mean_c,
        w.precip_mm,
        w.snow_mm,
        w.wind_max_kmh,
        COALESCE(w.is_rain, FALSE)                            AS is_rain,
        COALESCE(w.is_snow, FALSE)                            AS is_snow
    FROM dedup d
    LEFT JOIN dim_zone    z  ON d.pu_location_id = z.location_id
    LEFT JOIN dim_zone    dz ON d.do_location_id = dz.location_id
    LEFT JOIN dim_payment p  ON d.payment_type   = p.payment_type
    LEFT JOIN dim_ratecode r ON d.ratecode_id    = r.ratecode_id
    LEFT JOIN dim_weather w  ON d.pickup_date    = w.date
) TO '{{OUT_FILE}}' (FORMAT PARQUET, COMPRESSION ZSTD);
