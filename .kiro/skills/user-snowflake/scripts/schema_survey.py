"""Read-only survey of Snowflake schemas: what each holds, how large it is, and what depends on what.

Usage: python3 schema_survey.py <DB.SCHEMA> [<DB.SCHEMA> ...] [--manifest <manifest.json>] [--json <out.json>]

Per schema, from metadata only (SHOW and INFORMATION_SCHEMA, no table scan):
  - every table and view: kind, rows, bytes, clustering key, last altered;
  - view dependencies: the fully qualified relations each view's definition names.
With --manifest, the dbt model edges among the surveyed relations are added (ref() dependencies, which also
cover tables). A Python model that reads a relation by a name it builds itself has no edge in either source.
This role cannot read SNOWFLAKE.ACCOUNT_USAGE, so OBJECT_DEPENDENCIES is not used.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf import sql  # noqa: E402

NAME = re.compile(r'\b("?[A-Za-z_][\w$]*"?)\.("?[A-Za-z_][\w$]*"?)\.("?[A-Za-z_][\w$]*"?)')


def survey(db: str, schema: str) -> list[dict]:
    meta = {r["TABLE_NAME"]: r for r in sql(
        "select table_name, table_type, row_count, bytes, clustering_key, last_altered::varchar la "
        f"from {db}.INFORMATION_SCHEMA.TABLES where table_schema = '{schema}'")}
    views = {r["TABLE_NAME"]: r["VIEW_DEFINITION"] or "" for r in sql(
        f"select table_name, view_definition from {db}.INFORMATION_SCHEMA.VIEWS where table_schema = '{schema}'")}
    objects = []
    for name, r in sorted(meta.items()):
        refs = sorted({".".join(p.strip('"').upper() for p in m) for m in NAME.findall(views.get(name, ""))})
        objects.append({"name": f"{db}.{schema}.{name}", "kind": r["TABLE_TYPE"], "rows": r["ROW_COUNT"],
                        "bytes": r["BYTES"], "clustering_key": r["CLUSTERING_KEY"], "last_altered": r["LA"],
                        "reads": refs})
    return objects


def manifest_edges(path: Path, names: set[str]) -> dict[str, list[str]]:
    manifest = json.loads(path.read_text())
    nodes = {**manifest["nodes"], **manifest["sources"]}

    def relation(node):
        name = node.get("identifier") or node.get("alias") or node["name"]
        return f"{node['database']}.{node['schema']}.{name}".upper()

    edges = {}
    for node in manifest["nodes"].values():
        if node["resource_type"] == "model" and relation(node) in names:
            edges[relation(node)] = sorted(relation(nodes[d]) for d in node["depends_on"]["nodes"] if d in nodes)
    return edges


def human(n) -> str:
    if n is None:
        return "-"
    for unit in ("", "K", "M", "G", "T"):
        if abs(n) < 1000:
            return f"{n:.0f}{unit}"
        n /= 1000
    return f"{n:.0f}P"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("schemas", nargs="+")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    objects = []
    for target in args.schemas:
        db, schema = target.upper().split(".")
        objects += survey(db, schema)
    if args.manifest:
        edges = manifest_edges(args.manifest, {o["name"] for o in objects})
        for o in objects:
            o["model_depends_on"] = edges.get(o["name"])
    for o in objects:
        print(f"{o['kind']:<15} {human(o['rows']):>6} rows {human(o['bytes']):>6}B  {o['last_altered'][:19]}  {o['name']}"
              + (f"  cluster {o['clustering_key']}" if o["clustering_key"] else ""))
        for ref in o["reads"]:
            print(f"{'':17}view reads {ref}")
        for ref in o.get("model_depends_on") or []:
            print(f"{'':17}model ref  {ref}")
    if args.json:
        args.json.write_text(json.dumps(objects, indent=1))
