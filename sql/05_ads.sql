-- ADS 层：面向业务/面试追问的指标集市
-- 每个表都能直接对应一个业务问题，避免"为了分层而分层"

-- 1) 每日核心 KPI：规模、收入、效率、结构
CREATE OR REPLACE TABLE ads_daily_kpi AS
SELECT
    pickup_date                                                     AS date,
    count(*)                                                        AS trips,
    round(sum(total_amount), 2)                                     AS revenue,
    round(avg(total_amount), 2)                                     AS avg_fare,
    round(sum(trip_distance), 2)                                    AS total_miles,
    round(avg(trip_distance), 3)                                    AS avg_miles,
    round(avg(duration_min), 2)                                     AS avg_duration_min,
    round(avg(speed_mph), 2)                                        AS avg_speed_mph,
    round(sum(CASE WHEN is_airport_pickup THEN 1 ELSE 0 END)::DOUBLE / count(*), 4) AS airport_share,
    round(sum(CASE WHEN payment_type = 1 THEN 1 ELSE 0 END)::DOUBLE / count(*), 4)  AS card_share,
    round(sum(CASE WHEN payment_type = 1 THEN tip_amount ELSE 0 END)::DOUBLE
          / nullif(sum(CASE WHEN payment_type = 1 THEN fare_amount ELSE 0 END), 0), 4) AS card_tip_rate,
    count(DISTINCT pu_location_id)                                  AS active_zones,
    sum(CASE WHEN is_rain THEN 1 ELSE 0 END)                        AS rainy_trips,
    sum(CASE WHEN is_snow THEN 1 ELSE 0 END)                        AS snowy_trips
FROM dwd_trip_detail
GROUP BY 1;

-- 2) 月度 KPI：趋势与同比
CREATE OR REPLACE TABLE ads_monthly_kpi AS
SELECT
    strftime(date, '%Y-%m')                         AS year_month,
    min(date)                                       AS month_start,
    sum(trips)                                      AS trips,
    round(sum(revenue), 2)                          AS revenue,
    round(sum(revenue) / nullif(sum(trips), 0), 2)  AS avg_fare,
    round(avg(avg_speed_mph), 2)                    AS avg_speed_mph,
    round(avg(airport_share), 4)                    AS airport_share,
    round(avg(card_tip_rate), 4)                    AS card_tip_rate,
    count(*)                                        AS active_days
FROM ads_daily_kpi
GROUP BY 1
ORDER BY 1;

-- 3) 区域收入榜：每月 Top 20
CREATE OR REPLACE TABLE ads_zone_rank AS
SELECT * EXCLUDE (rn)
FROM (
    SELECT
        strftime(pickup_date, '%Y-%m')             AS year_month,
        pu_location_id,
        pu_zone,
        pu_borough,
        sum(trips)                                  AS trips,
        round(sum(revenue), 2)                      AS revenue,
        round(sum(revenue) / nullif(sum(trips), 0), 2) AS avg_fare,
        round(avg(avg_speed_mph), 2)                AS avg_speed_mph,
        row_number() OVER (PARTITION BY strftime(pickup_date, '%Y-%m') ORDER BY sum(revenue) DESC) AS rn
    FROM dws_zone_day
    GROUP BY 1, 2, 3, 4
)
WHERE rn <= 20;

-- 4) 小时 × 星期热力图：需求的时间分布
CREATE OR REPLACE TABLE ads_hourly_heatmap AS
SELECT
    dayofweek(pickup_date)                                  AS weekday,  -- 0=Sunday
    pickup_hour,
    round(sum(trips)::DOUBLE / count(DISTINCT pickup_date), 1) AS avg_trips_per_day,
    round(sum(revenue)::DOUBLE / count(DISTINCT pickup_date), 2) AS avg_revenue_per_day,
    round(avg(avg_speed_mph), 2)                            AS avg_speed_mph,
    round(sum(airport_trips)::DOUBLE / nullif(sum(trips), 0), 4) AS airport_share
FROM dws_hour_day
GROUP BY 1, 2;

-- 5) 机场需求：JFK / LGA / EWR 的日度表现
CREATE OR REPLACE TABLE ads_airport_daily AS
SELECT
    pickup_date                                     AS date,
    pu_location_id,
    pu_zone,
    sum(trips)                                      AS trips,
    round(sum(revenue), 2)                          AS revenue,
    round(sum(revenue) / nullif(sum(trips), 0), 2)  AS avg_fare,
    round(sum(airport_trips)::DOUBLE / nullif(sum(trips), 0), 4) AS airport_share
FROM dws_zone_day
WHERE pu_location_id IN (1, 132, 138)
GROUP BY 1, 2, 3;

-- 6) 小费榜：只统计信用卡（现金小费无法观测），且样本 >= 1000 单
CREATE OR REPLACE TABLE ads_tip_zone AS
SELECT
    pu_location_id,
    pu_zone,
    pu_borough,
    sum(card_trips)                                 AS card_trips,
    round(sum(card_tip), 2)                         AS card_tip,
    round(sum(card_tip) / nullif(sum(card_fare), 0), 4) AS card_tip_rate,
    round(sum(card_tip) / nullif(sum(card_trips), 0), 2) AS avg_tip_per_trip
