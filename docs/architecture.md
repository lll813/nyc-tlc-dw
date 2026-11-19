# 架构与实现细节

## 1. 总体架构

```mermaid
flowchart LR
    A[NYC TLC 官方 Parquet<br/>36 个月 / 2.0 GB] --> B[ODS<br/>按 pickup_year/month 分区<br/>贴源 + 来源文件]
    A2[Taxi Zone 维表] --> D[维度层<br/>zone/payment/rate/vendor/date]
    A3[Open-Meteo 天气] --> D
    B --> C[DWD<br/>清洗/去重/维表补全/天气关联<br/>122M 行]
    D --> C
    C --> E[DWS<br/>zone_day/hour_day/payment_day<br/>borough_day/zone_hour/weather_day]
    E --> F[ADS<br/>daily/monthly KPI、区域榜、热力图<br/>机场、小费、支付、预测特征]
    F --> G[DuckDB 查询 + Parquet 湖]
    G --> H[FastAPI / HTML Dashboard]
    C -. Spark 4.3 对照 .-> I[Spark SQL<br/>1 个月样本 + 加盐实验]
    F -. 可选 .-> J[ClickHouse / Doris]
    C -. 实时设计 .-> K[Flink SQL + Kafka]
```

## 2. 分层与粒度

| 层 | 表/目录 | 一行代表什么 | 行数（实测） | 存储 |
|---|---|---|---|---|
| ODS | `data/ods/trips/pickup_year=*/pickup_month=*` | 原始行程（仅时间范围过滤） | 128,202,401 | Parquet + zstd，36 分区 |
| DWD | `data/dwd/trip_detail/...` | 清洗后的行程明细 | 122,349,675 | Parquet + zstd，36 分区，约 4.3 GB |
| DWS | `dws_zone_day` | 日期 × 上车 zone | 251,873 | DuckDB 表 + Parquet 副本 |
| DWS | `dws_hour_day` | 日期 × 小时 | 26,301 | 同上 |
| DWS | `dws_payment_day` | 日期 × 支付方式 | 5,480 | 同上 |
| DWS | `dws_borough_day` | 日期 × 行政区 | 8,469 | 同上 |
| DWS | `dws_zone_hour` | zone × 星期 × 小时 | 42,074 | 同上 |
| DWS | `dws_weather_day` | 日期 × 天气 | 1,096 | 同上 |
| ADS | 10 张表 | 业务指标/特征 | 几百 ~ 3 万 | DuckDB 表 + Parquet 副本 |

## 3. 分区、增量、幂等

### 分区

- ODS/DWD 都按 `pickup_year=YYYY/pickup_month=M/` 组织，查询带 `WHERE pickup_year=... AND pickup_month=...` 时 DuckDB/Spark 只扫对应目录。
- 文件名固定 `data.parquet`，避免每次跑产生新小文件。
- 生产环境可细到 `dt=YYYY-MM-DD/hour=HH`；本项目按月是因为 TLC 官方就是月文件，且 36 个月已足够讲清分区裁剪。

### 增量

- 全量初始化：`00_download.py` 拉 36 个月。
- 日常增量：只下载新月份 → 只重写该月分区 → 重跑 DWS/ADS（或按天增量）。
- 生产化：对象存储 + 水位线表 `etl_watermark(table_name, max_dt)`；DWD 用 `MERGE INTO`/`INSERT OVERWRITE PARTITION`。

### 幂等

- 每个分区 `COPY ... TO` 前由脚本清理/覆盖（`OVERWRITE_OR_IGNORE`），同一天重跑结果一致。
- 去重键：`hash(vendor_id, pickup_ts, dropoff_ts, pu_location_id, do_location_id, total_amount, trip_distance)`。
- `run_all.py` 写 `output/run_manifest.json`，记录每步耗时/返回码，失败可定位。
- 实测：同一月连续跑两次，DWD 行数与 `sum(total_amount)` 一致（见 `docs/interview.md`）。

## 4. 数据质量

18 条规则分三层：

