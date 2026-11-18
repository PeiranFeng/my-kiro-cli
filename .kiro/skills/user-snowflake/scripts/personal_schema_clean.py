"""List or remove what tests wrote to the personal schemas and to local disk, by test tag (test_tag.py).

Usage: python3 personal_schema_clean.py list                    every tag found with its objects, then untagged objects
       python3 personal_schema_clean.py clean <TAG>             print what <TAG> owns (dry run)
       python3 personal_schema_clean.py clean <TAG> --execute   drop it: tables, views, procedures, stage files, local dir

Scope: DEV_<USER> and every DEV_<USER>_<LAYER> schema. The preprocess layer's own relations carry no tag and are
not listed; other untagged objects, layer model outputs included, are listed and never removed here.
"""

import os
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sf  # noqa: E402
import test_tag  # noqa: E402



def personal_schemas() -> list[str]:
    """Return DEV_<USER> and every layer schema DEV_<USER>_<LAYER> that exists."""
    names = [r["name"] for r in sf.sql(f"show schemas like '{sf.SCHEMA}%' in database FEATURELAB")]
    return sorted(n for n in names if n == sf.SCHEMA or n.startswith(f"{sf.SCHEMA}_"))
STAGE = f"FEATURELAB.{sf.SCHEMA}.PYTHON_STAGE"


def snowflake_objects() -> list[dict]:
    """Return every table, view and user procedure of the personal schemas, plus PYTHON_STAGE files."""
    objects = []
    for schema in personal_schemas():
        # SHOW reads metadata only, so it answers even while the warehouse is saturated.
        for kind in ("TABLE", "VIEW"):
            for r in sf.sql(f"show {kind.lower()}s in schema FEATURELAB.{schema}"):
                objects.append({"kind": kind, "schema": schema, "name": r["name"]})
        for r in sf.sql(f"show user procedures in schema FEATURELAB.{schema}"):
            signature = r["arguments"].split(" RETURN ")[0]
            objects.append({"kind": "PROCEDURE", "schema": schema, "name": r["name"],
                            "signature": signature[len(r["name"]):]})
    for r in sf.sql(f"list @{STAGE}"):
        objects.append({"kind": "STAGE_FILE", "schema": sf.SCHEMA, "name": r["name"]})
    return objects


def owner(obj: dict):
    return test_tag.stage_owner(obj["name"]) if obj["kind"] == "STAGE_FILE" else test_tag.owner(obj["name"])


def local_dirs() -> dict[str, Path]:
    root = test_tag.LOCAL_ROOT
    return {p.name: p for p in root.iterdir() if p.is_dir()} if root.exists() else {}


def describe(obj: dict) -> str:
    return f"{obj['kind']:<10} {obj['schema']}.{obj['name']}"


def list_all():
    layer = sf.preprocess_layer_names()
    by_tag, untagged = defaultdict(list), []
    for obj in snowflake_objects():
        tag = owner(obj)
        if tag:
            by_tag[tag].append(obj)
        elif not (obj["schema"] == sf.PREPROCESS_SCHEMA and obj["name"] in layer):
            untagged.append(obj)
    dirs = local_dirs()
    lines = []
    for tag in sorted(set(by_tag) | {d for d in dirs if test_tag.TAG.match(d)}):
        lines.append(f"[{tag}]")
        lines += ["  " + describe(obj) for obj in by_tag.get(tag, [])]
        if tag in dirs:
            lines.append(f"  LOCAL      {dirs[tag]}")
    lines.append(f"[untagged: {len(untagged)} objects, listed only]")
    lines += ["  " + describe(obj) for obj in untagged]
    lines += [f"  LOCAL      {path}" for name, path in sorted(dirs.items()) if not test_tag.TAG.match(name)]
    print("\n".join(lines))


def live_runs(path: Path) -> list[Path]:
    live = []
    for pid_file in path.rglob("run.pid"):
        try:
            os.kill(int(pid_file.read_text().strip()), 0)
            live.append(pid_file)
        except (OSError, ValueError):
            pass
    return live


def clean(tag: str, execute: bool):
    test_tag.check(tag)
    owned = [obj for obj in snowflake_objects() if owner(obj) == tag]
    path = test_tag.local_dir(tag)
    for obj in owned:
        print(describe(obj))
    if path.exists():
        print(f"LOCAL      {path}")
    if not execute:
        print("dry run: add --execute to remove the above")
        return
    if path.exists() and live_runs(path):
        raise SystemExit(f"a run under {path} is still alive: {live_runs(path)}")
    statements = []
    for obj in owned:
        full = f"FEATURELAB.{obj['schema']}.{sf.quote(obj['name'])}"
        if obj["kind"] in ("TABLE", "VIEW"):
            statements.append(f"drop {obj['kind'].lower()} if exists {full}")
        elif obj["kind"] == "PROCEDURE":
            statements.append(f"drop procedure if exists {full}{obj['signature']}")
    libs = {re.match(r"python_stage/([a-z0-9_]+)/", obj["name"]).group(1) for obj in owned if obj["kind"] == "STAGE_FILE"}
    statements += [f"remove @{STAGE}/{test_tag.stage_dir(lib, tag)}" for lib in sorted(libs)]
    if statements:
        sf.sql(";\n".join(statements))
    if path.exists():
        shutil.rmtree(path)
    print(f"removed {len(owned)} Snowflake objects and {path}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["list"]:
        list_all()
    elif sys.argv[1:2] == ["clean"] and len(sys.argv) >= 3:
        clean(sys.argv[2], "--execute" in sys.argv[3:])
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