FROM dws_zone_day
GROUP BY 1, 2, 3
HAVING sum(card_trips) >= 1000
ORDER BY card_tip_rate DESC;

-- 7) 支付结构：月度各支付方式占比
CREATE OR REPLACE TABLE ads_payment_mix AS
SELECT
    strftime(pickup_date, '%Y-%m')                  AS year_month,
    payment_type,
    payment_name,
    sum(trips)                                      AS trips,
    round(sum(revenue), 2)                          AS revenue,
    round(sum(trips)::DOUBLE / sum(sum(trips)) OVER (PARTITION BY strftime(pickup_date, '%Y-%m')), 4) AS trip_share
FROM dws_payment_day
GROUP BY 1, 2, 3;

-- 8) 行政区 × 小时：运力/拥堵画像
CREATE OR REPLACE TABLE ads_borough_hour AS
SELECT
    COALESCE(pu_borough, 'Unknown')                 AS borough,
    pickup_hour,
    count(*)                                        AS trips,
    round(sum(total_amount), 2)                     AS revenue,
    round(avg(speed_mph), 2)                        AS avg_speed_mph,
    round(sum(CASE WHEN is_airport_pickup THEN 1 ELSE 0 END)::DOUBLE / count(*), 4) AS airport_share
FROM dwd_trip_detail
GROUP BY 1, 2;

-- 9) 需求预测特征：7/28 日移动平均、周同比、z-score
CREATE OR REPLACE TABLE ads_demand_forecast AS
WITH base AS (
    SELECT
        date,
        trips,
        avg(trips) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)  AS ma7,
        avg(trips) OVER (ORDER BY date ROWS BETWEEN 27 PRECEDING AND CURRENT ROW) AS ma28,
        lag(trips, 7) OVER (ORDER BY date)                                         AS trips_lag7,
        avg(trips) OVER ()                                                         AS mean_trips,
        stddev_pop(trips) OVER ()                                                  AS std_trips
    FROM ads_daily_kpi
)
SELECT
    date,
    trips,
    round(ma7, 1)                                   AS ma7,
    round(ma28, 1)                                  AS ma28,
    round((trips - trips_lag7)::DOUBLE / nullif(trips_lag7, 0), 4) AS wow_pct,
    round((trips - mean_trips) / nullif(std_trips, 0), 3)          AS zscore,
    CASE WHEN abs((trips - mean_trips) / nullif(std_trips, 0)) >= 2.5 THEN TRUE ELSE FALSE END AS is_anomaly
FROM base;

-- 10) 一屏 KPI：给 dashboard / API 用
CREATE OR REPLACE TABLE ads_kpi_summary AS
SELECT 'total_trips' AS metric, CAST(sum(trips) AS VARCHAR) AS value FROM ads_daily_kpi
UNION ALL SELECT 'total_revenue', CAST(round(sum(revenue), 0) AS VARCHAR) FROM ads_daily_kpi
UNION ALL SELECT 'avg_fare', CAST(round(avg(avg_fare), 2) AS VARCHAR) FROM ads_daily_kpi
UNION ALL SELECT 'avg_speed_mph', CAST(round(avg(avg_speed_mph), 2) AS VARCHAR) FROM ads_daily_kpi
UNION ALL SELECT 'airport_share', CAST(round(avg(airport_share), 4) AS VARCHAR) FROM ads_daily_kpi
UNION ALL SELECT 'card_tip_rate', CAST(round(avg(card_tip_rate), 4) AS VARCHAR) FROM ads_daily_kpi
UNION ALL SELECT 'active_zones', CAST(max(active_zones) AS VARCHAR) FROM ads_daily_kpi
UNION ALL SELECT 'days', CAST(count(*) AS VARCHAR) FROM ads_daily_kpi;

COPY ads_daily_kpi       TO '{{ADS_DIR}}/ads_daily_kpi.parquet'       (FORMAT PARQUET, COMPRESSION ZSTD);
COPY ads_monthly_kpi     TO '{{ADS_DIR}}/ads_monthly_kpi.parquet'     (FORMAT PARQUET, COMPRESSION ZSTD);
COPY ads_zone_rank       TO '{{ADS_DIR}}/ads_zone_rank.parquet'       (FORMAT PARQUET, COMPRESSION ZSTD);
COPY ads_hourly_heatmap  TO '{{ADS_DIR}}/ads_hourly_heatmap.parquet'  (FORMAT PARQUET, COMPRESSION ZSTD);
COPY ads_airport_daily   TO '{{ADS_DIR}}/ads_airport_daily.parquet'   (FORMAT PARQUET, COMPRESSION ZSTD);
COPY ads_tip_zone        TO '{{ADS_DIR}}/ads_tip_zone.parquet'        (FORMAT PARQUET, COMPRESSION ZSTD);
COPY ads_payment_mix     TO '{{ADS_DIR}}/ads_payment_mix.parquet'     (FORMAT PARQUET, COMPRESSION ZSTD);
COPY ads_borough_hour    TO '{{ADS_DIR}}/ads_borough_hour.parquet'    (FORMAT PARQUET, COMPRESSION ZSTD);
COPY ads_demand_forecast TO '{{ADS_DIR}}/ads_demand_forecast.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY ads_kpi_summary     TO '{{ADS_DIR}}/ads_kpi_summary.parquet'     (FORMAT PARQUET, COMPRESSION ZSTD);
