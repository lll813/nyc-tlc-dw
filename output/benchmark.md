| 实验 | 中位耗时(s) | 最快(s) | 说明 |
|---|---:|---:|---|
| raw_full_scan_sum | 0.221 | 0.219 | 36 个月原始 Parquet 全量，真实读金额列 |
| raw_one_month_sum | 0.010 | 0.010 | 单月 Parquet，模拟分区裁剪 |
| dwd_full_scan_sum | 0.252 | 0.251 | DWD 全量金额列 |
| dwd_one_month_sum | 0.061 | 0.061 | 分区裁剪到 1 个月 |
| dwd_groupby_zone | 0.504 | 0.474 | 按 zone 聚合全量 |
| dwd_groupby_date | 0.864 | 0.855 | 按天聚合全量 |
| column_1 | 0.476 | 0.466 | 只读 1 列 |
| column_6 | 1.824 | 1.765 | 读 6 列 |
| threads_1_groupby_zone | 3.431 | 3.379 | threads=1 |
| threads_2_groupby_zone | 1.784 | 1.774 | threads=2 |
| threads_4_groupby_zone | 0.965 | 0.947 | threads=4 |
| threads_8_groupby_zone | 0.659 | 0.618 | threads=8 |
| csv_one_month_agg | 2.154 | 2.061 | CSV 1.21 GB |
| parquet_one_month_agg | 0.104 | 0.100 | Parquet 0.12 GB |
| skew_naive_groupby | 0.970 | 0.965 | 普通两列 group by |
| skew_salted_groupby | 2.441 | 2.412 | 加盐两阶段聚合 |