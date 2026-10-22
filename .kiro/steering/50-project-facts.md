---
inclusion: always
---

# 项目事实

## 项目概述  {#overview}

这个控制台目录（`~/data/my-kiro-cli`）存放 Kiro 配置（steering、skills），用于操控 `~/data` 下的多个项目仓库。`compass-app-jasper` 是量化研究平台主仓库，`compass-core` 是它唯一 submodule 的源仓库，两者共用本控制台的配置。fenghe-nn 的代码已并入 `compass-core` 的 `lib/fenghe-nn`。

## 仓库关系  {#repos}

| 仓库路径 | 角色 | 主分支 |
|---------|------|--------|
| `~/data/compass-app-jasper` | 主仓库（量化研究平台），含一个 submodule `core/` | — |
| `~/data/compass-core` | submodule `core/` 的源仓库（底层数值运算，含 `lib/fenghe-nn` 的 GPU 内核 / PyTorch 绑定） | `develop` |
| `~/data/fenghe-nn` | 历史独立仓库，代码已并入 `compass-core`，不再作为开发入口 | `develop` |
| `~/data/feature-lab` | 独立仓库（`FinAI-Project/feature-lab`），dbt (Snowflake) 项目，承担 Snowflake 侧的 model/test/hook/schema：RAW/STAGING/MARTS 分层建模股票参考、行情、基本面数据，`models/preprocess/` 下定义因子预处理四阶段模型（fill/normalize × cross-section/timing）与增量写入边界，`analyses/create_preprocess_procedure.sql` 创建调用 `preprocess_evaluate` 代码的存储过程 `FEATURELAB.PUBLIC.PREPROCESS_FACTORS` | `dev` |
| `~/data/preprocess_evaluate` | 独立仓库（`FinAI-Project/preprocess_evaluate`），含两个 submodule：`extern/fenghe`（源 `fenghe-nn`）、`extern/core`（源 `compass-core`）。提供因子预处理与评估的计算代码，有两条独立路径：本地路径由 `main.py`（Hydra 入口）驱动 `lib/_PreprocessingJob_.py` 对 Parquet 文件做因子处理与归一化（`lib/processor/`）；Snowflake 路径由 `snowflake_preprocess.py` 的存储过程入口 `mart_handler`（Snowpark）提供，供 `feature-lab` 的 dbt 模型调用，`orchestration.py` 负责按 rule 调用与增量边界。`scripts/build_bundle.py` 打包部署用 zip，上传路径与存储过程确认流程见 `docs/snowflake_preprocess.md`（完整数据流与数学说明见 `feature-lab` 仓库同名文档）。本地测试（含 `test/snowpark/` 下依赖 `snowflake.snowpark` 的用例）的 conda 环境名见 `.kiro/local-context.sh` 的 `CONDA_ENV_SNOWFLAKE`，与 jasper 等原有仓库用的 `CONDA_ENV` 是两个不同环境 | — |
| `~/data/test/` | 临时实验输出目录 | — |
| `~/data/exp/` | 持久化实验输出目录 | — |
| `~/data/review/<repo>/<branch>/` | review 输出目录，按仓库+分支分类，避免同名冲突 | — |

`compass-app-jasper/core/` 是 submodule，对应 `compass-core`，在 jasper 中是 detached HEAD 状态，`git checkout` 到具体 commit 才生效。submodule 联合开发流程见 `user-update-submodule` skill。

## 架构约束  {#architecture-constraints}

### 不在仓库内跑实验/测试  {#no-run-in-repo}

`[review]` 实验和测试一律在独立输出目录（`test/`、`exp/`）运行，禁止在仓库目录内直接运行——Hydra 等会生成 `outputs/`、`train/`、`merged/` 等产物污染仓库代码。运行前确认工作目录在仓库之外。

### Hydra 管理的工作通过配置，不硬编码  {#hydra-config-not-hardcode}

`[review]` 凡由 Hydra 负责的工作（实例化、超参设置等），其配置一律在 `app2/conf/` 下对应的 config group 中书写，禁止硬编码到代码中。需新增配置项而对应配置文件不存在时，先询问用户该配置应如何增加，不自行在代码里绕过 Hydra 配置体系。

### app2 是当前版本  {#app2-current}

新工作一律用 `app2/`，`app/` 是旧版 v3。

