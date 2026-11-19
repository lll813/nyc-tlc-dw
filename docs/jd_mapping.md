# 17 条 JD → 本项目证据映射

> 输入：桌面 `JD/` 下 17 条有效岗位截图（另 1 张简历页、1 张重复）。
> 说明：不是"每个 JD 做一个项目"，而是用**一个完整项目**覆盖高频能力；面试时按目标公司挑对应的 2~3 个点讲。

| # | 公司 / 岗位 | JD 关键要求 | 本项目对应证据 |
|---|---|---|---|
| 1 | Shopee 大数据开发（27 秋招） | Java/Python、Hive/Hadoop/Flink、数仓+实时+OLAP、LLM | 四层数仓 + Spark 4.3 + Flink SQL + ClickHouse DDL + FastAPI |
| 2 | 华勤 IT 数据工程师 | 数据湖/数仓建模、ETL、数据核对 | ODS/DWD/DWS/ADS + 18 条质量对账 + `source_file` 血缘 |
| 3 | 数仓开发（AI 向） | 游戏数仓、指标体系、维度建模/Data Vault | 6 张维表 + 指标字典 + 10 张 ADS（本项目是出行域，方法论一致） |
| 4 | 友邦资讯 数据开发实习 | Python、Oracle/MSSQL/Sybase/MySQL | Python 全链路 + SQL 方言集中在 `sql/`，可平移 |
| 5 | 能科瑞元 数据治理实习 | 清洗/校验/质量报告、血缘元数据、调度、窗口函数 | `06_quality.py` + JSON 报告 + Airflow DAG + 窗口函数 |
| 6 | 影石 Insta360 数据开发实习 | 离线+实时数仓、采集、SQL/Python/Java/Linux | 离线全链路 + Flink SQL 实时设计 + Python 采集 |
| 7 | 小红书 数仓开发实习 | Hive/Spark SQL、分层建模、SQL 优化、**数据倾斜** | Hive DDL + Spark 4.3 + 加盐实验 48.4% + 基准测试 |
| 8 | Anker 大数据开发实习 | 数仓/集市、ETL/ELT、质量监控、Airflow、ODS/DWD/DWS/ADS | 四层 + 质量门禁 + Airflow DAG + 运行清单 |
| 9 | 卫宁健康 ETL 数据开发 | Flink CDC、多源库、Paimon/Doris/Iceberg POC | Flink SQL + Doris DDL + 多源（TLC/zone/weather） |
| 10 | 万声音乐 大数据开发实习 | 离线+实时、维度建模/星型、Flink/Trino、Git | 星型模型 + Flink SQL + SQL 可平移 Trino/Spark |
| 11 | 华为 数据岗 | 采集/清洗/分析、模型设计优化 | 清洗漏斗 + 质量规则 + 性能实验 |
| 12 | 蓝禾 数据产品经理 | 指标字典、Excel/SQL、BI、需求拆解 | `docs/metric_dict.md` + HTML 看板 + 指标分层 |
| 13 | 转转 数仓开发 | Hadoop、Spark/Flink/Doris/HBase/Redis、治理 | Spark + Flink SQL + Doris DDL + 质量/血缘 |
| 14 | 百观科技 数据分析实习 | SQL/Python、商业分析 | ADS 业务指标 + Python 分析 + 看板 |
| 15 | Anker 大数据分析实习 | 日报月报、集成清洗建模、质量、BI | 日/月 KPI + 质量报告 + 看板 |
| 16 | 华为 数据科学工程师 | 湖仓、埋点、画像标签、SQL/Python、Agent | 湖仓分层 + 预测特征 + Python；Agent 可复用你简历项目 |
| 17 | 数新智能 大数据开发 | 数仓建模、Hive/Spark/Flink/Paimon/Hudi/Iceberg/DataX、集群运维 | 四层建模 + Spark/Flink 文件 + 湖仓选型说明 |

## 面试时怎么用这张表

1. **先看目标公司**：Shopee/小红书/转转/Anker 重点讲 Spark + 倾斜 + 分层；卫宁/万声重点讲 Flink + 实时；能科/华勤重点讲质量 + 治理。
2. **每个能力只讲一个证据**：不要背组件清单，直接说"我在 1.22 亿行上跑过，耗时从 X 降到 Y"。
3. **主动说边界**：本机没有 Hadoop 集群，Hive/Flink/ClickHouse 是可执行 SQL/DDL，不是生产集群经验；这比硬吹更加分。
4. **把淘宝项目当第二项目**：电商行为 + 出行交易两个域，证明方法论可迁移，而不是背同一个项目。
