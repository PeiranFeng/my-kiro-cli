"""Compare tables pairwise, column by column, on their shared key columns.

Usage: python3 compare_tables.py <out.json> <base>=<new> [<base>=<new> ...]
  each side is a fully qualified table name; two pairs run at a time.

Per pair:
  1. the key columns (those of KEYS present in the new table) must be unique on both sides, else the pair is
     reported as "grain differs" and not compared further;
  2. one scan of each side computes HASH_AGG over (keys, column) for every column; a column whose two hashes
     agree holds the same value at the same keys on both sides and needs no join;
  3. only columns whose hashes differ go through the join, which counts per column NULL/NaN pattern mismatches,
     +/-Inf mismatches and rows beyond a relative difference of 1e-9 (absolute floor 1e-12), and the max
     relative difference;
  4. key-set differences are counted only when the key hashes or row counts differ.
"""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf import quote as q  # noqa: E402
from sf import sql  # noqa: E402

KEYS = ["RULE_ID", "DATE", "STOCK_ID", "INDEX_ID", "FACTOR"]
CHUNK = 120


def columns(table: str) -> list[tuple[str, str]]:
    db, schema, name = table.split(".")
    rows = sql(f"select column_name, data_type from {db}.INFORMATION_SCHEMA.COLUMNS where table_schema = '{schema}' "
               f"and table_name = '{name}' order by ordinal_position")
    return [(r["COLUMN_NAME"], r["DATA_TYPE"]) for r in rows]


def scan(table: str, keys: list[str], values: list[str]) -> dict:
    """One pass over the table: row count, distinct key count, and one hash per column."""
    key_list = ", ".join(q(k) for k in keys)
    exprs = ["count(*) as n", f"count(distinct {key_list}) as u", f"hash_agg({key_list}) as k"]
    exprs += [f"hash_agg({key_list}, {q(c)}) as h{i}" for i, c in enumerate(values)]
    (row,) = sql(f"select {', '.join(exprs)} from {table}")
    return row


def detail(base: str, new: str, keys: list[str], chunk: list[tuple[int, str, str]]) -> dict:
    exprs = []
    for i, c, t in chunk:
        x, y = f"a.{q(c)}", f"b.{q(c)}"
        if t == "FLOAT":
            nan_x, nan_y = f"({x} = 'NaN'::float)", f"({y} = 'NaN'::float)"
            ok = f"not ({nan_x} or {nan_y} or abs({x}) > 1e308 or abs({y}) > 1e308)"
            rel = f"abs({x} - {y}) / greatest(abs({x}), abs({y}), 1e-300)"
            exprs += [f"count_if(({x} is null) != ({y} is null) or {nan_x} != {nan_y}) n{i}",
                      f"count_if({ok} and abs({x} - {y}) > 1e-12 and {rel} > 1e-9) d{i}",
                      f"max(iff({ok}, {rel}, null)) m{i}",
                      f"count_if((abs({x}) > 1e308) != (abs({y}) > 1e308)) i{i}"]
        else:
            exprs.append(f"count_if({x} is distinct from {y}) n{i}")
    on = " and ".join(f"a.{q(k)} = b.{q(k)}" for k in keys)
    (row,) = sql(f"select {', '.join(exprs)} from {base} a join {new} b on {on}")
    return row


def compare(base: str, new: str) -> dict:
    new_cols = columns(new)
    base_types = dict(columns(base))
    keys = [c for c, _ in new_cols if c in KEYS]
    values = [(c, t) for c, t in new_cols if c not in KEYS and c in base_types]
    names = [c for c, _ in values]
    result = {"keys": keys, "columns": len(values),
              "missing_in_base": [c for c, _ in new_cols if c not in base_types],
              "missing_in_new": sorted(set(base_types) - {c for c, _ in new_cols})}
    if not keys or any(k not in base_types for k in keys):
        return {**result, "grain_differs": "key columns differ between the two tables"}
    with ThreadPoolExecutor(2) as pool:
        hb, hn = pool.map(lambda t: scan(t, keys, names), (base, new))
    result.update(rows_base=hb["N"], rows_new=hn["N"], only_base=0, only_new=0)
    if hb["U"] != hb["N"] or hn["U"] != hn["N"]:
        return {**result, "grain_differs": f"keys {keys} not unique: base {hb['N'] - hb['U']}, "
                                           f"new {hn['N'] - hn['U']} duplicate rows"}
    if hb["K"] != hn["K"] or hb["N"] != hn["N"]:
        on = " and ".join(f"a.{q(k)} = b.{q(k)}" for k in keys)
        (head,) = sql(f"select count_if(a.{q(keys[0])} is null) only_new, count_if(b.{q(keys[0])} is null) only_base "
                      f"from {base} a full outer join {new} b on {on}")
        result.update(only_new=head["ONLY_NEW"], only_base=head["ONLY_BASE"])
    differing = [(i, c, t) for i, (c, t) in enumerate(values) if hb[f"H{i}"] != hn[f"H{i}"]]
    result["hash_equal_columns"] = len(values) - len(differing)
    row = {}
    for start in range(0, len(differing), CHUNK):
        row.update(detail(base, new, keys, differing[start:start + CHUNK]))
    mismatch, max_rel = {}, None
    for i, c, t in differing:
        entry = {"null_or_nan_mismatch": int(row[f"N{i}"])}
        if t == "FLOAT":
            entry.update(beyond_1e9=int(row[f"D{i}"]), inf_mismatch=int(row[f"I{i}"]),
                         max_rel=float(row[f"M{i}"]) if row[f"M{i}"] is not None else None)
            if entry["max_rel"] is not None:
                max_rel = max(max_rel or 0.0, entry["max_rel"])
        if entry["null_or_nan_mismatch"] or entry.get("beyond_1e9") or entry.get("inf_mismatch"):
            mismatch[c] = entry
    result.update(mismatch_columns=mismatch, max_rel=max_rel)
    return result


def summary(name: str, r: dict) -> str:
    if "grain_differs" in r:
        return f"{name}: GRAIN DIFFERS ({r['grain_differs']})"
    return (f"{name}: rows {r['rows_base']} -> {r['rows_new']}, only_base={r['only_base']} only_new={r['only_new']}, "
            f"cols={r['columns']} (hash-equal {r['hash_equal_columns']}), missing={r['missing_in_base']}/"
            f"{r['missing_in_new']}, mismatch_cols={len(r['mismatch_columns'])}, max_rel={r['max_rel']}")


if __name__ == "__main__":
    out, pairs = Path(sys.argv[1]), [arg.split("=", 1) for arg in sys.argv[2:]]
    if not pairs or any(len(p) != 2 or not all(re.match(r"^\w+\.\w+\.\w+$", s) for s in p) for p in pairs):
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    results = {}
    with ThreadPoolExecutor(2) as pool:
        for (base, new), r in zip(pairs, pool.map(lambda p: compare(*p), pairs)):
            results[f"{base}={new}"] = r
            print(summary(new, r), flush=True)
            out.write_text(json.dumps(results, indent=1))
