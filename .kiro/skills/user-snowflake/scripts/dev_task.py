"""Read DEV's task state and history, and start the DEV CORE task graph, on the FEATURELAB_DEV_OP connection.

Usage: python3 dev_task.py status [--days <n>]     read-only: tasks, current graphs, recent graph runs
       python3 dev_task.py run                     read-only preflight: what a run would meet; starts nothing
       python3 dev_task.py run --execute [--near-schedule-confirmed]
                                                   preflight, then EXECUTE TASK FEATURELAB.DEV.CORE

The connection is SNOWFLAKE_CONNECTION_DEV_OP of .kiro/local-context.sh, whose token is restricted to
FEATURELAB_DEV_OP, so no USE ROLE is issued. A run is refused while a CORE graph or a statistics check is executing
(the DBA's guard), and while the next scheduled CORE run starts sooner than the last complete graph run lasted,
unless --near-schedule-confirmed is given: a manual run then would still be executing when the schedule fires.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sf  # noqa: E402

ROOTS = ("CORE", "PREPROCESS_STATS_CHECK_CROSS_SECTION", "PREPROCESS_STATS_CHECK_TIMING")


def q(text: str) -> list[dict]:
    if not sf.DEV_OP_CONNECTION:
        raise SystemExit("SNOWFLAKE_CONNECTION_DEV_OP is not set in .kiro/local-context.sh")
    return sf.sql(text, connection=sf.DEV_OP_CONNECTION)


def when(text):
    return datetime.fromisoformat(text.replace(" -", "-").replace(" +", "+")) if text else None


def current_graphs() -> list[dict]:
    roots = ", ".join(f"'{r}'" for r in ROOTS)
    return q("select root_task_name, state, scheduled_time::varchar as scheduled, query_start_time::varchar as started "
             "from table(FEATURELAB.INFORMATION_SCHEMA.CURRENT_TASK_GRAPHS(RESULT_LIMIT => 10000)) "
             f"where database_name = 'FEATURELAB' and schema_name = 'DEV' and root_task_name in ({roots})")


def graph_runs(days: int) -> list[dict]:
    """Return each finished graph run of the last `days` days: its tasks, states, start and end."""
    rows = q("select graph_run_group_id g, name, state, scheduled_time::varchar s, query_start_time::varchar b, "
             "completed_time::varchar c, left(error_message, 160) e from table(FEATURELAB.INFORMATION_SCHEMA.TASK_HISTORY("
             f"SCHEDULED_TIME_RANGE_START => dateadd('day', -{days}, current_timestamp()), RESULT_LIMIT => 10000)) "
             "where database_name = 'FEATURELAB' and schema_name = 'DEV' and completed_time is not null order by s")
    runs = {}
    for r in rows:
        runs.setdefault(r["G"], []).append(r)
    return list(runs.values())


def core_duration(runs) -> float | None:
    """Seconds from the start of the last complete CORE graph run to its last task's end."""
    complete = [run for run in runs if any(t["NAME"] == "CORE" for t in run)]
    if not complete:
        return None
    run = complete[-1]
    start = min(when(t["B"] or t["S"]) for t in run)
    end = max(when(t["C"]) for t in run)
    return (end - start).total_seconds()


def status(days: int):
    for t in q("show tasks in schema FEATURELAB.DEV"):
        after = " after " + t["predecessors"].replace("\n", "").replace(" ", "") if t["predecessors"] != "[]" else ""
        print(f"task {t['name']}: {t['state']}, schedule {t['schedule']}{after}")
    for g in current_graphs():
        print(f"graph {g['ROOT_TASK_NAME']}: {g['STATE']}, scheduled {g['SCHEDULED']}, started {g['STARTED']}")
    for run in graph_runs(days):
        print("run:")
        for t in run:
            print(f"  {t['NAME']}: {t['STATE']} {t['B'] or t['S']} -> {t['C']}" + (f"  {t['E']}" if t["E"] else ""))


def run(execute: bool, near_confirmed: bool):
    graphs = current_graphs()
    executing = [g for g in graphs if g["STATE"] == "EXECUTING"]
    scheduled = [when(g["SCHEDULED"]) for g in graphs if g["ROOT_TASK_NAME"] == "CORE" and g["STATE"] == "SCHEDULED"]
    duration = core_duration(graph_runs(3))
    now = datetime.now(timezone.utc)
    to_next = (min(scheduled) - now).total_seconds() if scheduled else None
    print(f"executing graphs: {[g['ROOT_TASK_NAME'] for g in executing]}")
    print(f"next scheduled CORE run: {min(scheduled) if scheduled else None}, in {to_next and round(to_next / 60)} min")
    print(f"last complete CORE graph run lasted {duration and round(duration / 60)} min")
    if executing:
        raise SystemExit("refused: a DEV CORE run or statistics check is still executing")
    near = to_next is not None and duration is not None and to_next < duration
    if near:
        print("the next scheduled run starts before a manual run started now would finish")
    if not execute:
        print("preflight only: nothing started")
        return
    if near and not near_confirmed:
        raise SystemExit("refused: near the scheduled run; pass --near-schedule-confirmed once the user confirms knowing it")
    q("execute task FEATURELAB.DEV.CORE")
    print(f"started FEATURELAB.DEV.CORE at {now.isoformat(timespec='seconds')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["status", "run"])
    parser.add_argument("--days", type=int, default=2)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--near-schedule-confirmed", action="store_true")
    args = parser.parse_args()
    if args.command == "status":
        status(args.days)
    else:
        run(args.execute, args.near_schedule_confirmed)
