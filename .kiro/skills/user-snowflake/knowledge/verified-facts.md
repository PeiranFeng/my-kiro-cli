# 本项目实测过的 Snowflake 行为

每条写结论、依据与日期；只收在本账号上实际验证过的行为。模型知识或搜索得来、尚未验证的说法不进本文，回答时标"未核实"。团队约定的用法以 `snowflake-guide.md` 为准。

## 连接与权限

- `dbt` 与 `snow` 各用一套凭据：`profiles.yml` 的 `env_var('SNOWFLAKE_USER'|'SNOWFLAKE_PASSWORD'|'SNOWFLAKE_ACCOUNT')` 只读进程环境变量，不读 `~/.config/snowflake/config.toml`。跑 dbt 前 `source .kiro/local-context.sh`，并 export `DBT_PERSONAL_ROLE=FEATURELAB_PERSONAL_<USER>`、`DBT_PERSONAL_SCHEMA=DEV_<USER>`（`profiles.yml` 要求显式赋值）。
- 个人 role 没有 `FEATURELAB_DEV`/`FEATURELAB_PROD`：对 `--target dev|prod` 只执行 `dbt parse`，它纯本地解析、不连接 Snowflake；其余子命令只用 `--target personal`。DEV/PROD 的代码变更只走 CI/CD（`snowflake-guide.md#human-vs-runner`）；唯一的例外是用 `FEATURELAB_DEV_OP` 手动触发 DEV 已部署的任务图，见 `operations/dev-task.md`。
- 用户名下的编程访问令牌带角色限制（`SHOW USER PROGRAMMATIC ACCESS TOKENS` 的 `role_restriction`）：用它登录的会话是受限会话，`USE ROLE` 报 "session is restricted"，连接时指定别的角色报 "not permitted for the credentials being used"，即使该角色已授给用户（2026-11-18）。换角色要换一个限定该角色的令牌与连接（`SKILL.md` 的连接表）。
- `snow connection test -c <dev_op 连接>` 会报 `Could not use schema "DEV_<USER>"`：它尝试进入用户的默认 namespace，而 DEV_OP 看不到个人 schema；实际查询不受影响（2026-11-18）。
- `FEATURELAB_DEV_OP` 对 `FEATURELAB.DEV` 的任务有 OPERATE 与 MONITOR（owner 是 `FEATURELAB_DEV`），能看到 `SHOW TASKS`、`CURRENT_TASK_GRAPHS`、`TASK_HISTORY`；个人 role 对这些任务没有任何权限，查到空结果不代表没有任务（2026-11-18）。
- 个人 role 读不到 `SNOWFLAKE.ACCOUNT_USAGE`（2026-11-17，`OBJECT_DEPENDENCIES` 报 schema 不存在或未授权）。个人 role 的 `INFORMATION_SCHEMA.QUERY_HISTORY` 能看到 DEV 任务（`FEATURELAB_DEV`）发出的查询（2026-11-18，一次 PREPROCESS 运行期间 630 条），也能对其中的查询调 `GET_QUERY_OPERATOR_STATS`。
- 查询历史（`INFORMATION_SCHEMA` 的 `QUERY_HISTORY*`）保留 7 天，`GET_QUERY_OPERATOR_STATS` 保留 14 天；2026-11-17 据此补回了前一天的耗时与算子统计。
- `SYSTEM$GET_DBT_LOG(<query_id>[, <最大行数>])` 返回一次 `EXECUTE DBT PROJECT` 运行的 dbt 日志；参数必须是那条 `EXECUTE DBT PROJECT` 语句的 query id，传任务本身的 query id 会报 "DBT project not found or access denied"。DEV 的 dbt project 把 MONITOR 授给了 `FEATURELAB_DEV_READ`，个人 role 经由它能读 DEV 的日志；PROD 的 dbt project 个人 role 没有权限（2026-11-18）。默认只返回最后 1000 行。

## Warehouse