| 层 | 规则示例 | 失败动作 |
|---|---|---|
| ODS | 异常时间戳占比 < 2%、36 个分区齐全 | FAIL 阻断 |
| DWD | 时间顺序、时长 1~240 min、里程 0~200、金额非负、zone 1~265、维表覆盖率 | FAIL 阻断 |
| DWD | 分项金额 ≈ total_amount | WARN（TLC Vendor 口径差异，收入以 total 为准） |
| DWD | 自然键重复率 < 0.5% | FAIL 阻断 |
| ADS | 1096 天 / 36 个月齐全、ADS 行数与收入对账 | FAIL 阻断 |

输出：

- `output/quality_report.json`：机器可读，Airflow 质量门禁读取 `overall != FAIL`。
- DuckDB `dq_result` 表：看板/接口查询。
- `output/dashboard.html`：人工 review。

## 5. 性能设计

- **列裁剪**：Parquet 列存，聚合只读需要的列；DWD 宽表 40+ 列，但 ADS 聚合只读 5~10 列。
- **分区裁剪**：单月查询只扫 1/36 数据。
- **去重策略**：不做 1.2 亿行全局 `row_number()`（实测 20 分钟只写 20%），改为**按月循环**，每月 350 万行窗口排序在内存完成，总耗时约 5 分钟。
- **内存**：DuckDB `memory_limit=3GB`、`threads=4`、`temp_directory=db/tmp`、`preserve_insertion_order=false`。
- **倾斜**：TLC 的热点 zone（JFK/LGA/Midtown）占比高；Spark 实验用 `pmod(hash(pickup_ts), 8)` 加盐两阶段聚合，
  DuckDB 单机无 shuffle，加盐不一定更快，报告中如实记录。
- **小文件**：每月一个 Parquet 文件；生产按天/小时落盘后需 `compact`（DuckDB `COPY` 重写或 Spark `repartition`）。

## 6. 技术栈映射

| 组件 | 本项目实际使用 | 生产替代 |
|---|---|---|
| 计算 | DuckDB 2.0（单机 MPP） | Spark SQL / Hive / Trino |
| 存储 | Parquet + zstd，Hive 风格分区 | HDFS / S3 / OSS + Hive Metastore / Iceberg |
| 调度 | `run_all.py` + Airflow DAG | Airflow / DolphinScheduler |
| 质量 | 自研 18 条规则 + JSON | Great Expectations / dbt tests / DataHub |
| OLAP | DuckDB 查询 + Parquet | Doris / ClickHouse / StarRocks |
| 实时 | Flink SQL 设计（Kafka source） | Flink + Kafka + Paimon/Iceberg |
| 服务 | FastAPI + HTML Dashboard | Superset / FineBI / 自研 API |
| 元数据/血缘 | `source_file` + 指标字典 | DataHub / Atlas |

## 7. 目录

```text
nyc_tlc_dw/
├─ run_all.py                 # 一键编排
├─ config.py                  # 路径/资源/阈值
├─ scripts/
│  ├─ 00_download.py          # 36 个月 + zone + weather
│  ├─ 01_build_dim.py         # 6 张维表
│  ├─ 02_build_ods.py         # ODS 分区
│  ├─ 03_build_dwd.py         # DWD 清洗/去重/补全（按月）
│  ├─ 04_build_dws.py         # DWS 预聚合
│  ├─ 05_build_ads.py         # ADS 指标
│  ├─ 06_quality.py           # 18 条质量规则
│  ├─ 07_benchmark.py         # 性能/倾斜实验
│  ├─ 08_report.py            # HTML 看板
│  └─ serve.py                # FastAPI
├─ sql/                       # 01_dim ~ 05_ads
├─ spark/                     # Spark 4.3 对照实验
├─ airflow/                   # DAG
├─ flink/                     # Flink SQL
├─ olap/                      # ClickHouse/Doris DDL
├─ data/                      # raw/ods/dwd/dws/ads/dim
├─ db/nyc_tlc.duckdb          # 本地数仓
└─ output/                    # 质量/性能/看板/运行清单
```
