-- DWS 层：轻度汇总，按「日期 × 维度」预聚合，供 ADS 和 BI 复用
-- 所有指标都能从 dwd_trip_detail 重新计算，DWS 只做空间换时间

CREATE OR REPLACE TABLE dws_zone_day AS
SELECT
    pickup_date,
    pu_location_id,
    pu_borough,
    pu_zone,
    pu_service_zone,
    count(*)                                                     AS trips,
    count(DISTINCT vendor_id)                                    AS active_vendors,
    round(sum(total_amount), 2)                                  AS revenue,
    round(sum(fare_amount), 2)                                   AS fare_revenue,
    round(sum(tip_amount), 2)                                    AS tip_amount,
    round(sum(trip_distance), 2)                                 AS total_miles,
    round(sum(duration_min), 2)                                  AS total_minutes,
    round(avg(trip_distance), 3)                                 AS avg_miles,
    round(avg(duration_min), 2)                                  AS avg_duration_min,
    round(avg(speed_mph), 2)                                     AS avg_speed_mph,
    sum(CASE WHEN is_airport_pickup THEN 1 ELSE 0 END)           AS airport_trips,
    sum(CASE WHEN payment_type = 1 THEN 1 ELSE 0 END)            AS card_trips,
    round(sum(CASE WHEN payment_type = 1 THEN fare_amount ELSE 0 END), 2) AS card_fare,
    round(sum(CASE WHEN payment_type = 1 THEN tip_amount ELSE 0 END), 2) AS card_tip,
    round(avg(CASE WHEN payment_type = 1 AND fare_amount > 0 THEN tip_rate END), 4) AS card_tip_rate
FROM dwd_trip_detail
GROUP BY 1, 2, 3, 4, 5;

CREATE OR REPLACE TABLE dws_hour_day AS
SELECT
    pickup_date,
    pickup_hour,
    is_weekend,
    count(*)                                                     AS trips,
    round(sum(total_amount), 2)                                  AS revenue,
    round(avg(speed_mph), 2)                                     AS avg_speed_mph,
    sum(CASE WHEN is_airport_pickup THEN 1 ELSE 0 END)           AS airport_trips,
    round(avg(CASE WHEN payment_type = 1 AND fare_amount > 0 THEN tip_rate END), 4) AS card_tip_rate
FROM dwd_trip_detail
GROUP BY 1, 2, 3;

CREATE OR REPLACE TABLE dws_payment_day AS
SELECT
    pickup_date,
    payment_type,
    payment_name,
    count(*)                                                     AS trips,
    round(sum(total_amount), 2)                                  AS revenue,
    round(sum(tip_amount), 2)                                    AS tip_amount,
    round(avg(total_amount), 2)                                  AS avg_fare
FROM dwd_trip_detail
GROUP BY 1, 2, 3;

CREATE OR REPLACE TABLE dws_borough_day AS
SELECT
    pickup_date,
    COALESCE(pu_borough, 'Unknown')                              AS borough,
    count(*)                                                     AS trips,
    round(sum(total_amount), 2)                                  AS revenue,
    round(avg(speed_mph), 2)                                     AS avg_speed_mph,
    sum(CASE WHEN is_airport_pickup THEN 1 ELSE 0 END)           AS airport_trips,
    round(avg(trip_distance), 3)                                 AS avg_miles
FROM dwd_trip_detail
GROUP BY 1, 2;

CREATE OR REPLACE TABLE dws_zone_hour AS
SELECT
    pu_location_id,
    pu_zone,
    pu_borough,
    pickup_weekday,
    pickup_hour,
    count(*)                                                     AS trips,
    round(sum(total_amount), 2)                                  AS revenue,
    round(avg(speed_mph), 2)                                     AS avg_speed_mph,
    sum(CASE WHEN is_airport_pickup THEN 1 ELSE 0 END)           AS airport_trips
FROM dwd_trip_detail
GROUP BY 1, 2, 3, 4, 5;

CREATE OR REPLACE TABLE dws_weather_day AS
SELECT
    d.pickup_date,
    w.temp_mean_c,
    w.precip_mm,
    w.snow_mm,
    w.wind_max_kmh,
    w.is_rain,
    w.is_snow,
    count(*)                                                     AS trips,
    round(sum(d.total_amount), 2)                                AS revenue,
    round(avg(d.speed_mph), 2)                                   AS avg_speed_mph,
    round(sum(CASE WHEN d.is_airport_pickup THEN 1 ELSE 0 END)::DOUBLE / count(*), 4) AS airport_share
FROM dwd_trip_detail d
LEFT JOIN dim_weather w ON d.pickup_date = w.date
GROUP BY 1, 2, 3, 4, 5, 6, 7;

COPY dws_zone_day     TO '{{DWS_DIR}}/dws_zone_day.parquet'     (FORMAT PARQUET, COMPRESSION ZSTD);
COPY dws_hour_day     TO '{{DWS_DIR}}/dws_hour_day.parquet'     (FORMAT PARQUET, COMPRESSION ZSTD);
COPY dws_payment_day  TO '{{DWS_DIR}}/dws_payment_day.parquet'  (FORMAT PARQUET, COMPRESSION ZSTD);
COPY dws_borough_day  TO '{{DWS_DIR}}/dws_borough_day.parquet'  (FORMAT PARQUET, COMPRESSION ZSTD);
COPY dws_zone_hour    TO '{{DWS_DIR}}/dws_zone_hour.parquet'    (FORMAT PARQUET, COMPRESSION ZSTD);
COPY dws_weather_day  TO '{{DWS_DIR}}/dws_weather_day.parquet'  (FORMAT PARQUET, COMPRESSION ZSTD);
