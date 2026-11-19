-- Flink SQL 1.18：实时小时级需求聚合（Kafka → 1h 滚动窗口 → Print/ClickHouse）
-- 该文件不依赖本机环境，放到 Flink SQL Client 或 sql-gateway 执行。
-- 生产链路：TLC 行程事件 → Kafka(trips) → Flink 窗口聚合 → ClickHouse/Doris → BI

SET 'execution.runtime-mode' = 'streaming';
SET 'pipeline.name' = 'nyc-tlc-hourly-demand';

CREATE TABLE trip_events (
    trip_id        STRING,
    vendor_id      INT,
    pickup_ts      TIMESTAMP(3),
    dropoff_ts     TIMESTAMP(3),
    pu_location_id INT,
    do_location_id INT,
    trip_distance  DOUBLE,
    total_amount   DOUBLE,
    payment_type   INT,
    event_time     TIMESTAMP(3),
    WATERMARK FOR event_time AS event_time - INTERVAL '10' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'nyc_tlc_trips',
    'properties.bootstrap.servers' = 'kafka:9092',
    'properties.group.id' = 'tlc-hourly-demand',
    'scan.startup.mode' = 'latest-offset',
    'format' = 'json',
    'json.fail-on-missing-field' = 'false',
    'json.ignore-parse-errors' = 'true'
);

CREATE TABLE hourly_demand_sink (
    window_start   TIMESTAMP(3),
    window_end     TIMESTAMP(3),
    pu_location_id INT,
    trips          BIGINT,
    revenue        DOUBLE,
    avg_amount     DOUBLE
) WITH (
    'connector' = 'print'
);

-- 1 小时滚动窗口：按上车 zone 聚合
INSERT INTO hourly_demand_sink
SELECT
    window_start,
    window_end,
    pu_location_id,
    COUNT(*)                         AS trips,
    ROUND(SUM(total_amount), 2)      AS revenue,
    ROUND(AVG(total_amount), 2)      AS avg_amount
FROM TABLE(
    TUMBLE(TABLE trip_events, DESCRIPTOR(event_time), INTERVAL '1' HOUR)
)
GROUP BY window_start, window_end, pu_location_id;

-- 面试可讲：
-- 1) 为什么用事件时间 + watermark：手机/GPS 事件会乱序，处理时间会被"迟到数据"污染；
-- 2) 为什么窗口 1h：TLC 原始是行程粒度，实时看板按小时更新即可，窗口太大失去实时性；
-- 3) 精确一次：Kafka source + 幂等 sink（ClickHouse ReplacingMergeTree / Doris Unique Key）；
-- 4) 倾斜：热点 zone（JFK/LGA）key 很大，Flink 侧可加 local-global 两阶段聚合。
