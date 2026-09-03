#!/bin/bash
# Usage: bg.sh <workdir> <command...>
# 把任意命令挂后台运行，日志写 <workdir>/run.log，命令 PID 写 <workdir>/run.pid。
# 通用后台入口：不关心跑的是什么，仅负责后台化 + 日志重定向 + 记录 PID。
# 任务结束不会通知 Kiro（无信号通路）；查状态用 `kill -0 $(cat run.pid)` 主动探测，看结果读 run.log。
WORKDIR="$1"; shift
cd "$WORKDIR" || exit 1
"$@" > run.log 2>&1 &
echo $! > run.pid
