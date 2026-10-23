# 在私有 schema 测试：只读 PROD，写自己的 schema

`feature-lab` 仓库的常见开发动作：不改 PROD 数据，只用 PROD 的现成表做输入，把计算结果写到自己的个人 schema（`DBT_PERSONAL_SCHEMA`，按用户名自动生成，格式 `DEV_<USER>`，定义见 `profiles.yml` + `env.yml`）。

## 大多数 model 可以 defer：标准 ref() 层

`models/raw`、`models/staging`、`models/marts`、`models/evaluator`、`models/weight`、`models/screener`、`models/feature_export` 下的 model 大多用 `{{ ref(...) }}` 声明依赖，依赖关系由 dbt 在 compile 时解析成具体 relation，可以用标准的 defer 机制只读 PROD：

```bash
dbt build --target personal --select <model>+ \
  --defer --state <prod manifest 目录> --favor-state
```

`--select <model>+` 只构建你要改的 model 和它的下游，未被 selected 的上游（包括它们引用的 source）通过 `--state` 里的 PROD manifest 解析到 `FEATURELAB.PROD_RAW`/`PROD_STG` 等只读表，不会往 PROD 写。PROD manifest 获取方式见下一节。

**"按目录判断"只是经验规则，不是充要条件**——`models/preprocess` 之外的目录大多是纯 SQL model，但目录本身不是判断依据，决定能否 defer 的是下一节"影响范围的判断方法"里讲的依赖声明方式。即使是这些目录下的 Snowpark Python model，只要它被另一个 model 用 `sibling_relation` 之类的字符串拼接方式引用（比如 `weight` 层的 `fact_weight_dense` 被 `preprocess` 层的 `fact_pool_weight_source` 这样引用），也会被要求在当前 schema 本地存在，不能单纯因为它不在 `models/preprocess` 目录下就假定能 defer。

## 获取 PROD manifest：只为 defer，不验证 PROD 是否已部署

`--defer` 唯一要从 manifest 里取的信息是"每个 model 在 PROD 编译后解析成哪个具体 relation"，不需要这份 manifest 证明该 relation 已经在 PROD 真实建成——如果上游还没部署到 PROD，defer 后构建会直接报错（引用到不存在的表），等上游部署后再重新跑即可，不需要在生成 manifest 这一步就确认 PROD 侧状态。

用 `dbt parse` 在本机生成。**`dbt parse` 是唯一允许对 `--target prod` 执行的 dbt 子命令**——它纯本地解析 Jinja/YAML/依赖图，不连接 Snowflake、不触发任何权限校验，`--target prod` 在这里只是选用 `profiles.yml` 里 `prod` 这段的变量值去编译，不代表会用 `FEATURELAB_PROD` 这个身份登录。除 `dbt parse` 外，禁止对 `--target dev`/`--target prod` 执行任何 dbt 命令（`debug`、`build`、`run`、`test` 等）——个人角色没有 `FEATURELAB_DEV`/`FEATURELAB_PROD` 权限，这类命令会在连接阶段被拒绝，而且不应该去尝试：DEV/PROD 的数据变更只能走 CI/CD 审批流程（见 `snowflake-guide.md` 的 access control 章节），本地个人身份不具备、也不应该具备绕过这条路径的能力：

```bash
cd ~/data/feature-lab
uv run dbt parse --target prod --no-partial-parse \
  --target-path ~/data/test/<测试目录名>/artifacts/prod
```

生成的 `~/data/test/<测试目录名>/artifacts/prod/manifest.json` 直接作为后续 `--state` 参数使用：

```bash
dbt build --target personal --select <model>+ \
  --defer --state ~/data/test/<测试目录名>/artifacts/prod --favor-state
```

`feature-lab` 仓库的 `AGENTS.md` 另外记录了一条更严格的路径——从 Snowsight 网页（Transformations → dbt Projects → `FEATURELAB.PROD.FEATURE_LAB` → 某次成功 execution 的 Query Details → Download Build Artifacts）下载一次**真实构建过**的 manifest，用于需要同时确认 PROD 侧已部署该 relation 的场景（例如要在 PR 里证明某个上游改动已经上线）。本 skill 的场景（本地验证、不需要对外证明部署状态）用 `dbt parse` 已经够用，不需要走网页下载。

## preprocess 层是已知的例外：不能 defer，必须 full-refresh

`models/preprocess` 下几个 Snowpark Python model（`fact_stock_factor_filled_cross_section.py`、`fact_stock_factor_filled_timing.py`、`fact_stock_factor_cross_section.py`、`fact_stock_factor_cross_section_stats.py`、`fact_stock_factor_timing.py`）不能用 defer 只读 PROD 的同层输入表，必须在自己的 schema 里把这一层全部 full-refresh 出来。

原因：这几个 model 读取同层输入表时不用 `dbt.ref()`，而是调用 `preprocess_evaluate` 仓库 `orchestration.py` 的 `sibling_relation(dbt.this, name)`——这个函数截取 `dbt.this`（当前 model 自己的输出 relation）的 database+schema 部分，直接拼上兄弟表名作为要读的表名。`dbt.this` 永远指向当前 target 的 schema（个人测试时就是 `DEV_<USER>_PREPROCESS`），所以 `sibling_relation` 推导出来的"兄弟表"也必须在这个 schema 里实际存在，和 dbt 的 relation 解析（`ref()`/`--defer`/`--state`）完全无关，`--favor-state` 不会改变这个行为。

连带影响：这几个 model 的 Python import 路径同样不走 defer。`imports: ["{{ var('preprocess_bundle', '@' ~ target.database ~ '.' ~ target.schema ~ '.PYTHON_STAGE/preprocess_evaluate/current/preprocess_evaluate.zip') }}"]`（`models/preprocess/_preprocess_models.yml`）默认解析到当前 target 的 schema，`meta.procedure` 同理解析到 `<target.database>.<target.schema>.PREPROCESS_FACTORS`。`macros/preprocess_runtime.sql` 的 `validate_prod_preprocess_runtime()` 只在 `target.name == 'prod'` 时校验这两个值不被覆盖（`macros/generate_schema_name.sql`），对 `personal` target 不设限，但默认表达式仍然指向个人 schema。因此在私有 schema 测试 `preprocess` 层前，必须先把 `preprocess_evaluate.zip` 上传到自己 schema 的 `PYTHON_STAGE`，且对应的 `PREPROCESS_FACTORS` 存储过程也要在同一 schema 下创建，不能复用 PROD 的部署。

## 影响范围的判断方法

某个 model 能否只读 PROD 不重新计算，看它的依赖声明方式：用 `{{ ref(...) }}` 或标准 dbt Python model 的 `dbt.ref(...)` 是可以 defer 的；用字符串拼接（`sibling_relation`、或任何手工拼 `target.database`/`target.schema` 的写法）定位输入表的，必须在当前 schema 里让该表实际存在。遇到新的 Python model 时，检查其 import 的 helper 库里是否有类似 `sibling_relation` 的函数，不要默认所有 `dbt.ref()` 调用都等价于真正的依赖读取——`fact_stock_factor_cross_section.py` 里 `dbt.ref("fact_pool_weight_source")` 这行只用于让 dbt 的 DAG 分析能感知依赖顺序，实际读表仍是后面 `sibling_relation` 拼出来的路径，两者可能不一致。
