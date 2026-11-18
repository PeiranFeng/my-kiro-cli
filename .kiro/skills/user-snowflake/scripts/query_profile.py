"""Summarize where one completed query spent its time, against the four common problems of Snowflake's Query Profile.

Usage: python3 query_profile.py <query_id> [<query_id> ...]

Per query it prints:
  - elapsed, queued, compilation and execution seconds (QUERY_HISTORY_BY_USER, last 7 days);
  - the operators taking 5% or more of execution time, with their output rows;
  - the four checks: Join output rows / input rows (exploding join), UnionAll under an Aggregate (UNION
    without ALL), bytes spilled to local and remote storage, TableScan partitions scanned / total (pruning).
Operator statistics come from GET_QUERY_OPERATOR_STATS (completed queries of the last 14 days).
"""

import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf import sql  # noqa: E402


def timing(query_id: str) -> dict | None:
    rows = sql("select total_elapsed_time, queued_overload_time, queued_provisioning_time, compilation_time, "
               "execution_time, warehouse_name, left(query_text, 100) q from table("
               "FEATURELAB.INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER(RESULT_LIMIT => 10000)) "
               f"where query_id = '{query_id}'")
    return rows[0] if rows else None


def operators(query_id: str) -> list[dict]:
    rows = sql("select step_id, operator_id, operator_type, parent_operators, operator_statistics, execution_time_breakdown, "
               f"operator_attributes from table(get_query_operator_stats('{query_id}'))")
    for r in rows:
        for key in ("PARENT_OPERATORS", "OPERATOR_STATISTICS", "EXECUTION_TIME_BREAKDOWN", "OPERATOR_ATTRIBUTES"):
            r[key] = json.loads(r[key]) if r[key] else None
    # The function can return an operator more than once, and operator ids are unique within a step only.
    unique = {}
    for r in rows:
        unique.setdefault((r["STEP_ID"], r["OPERATOR_ID"]), r)
    for r in unique.values():
        r["OPERATOR_ID"] = f"{r['STEP_ID']}.{r['OPERATOR_ID']}"
        r["PARENT_OPERATORS"] = [f"{r['STEP_ID']}.{p}" for p in r["PARENT_OPERATORS"] or []]
    return list(unique.values())


def report(query_id: str) -> str:
    lines = [f"== {query_id}"]
    t = timing(query_id)
    if t:
        queued = (t["QUEUED_OVERLOAD_TIME"] + t["QUEUED_PROVISIONING_TIME"]) / 1000
        lines.append(f"elapsed {t['TOTAL_ELAPSED_TIME'] / 1000:.1f}s, queued {queued:.1f}s, compile "
                     f"{t['COMPILATION_TIME'] / 1000:.1f}s, execute {t['EXECUTION_TIME'] / 1000:.1f}s on "
                     f"{t['WAREHOUSE_NAME']}: {re.sub(r'\s+', ' ', t['Q'])}")
    ops = operators(query_id)
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


if __name__ == "__main__":
    if len(sys.argv) < 2 or not all(re.match(r"^[0-9a-f-]+$", a) for a in sys.argv[1:]):
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    for query_id in sys.argv[1:]:
        print(report(query_id), flush=True)
