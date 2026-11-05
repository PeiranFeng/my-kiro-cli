#!/usr/bin/env bash
set -euo pipefail

readonly RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}/kiro-agent-correspondence-${UID}"

work_id=""

usage() {
    printf 'Usage: %s --work-id <work-id>\n' "${0##*/}" >&2
}

while (($# > 0)); do
    case "$1" in
        --work-id)
            (($# >= 2)) || { usage; exit 2; }
            work_id="$2"
            shift 2
            ;;
        *)
            usage
            exit 2
            ;;
    esac
done

[[ "$work_id" =~ ^[a-z0-9_][a-z0-9_-]*$ ]] || {
    printf 'Invalid work_id: %s\n' "$work_id" >&2
    exit 2
}

pid_file="$RUNTIME_DIR/$work_id.pid"
[[ -f "$pid_file" ]] || exit 0

pid="$(<"$pid_file")"
if [[ ! "$pid" =~ ^[0-9]+$ || ! -r "/proc/$pid/cmdline" ]]; then
    rm -f -- "$pid_file"
    exit 0
fi

command_line="$(tr '\0' ' ' < "/proc/$pid/cmdline")"
if [[ "$command_line" != *watch-receive.sh* || "$command_line" != *"--work-id $work_id"* ]]; then
    rm -f -- "$pid_file"
    exit 0
fi

kill -TERM "$pid"
