-- 维度层：zone / payment / ratecode / vendor / date / weather
-- DuckDB 方言；字段命名与 DWD 保持一致

CREATE OR REPLACE TABLE dim_zone AS
SELECT
    CAST(LocationID AS INTEGER) AS location_id,
    TRIM(Borough)               AS borough,
    TRIM(Zone)                  AS zone,
    TRIM(service_zone)          AS service_zone
FROM read_csv_auto('{{ZONE_CSV}}', header = true);

CREATE OR REPLACE TABLE dim_payment AS
SELECT * FROM (VALUES
    (0, 'Unknown'),
    (1, 'Credit card'),
    (2, 'Cash'),
    (3, 'No charge'),
    (4, 'Dispute'),
    (5, 'Unknown'),
    (6, 'Voided trip')
) AS t(payment_type, payment_name);

CREATE OR REPLACE TABLE dim_ratecode AS
SELECT * FROM (VALUES
    (1, 'Standard rate'),
    (2, 'JFK'),
    (3, 'Newark'),
    (4, 'Nassau/Westchester'),
    (5, 'Negotiated fare'),
    (6, 'Group ride'),
    (99, 'Unknown')
) AS t(ratecode_id, ratecode_name);

CREATE OR REPLACE TABLE dim_vendor AS
SELECT * FROM (VALUES
    (1, 'Creative Mobile Technologies'),
    (2, 'VeriFone Inc.'),
    (6, 'Other / Myle')
) AS t(vendor_id, vendor_name);

CREATE OR REPLACE TABLE dim_date AS
SELECT
    CAST(d AS DATE)                                      AS date,
    CAST(year(d) AS SMALLINT)                            AS year,
    CAST(month(d) AS TINYINT)                            AS month,
    CAST(day(d) AS TINYINT)                              AS day,
    CAST(dayofweek(d) AS TINYINT)                        AS weekday,   -- 0=Sunday
    CASE WHEN dayofweek(d) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend,
    CAST(dayofyear(d) AS SMALLINT)                       AS day_of_year,
    CAST(week(d) AS TINYINT)                             AS week_of_year,
    strftime(d, '%Y-%m')                                 AS year_month
FROM generate_series(DATE '{{START_DATE}}', DATE '{{END_DATE}}', INTERVAL 1 DAY) AS t(d);

CREATE OR REPLACE TABLE dim_weather AS
SELECT
    CAST(date AS DATE)             AS date,
    CAST(temp_mean_c AS DOUBLE)    AS temp_mean_c,
    CAST(precip_mm AS DOUBLE)      AS precip_mm,
    CAST(snow_mm AS DOUBLE)        AS snow_mm,
    CAST(wind_max_kmh AS DOUBLE)   AS wind_max_kmh,
    CASE WHEN CAST(precip_mm AS DOUBLE) >= 1.0 THEN TRUE ELSE FALSE END AS is_rain,
    CASE WHEN CAST(snow_mm AS DOUBLE)   >= 0.1 THEN TRUE ELSE FALSE END AS is_snow
FROM read_csv_auto('{{WEATHER_CSV}}', header = true);

COPY dim_zone     TO '{{DIM_DIR}}/dim_zone.parquet'     (FORMAT PARQUET, COMPRESSION ZSTD);
COPY dim_payment  TO '{{DIM_DIR}}/dim_payment.parquet'  (FORMAT PARQUET, COMPRESSION ZSTD);
COPY dim_ratecode TO '{{DIM_DIR}}/dim_ratecode.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
COPY dim_vendor   TO '{{DIM_DIR}}/dim_vendor.parquet'   (FORMAT PARQUET, COMPRESSION ZSTD);
COPY dim_date     TO '{{DIM_DIR}}/dim_date.parquet'     (FORMAT PARQUET, COMPRESSION ZSTD);
COPY dim_weather  TO '{{DIM_DIR}}/dim_weather.parquet'  (FORMAT PARQUET, COMPRESSION ZSTD);
