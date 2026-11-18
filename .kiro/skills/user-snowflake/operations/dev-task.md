# DEV 任务：只读状态与历史，以及经同意后的手动运行

DEV 的任务图（`CORE` → `PREPROCESS` → `EVALUATOR`、`PREPROCESS_STATS_DISPATCH`，统计检查是独立的根任务）定义在 `feature-lab` 的 `orchestration/create_tasks.sql`，调度时间以 `SHOW TASKS IN SCHEMA FEATURELAB.DEV` 的 `schedule` 为准。接口是 `scripts/dev_task.py`（用法见脚本头部），走 `dev_op` 连接（`SKILL.md` 的连接表）。

## 默认只读

默认只做两件事：读任务状态（`dev_task.py status`、`run` 不加 `--execute` 的预检）与读历史（`TASK_HISTORY`、查询历史、dbt 日志，见 `incident/investigation.md`）。只读操作随时可做，不需要事先确认。

## 手动运行 DEV

手动运行 `FEATURELAB.DEV.CORE` 会重建整个 DEV，其他共同开发者此刻读的 DEV 表随之改变，所以它要在用户与相关开发者线下充分讨论之后才决定。执行前按顺序完成：

1. **调查后果**：用 `dev_task.py run`（不加 `--execute`）预检，得到是否有任务图在执行、距下一次定时运行多久、上一次完整运行持续多久；再列出这次运行会重建什么、谁会受影响（DEV 上依赖这些表的开发与检查），以及失败时 DEV 停在什么状态（`dbt build` 不是整体事务，部分表会先被更新，见 `knowledge/snowflake-guide.md#release-evidence-recovery`）。
2. **向用户说明必要性**：为什么不能等定时运行，等待的代价是什么。
3. **得到用户明确同意，或用户直接要求运行**，才执行。
4. **临近定时运行时先劝阻**：下一次定时运行开始前，手动运行若还来不及结束（预检里"距下一次定时运行"短于"上一次完整运行持续时间"），向用户说明这一点并建议不要手动运行，等定时运行即可；用户知道这一信息后再次明确要求，才以 `--near-schedule-confirmed` 执行。
5. 执行 `dev_task.py run --execute`。脚本在有任务图执行中时拒绝运行（DBA 给出的防重入检查）。

DBA 给的原始 SQL 以 `USE ROLE FEATURELAB_DEV_OP` 开头；`dev_op` 连接的令牌已把会话限定在这个角色，令牌会话不允许 `USE ROLE`/`USE SECONDARY ROLES`，所以脚本只执行其中的检查与 `EXECUTE TASK`。

## 运行之后

- 用 `dev_task.py status` 跟踪，结局从 `TASK_HISTORY` 读；要看 dbt 层面的细节，按 `incident/investigation.md` 取 dbt 日志。
- 两个统计检查 task 目前每次运行都以 `FAILED` 结束（阈值问题见 feature-lab #223），在该问题解决前，它们的失败不代表这次构建失败。
- Deploy（`feature-lab` 的 `deploy.yaml`）运行期间会先暂停任务再恢复，此时 `CORE` 显示为 `suspended`、没有排定的下一次运行，预检里的距离为空；等 Deploy 结束再判断。
