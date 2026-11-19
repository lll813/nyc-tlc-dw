# 指标口径字典

> 原则：每个指标写清「分子/分母/过滤条件/时间口径/数据源」。面试时口径说不清，会被认为只是"跑过 SQL"。

## 1. 通用口径

| 项 | 定义 |
|---|---|
| 时间口径 | `pickup_ts`（上车时间），本地时区 America/New_York；TLC 原始时间已是本地时间 |
| 行程粒度 | 一行 = 一次黄色出租车行程（`vendor_id + pickup_ts + dropoff_ts + pu/do zone + total_amount + distance` 去重后） |
| 收入 | `total_amount`（含车费/附加费/小费/过路费/拥堵费；不含退款负数单） |
| 有效行程 | 时长 1~240 分钟、里程 0~200 英里、金额非负、zone 1~265、支付方式 0~6 |
| 机场 | 上车 zone ∈ {1 EWR, 132 JFK, 138 LaGuardia} |

## 2. 核心指标

| 指标 | 公式 | 说明 |
|---|---|---|
| `trips` | `count(*)` | 有效行程数 |
| `revenue` | `sum(total_amount)` | 收入（美元） |
| `avg_fare` | `revenue / trips` | 客单价 |
| `avg_miles` | `avg(trip_distance)` | 平均里程 |
| `avg_duration_min` | `avg(duration_min)` | 平均时长（分钟） |
| `avg_speed_mph` | `avg(least(trip_distance / (duration_min/60), 120))` | 平均速度，封顶 120 mph 过滤 GPS 异常 |
| `airport_share` | `sum(is_airport_pickup) / trips` | 机场单占比 |
| `card_share` | `sum(payment_type=1) / trips` | 信用卡支付占比 |
| `card_tip_rate` | `sum(tip where payment_type=1) / sum(fare where payment_type=1)` | 信用卡小费率；现金小费不可观测，不能算 |
| `active_zones` | `count(distinct pu_location_id)` | 当日有单的上车 zone 数 |
| `rainy_trips` / `snowy_trips` | `sum(is_rain)` / `sum(is_snow)` | 天气关联后的雨/雪天行程数（按日关联，非逐小时） |

## 3. 衍生指标

| 指标 | 公式 | 用途 |
|---|---|---|
| `ma7` | `avg(trips) over (order by date rows 6 preceding)` | 7 日移动平均，去掉周内波动 |
| `ma28` | 28 日移动平均 | 月度趋势 |
| `wow_pct` | `(trips - lag(trips,7)) / lag(trips,7)` | 周同比 |
| `zscore` | `(trips - mean(trips)) / stddev_pop(trips)` | 异常日检测；`abs(z) >= 2.5` 标记 |
| `trip_share` | `trips / sum(trips) over (partition by month)` | 支付方式/区域结构占比 |
| `revenue_diff` | `total_amount - (fare+extra+mta+tip+tolls+improvement+congestion+airport+cbd)` | 分项对账差额，仅观测 |

## 4. 清洗规则（DWD）

| # | 规则 | 处理 |
|---|---|---|
| 1 | `dropoff_ts > pickup_ts` | 不满足则剔除 |
| 2 | 时长 1~240 分钟 | 剔除 |
| 3 | 里程 0~200 英里 | 剔除 |
| 4 | `fare_amount` 0~1000，`total_amount` 0~2000 | 剔除（含退款负数单） |
| 5 | `tip_amount` 0~500，`tolls_amount` 0~200 | 剔除 |
| 6 | `pu_location_id`/`do_location_id` 1~265 | 剔除 |
| 7 | `payment_type` 0~6 | 剔除 |
| 8 | `ratecode_id` NULL 或 0~6/99 | 剔除 |
| 9 | `passenger_count` NULL 或 0~8 | 剔除 |
| 10 | 自然键去重（月分区内） | 保留 `source_file, pickup_ts` 排序第一条 |

## 5. 已知数据问题（必须能解释）

1. **Vendor 记账口径不一致**：Vendor 1 的 `total_amount` 与分项之和平均差约 -$2.5（拥堵费是否计入不同），Vendor 2 约 +$2.5；
   因此分项对账通过率只有约 68%，本项目把该规则标为 WARN，收入统一用 `total_amount`。
2. **payment_type=0**：约 15% 的 2025-01 记录为 0（Unknown），不能直接丢弃；ADS 中保留为 Unknown。
3. **跨月时间戳**：月文件里存在上月/下月甚至 2001/2026 的时间戳（共 147 条），ODS 只保留 2023-01-01~2025-12-31，
   其余落 `data/ods/_rejected/`，可追溯。
4. **0 里程/超长行程**：保留 0 里程（可能是取消/计价异常），但里程 >200 或时长 >240 分钟剔除。
5. **机场 zone**：EWR 属于 New Jersey，但计入 NYC 出租车机场单；口径需在文档中注明。