## 本机配置  {#local-context}

机器相关配置（conda 环境名、路径等）集中在本机文件 `.kiro/local-context.sh`，该文件不纳入版本控制（每台机器自建，模板见 `.kiro/local-context.sh.example`）。执行任何实验或测试前先读取该文件确认变量值，禁止把机器相关值硬编码进 steering、skill 或命令。命令自带环境激活前缀（如 `conda run -n $CONDA_ENV ...`），不依赖预先注入的环境。具体用法见 `user-run-experiment`、`user-run-tests` skill。

## Snowflake 访问  {#snowflake}

### 入口只有 snow CLI  {#snow-cli-only}

`snow`（Snowflake CLI）由 `uv tool` 独立安装，位于 conda 之外。人工查询、建表、传文件一律用 `snow sql` / `snow stage` 子命令，不写 Python 客户端脚本，也不给 `snow` 加 `conda run` 前缀——`preprocess_evaluate` 本地测试用到的 `snowflake-connector-python`/`snowflake-snowpark-python`（`.kiro/local-context.sh` 的 `CONDA_ENV_SNOWFLAKE` 环境）是该仓库测试代码的依赖，不改变这条访问入口的选择。

### 连接定义在本机 config.toml  {#snow-config}

连接与凭据在本机文件 `~/.config/snowflake/config.toml`（权限 600）——`~/.snowflake/` 不存在且 `SNOWFLAKE_HOME` 未设时，`snow` 读取该 XDG 路径。文件含明文口令与私钥路径：引用连接时只写连接名，禁止把其中的口令、私钥内容或其它取值复述进回复、仓库、steering、skill。

连接名用 `-c` 显式指定，取值见 `.kiro/local-context.sh` 的 `SNOWFLAKE_CONNECTION`（该文件用途见 #local-context）。该连接的定义里没有 database 与 schema，故对象名一律写全限定形式（`<db>.<schema>.<object>`），不依赖会话上下文；warehouse 由账号级用户默认值提供，不在命令里指定。

个人工作区是 `FEATURELAB` 库下以本人名字命名的 `DEV_<name>` schema，与他人 schema 并列；跨出该 schema 的写操作先与用户确认。

### preprocess_evaluate 的部署 stage  {#preprocess-evaluate-stage}

`preprocess_evaluate` 打包后的 zip（`scripts/build_bundle.py` 产出）实际被引用的位置是 `FEATURELAB.PUBLIC.FEATURE_LAB_PYTHON_STAGE`（`feature-lab` 仓库 `models/preprocess/*.py` 的 `imports=` 字段引用该路径下的 `preprocess_evaluate.zip`，具体列表以仓库代码为准）。个人工作区下同名/近似命名的 stage（如 `DEV_PEIRAN.STG_CODE`）与之无关，只是个人测试副本，排查部署版本时不要与之混淆。stage 不区分 git 分支，且该 stage 上的文件名是否带 commit 短 hash 后缀当前不一致（同时存在带后缀与不带后缀的版本），文件名或 `LIST` 的 `last_modified` 都不可作为版本依据，必须下载后与目标 commit 做 `git archive` 逐文件内容比对才能确认对应关系。

`DEV_PREPROCESS` schema 存放的是 dbt 构建出的 mart 层表/视图（`fact_stock_factor_*`、`fact_pool_weight_source` 等，定义见 `feature-lab` 仓库 `models/preprocess/`），不存放 zip，与上述 stage 是两个不相关的对象。

该 stage 上 zip 的命名习惯当前不统一：同时存在不带后缀的 `preprocess_evaluate.zip`（`imports=` 实际引用的文件名）和带 commit 短 hash 后缀的 `preprocess_evaluate-<短hash>.zip`（后者是 `scripts/build_bundle.py` 一度加入又移除的命名尝试遗留，见该脚本的 git 历史），无后缀版本不代表旧版本，需按上一条的内容比对方法确认。

### 密钥对认证当前不可用  {#snow-jwt-unavailable}

本机已生成 RSA 密钥对，但账号侧用户未注册公钥（`DESC USER` 的 `RSA_PUBLIC_KEY` 为空），故 `authenticator = "SNOWFLAKE_JWT"` 的连接必然报 JWT 无效。遇到该报错时不调参重试，改用口令连接，或请有权限者先注册公钥。
