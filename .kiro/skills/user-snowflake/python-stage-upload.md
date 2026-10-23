# 手动上传 Python zip 到 PYTHON_STAGE

`preprocess_evaluate`、`evaluator_snowflake`、`feature_lab_weight` 等 Snowpark Python model 依赖的库以 zip 包形式放在 Snowflake stage 上，`models/preprocess/*.py` 等文件的 `imports=` 字段引用该路径。本文以 `preprocess_evaluate` 为例记录手动上传这类 zip 到个人 schema 时的命名与路径规范——"个人上传带 commit hash、和官方包区分"这条原则对三个库都适用，但具体的打包脚本调用方式、`imports=`/存储过程覆盖用的变量名、路径拼接规则，仅在 `preprocess_evaluate` 上验证过；给 `evaluator_snowflake`/`feature_lab_weight` 操作前先对照各自的 `models/*/_*.yml` 配置和打包脚本确认对应命令，不要直接套用下面的命令。

## 官方固化包与个人上传包严格区分

`preprocess_evaluate` 仓库的 `.github/workflows/snowflake-upload.yaml` 在 push 到 `main`/`develop` 时自动打包并上传到官方共享路径 `FEATURELAB.PUBLIC.FEATURE_LAB_PYTHON_STAGE`，文件名不带 commit 短 hash（即 `imports=` 默认引用的 `preprocess_evaluate/current/preprocess_evaluate.zip`）。**正式开发和生产环境已禁止手动上传到这个共享路径**，官方包的更新只能通过 push 到这两个 branch 触发 CI。这条 CI 和禁手动上传的约束目前只确认了 `preprocess_evaluate` 一个库，`evaluator_snowflake`/`feature_lab_weight` 是否有同等 CI、是否同样禁止手动上传正式路径，需要分别查各自仓库的 `.github/workflows/`，不能假定一致。

个人在自己的 `DEV_<USER>` schema 下的 `PYTHON_STAGE` 手动上传 zip 不受这条限制（这是自己的 schema，不影响他人）。个人上传的文件名必须带 commit 短 hash 后缀（如 `preprocess_evaluate-<短hash>.zip`），和官方固化包的命名规则（不带后缀）严格区分，避免个人临时产物被误认成官方发布版本。

## 上传命令

本地打包用 `preprocess_evaluate` 仓库自己的 `scripts/build_bundle.py`（输出路径必须在仓库外，见该脚本 docstring）。该脚本只依赖标准库（`argparse`/`zipfile`/`pathlib`），直接用仓库已配置的 conda 环境（`CONDA_ENV`，见 `.kiro/local-context.sh`）运行，不要用 `uv run`——`uv run` 会先把 `pyproject.toml` 声明的全部依赖（含 torch/CUDA 相关包，数百 MB 到数 GB）解析安装一遍，只为跑这一个不需要这些依赖的脚本：

```bash
cd ~/data/preprocess_evaluate
git fetch origin && git switch develop && git pull --ff-only origin develop
HASH=$(git rev-parse --short HEAD)
conda run -n "$CONDA_ENV" python scripts/build_bundle.py \
  --output ~/data/test/preprocess_evaluate-build/preprocess_evaluate.zip
```

上传到个人 `PYTHON_STAGE`，路径带上这个 `$HASH`。`snow stage copy` 的目标参数是目录而非文件路径（上传后文件名固定跟随本地源文件名），destination 只写到 hash 这一层，不要在末尾再拼一次文件名——拼了会在 stage 上多出一层同名子目录（如 `preprocess_evaluate.zip/preprocess_evaluate.zip`）：

```bash
snow stage copy -c "$SNOWFLAKE_CONNECTION" \
  ~/data/test/preprocess_evaluate-build/preprocess_evaluate.zip \
  "@FEATURELAB.DEV_<USER>.PYTHON_STAGE/preprocess_evaluate/${HASH}"
```

上传后用 `snow stage list-files` 核对实际落地路径是 `.../preprocess_evaluate/${HASH}/preprocess_evaluate.zip`，不是多一层嵌套。

## 让 model 引用个人上传的 zip

`models/preprocess/_preprocess_models.yml` 里 `imports=` 默认表达式是 `'@' ~ target.database ~ '.' ~ target.schema ~ '.PYTHON_STAGE/preprocess_evaluate/current/preprocess_evaluate.zip'`，硬编码了 `current/preprocess_evaluate.zip` 这个路径。要让 `personal` target 指向个人上传的带 hash zip，用 `--vars` 覆盖该变量，不要把官方包命名规则（不带 hash、`current/` 路径）复制到个人 schema 下——否则下次排查版本时又会分不清是官方包还是个人临时包：

