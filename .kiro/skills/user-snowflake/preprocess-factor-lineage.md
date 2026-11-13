# Preprocess 因子 source 血缘

## 范围

本文记录 `feature-lab` 预处理的原始因子输入的数据仓库语义与直接上游。所有原始因子列在 `models/preprocess/all_calday_stock_feature.sql` 中汇总；`models/preprocess/fact_stock_factor_source.sql` 是在其上按交易日过滤的 view。

## 两个 relation 的粒度

- `all_calday_stock_feature`：粒度 `(stock_id, date)`，日历日。行键是 5 张上游因子表键的并集，非交易日到达的值（周末评分、HOLT 网格日期、日内特征的可用日期）保留自己的行，供存储过程的 fill 阶段向后填充。
- `fact_stock_factor_source`：粒度 `(stock_id, date)`，只保留 `date` 出现在 `fact_stock_feature` 中的行（交易日与股票无关）。不做填充。

两者均不含 `rule_id`。PR #182 验收 build 中该 relation 共 348 列（`stock_id`、`date` 两个键列与 346 个因子列）；列数随上游变化，以核验结果为准。

## 因子列血缘

| 上游 relation | join 日期 | 传递方式 |
|---|---|---|
| `fact_stock_feature` | `date` | 投影业务特征列。 |
| `fact_stock_research_scoring_feature` | `date` | 按评分配置改名前缀并展开数组列。 |
| `fact_stock_factor_hk_holt100` | `date` | 投影 HOLT 因子列。 |
| `fact_stock_factor_jp_holt100` | `date` | 投影 HOLT 因子列。 |
| `fact_factset_intraday_kline_derived` | `date`（= `data_date` + 1 个日历日） | 投影日内派生特征列。 |

## fill 与 normalize 的输入

fill 阶段（`calday_stock_feature_fill_timing`、`calday_stock_feature_fill_cross_section`）读取 `all_calday_stock_feature`；normalize 阶段读取交易日过滤 view `trdday_stock_feature_fill_timing`、`trdday_stock_feature_fill_cross_section`。

`fact_pool_weight_source` 是独立的权重输入 view，其直接上游为 `fact_weight_dense`。预处理存储过程使用该 view 进行加权统计和截面归一化，权重列不属于因子列。

## 核验方法

因子列由 dbt 运行时 relation metadata 发现，源代码中的宏不能代替部署后的 schema 核验。调查实际血缘或列数时，查询 `FEATURELAB.INFORMATION_SCHEMA.COLUMNS`，分别核对目标 preprocess schema、相应 mart schema 和输出 relation 的列集合。