- `COMPUTE_WH`：Small，单集群，`MAX_CONCURRENCY_LEVEL` 8（2026-11-17 `show warehouses` 与 `show parameters`）；与他人共用，负载不同时同一 SQL 的总耗时可相差近一倍（2026-11-17，`fact_stock_factor_source` 150 s 与 261 s）。
- `SYSTEM$STREAMLIT_NOTEBOOK_WH`：X-Small，可作 `COMPUTE_WH` 饱和时的备用；`personal` target 的 warehouse 写死在 `profiles.yml`，改用时复制一份 `profiles.yml` 到仓库外并以 `--profiles-dir` 指定。
- `SHOW` 只读元数据，`COMPUTE_WH` 饱和时仍立即返回；`INFORMATION_SCHEMA` 表函数要排队（2026-11-17）。

## 数值语义

- Snowflake 中 NaN 等于自身、且大于任何数（含 +inf）：`'NaN'::float != 'NaN'::float` 为 false，`count_if(v != v)` 数不到 NaN，`v > 0`、`abs(v) > 1e308` 把 NaN 算作正数与 inf；判断 NaN 用 `v = 'NaN'::float`，判断 inf 用 `v in ('inf'::float, '-inf'::float)`（2026-11-17）。

## dbt

- 本机 CLI 编译不产生 Snowflake 编译开销，`--vars` 即时生效、不进 git；Snowflake 托管的 dbt Projects 须先部署才能执行，不支持临时 `--vars`。两者读写同一套对象。
- 本地与线上 dbt-core 版本可能不同；线上版本以 `feature-lab/.github/workflows/deploy.yaml` 的 `snow dbt deploy --dbt-version` 为准，复现时用 `uv run --with dbt-core==<版本>`，manifest 要用同一版本 parse。
- Python model 的 `dbt build` 在存储过程返回前不写最终 `run_results.json`，日志可长时间静默；本地进程中断不会取消已提交的查询。查询历史中一个 Python model 是同一 session 的三层：`<model>__dbt_sp`、其中的 `CALL`、过程内部的查询。

## Stage 与存储过程

- `snow stage copy` 的目标参数是目录，文件名跟随源文件；目标已有同名文件时默认显示 `SKIPPED` 并保留旧文件，加 `--overwrite` 才覆盖。
- 个人 role 读不到 `FEATURELAB.PUBLIC.FEATURE_LAB_PYTHON_STAGE` 与环境 stage。
- 共享 stage 上的文件名与 `last_modified` 不能证明 zip 对应哪个 commit，只能下载后与 `git archive <commit>` 的内容比对。
- Snowpark 生成的 UDTF 名字嵌入输出 schema，宽输出会超出标识符长度上限，注册时要显式给短名字。
- 一个 UDTF 注册最多 500 个输出列；ARRAY 输出列可原样往返 303 个 double，包括 ±inf、NULL、布尔与 5e-324（2026-11-17 实测）。本地 Snowpark 模拟器不能对 ARRAY 元素做类型转换。
- UDTF 沙箱的 `/tmp` 每个查询独立，跨查询缓存（如 numba 编译缓存）不可行。
- `system$cancel_query(query_id)` 放在 `select ... from <查询历史>` 里按列传参时报 "non-constant input"，要以字面量传入。

## 存储与 Time Travel

- `DEV_<USER>_PREPROCESS` 的 `DATA_RETENTION_TIME_IN_DAYS` 为 1（2026-11-17 `show parameters`），依赖 Time Travel 读回旧输入只在一天内可行，长期对照要靠物化保存。
- `CREATE ... CLONE` 可在一次提交里复制整层的输出表作对照（2026-11-17，12 张百万行级的表）。
- 个人 role 能把 DEV 的表 clone 进个人 schema；dbt 的 `--defer --state --favor-state` 读的是 state manifest 里节点的 `relation_name`，改写它就能让 defer 指向任意一张表（2026-11-18，`fact_weight_dense` 指向个人 schema 的快照后，`fact_pool_weight_source` 编译出的 SQL 读快照）。preprocess 层直接依赖的 19 个上游 relation（17 张表、2 个 view）全部固定成快照，连同一次 dbt parse 共约 50 秒。
