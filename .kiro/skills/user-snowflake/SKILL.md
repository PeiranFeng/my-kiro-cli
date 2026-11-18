---
name: user-snowflake
description: FeatureLab 数仓（Snowflake + feature-lab dbt）的现状调查、Snowflake 知识与构建者规范、临时 SQL 与高性能 SQL 编写、个人 schema 上的代码部署与数据验证、个人 schema 清理、线上报错调查、DEV 任务状态与历史的读取及经同意后的手动运行。用户要求这些操作或相关规范时使用。
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
| DEV 任务状态与历史；PR 合并后手动运行 DEV | [operations/dev-task.md](operations/dev-task.md) | `dev_task.py` |

接口的用法、步骤与产物写在各脚本头部的 docstring 或注释里，调用前先读。新增或修改 `scripts/` 下的脚本（以及测试中临时写的驱动脚本）时，脚本发出的每条 SQL 都按 [sql/writing.md](sql/writing.md) 的写法规则与 `user-explain` skill 的 `domain/snowflake-performance.md` 所列的官方常见问题逐条自查，完成后在回复中逐条给出结论；规则未覆盖、但实测发现的低效写法，先补进 `sql/writing.md` 再写代码。skill 文档不抄写 model 清单、数据流等随分支变化的结构，需要时用 `layer_flow.py` 从对应 ref 生成。

## 连接

两个连接名都取自 `.kiro/local-context.sh`。连接在登录时就固定了角色：两个连接都用限定角色的编程访问令牌，令牌会话不允许 `USE ROLE`/`USE SECONDARY ROLES`，换角色就是换连接。

| 连接（变量） | 角色 | 用于 |
|---|---|---|
| `SNOWFLAKE_CONNECTION` | 个人角色 | 默认。个人 schema 上的一切读写、DEV/PROD 表的只读查询、DEV 的查询历史与 dbt 日志 |
| `SNOWFLAKE_CONNECTION_DEV_OP` | `FEATURELAB_DEV_OP` | 只用于 DEV 任务：任务状态、`TASK_HISTORY`、经同意后的手动运行（`operations/dev-task.md`） |

- 每条命令显式带 `-c`，不依赖默认连接；`dev_op` 只用于上表所列，做完回到 `SNOWFLAKE_CONNECTION`。
- 换连接意味着换场景（如从个人 schema 的测试转去调查 DEV 历史）。换之前，先判断回来时要接着用的信息（正在进行的测试的 tag、build id、后台运行的 pid、待比对的表、调查已得到的 query id 与结论），有必要就写进当前 tag 本地目录的 `notes/<UTC 时间>-<去向>.md`（tag 规则见 `testing/naming.md`，没有对应 tag 时用所调查的 issue、PR 或 commit 定一个），不写进任何仓库，随 tag 一起清理。

## 所有场景通用

- 脚本经 `scripts/sf.py` 读取上表的两个连接名。
- `snow` 由 `uv tool` 安装，位于 conda 之外，命令前不加 `conda run`。
- 对象名一律写全限定形式 `<db>.<schema>.<object>`：连接定义里没有 database 与 schema。
- 写操作只落在个人 schema（`DEV_<USER>` 及其各层 schema），跨出时先与用户确认。DEV 默认只读：手动运行 DEV 任务按 `operations/dev-task.md` 的前置步骤，得到用户明确同意或直接要求后才执行。
- `config.toml` 的口令、私钥内容与其它取值不复述进回复、仓库、steering、skill。
- `authenticator = "SNOWFLAKE_JWT"` 报 JWT 无效时，改用口令连接或请有权限者注册公钥，不调参重试。
- 提交到 Snowflake 的长任务在后台运行，结局由监控 workflow 回报，做法见 `user-run-experiment` skill 的「监控后台任务」；取消查询前先向用户展示完整 query id 并得到确认（`my_queries.sh` 的用法见脚本头部）。

单条命令：

```bash
snow sql -c "$SNOWFLAKE_CONNECTION" -q "<SQL>"          # 多行 SQL 用 -f <文件>
snow stage list-files -c "$SNOWFLAKE_CONNECTION" "@<db>.<schema>.<stage>"
snow stage copy -c "$SNOWFLAKE_CONNECTION" <本地文件> "@<db>.<schema>.<stage>/<目录>"   # 下载时两个参数对调
```
