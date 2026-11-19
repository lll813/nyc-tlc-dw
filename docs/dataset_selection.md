# 数据集选型：为什么是 NYC TLC，而不是第二个淘宝/评论/日志集

> 结论：在「16 GB 内存 + 约 44 GB C 盘可用 + Windows + 无 Docker/Hadoop 集群」这台机器上，
> **NYC TLC 黄色出租车 2023–2025（36 个月，1.28 亿行，2.0 GB Parquet）** 是除淘宝 UserBehavior 之外
> 最适合做「数据开发岗作品集」的数据集。它原生 Parquet、官方免登录、有维表、有真实脏数据、
> 能在一台笔记本上把 ODS→DWD→DWS→ADS 全链路真正跑完，而不是只写 SQL 不执行。

---

## 1. 岗位要求提炼（来自桌面 `JD/` 的 17 条有效岗位）

| 能力 | 出现频次 | 面试追问方式 | 本项目怎么覆盖 |
|---|---|---|---|
| SQL（多表/聚合/窗口/优化） | 17/17 | 留存、漏斗、连续活跃、TopN、执行计划 | 窗口函数 `lag`/移动平均/`row_number`、10 张 ADS 表、性能实验 |
| 数仓分层 ODS/DWD/DWS/ADS + 维度建模 | 13/17 | 为什么分层？粒度是什么？ | 四层 + 6 张维表 + 指标字典 + 行数漏斗 |
| Spark / Spark SQL | 10/17 | 数据量多大？shuffle 怎么调？ | Spark 4.3 真跑 1 个月样本 + broadcast join + 加盐对照 |
| Hive / Hadoop | 9/17 | 分区、外部表、小文件 | Hive 风格 `pickup_year=/pickup_month=` 分区 + Hive DDL |
| 增量/分区/幂等/调度 | 9/17 | 重跑为什么不变？ | 月分区覆盖写 + 幂等校验 + Airflow DAG |
| 数据质量/治理/血缘 | 7/17 | 质量规则怎么落？ | 18 条规则 PASS/WARN/FAIL + `source_file` 血缘 + 质量门禁 |
| Flink/实时 | 7/17 | 为什么用 Flink？watermark？ | Flink SQL 1h 滚动窗口 + Kafka source（可运行文件） |
| 数据倾斜/性能 | 5/17 | 怎么发现？怎么解？ | Top zone 占比 + Spark 加盐两阶段 + CSV/Parquet/分区裁剪实测 |
| Python | 11/17 | 脚本/服务 | 全链路 Python + FastAPI |
| Doris/ClickHouse/StarRocks | 5/17 | 选型 | ClickHouse/Doris DDL + 选型话术 |
| Airflow/DolphinScheduler | 4/17 | DAG/重试/回填 | Airflow DAG（任务拆分/重试/质量门禁） |
| BI | 4/17 | 看板 | 单文件 HTML Dashboard（离线可看） |

> 17 条里 13 条是离线数仓/大数据开发，核心不是"用过多少组件"，而是**能不能把一条链路做完整、讲清楚**。
> 因此数据集必须满足：够大、有分区、有维表、有脏数据、下载不折腾、本机能跑完。

---

## 2. 候选对比（只列真正能打的）

| 数据集 | 体量 | 结构 | 本机可行性 | 与 JD 匹配 | 结论 |
|---|---|---|---|---|---|
| **NYC TLC 黄色出租车 2023–2025** | **1.28 亿行 / 2.0 GB Parquet** | 1 事实表 + zone 维表 + 天气 | **原生 Parquet，36 个月，一条命令下载，DuckDB/Spark 都能跑** | 分区/增量/倾斜/质量/OLAP 全中 | **主选** |
| GH Archive（1 个月） | 约 720 个 JSON.gz，十 GB 级 | 嵌套 JSON 事件流 | 16 GB 内存解析 JSON 压力大，下载文件多 | 实时/Flink/湖仓最强 | 备选，适合做第二项目 |
| Amazon Reviews 2023（Electronics） | 4390 万评论，压缩后数 GB | JSONL + 嵌套 meta | 文本大、解压 10 GB+，16 GB 内存吃紧 | 半结构化/入湖 | 不选 |
| BTS 航班准点数据 | 2 亿+ 行，数十 GB | 月度 CSV，多维表 | 下载走表单，CSV 解析慢，磁盘压力大 | 事实表设计经典 | 不选 |
| Citi Bike | 1 亿+ 行，约 30 GB | 月度 zip | 需要解压/清洗，体积偏大 | 出行域，和 TLC 重叠 | 不选 |
| TPC-DS SF=10 | 约 10 GB | 24 张表，合成数据 | 生成器要编译/WSL，磁盘紧 | 建模/99 查询 | 只做补充，不做主项目 |
| Olist | 10 万订单 / 120 MB | 9 张 CSV | 太轻 | 只能练星型模型 | 不选 |
| 淘宝 UserBehavior | 1 亿行 / 3.4 GB | 单事实表 | 已做过，重复 | 电商故事好 | **排除（用户要求换）** |

