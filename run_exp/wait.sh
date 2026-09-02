#!/bin/bash
# Usage: wait.sh <PID> [flag-file]
# 阻塞到 <PID> 退出，或 [flag-file]（若给了）出现为止，每 5s 轮询一次。
# 退出条件同时覆盖“完成标志出现”和“进程已死”——进程被 OOM kill / 信号终止时
# 不会写 log 或标志文件，故必须带 PID 存活检查，否则单靠标志会永远不退出。
PID="$1"; FLAG="$2"
until [ -n "$FLAG" ] && [ -f "$FLAG" ] || ! kill -0 "$PID" 2>/dev/null; do
  sleep 5
done
echo "[wait] pid $PID exited (flag=${FLAG:-none})"
