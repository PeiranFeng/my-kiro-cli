#!/bin/bash
# Usage:
#   my_queries.sh list   [--warehouse <wh>]                 list the current user's RUNNING/QUEUED/BLOCKED queries
#   my_queries.sh cancel [--warehouse <wh>] <query_id>...   cancel the given queries, each only if the current user submitted it
# The connection is read from .kiro/local-context.sh (SNOWFLAKE_CONNECTION). --warehouse runs the lookup on that
# warehouse, which matters when the default one is saturated: INFORMATION_SCHEMA table functions need a warehouse.
set -u
source "$HOME/data/my-kiro-cli/.kiro/local-context.sh" >/dev/null 2>&1
ACTION="${1:-list}"; shift || true
WAREHOUSE=""
if [ "${1:-}" = "--warehouse" ]; then WAREHOUSE="$2"; shift 2; fi
USE=""
[ -n "$WAREHOUSE" ] && USE="use warehouse \"$WAREHOUSE\";"
ACTIVE="execution_status in ('RUNNING', 'QUEUED', 'BLOCKED', 'RESUMING_WAREHOUSE')"
HISTORY="table(information_schema.query_history_by_user(user_name => current_user(), result_limit => 10000))"

case "$ACTION" in
  list)
    snow sql -c "$SNOWFLAKE_CONNECTION" -q "$USE
      select query_id, session_id, warehouse_name, role_name, execution_status, start_time,
             left(regexp_replace(query_text, '\\\\s+', ' '), 120) as query
      from $HISTORY where $ACTIVE order by start_time"
    ;;
  cancel)
    [ "$#" -gt 0 ] || { echo "cancel needs at least one query_id" >&2; exit 1; }
    for id in "$@"; do
      [[ "$id" =~ ^[0-9a-f-]+$ ]] || { echo "not a query id: $id" >&2; exit 1; }
    done
    ids=$(printf "'%s'," "$@"); ids="${ids%,}"
    # Cancel only ids that are the current user's and still active; anything else is reported and left alone.
    snow sql -c "$SNOWFLAKE_CONNECTION" -q "$USE
      select query_id, execution_status, system\$cancel_query(query_id) as result
      from $HISTORY where query_id in ($ids) and $ACTIVE;
      select column1 as query_id, 'not cancelled: not an active query of the current user' as result
      from values $(printf "('%s')," "$@" | sed 's/,$//')
      where column1 not in (select query_id from $HISTORY where $ACTIVE)"
    ;;
  *)
    echo "unknown action: $ACTION (list | cancel)" >&2; exit 1
    ;;
esac
