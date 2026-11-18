"""Summarize where one completed query spent its time, against the four common problems of Snowflake's Query Profile.

Usage: python3 query_profile.py [--warehouse <wh>] [--since <timestamp>] <query_id> [<query_id> ...]

Per query it prints:
  - elapsed, queued, compilation and execution seconds (QUERY_HISTORY_BY_USER, last 7 days);
  - the operators taking 5% or more of execution time, with their output rows;
  - the four checks: Join output rows / input rows (exploding join), UnionAll under an Aggregate (UNION
    without ALL), bytes spilled to local and remote storage, TableScan partitions scanned / total (pruning).
Operator statistics come from GET_QUERY_OPERATOR_STATS (completed queries of the last 14 days).

All the given queries are fetched in two statements, one history lookup and one UNION ALL of operator stats, so the
cost does not grow with the number of queries. --warehouse runs them on that warehouse: both are INFORMATION_SCHEMA
table functions, which queue when the default warehouse is saturated. --since bounds the history lookup to queries
ending after that timestamp instead of the user's whole 7-day history.

As a library: fetch() returns the raw rows, format_report() renders one query from rows a caller already holds, and
history_rows() / operator_rows() are the two statements, for callers that fetch with their own filters.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf import sql  # noqa: E402

HISTORY_COLUMNS = ("query_id, session_id, start_time::varchar s, end_time::varchar e, total_elapsed_time, "
                   "queued_overload_time, queued_provisioning_time, compilation_time, execution_time, "
                   "warehouse_name, left(query_text, 100) q")


def history_rows(where: str, since: str | None = None, warehouse: str | None = None) -> list[dict]:
    """The current user's query history rows matching `where`, ending after `since` when given."""
    bound = f"END_TIME_RANGE_START => '{since}'::timestamp_ltz, " if since else ""
    return sql(f"select {HISTORY_COLUMNS} from table(FEATURELAB.INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER("
               f"{bound}RESULT_LIMIT => 10000)) where {where}", warehouse=warehouse)


def operator_rows(query_ids: list[str], warehouse: str | None = None) -> dict[str, list[dict]]:
    """Every given query's operators, query id -> rows, in one statement; operator ids made unique across steps."""
    for query_id in query_ids:
        if not re.match(r"^[0-9a-f-]+$", query_id):
            raise ValueError(f"not a query id: {query_id}")
    result = {query_id: [] for query_id in query_ids}
    if not query_ids:
        return result
    # GET_QUERY_OPERATOR_STATS takes a constant, so each query is its own UNION ALL branch.
    branches = [f"select '{q}' as query_id, step_id, operator_id, operator_type, parent_operators, "
                "operator_statistics, execution_time_breakdown, operator_attributes "
                f"from table(get_query_operator_stats('{q}'))" for q in query_ids]
    seen = set()
    for r in sql("\nunion all\n".join(branches), warehouse=warehouse):
        key = (r["QUERY_ID"], r["STEP_ID"], r["OPERATOR_ID"])
        # The function can return an operator more than once, and operator ids are unique within a step only.
        if key in seen:
            continue
        seen.add(key)
        for column in ("PARENT_OPERATORS", "OPERATOR_STATISTICS", "EXECUTION_TIME_BREAKDOWN", "OPERATOR_ATTRIBUTES"):
            r[column] = json.loads(r[column]) if r[column] else None
        r["OPERATOR_ID"] = f"{r['STEP_ID']}.{r['OPERATOR_ID']}"
        r["PARENT_OPERATORS"] = [f"{r['STEP_ID']}.{p}" for p in r["PARENT_OPERATORS"] or []]
        result[r["QUERY_ID"]].append(r)
    return result


def fetch(query_ids: list[str], since: str | None = None, warehouse: str | None = None) -> tuple[dict, dict]:
    """Return (query id -> history row, query id -> operator rows) for the given queries, in two statements."""
    listed = ", ".join(f"'{q}'" for q in query_ids)
    history = {r["QUERY_ID"]: r for r in history_rows(f"query_id in ({listed})", since, warehouse)}
    return history, operator_rows(query_ids, warehouse)


