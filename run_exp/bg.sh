#!/bin/bash
# Usage: bg.sh <workdir> <command...>
# 把任意命令挂后台运行，日志写 <workdir>/run.log，命令 PID 写 <workdir>/run.pid。
# 通用后台入口：不关心跑的是什么，仅负责后台化 + 日志重定向 + 记录 PID。
# 与 wait.sh 配合监控（wait.sh 带 PID 存活检查，进程被 kill 也能正确退出）。
WORKDIR="$1"; shift
cd "$WORKDIR" || exit 1
"$@" > run.log 2>&1 &
echo $! > run.pid
