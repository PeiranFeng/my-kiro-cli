# 验证 SQL 的性能

## 运行前

1. 选 warehouse：`show warehouses` 看 `COMPUTE_WH` 的 `running` 与 `queued`。`running` 达到 `MAX_CONCURRENCY_LEVEL` 或有排队时，若 `SYSTEM$STREAMLIT_NOTEBOOK_WH` 的 `running` 与 `queued` 都为 0，就在它上面运行（`use warehouse`），否则等待；两者都空闲时用 `COMPUTE_WH`。
2. 估算会扫多少：行数与字节数来自 `scripts/schema_survey.py`。全表扫描超过百万行、或含多次 join 的查询，先限定一个 rule 或一段日期试跑。
3. 自己同时提交的查询不超过 2 条，免得把共享 warehouse 的队排满。

## 度量

- 用 `scripts/query_profile.py <query_id>` 读一条已完成查询的度量（用法见脚本头部）。query id 取自 `snow sql` 后的 `select last_query_id()`、dbt 的 `run_results.json`（`adapter_response.query_id`），或 `QUERY_HISTORY_BY_USER`。
- 快慢只看执行时间，即总耗时减去排队时间；`COMPUTE_WH` 与他人共用，总耗时随负载变化。
- 先看耗时占比最高的算子，再按四项检查定位原因：Join 的输出 / 输入行数、UnionAll 是否在 Aggregate 之下、溢出字节数、TableScan 的 partitions scanned / total。每一项对应的改写见 `sql/writing.md`。

## 改写前后对比

1. 改写前后的两条查询在同一 warehouse、相近时间各跑一次，在同一份数据上。
2. 先确认结果相同（行数与 `HASH_AGG(*)` 一致），再比较执行时间与四项检查。
3. 改写有效且原因明确时，把查询、两组度量写进 `sql/writing.md` 对应规则的"实测"列。