def format_report(query_id: str, t: dict | None, ops: list[dict]) -> str:
    """Render one query's report from its history row (None when absent) and its operator rows."""
    lines = [f"== {query_id}"]
    if t:
        queued = (t["QUEUED_OVERLOAD_TIME"] + t["QUEUED_PROVISIONING_TIME"]) / 1000
        lines.append(f"elapsed {t['TOTAL_ELAPSED_TIME'] / 1000:.1f}s, queued {queued:.1f}s, compile "
                     f"{t['COMPILATION_TIME'] / 1000:.1f}s, execute {t['EXECUTION_TIME'] / 1000:.1f}s on "
                     f"{t['WAREHOUSE_NAME']}: {re.sub(r'\s+', ' ', t['Q'])}")
    by_id = {o["OPERATOR_ID"]: o for o in ops}
    stats = {o["OPERATOR_ID"]: o["OPERATOR_STATISTICS"] or {} for o in ops}
    share = {o["OPERATOR_ID"]: (o["EXECUTION_TIME_BREAKDOWN"] or {}).get("overall_percentage", 0) for o in ops}
    for o in sorted(ops, key=lambda o: -share[o["OPERATOR_ID"]]):
        if share[o["OPERATOR_ID"]] >= 0.05:
            lines.append(f"  {share[o['OPERATOR_ID']]:6.1%}  #{o['OPERATOR_ID']} {o['OPERATOR_TYPE']}, "
                         f"output rows {stats[o['OPERATOR_ID']].get('output_rows')}")
    checks = []
    for o in ops:
        s, kind = stats[o["OPERATOR_ID"]], o["OPERATOR_TYPE"]
        if kind in ("Join", "CartesianJoin") and s.get("input_rows"):
            ratio = (s.get("output_rows") or 0) / s["input_rows"]
            if ratio > 1:
                checks.append(f"  exploding join? #{o['OPERATOR_ID']} output/input rows {ratio:.1f}")
        if kind == "UnionAll" and any(by_id.get(p, {}).get("OPERATOR_TYPE") == "Aggregate"
                                      for p in o["PARENT_OPERATORS"] or []):
            checks.append(f"  UNION without ALL? #{o['OPERATOR_ID']} has an Aggregate parent")
        spill = s.get("spilling") or {}
        if spill:
            checks.append(f"  spilling #{o['OPERATOR_ID']} {kind}: local {spill.get('bytes_spilled_local_storage', 0):.3g} B, "
                          f"remote {spill.get('bytes_spilled_remote_storage', 0):.3g} B")
        pruning = s.get("pruning") or {}
        if kind == "TableScan" and pruning.get("partitions_total"):
            table = (o["OPERATOR_ATTRIBUTES"] or {}).get("table_name")
            checks.append(f"  pruning #{o['OPERATOR_ID']} {table}: scanned {pruning.get('partitions_scanned', 0):.0f}"
                          f" / total {pruning['partitions_total']:.0f}")
    lines += checks or ["  no join explosion, UNION, spilling or table scan found"]
    return "\n".join(lines)


def report(query_id: str, since: str | None = None, warehouse: str | None = None) -> str:
    history, ops = fetch([query_id], since, warehouse)
    return format_report(query_id, history.get(query_id), ops[query_id])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(usage=__doc__.split("\n\n")[1])
    parser.add_argument("--warehouse")
    parser.add_argument("--since")
    parser.add_argument("query_ids", nargs="+")
    args = parser.parse_args()
    if not all(re.match(r"^[0-9a-f-]+$", a) for a in args.query_ids):
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    history, ops = fetch(args.query_ids, args.since, args.warehouse)
    print("\n\n".join(format_report(q, history.get(q), ops[q]) for q in args.query_ids), flush=True)
