---
name: user-run-experiment
description: compass-app-jasper 实验的运行、后台监控、停止、实验目录文档规范，以及 GitHub Actions / k8s 上实验产物的观察方式。当用户要求跑实验、监控实验、停止实验或分析实验产物时使用。
---

# user-run-experiment

compass-app-jasper 实验的完整流程。运行前先读 `.kiro/local-context.sh` 取 `CONDA_ENV` 等机器相关变量（见 `50-project-facts.md#local-context`）。实验和测试一律在仓库外的独立目录运行（见 `50-project-facts.md#no-run-in-repo`）。

## 副作用封装原则

实验的后台运行、日志重定向、PID 记录、轮询等副作用封装在 `run_exp/` 脚本内，调用方只发单条命令，保证可自动化、可复现。`run.sh` 首参是工作目录，脚本自己 cd 进去、后台运行、写 `run.log` 与 `run.pid`。

## 运行实验

必须通过 `run_exp/run.sh`，禁止直接调用子 Makefile。`CONFIG_NAME`、`DATA_SOURCE_PATH`、`BACKTEST`、`SEEDS`、`OVERRIDE` 等参数的取值与配置一律参见 `app2/README.md`。临时验证 → `test/`；持久化 → `exp/`；先创建 `description.md`。

```bash
mkdir -p ~/data/test/<exp-dir>
conda run -n $CONDA_ENV --no-capture-output bash ~/data/my-kiro-cli/run_exp/run.sh ~/data/test/<exp-dir> <参见 README 的参数>
```

OVERRIDE 中每个参数必须确认存在于 `conf/` 下的 yaml，且使用从对应 config group 顶层开始的完整 Hydra 路径，不省略中间层级。seed 覆盖时该 key 已存在于配置中，直接赋值，不加 `+` 前缀（`+` 用于新增不存在的 key，加在已存在的 key 上会报重复 key 错误）。

## 查看实验状态

Kiro 无后台任务完成通知机制：任务结束不会主动告知 agent，也没有可对标 Claude Code monitor 的工具。判断"是否结束"只能主动探测，不要写脚本阻塞等待（阻塞等待等价于前台运行，失去后台的意义）：

```bash
kill -0 "$(cat ~/data/test/<exp-dir>/run.pid)" 2>/dev/null && echo running || echo finished
```

这条命令瞬间返回、不占会话。何时探测由用户下一轮交互驱动。看结果读 `run.log`。进程被 OOM kill 或信号终止时不写 log 或标志文件，故判断结束以 `kill -0`（进程存活检查）为准，不靠 log/标志匹配。

## 停止实验

从 `run.pid` 取 PID、查 PGID、按进程组 kill：

```bash
cat ~/data/test/<exp-dir>/run.pid    # -> <PID>
ps -o pgid= -p <PID>                 # -> <PGID>
kill -- -<PGID>
```

## 实验目录文档规范

每个实验目录下维护 `description.md`（创建或重启实验时更新）：

```markdown
# <实验名>

**目的**：
**分支**：
**关键参数**：
**预期验证**：
```

重复运行实验时保留 `description.md`，只删实验产物（`train/`、`merged/`、`outputs/`、`run.log`、`windows/`）。

## 分析实验前

分析实验前必须先读 `compass-app-jasper/app2/README.md` 了解输出目录层级，不对目录结构做假设。

## TensorBoard

```bash
conda run -n $CONDA_ENV tensorboard --logdir ~/data/exp --port 6006 --bind_all
```

## GitHub Actions / k8s 实验产物

GitHub Actions 触发的实验，代码同样来自 compass-app-jasper 仓库，输出目录结构与本地大同小异，差异仅在所跑分支不同。最终产物同步到 `/output/` 下，批次目录默认为当月（如 `2026-05`），目录内每个实验命名为 `<branch>-<run-id>-<job>`。找不到某 run-id 的条目时，可能是产物尚未同步，而非实验未运行。

当前机器是否受 k8s 调度，以 `kubectl get po` 能否执行为准：

- 能执行 → 当前机器接收 k8s 调度，可直接观察运行中的实验：
  - 找实验：`kubectl get po` 列出所有 pod，pod 名即「实验名（与 git action 一致，含 run-id）+ k8s 随机后缀」；`STATUS` 为 `Running` 进行中，`Completed` 已结束。
  - 从 Actions run 链接对齐 pod：pod 名（及 `/output` 产物名）里的 `<run-id>` 是 Actions 的 run number（页面显示为 `#N`）。用 `gh run list --repo <repo> --branch <branch> --json number,databaseId` 取 `number` 字段，对齐到 pod 名前缀 `<branch>-<number>-<job>`。
  - 看日志/中间产物：实验在 pod 内工作目录是 `/tmp/runner`（不是 `/output`），实时日志 `kubectl exec <pod> -- tail -f /tmp/runner/output.log`。`/tmp/runner` 内输出层级随分支而异，以对应分支代码（makefile）为准。
  - 同步时机：运行期间 `/output` 为空；所有窗口完成后，由 `rclone-output-*` pod 将 `/tmp/runner` 结果 rclone 同步到 `/output/<批次>/`。
- 不能执行 → 当前机器不受 k8s 调度，无法观察运行中实验，只能被动等结果同步到 `/output` 后再分析。
