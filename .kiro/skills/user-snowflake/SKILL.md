---
name: user-snowflake
description: FeatureLab 数仓（Snowflake + feature-lab dbt）的现状调查、Snowflake 知识与构建者规范、临时 SQL 与高性能 SQL 编写、个人 schema 上的代码部署与数据验证、个人 schema 清理、线上报错调查。用户要求这些操作或相关规范时使用。
---

# user-snowflake

访问入口、连接配置位置、认证限制、`preprocess_evaluate` 的共享 stage 见 `50-project-facts.md#snowflake`。

## 按场景进入

| 场景 | 先读 | 接口（`scripts/`） |
|---|---|---|
| 线上各 schema 的组织结构、数据量级、依赖关系 | [survey/method.md](survey/method.md)；preprocess 层另读 [survey/preprocess-layer.md](survey/preprocess-layer.md) | `schema_survey.py`、`layer_flow.py` |
| Snowflake 知识、构建者推荐的用法 | [knowledge/snowflake-guide.md](knowledge/snowflake-guide.md)（构建者规范）、[knowledge/verified-facts.md](knowledge/verified-facts.md)（本项目实测） | — |
| 临时 SQL、编写或优化 SQL | [sql/writing.md](sql/writing.md)、[sql/verify.md](sql/verify.md) | `query_profile.py`、`my_queries.sh` |
| 临时部署代码到个人 schema | [testing/naming.md](testing/naming.md)、[testing/deploy.md](testing/deploy.md) | `deploy.sh` |
| 个人 schema 上的数据验证（一致性、耗时） | [testing/naming.md](testing/naming.md)、[testing/build.md](testing/build.md)、[testing/compare.md](testing/compare.md) | `preprocess_build.py`、`compare_tables.py` |
| 个人 schema 清理 | [testing/clean.md](testing/clean.md) | `personal_schema_clean.py` |
| DEV/PROD 线上 build 或部署报错 | [incident/investigation.md](incident/investigation.md) | `deploy.sh` |

接口的用法、步骤与产物写在各脚本头部的 docstring 或注释里，调用前先读。skill 文档不抄写 model 清单、数据流等随分支变化的结构，需要时用 `layer_flow.py` 从对应 ref 生成。

## 所有场景通用

- 连接名取 `.kiro/local-context.sh` 的 `SNOWFLAKE_CONNECTION`，每条 `snow` 命令显式带 `-c "$SNOWFLAKE_CONNECTION"`；脚本经 `scripts/sf.py` 读取同一个值。
- `snow` 由 `uv tool` 安装，位于 conda 之外，命令前不加 `conda run`。
- 对象名一律写全限定形式 `<db>.<schema>.<object>`：连接定义里没有 database 与 schema。
- 写操作只落在个人 schema（`DEV_<USER>`、`DEV_<USER>_PREPROCESS`），跨出时先与用户确认。
- `config.toml` 的口令、私钥内容与其它取值不复述进回复、仓库、steering、skill。
- `authenticator = "SNOWFLAKE_JWT"` 报 JWT 无效时，改用口令连接或请有权限者注册公钥，不调参重试。
- 提交到 Snowflake 的长任务在后台运行，结局由监控 workflow 回报，做法见 `user-run-experiment` skill 的「监控后台任务」；取消查询前先向用户展示完整 query id 并得到确认（`my_queries.sh` 的用法见脚本头部）。

单条命令：

```bash
snow sql -c "$SNOWFLAKE_CONNECTION" -q "<SQL>"          # 多行 SQL 用 -f <文件>
snow stage list-files -c "$SNOWFLAKE_CONNECTION" "@<db>.<schema>.<stage>"
snow stage copy -c "$SNOWFLAKE_CONNECTION" <本地文件> "@<db>.<schema>.<stage>/<目录>"   # 下载时两个参数对调
```
