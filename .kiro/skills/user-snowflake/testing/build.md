# 在个人 schema 跑 dbt build

## 执行前确认

1. **分支与 tag**：确定 `feature-lab` 与 `preprocess_evaluate` 各自要测的分支和 commit，以及 test tag。优先从当前任务推断（正在开发或 review 的分支、PR 的 head 分支、上一次同类运行记录在 `run.json` 里的分支），推断不出再问用户；把推断结果告诉用户并得到确认，再把 `feature-lab` 检出到该分支。
2. **上游环境**：defer 读 DEV 还是 PROD 的上游（`--upstream`）。验证未合并的改动默认 DEV。
3. **warehouse 与在跑的查询**：同一目标仍有 `RUNNING` 的查询时不启动新的 build（`scripts/my_queries.sh list`）。

## 通用 build：defer 只读上游

```bash
dbt build --target personal --select <model>+ --defer --state <manifest 目录> --favor-state
```

- manifest 用 `dbt parse --target <dev|prod> --no-partial-parse --target-path <仓库外目录>` 在本机生成，它只提供上游 relation 的解析结果，不证明上游已部署；上游不存在时 build 报错，等部署后重跑。需要证明 PROD 已部署时，按 `feature-lab/AGENTS.md` 从 Snowsight 下载真实构建过的 manifest。
- `--favor-state` 不可省：个人 schema 里有同名旧表时，缺了它会读到旧表。
- `--target-path`、`--log-path` 指向仓库外的 tag 本地目录（`testing/naming.md`），dbt 产物不留在仓库里。
- 能否 defer 看依赖的声明方式：`ref()` 可以；按名字拼表名的（`sibling_relation` 等）必须在当前 schema 里实际存在，见 `survey/preprocess-layer.md`。

## preprocess 层：用接口

验证 `preprocess_evaluate` 或 `feature-lab` 的改动，一律在个人 schema 整层 `--full-refresh` 构建 preprocess 层，由此同时得到联调结果和每个 model 的耗时；不绕过 dbt 直接 `CALL` 存储过程（那只用于复现单个报错，见 `incident/investigation.md`）。

接口是 `scripts/preprocess_build.py`（用法、判定规则与产物见脚本头部）。一个版本是一对（feature-lab rev，preprocess_evaluate rev），两个仓库都从 git 导出或部署，不依赖工作区：

- 每次 build 都读一份上游快照：该层直接 `ref()` 的层外 relation 固定成带 tag 的表（表 clone、view 物化），defer 的 state 改写为指向快照。快照随 tag 保存，供同一 tag 的后续 build 复用。
- `build <TAG> [--fl <rev>] [--pe <rev>] [--snapshot <id>]`：构建一个版本，把整层输出 clone 成带 tag 与 build id 的表，记录性能（`testing/compare.md` 的性能一节）。只看性能或联调时用它。
- `verify <TAG> [--base-fl] [--base-pe] [--new-fl] [--new-pe]`：一致性对比，按 `testing/compare.md` 的复用规则选出最少的 build 次数。
- **`verify` 尚未端到端实测**（截至 2026-11-18，只单独验证过快照的生成、state 改写后的 defer 重定向与兼容判断）：第一次实跑时逐步核对方案选择、两次 build 与比对的结果；跑通且无问题后删除本条，发现问题则修正脚本与本文后再删除。
- 加 `--background` 后台运行，监控按 `user-run-experiment` skill 的「监控后台任务」：完成正则 `BUILD DONE|VERIFY DONE`，错误正则 `^FAILED:`。

## 运行中与中断后

- Python model 的 build 可长时间无日志、无最终 `run_results.json`，这只说明存储过程未返回，不说明失败（`knowledge/verified-facts.md` 的 dbt 一节）。
- 本地进程中断后先查 `QUERY_HISTORY_BY_USER` 中该 model 或过程的记录，核对状态与时间，不直接重跑；仍有 `RUNNING` 时只读等待它进入终态。
- 取消查询前向用户展示完整 query id、提交用户与角色并得到确认；一个 Python model 的三层查询一起取消。
- 测试失败（`FAIL <n>`）不中止构建，结束后按 `run_results.json` 判断，并在汇报中单独列出。
