# 面试问答（按 17 条 JD 的高频追问准备）

> 所有数字都来自本机真实运行结果，可在 `output/*.json` 复核。

## Q1：数据量多大？怎么证明不是玩具数据？

- 原始：36 个官方 Parquet，**128,202,548 行，2.01 GB**，2023-01 ~ 2025-12。
- ODS：128,202,401 行（147 条异常时间戳进 `_rejected`）。
- DWD：**122,349,675 行，4.32 GB**，36 个月分区。
- DWS：`dws_zone_day` 251,873 行、`dws_hour_day` 26,301 行。
- ADS：1,096 天日 KPI、36 个月月 KPI、720 行区域榜、168 行热力图。
- 总收入 **$3,515,258,864**，平均客单价 **$28.73**，机场单占比 **7.89%**，信用卡小费率 **22.05%**。

> 回答时先说"原始/ODS/DWD/ADS 各多少行"，再说"几个分区、多大"，比说"大数据"有说服力。

## Q2：为什么分层？每层粒度是什么？

- ODS：贴源，保留 `source_file` 和 `ingest_ts`，只做时间范围过滤，方便回溯。
- DWD：一行一个有效行程，清洗/去重/补 zone/支付/费率/天气维表，是**唯一事实口径**。
- DWS：按日期 × zone / hour / payment / borough 预聚合，空间换时间，供多个 ADS 复用。
- ADS：面向业务问题（日 KPI、区域榜、热力图、机场、小费、预测特征），每个表对应一个面试追问。

分层不是为了背概念，是为了：① 口径统一（DWD 只洗一次）；② 复用（DWS 被多个 ADS 用）；③ 回溯成本低（哪层错修哪层）。

## Q3：怎么增量？重跑为什么结果不变？

- 增量：TLC 官方按月发布 → 只下载新月份 → 只重写 `pickup_year=YYYY/pickup_month=M` 分区 → 重跑 DWS/ADS。
- 幂等：分区覆盖写 + 自然键去重；`run_all.py` 记录 `run_manifest.json`。
- 实测：2025-12 分区连续跑两次，行数 4,154,358、收入 $130,667,237.45、行级 hash 完全一致；
  文件字节不完全一致是 Parquet 并行写顺序导致，**逻辑幂等**才是生产标准（见 `output/idempotency.json`）。
- 生产化：水位线表 + `INSERT OVERWRITE PARTITION` / `MERGE INTO`；调度失败按分区重跑。

## Q4：数据倾斜怎么发现？怎么解？

- 发现：`GROUP BY pu_location_id` 看 Top1 占比。全量 Top1 是 zone 237（Upper East Side South），占 **4.63%**；
  JFK（132）5,616,827 单、LaGuardia（138）3,759,855 单，机场 zone 明显高于普通 zone。
- DuckDB 单机：普通两列 group by 0.555s，加盐两阶段 1.534s——**单机无 shuffle，加盐反而更慢**，如实记录。
- Spark 4.3（local[2]，2023-01 样本 3,009,745 行）：普通 group by **1.638s**，8 桶加盐两阶段 **0.845s**，
  **提升 48.4%**，两边结果都是 4,966 行。
- 结论：倾斜治理要看执行引擎。分布式 shuffle 下加盐/两阶段有效；单机 MPP 下不要为了"政治正确"硬加盐。

## Q5：为什么用 Parquet？实测收益？

- 同一份 2025-01 DWD：CSV **1.21 GB**，Parquet **0.116 GB**，压缩约 **10.4×**。
- 同一聚合：CSV **1.546s**，Parquet **0.085s**，约 **18×**。
- 列裁剪：只读 1 列 0.312s，读 6 列 1.428s，约 **4.6×**。
- 分区裁剪：全量金额 0.261s，单月 0.073s，约 **3.6×**（原始层 0.240s → 0.011s，约 21.8×）。
- 线程扩展：1/2/4/8 线程 = 2.277 / 1.115 / 0.715 / 0.437s。

## Q6：为什么用 DuckDB，不用 Spark/Hive？是不是没做过大数据？

- 本机 16 GB 内存、无 Hadoop/Docker 集群，DuckDB 单机 MPP 能在 3 GB 内存上限内跑完 1.22 亿行，适合把链路做完整。
- 同时用 **Spark 4.3 + JDK 21** 真跑了 2023-01 样本：清洗 + broadcast join + cache 30.6s，group by 1.638s，
  加盐 0.845s，证明同一套 SQL 能平移 Spark。