### 为什么不是 GH Archive / Amazon Reviews？

- **内存**：本机 16 GB，实测空闲只有 3~4 GB。TLC 的 Parquet 列裁剪 + 分区裁剪让 1.2 亿行聚合能在 3 GB 上限内完成；
  GH Archive 的 JSON 解析和 Amazon Reviews 的文本字段会显著抬高内存与磁盘。
- **下载/复现**：TLC 是 36 个固定 URL，断点续传 2 分钟下完；GH Archive 一个月 720 个文件，Amazon Reviews 单类目压缩包数 GB，
  对"作品集要别人能复现"不友好。
- **岗位匹配**：17 条 JD 里 13 条是离线数仓，TLC 的"月分区 + 事实/维表 + 增量 + 倾斜"正好是同一套能力；
  实时/Flink 只需要一个可讲清楚的 Flink SQL 设计，不必为了实时而牺牲整条链路的可运行性。

---

## 3. 数据集详情

- 官方页面：<https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page>
- 直链规律：`https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_YYYY-MM.parquet`
- Zone 维表：`https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv`
- 天气：<https://archive-api.open-meteo.com/v1/archive>（免费、无需 key，本项目取 NYC 日度温度/降水/降雪/风速）

| 项 | 值 |
|---|---|
| 时间范围 | 2023-01-01 ~ 2025-12-31（36 个月） |
| 原始文件 | 36 个 Parquet，**2.01 GB** |
| 原始行数 | **128,202,548** |
| 字段 | 19~20 列：时间、地点 ID、里程、车费/小费/过路费/拥堵费、支付方式、乘客数等 |
| 维表 | `taxi_zone_lookup` 265 个 zone（Borough / Zone / service_zone） |
| 外部维表 | Open-Meteo 1096 天天气 |
| 脏数据 | 跨月时间戳、负金额/退款、0 里程、超长行程、缺失乘客数、Vendor 记账口径差异 |
| 许可 | NYC Open Data，公开可用；不二次分发原始文件即可 |

---

## 4. 本机适配（实测）

| 资源 | 现状 | 项目策略 |
|---|---|---|
| CPU | i7-12700H（14 核 20 线程） | DuckDB `threads=4`，避免抢满 |
| 内存 | 16 GB，空闲约 3~4 GB | DuckDB `memory_limit=3GB` + 临时目录落盘；Spark 只跑 1 个月样本 |
| 磁盘 | C 盘约 44 GB 可用 / D 盘约 72 GB | 原始 2.0 GB + ODS 1.9 GB + DWD 约 4 GB + 实验 1 GB，合计 < 10 GB |
| Python | 3.13.2 | DuckDB 2.0 / pandas / matplotlib / FastAPI 均可用 |
| Java | 系统 Java 26，Spark 4.3 要求 17/21 | 项目自带 JDK 21 + Spark 4.3（`tools/`），不污染系统 |
| Docker | 未安装/未运行 | 不依赖 Docker；Flink/ClickHouse 只给可执行 SQL/DDL |

---

## 5. 这个数据集能讲出的"业务故事"

1. **需求**：每天/每小时/每个 zone 有多少单？工作日 vs 周末、机场 vs 市区。
2. **收入**：月度收入、客单价、支付结构、小费率；2025 年拥堵费政策变化。
3. **效率**：平均速度、里程、时长；雨天/雪天对需求与速度的影响。
4. **供需**：Top zone、机场排队、夜间运力；为"调价/派单/司机调度"提供依据。
5. **预测**：7/28 日移动平均、周同比、z-score 异常日，作为需求预测特征。

> 面试时不要只说"我做了个出租车分析"，要说"我把 1.28 亿行行程做成了可增量、可对账、可回补的四层数仓，
> 并用 Spark 验证了倾斜治理"。前者是课程作业，后者是数据开发。

---

## 6. 明确不做什么（避免作品集变味）

- 不做机器学习模型（不是数据开发岗的核心；有需求再基于 `ads_demand_forecast` 加）。
- 不追求把 Flink/Kafka/Doris 真跑起来（本机资源不允许；给可执行 SQL/DDL + 选型说明，面试够用）。
- 不下载 17 年全量（几十 GB，没必要；3 年足够 1.2 亿行）。
- 不把 `total_amount` 的分项差额硬洗成 0（这是真实数据质量问题，应该被记录和解释）。
