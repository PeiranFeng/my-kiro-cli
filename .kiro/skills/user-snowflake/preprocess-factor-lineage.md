# Preprocess 因子 source 血缘

## 范围

本文记录 `feature-lab` 的预处理输入 relation `fact_stock_factor_source` 的数据仓库语义、直接上游和已物化 schema 快照。模型定义位于 `models/preprocess/fact_stock_factor_source.sql`。

## 已物化 schema 快照

核验日期：2026-11-04。

`FEATURELAB.PROD_PREPROCESS.FACT_STOCK_FACTOR_SOURCE`、`FEATURELAB.DEV_PREPROCESS.FACT_STOCK_FACTOR_SOURCE` 和 `FEATURELAB.DEV_PEIRAN_PREPROCESS.FACT_STOCK_FACTOR_SOURCE` 均有 209 列：`rule_id`、`date`、`stock_id` 三个键列，以及 206 个因子列。

## 因子列血缘

因子值来自两个 mart relation：

| 上游 relation | source 因子列 | 传递方式 |
|---|---:|---|
| `FEATURELAB.<环境>_MART.FACT_STOCK_FEATURE` | 40 | 直接投影其业务特征列。 |
| `FEATURELAB.<环境>_MART.FACT_STOCK_RESEARCH_SCORING_FEATURE` | 166 | 按评分配置改名前缀并展开数组列。 |

研究评分上游当前提供 37 个标量评分列和 4 个数组评分列。20 维评分配置产生 117 个 `scoring20_*` 列，3 维评分配置产生 49 个 `scoring3d_*` 列，因此共提供 166 个输入因子。

## 面板与权重上游

`fact_stock_pool`、`fact_stock_pool_scope` 和 `fact_index_market_data` 共同构造 `(rule_id, date, stock_id)` 样本面板：前两者确定规则的股票池及有效范围，市场数据确定交易日期。它们不提供 source 因子宽列。

`fact_pool_weight_source` 是独立的权重输入 view，其直接上游为 `fact_weight_dense`。预处理存储过程使用该 view 进行加权统计和截面归一化，权重列不属于 `fact_stock_factor_source` 的因子列。

## 核验方法

因子列由 dbt 运行时 relation metadata 发现，源代码中的评分宏不能代替部署后的 schema 核验。调查实际血缘或列数时，查询 `FEATURELAB.INFORMATION_SCHEMA.COLUMNS`，分别核对目标 preprocess schema、相应 mart schema 和输出 relation 的列集合。