```bash
dbt build --target personal --vars '{
  preprocess_bundle: "@FEATURELAB.DEV_<USER>.PYTHON_STAGE/preprocess_evaluate/<短hash>/preprocess_evaluate.zip",
  preprocess_procedure: "FEATURELAB.DEV_<USER>.PREPROCESS_FACTORS_<短hash>"
}' ...
```

## 存储过程也要带 commit hash 后缀，不能复用已有的 PREPROCESS_FACTORS

个人 schema 下首次测试 `preprocess` 层时可能已经创建过 `PREPROCESS_FACTORS`（见 `personal-schema-testing.md`），但那是之前某次测试遗留的版本，内部 `IMPORTS` 指向的 zip commit 和这次要测的不一定一致。测试不同 commit 时新建一个带 hash 后缀的存储过程，不要 `CREATE OR REPLACE` 覆盖已有的 `PREPROCESS_FACTORS`——否则旧测试结果和新测试结果会混在同一个过程名下，无法区分。

`feature-lab` 仓库 `orchestration/create_preprocess_procedure.sql`（以及 `preprocess_evaluate` 仓库同名文件）是官方部署用的模板，带 `&{role}`/`&{schema}` 占位符和 ownership 检查（拒绝替换非本角色拥有的过程），个人测试不套用这个模板，直接手写一份简化版，过程名和 `IMPORTS` 都带上同一个 hash：

```sql
CREATE PROCEDURE FEATURELAB.DEV_<USER>.PREPROCESS_FACTORS_<短hash>(
    CONFIG_NAME VARCHAR, RULE_ID NUMBER, STAGE VARCHAR,
    DATE_START DATE, DATE_END DATE, SRC_TABLE VARCHAR, WEIGHT_TABLE VARCHAR
)
RETURNS TABLE ()
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
ARTIFACT_REPOSITORY = snowflake.snowpark.pypi_shared_repository
PACKAGES = ('snowflake-snowpark-python', 'pandas==2.3.3', 'numpy==2.4.6',
            'scipy==1.17.1', 'pyarrow==25.0.1', 'pyyaml==6.0.3', 'hydra-core==1.3.2')
HANDLER = 'snowflake_preprocess.mart_handler'
IMPORTS = ('@FEATURELAB.DEV_<USER>.PYTHON_STAGE/preprocess_evaluate/<短hash>/preprocess_evaluate.zip')
EXECUTE AS CALLER;
```

`PACKAGES` 版本号跟随官方模板当前记录的值，若 `preprocess_evaluate` 的依赖版本有变化需要核对该仓库的 `pyproject.toml`/`requirements.txt`。建完之后 `dbt build` 的 `--vars` 里的 `preprocess_procedure` 要指向这个带 hash 的过程名（见上一节）。

## zip 内容对应哪个 commit，不能靠文件名或时间判断

`FEATURELAB.PUBLIC.FEATURE_LAB_PYTHON_STAGE` 上历史遗留的文件名/命名习惯不统一（曾经存在带 hash 和不带 hash的版本混存，是 `scripts/build_bundle.py` 命名尝试变更的遗留），文件名或 `LIST` 的 `last_modified` 都不可作为版本依据。确认 zip 对应的源码版本，必须下载后与目标 commit 做内容比对：

1. 下载目标 zip 到临时目录（`~/data/test/` 下）并解压。
2. 对候选 commit 执行 `git archive <commit> | tar -x -C <临时目录>`，导出该 commit 的内容到另一临时目录。
3. 逐文件比对两个目录（`diff -r`），内容一致才能确认对应关系。

个人 role（如 `FEATURELAB_PERSONAL_<USER>`）通常没有 `FEATURELAB.PUBLIC` schema 的权限，无法直接 `LIST`/`GET` 官方共享 stage 上的文件——这是预期的隔离设计，遇到该报错不代表配置错误，需要本地重新打包而不是尝试从官方 stage 复制。

`DEV_PREPROCESS`（dev target 构建产物所在 schema）等 mart 层 schema 不存放 zip，与 `PYTHON_STAGE` 是两个不相关的对象，排查部署版本时不要混淆。
