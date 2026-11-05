#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly WORKSPACE_DIR="$(cd -- "$SCRIPT_DIR/../../../.." && pwd)"
readonly CORRESPONDENCE_DIR="${AGENT_CORRESPONDENCE_DIR:-$WORKSPACE_DIR/.kiro/agent-correspondence}"
readonly MESSAGES_DIR="$CORRESPONDENCE_DIR/messages"
readonly ACTIVE_STATE_DIR="$CORRESPONDENCE_DIR/state/active"
readonly RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}/kiro-agent-correspondence-${UID}"
readonly INTERVAL_SECONDS=10

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

readonly STATE_FILE="$ACTIVE_STATE_DIR/$work_id.md"
readonly PID_FILE="$RUNTIME_DIR/$work_id.pid"
readonly MESSAGE_FILENAME_PATTERN='^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{9}Z\.md$'

frontmatter_value() {
    local key="$1"
    local file="$2"

    awk -v key="$key" '
        $0 == "---" { delimiters += 1; next }
        delimiters == 1 && index($0, key ": ") == 1 {
            value = substr($0, length(key) + 3)
            sub(/^"/, "", value)
            sub(/"$/, "", value)
            print value
            exit
        }
        delimiters >= 2 { exit }
    ' "$file"
}

watcher_matches_pid() {
    local pid="$1"
    local command_line

    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    [[ -r "/proc/$pid/cmdline" ]] || return 1
    command_line="$(tr '\0' ' ' < "/proc/$pid/cmdline")"
    [[ "$command_line" == *watch-receive.sh* && "$command_line" == *"--work-id $work_id"* ]]
}

umask 077
mkdir -p -- "$RUNTIME_DIR"
chmod 700 -- "$RUNTIME_DIR"

if [[ -f "$PID_FILE" ]]; then
    existing_pid="$(<"$PID_FILE")"
    if watcher_matches_pid "$existing_pid"; then
        printf 'Receive watcher already running for %s with PID %s\n' "$work_id" "$existing_pid" >&2
        exit 1
    fi
    rm -f -- "$PID_FILE"
fi

printf '%s\n' "$$" > "$PID_FILE"

cleanup() {
    if [[ -f "$PID_FILE" && "$(<"$PID_FILE")" == "$$" ]]; then
        rm -f -- "$PID_FILE"
    fi
}
trap cleanup EXIT
trap 'exit 0' INT TERM

last_notified=""
while true; do
    [[ -f "$STATE_FILE" ]] || exit 0

    lifecycle="$(frontmatter_value lifecycle "$STATE_FILE")"
    case "$lifecycle" in
        active|blocked) ;;
        *) exit 0 ;;
    esac

    last_read_file="$(frontmatter_value last_read_file "$STATE_FILE")"
    if [[ "$last_read_file" != none && ! "$last_read_file" =~ $MESSAGE_FILENAME_PATTERN ]]; then
        printf 'Invalid last_read_file in %s\n' "$STATE_FILE" >&2
        exit 2
    fi

    if [[ -z "$last_notified" || ( "$last_read_file" != none && "$last_read_file" > "$last_notified" ) ]]; then
        last_notified="$last_read_file"
    fi

    new_files=()
    if [[ -d "$MESSAGES_DIR" ]]; then
        while IFS= read -r message_file; do
            message_name="${message_file##*/}"
            [[ "$message_name" =~ $MESSAGE_FILENAME_PATTERN ]] || continue
            if [[ "$last_notified" == none || "$message_name" > "$last_notified" ]]; then
                new_files+=("$message_name")
            fi
        done < <(find "$MESSAGES_DIR" -maxdepth 1 -type f -name '*.md' -mmin -1440 -printf '%f\n' | LC_ALL=C sort)
    fi

    if ((${#new_files[@]} > 0)); then
        printf 'agent-correspondence: new message files for %s: %s\n' "$work_id" "$(IFS=,; printf '%s' "${new_files[*]}")"
        last_notified="${new_files[${#new_files[@]} - 1]}"
    fi

    sleep "$INTERVAL_SECONDS"
done
