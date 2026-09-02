#!/bin/bash
# Usage: run.sh <workdir> <make-arg>...
# Runs the app2 experiment inside <workdir>, backgrounded.
# Logs to <workdir>/run.log and writes the make PID to <workdir>/run.pid.
WORKDIR="$1"; shift
cd "$WORKDIR" || exit 1
HYDRA_FULL_ERROR=1 make -f "$HOME/data/compass-app-jasper/app2/Makefile" "$@" > run.log 2>&1 &
echo $! > run.pid
