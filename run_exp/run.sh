#!/bin/bash
# Usage: [PROGRAM=<repo root>] run.sh <workdir> <make-arg>...
# Runs the app2 experiment inside <workdir>, backgrounded.
# PROGRAM selects the repo (worktree) whose app2/Makefile is used.
# Logs to <workdir>/run.log and writes the make PID to <workdir>/run.pid.
WORKDIR="$1"; shift
PROGRAM="${PROGRAM:-$HOME/data/compass-app-jasper}"
cd "$WORKDIR" || exit 1
HYDRA_FULL_ERROR=1 make -f "$PROGRAM/app2/Makefile" "$@" > run.log 2>&1 &
echo $! > run.pid
