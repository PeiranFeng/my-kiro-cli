# 调查线上现状：组织结构、数据量级、依赖关系

只读回答"某个环境里有什么、多大、谁依赖谁"，结论用于判断下一步工作要点。

## 环境与 schema

`FEATURELAB` 库下每个环境一个 target schema（`PROD`、`DEV`、个人的 `DEV_<USER>`），层的 schema 是 `<target schema>_<层名>`（`_RAW`、`_STG`、`_MART`、`_PREPROCESS`、`_METRIC`、`_FEATURE_EXPORT` 等），规则见 `feature-lab` 的 `macros/generate_schema_name.sql`；外部表在 `RAW_EXT`。当前存在哪些 schema 用 `show schemas in database FEATURELAB` 列出，不凭记忆。个人 role 对 DEV/PROD 只读，权限分配见 `knowledge/snowflake-guide.md#writer-roles`。

## 每个问题从哪里取数

| 问题 | 来源 | 说明 |
|---|---|---|
| 有哪些对象、类型 | `SHOW TABLES/VIEWS IN SCHEMA` | 只读元数据，不占 warehouse 算力 |
| 行数、字节数、聚簇键、最后修改时间 | `<DB>.INFORMATION_SCHEMA.TABLES` | view 没有行数与字节数；行数是元数据，不扫表 |
| 列与类型 | `<DB>.INFORMATION_SCHEMA.COLUMNS` | 宽表的因子列数以这里为准 |
| view 读哪些表 | `INFORMATION_SCHEMA.VIEWS.VIEW_DEFINITION` 中的全限定名 | 个人 role 读不到 `SNOWFLAKE.ACCOUNT_USAGE.OBJECT_DEPENDENCIES`（2026-11-17 实测） |
| model 之间的依赖 | dbt manifest（`dbt parse --target <dev|prod>`，见 `testing/build.md`） | 覆盖 table 与 view；按名字拼表的 Python model 不在其中，见 `survey/preprocess-layer.md` |
| 某个值的分布、粒度是否唯一 | 对表做聚合查询 | 会扫表，按 `sql/writing.md` 写，大表先限定范围 |

以上前五项由 `scripts/schema_survey.py` 一次取齐（用法见脚本头部）。表的实际粒度不由元数据给出：需要时用 `count(*)` 与 `count(distinct <键>)` 核对。

## 呈现

按层从上游到下游排列，每层列出对象、行数与大小量级、最后修改时间；依赖关系写成"谁读谁"的边，并标明来源是 view 定义还是 manifest。只写和用户问题相关的层。LAST_ALTERED 相差很远的上下游对，说明某次构建停在了中间，值得单独指出。
