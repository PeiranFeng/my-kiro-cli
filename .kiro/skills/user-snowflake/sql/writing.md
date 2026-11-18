# 编写 SQL

临时查询与正式 model 的 SQL 都按本文写。快慢以 `sql/verify.md` 的度量为准；Snowflake 官方的常见问题与提速手段的说明见 `user-explain` skill 的 `domain/snowflake-performance.md`，本文只写在本项目上怎么用。

## 写之前：先查数据特性

1. 用 `scripts/schema_survey.py` 查目标表的行数、大小、聚簇键与最后修改时间；表的粒度与键是否唯一，用 `count(*)` 与 `count(distinct <键>)` 核对。
2. 写法依据这些约束选择（`20-engineering.md#match-algorithm-to-data`）：键已唯一就不去重；已知一个 rule 或一段日期就先过滤；结果只要聚合值就不取明细。
3. 本项目的表都没有聚簇键（2026-11-17，DEV/PROD 的 RAW、STG、MART、PREPROCESS 共 165 张表），裁剪只能靠数据按写入顺序形成的自然聚集，日期过滤是否有效要看 `query_profile.py` 的 partitions scanned / total，不能假定。

## 写法规则

每条规则针对 Query Profile 能观测到的一类问题；"实测"列出本项目的证据，空着的规则来自官方文档、尚未在本项目复现。

| 规则 | 针对的问题 | 实测 |
|---|---|---|
| join 前确认两边的连接键唯一，或预期中的一对多倍数；不写无条件 join | join 膨胀：Join 的输出行数远大于输入 | |
| join 条件写成等值；非等值条件放到 join 之后会让 join 先产生大结果再过滤 | 非等值 join 条件（官方 Join 算子说明） | |
| 两边不相交时用 `UNION ALL`；只在需要去重时用 `UNION`，`DISTINCT`、`GROUP BY` 同理 | 多余的去重：UnionAll 上多一个 Aggregate；DISTINCT/GROUP BY 不减少行数 | preprocess_evaluate 的 timing scale floor SELECT（2026-11-16，#96 基线，算子统计在 `~/data/exp/timing-speed-optimization/raw/`）：223 s 中 DISTINCT 占 27%、自连接 24%、join 回原表 22%，而 351 列的 AVG 窗口只占 14%；timing 每个（股票, 日期）只有一行，DISTINCT 与自连接对它是多余的 |
| 中间结果大时缩小每次处理的范围（按 rule 或日期分批），或减少带入的列 | 溢出：bytes spilled to local / remote storage | 同一条 SELECT：自连接与 join 回原表分别溢出 1.2 GB 与 4.4 GB |
| 过滤条件直接写在被扫描的列上，不包函数，不用前导通配的 `LIKE` | 裁剪无效：partitions scanned 接近 total | |
| 比较两张宽表时，先对每列算 `HASH_AGG(键, 列)`，只对哈希不同的列做 join | 宽表逐列 join：一列一次全表 join | `compare_tables.py`：一对 357 列、184 万行的表，扫描一遍即判定 198 列相同，3 对表共 37 s（2026-11-17） |
| 只取需要的列，不写 `select *` 进 join 或聚合 | 列式存储下多读的列都要扫描 | |
| 查元数据用 `SHOW`，不用 `INFORMATION_SCHEMA` 表函数 | 排队：warehouse 饱和 | `SHOW` 立即返回，`INFORMATION_SCHEMA` 查询排队超过 30 分钟（2026-11-17） |

一条规则在本项目上复现后，把证据（查询、改写前后的度量）补进"实测"列；复现结果与规则相反时，改写或删除该规则。

## 改表或改 warehouse 的手段

聚簇键、Search Optimization、物化视图、Query Acceleration、更大的 warehouse 都改变表或 warehouse 的配置并产生持续费用，不在写 SQL 时自行采用。需要时把度量结果和理由交给用户，按 `knowledge/snowflake-guide.md` 的权限与评审流程处理。