- 生产化路径：DuckDB 负责本地验证/小数据；Spark SQL 负责 TB 级；Hive Metastore/Iceberg 管元数据；Doris/ClickHouse 做 serving。
- 面试重点不是"你装了什么集群"，而是"你知道数据涨 100 倍时哪里会崩、怎么改"。

## Q7：数据质量怎么落？失败了怎么办？

- 18 条规则：ODS 接入 3 条、DWD 规则 9 条、ADS 对账 6 条。
- 输出 `quality_report.json`（机器可读）+ `dq_result` 表（看板/接口）+ HTML 明细。
- 结果：**17 PASS / 1 WARN / 0 FAIL**。WARN 是"分项金额 ≈ total_amount"，通过率 70.16%：
  TLC 不同 Vendor 对拥堵费/机场费的记账口径不同，收入统一以 `total_amount` 为准，所以只观测不阻断。
- Airflow DAG 里 `quality_gate` 读取 `overall`，FAIL 则阻断下游报表。

## Q8：口径怎么对齐？

- 指标字典在 `docs/metric_dict.md`：每个指标写清分子/分母/过滤条件/时间口径。
- 典型坑：① 收入用 `total_amount` 还是分项之和？② 小费只能算信用卡（现金不可观测）；③ 机场 zone 是否含 EWR；
  ④ 退款负数单是否计入收入（本项目剔除）；⑤ 时区（TLC 已是 America/New_York 本地时间）。
- 对账 SQL：ADS 行数 = DWD 行数；ADS 收入 = DWD 收入（误差 < 0.1%，实测 0）。

## Q9：实时链路怎么设计？为什么本项目不做？

- 设计：TLC 行程事件 → Kafka `nyc_tlc_trips` → Flink SQL 1h 滚动窗口（event time + watermark 10s）→
  ClickHouse/Doris（ReplacingMergeTree/Unique Key 幂等）→ BI。
- 为什么不在本机跑：Windows + 16 GB + 无 Docker，起 Kafka/Flink/ClickHouse 会挤爆内存；
  离线链路已经能证明 SQL/建模/治理能力，实时给可执行 SQL + 选型说明，面试够用。
- 面试可讲：为什么事件时间、watermark 怎么处理迟到数据、精确一次怎么保证、热点 zone 怎么 local-global 聚合。

## Q10：如果数据涨 100 倍，方案哪里会崩？

- 单机 DuckDB 的瓶颈：单机磁盘/内存、并发查询、写入吞吐。
- 改造：① 存储换 HDFS/S3 + Iceberg/Hudi，按天/小时分区；② 计算换 Spark/Flink，按 slot 扩；③
  shuffle 分区数按数据量调，倾斜 key 加盐/拆分；④ DWS/ADS 落 Doris/ClickHouse，按天分区 + 物化视图；
  ⑤ 调度换 Airflow/DolphinScheduler，质量门禁 + 血缘；⑥ 小文件治理（compact/rewrite）。
- 回答结构：先说"哪里崩"，再说"怎么演进"，最后说"哪些不用改"（SQL/分层/口径不变）。

## Q11：这个项目和淘宝 UserBehavior 项目有什么区别？

- 淘宝是电商行为（pv/cart/fav/buy），偏漏斗/留存/用户行为；本项目是**出行交易事实**，偏收入/供需/时空/天气。
- 两个项目共享同一套数仓方法论，但业务口径、维表、清洗规则完全不同，能证明"换域也能做"，而不是背同一个项目。
- 淘宝项目已经做过，本项目重点补：官方 Parquet、分区裁剪、Spark 倾斜实验、FastAPI/看板、真实脏数据治理。

## Q12：你在这个项目里最大的坑是什么？

- 1.22 亿行做全局 `row_number()` 去重，20 分钟只写出 20%，临时文件打满；改成**按月循环**后 36 个月 4.93 分钟完成。
- TLC Vendor 记账口径不一致，最初想把分项硬对齐，后来改成"total_amount 为收入口径 + WARN 观测"，这是更真实的数据治理。
- Windows 下 Spark 需要 winutils，且写 Parquet 会被 ACL 拦 chmod；于是 Spark 只做内存计算验证，落盘交给 DuckDB。
- 这些坑比"跑通一个 SQL"更能说明工程能力。
