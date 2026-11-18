# 部署代码到个人 schema

把某个库的一个 commit 打包上传到个人 `PYTHON_STAGE`，并建一个引用它的存储过程，供 dbt build 或直接调用使用。接口是 `scripts/deploy.sh <lib> <TAG> [<commit>]`，步骤与输出见脚本头部；它从 `git archive` 导出该 commit 打包，不需要检出、不受工作区改动影响。

## 库的登记

`deploy.sh` 按库登记打包命令、存储过程定义与 dbt 变量，目前只登记了 `preprocess_evaluate`。新增一个库（如 `evaluator_snowflake`、`feature_lab_weight`）时，先核对该库的打包脚本、`feature-lab` 中引用它的 `imports` 与变量名，以及该库的上传 CI，再在脚本里加一个分支；命名、构建、清理接口不需改动。

## 规则

- 官方包与个人包严格区分：官方包由 `preprocess_evaluate` 的 CI 在 push 到 `main`/`develop` 时上传到共享路径（`50-project-facts.md#preprocess-evaluate-stage`），禁止手动上传；个人包只放个人 `PYTHON_STAGE`，路径带 tag 与 commit 短 hash，与官方的 `current/` 路径分开。
- 每个 commit 一个存储过程，名字带 tag 与 hash，不覆盖已有的 `PREPROCESS_FACTORS`，避免不同 commit 的结果混在同一个名字下。
- 存储过程的 `PACKAGES` 跟随官方模板 `orchestration/create_preprocess_procedure.sql`；该库依赖版本变化时核对它的 `pyproject.toml` 并同步 `deploy.sh`。
- 判断某个 zip 对应哪个 commit，下载后与 `git archive <commit>` 的内容逐文件比对，不看文件名或时间（`knowledge/verified-facts.md` 的 Stage 一节）。
