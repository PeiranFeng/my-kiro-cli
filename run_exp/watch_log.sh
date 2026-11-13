#!/bin/bash
# Usage: watch_log.sh <log> <done regex> <error regex> <max seconds> [pid file] [exit-code file]
# Blocks until one outcome holds, prints only the lines that decide it, and exits:
#   0  the done regex matched (prints the matching line, and the exit-code file's content when given)
#   2  the error regex matched (prints up to 5 matching lines)
#   3  nothing decided within max seconds
#   4  the pid file's process is gone without a done match (crash, OOM kill, signal)
# ANSI colour codes are stripped before matching. The error regex wins over the done regex.
LOG="$1"; DONE="$2"; ERR="$3"; MAX="$4"; PIDFILE="${5:-}"; CODEFILE="${6:-}"
start=$(date +%s)
plain() { sed 's/\x1b\[[0-9;]*m//g' "$LOG" 2>/dev/null; }
while true; do
  hit=$(plain | grep -E "$ERR" | head -5)
  if [ -n "$hit" ]; then echo "$hit"; exit 2; fi
  hit=$(plain | grep -E "$DONE" | tail -1)
  if [ -n "$hit" ]; then
    echo "$hit"
    if [ -n "$CODEFILE" ] && [ -f "$CODEFILE" ]; then echo "exit code: $(cat "$CODEFILE")"; fi
    exit 0
  fi
  if [ -n "$PIDFILE" ] && [ -f "$PIDFILE" ] && ! kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "process $(cat "$PIDFILE") exited without a done match; last lines:"
    plain | tail -3
    exit 4
  fi
  if [ $(( $(date +%s) - start )) -ge "$MAX" ]; then echo "no outcome after ${MAX}s"; exit 3; fi
  sleep 30
done
