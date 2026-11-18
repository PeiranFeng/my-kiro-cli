"""Build feature-lab's preprocess layer in the personal schema on a fixed upstream snapshot, and verify two versions.

A version is a pair (feature-lab rev, preprocess_evaluate rev). Every build reads its upstream from a snapshot: each
relation outside the layer that a layer model refs directly is fixed as <NAME>__<TAG>__S<id> in DEV_<USER> (a table
is cloned, a view is materialized), and the defer state manifest is rewritten to point at the copies. A snapshot is
reused by later builds of the same tag while its structure stays compatible, so two versions read one input.

Usage:
  python3 preprocess_build.py build  <TAG> [--fl <rev>] [--pe <rev>] [--snapshot <id>] [--upstream dev|prod] [--background]
  python3 preprocess_build.py verify <TAG> [--base-fl <rev>] [--base-pe <rev>] [--new-fl <rev>] [--new-pe <rev>]
                                     [--exclude <regex>] [--upstream dev|prod] [--background]
Revs default to HEAD of ~/data/feature-lab and ~/data/preprocess_evaluate; HEAD of feature-lab needs a clean tree.

build: exports the feature-lab rev with git archive, deploys the preprocess_evaluate rev (deploy.sh), parses the
upstream manifest, takes a new snapshot (or extends --snapshot with what this version reads and it lacks), runs
dbt build --full-refresh --select path:models/preprocess against it, clones every base table of the layer to
<TABLE>__<TAG>__B<build id>, and records performance: the layer's wall clock, each model's elapsed minus queued
seconds, and query_profile.py reports of the slowest queries. Writes runs/<build id>/{run.json, summary.txt,
profile.txt} under ~/data/test/snowflake/<TAG>/. A failed model stops it; failed tests are recorded only.

verify: decides consistency of the new version against the base version on one compatible snapshot, building as
little as it can. With R(v) the relations version v reads:
  - a snapshot fits a version when, for every relation of R(v) it holds, its columns and types equal the current
    upstream's; a relation of R(v) it lacks is added from the current upstream, which leaves any other version's
    output on it unchanged, since that version does not read it;
  - an earlier build stands for the base version when the diffs between their revs touch nothing the layer runs:
    models/preprocess, macros and dbt_project.yml in feature-lab, the bundle's modules (read from
    scripts/build_bundle.py at the base rev) in preprocess_evaluate.
  Plan A: a recorded build on a snapshot that fits the new version stands for the base: build the new version once.
  Plan B: a recorded snapshot fits both versions: build the base, then the new version, on it.
  Plan C: take a new snapshot and build both.
It then compares every layer table the two builds both cloned, except names matching --exclude, with
compare_tables.compare (keys unique on both sides, then column by column), and writes verify.json and summary.txt.
Performance is read from the new build's own summary, not compared with the base.

--background runs the command detached in ~/data/test/snowflake/<TAG>/<command>-<UTC time>/, writing run.log,
run.pid and exit_code there. The log ends with "BUILD DONE" / "VERIFY DONE", or a line starting "FAILED:".
"""

import argparse
import ast
import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compare_tables  # noqa: E402
import query_profile  # noqa: E402
import sf  # noqa: E402
import test_tag  # noqa: E402

FL = sf.FEATURE_LAB
PE = Path.home() / "data" / "preprocess_evaluate"
LAYER = "models/preprocess/"
FL_LAYER_PATHS = ["models/preprocess", "macros", "dbt_project.yml"]
SPARE_WAREHOUSE = "SYSTEM$STREAMLIT_NOTEBOOK_WH"
PROFILED = 5
SIBLING = re.compile(r'sibling_relation\(\s*dbt\.this,\s*"([a-z0-9_]+)"')


def log(message: str):
    print(f"[{datetime.now(timezone.utc):%H:%M:%S}] {message}", flush=True)


def stamp() -> str:
    return f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def commit(repo: Path, rev: str) -> str:
    if rev == "HEAD" and repo == FL and git(FL, "status", "--porcelain"):
        raise RuntimeError(f"uncommitted changes in {FL}: commit them or name a rev")
    return git(repo, "rev-parse", f"{rev}^{{commit}}")


def tag_dir(tag: str) -> Path:
    return test_tag.local_dir(tag)


# ---------------------------------------------------------------- feature-lab export, parse, dbt

def export_feature_lab(fl_commit: str, workdir: Path) -> Path:
    project = workdir / "feature-lab"
    project.mkdir(parents=True)
    archive = subprocess.run(["git", "-C", str(FL), "archive", fl_commit], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(project)], input=archive.stdout, check=True)
    return project


def dbt(project: Path, args: str) -> int:
    command = (f"source '{sf.LOCAL_CONTEXT}' >/dev/null 2>&1; "
               f"export DBT_PERSONAL_ROLE={sf.ROLE} DBT_PERSONAL_SCHEMA={sf.SCHEMA}; "
               f"uv run --project '{FL}' dbt {args} --project-dir '{project}' --profiles-dir '{project}'")
    return subprocess.run(["bash", "-c", command]).returncode


def parse(project: Path, upstream: str, target: Path) -> dict:
    if dbt(project, f"parse --target {upstream} --no-partial-parse --target-path '{target}' --log-path '{target}/logs' -q"):
        raise RuntimeError("dbt parse failed")
    return json.loads((target / "manifest.json").read_text())


def layer_models(manifest: dict) -> dict:
    return {k: v for k, v in manifest["nodes"].items()
            if v["resource_type"] == "model" and v["original_file_path"].startswith(LAYER)}


def relation(node: dict) -> str:
    name = node.get("identifier") or node.get("alias") or node["name"]
    return f"{node['database']}.{node['schema']}.{name}".upper()


def reads(manifest: dict) -> dict[str, str]:
    """Return R(v): unique id -> relation of every node outside the layer that a layer model refs directly."""
    nodes = {**manifest["nodes"], **manifest["sources"]}
    layer = layer_models(manifest)
    ids = {d for v in layer.values() for d in v["depends_on"]["nodes"] if d not in layer and d in nodes}
    return {i: relation(nodes[i]) for i in sorted(ids)}


def layer_tables(manifest: dict, project: Path) -> list[str]:
    """Return the base tables the layer writes: its table models and the siblings they write by name."""
    layer = layer_models(manifest)
    names = {v["name"].upper() for v in layer.values() if v["config"]["materialized"] in ("table", "incremental")}
    model_names = {v["name"] for v in layer.values()}
    for v in layer.values():
        if v["language"] == "python":
            names |= {s.upper() for s in SIBLING.findall((project / v["original_file_path"]).read_text())
                      if s not in model_names}
    return sorted(names)


# ---------------------------------------------------------------- warehouse, deploy

def refuse_if_active():
    """Refuse while the current user has active queries; the lookup is a table function, so it runs on the
    warehouse pick_warehouse() chooses at this moment rather than queueing on a saturated default."""
    active = sf.sql("select count(*) as n from table(FEATURELAB.INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER("
                    "RESULT_LIMIT => 1000)) where execution_status in ('RUNNING', 'QUEUED', 'BLOCKED', "
                    "'RESUMING_WAREHOUSE') and query_text not ilike '%query_history_by_user%'",
                    warehouse=pick_warehouse())[0]["N"]
    if active:
        raise RuntimeError(f"{active} active queries of the current user; see my_queries.sh list")


def pick_warehouse() -> str:
    """COMPUTE_WH unless it is saturated while the spare warehouse is idle."""
    rows = {r["name"]: r for r in sf.sql("show warehouses")}
    main = rows["COMPUTE_WH"]
    level = int(sf.sql("show parameters like 'MAX_CONCURRENCY_LEVEL' in warehouse COMPUTE_WH")[0]["value"])
    spare = rows.get(SPARE_WAREHOUSE)
    if (main["running"] >= level or main["queued"] > 0) and spare and spare["running"] == 0 and spare["queued"] == 0:
        return SPARE_WAREHOUSE
    return "COMPUTE_WH"


def use_warehouse(project: Path, warehouse: str):
    if warehouse != "COMPUTE_WH":
        profiles = project / "profiles.yml"
        profiles.write_text(profiles.read_text().replace("warehouse: COMPUTE_WH\n", f'warehouse: "{warehouse}"\n', 1))


def deploy(tag: str, pe_commit: str) -> dict:
    run = subprocess.run(["bash", str(HERE / "deploy.sh"), "preprocess_evaluate", tag, pe_commit],
                         capture_output=True, text=True)
    if run.returncode:
        raise RuntimeError("deploy failed: " + run.stdout[-800:] + run.stderr[-800:])
    return dict(line.split(" ", 1) for line in run.stdout.strip().splitlines())


# ---------------------------------------------------------------- snapshots

# SHOW COLUMNS reports FIXED and REAL where INFORMATION_SCHEMA.COLUMNS says NUMBER and FLOAT; recorded snapshots
# hold the latter names, so they are kept. Other type names are the same in both.
SHOW_TYPE_NAMES = {"FIXED": "NUMBER", "REAL": "FLOAT"}
SHOW_ROW_CAP = 10000


def show_columns(scope: str) -> list[dict]:
    return sf.sql(f"show columns in {scope}")


def columns(rels) -> dict[str, list[list[str]]]:
    """Return each relation's (column, type) list, with SHOW COLUMNS: metadata only, no warehouse, so it does not
    queue. One statement per schema; a schema whose listing reaches SHOW's row cap is read table by table instead.
    Columns come in ordinal order (checked 2026-11-18); were it ever otherwise, fits() would only take a new snapshot."""
    result = {rel: [] for rel in rels}
    by_schema = {}
    for rel in rels:
        db, schema, name = rel.split(".")
        by_schema.setdefault((db, schema), []).append(name)
    for (db, schema), names in by_schema.items():
        rows = show_columns(f"schema {db}.{schema}")
        if len(rows) >= SHOW_ROW_CAP:
            rows = [r for name in names for r in show_columns(f"table {db}.{schema}.{sf.quote(name)}")]
        wanted = set(names)
        for r in rows:
            if r["table_name"] in wanted:
                kind = json.loads(r["data_type"])["type"]
                result[f"{db}.{schema}.{r['table_name']}"].append([r["column_name"], SHOW_TYPE_NAMES.get(kind, kind)])
    return result


def snapshot_path(tag: str, sid: str) -> Path:
    return tag_dir(tag) / "snapshots" / f"{sid}.json"


def load_snapshot(tag: str, sid: str) -> dict:
    return json.loads(snapshot_path(tag, sid).read_text())


def extend_snapshot(tag: str, snapshot: dict, wanted: dict[str, str]) -> list[str]:
    """Fix every relation of `wanted` the snapshot lacks; return the unique ids added."""
    missing = {i: rel for i, rel in wanted.items() if i not in snapshot["tables"]}
    if not missing:
        return []
    kinds = {}
    for (db, schema) in {tuple(rel.split(".")[:2]) for rel in missing.values()}:
        for r in sf.sql(f"show objects in schema {db}.{schema}"):
            kinds[f"{db}.{schema}.{r['name']}".upper()] = r["kind"]
    absent = [rel for rel in missing.values() if rel not in kinds]
    if absent:
        raise RuntimeError(f"upstream relations not found: {absent}")
    statements, added = [], {}
    taken = {t["snapshot"].split(".")[-1] for t in snapshot["tables"].values()}
    for i, rel in missing.items():
        copy = test_tag.table_name(rel.split(".")[-1], tag, snapshot["id"])
        if copy in taken:
            raise RuntimeError(f"two upstream relations would share the snapshot name {copy}")
        taken.add(copy)
        target = f"FEATURELAB.{sf.SCHEMA}.{copy}"
        source = "clone" if kinds[rel] == "TABLE" else "as select * from"
        statements.append(f"create transient table {target} {source} {rel}")
        added[i] = {"source": rel, "snapshot": target}
    sf.sql(";\n".join(statements))
    fixed = columns([e["snapshot"] for e in added.values()])
    for i, entry in added.items():
        entry["columns"] = fixed[entry["snapshot"]]
        snapshot["tables"][i] = entry
    snapshot_path(tag, snapshot["id"]).parent.mkdir(parents=True, exist_ok=True)
    snapshot_path(tag, snapshot["id"]).write_text(json.dumps(snapshot, indent=1))
    return sorted(added)


def fits(snapshot: dict, wanted: dict[str, str], current: dict[str, list]) -> list[str]:
    """Return the relations of `wanted` whose snapshot columns differ from the current upstream's; empty if it fits."""
    return [wanted[i] for i in wanted if i in snapshot["tables"] and snapshot["tables"][i]["columns"] != current[i]]


def snapshot_alive(snapshot: dict) -> bool:
    existing = {r["name"] for r in sf.sql(f"show tables like '%{snapshot['id']}' in schema FEATURELAB.{sf.SCHEMA}")}
    return all(t["snapshot"].split(".")[-1] in existing for t in snapshot["tables"].values())


def rewrite_state(manifest: dict, snapshot: dict, target: Path):
    for i, entry in snapshot["tables"].items():
        node = manifest["nodes"].get(i) or manifest["sources"].get(i)
        if node is None:
            continue
        db, schema, name = entry["snapshot"].split(".")
        node.update(database=db, schema=schema, relation_name=entry["snapshot"])
        node["identifier" if node["resource_type"] == "source" else "alias"] = name
    target.mkdir(parents=True, exist_ok=True)
    (target / "manifest.json").write_text(json.dumps(manifest))


# ---------------------------------------------------------------- timings

def handler_seconds(ops: list[dict]) -> float:
    """Sum the Python UDF/UDTF handler execution time over one query's operator rows."""
    total = 0.0
    for o in ops:
        # Observed keys: python_udtf_{__init__,process,end_partition}_execution_time and their avg_ twins, in ms.
        stats = (o["OPERATOR_STATISTICS"] or {}).get("extension_functions") or {}
        total += sum(float(v) for k, v in stats.items() if k.startswith("python_") and k.endswith("_execution_time"))
    return total / 1000


def model_timings(run_results: dict, started: str, warehouse: str | None = None) -> tuple[dict, list, str]:
    """Return each model's elapsed, queued and Python handler seconds, its session's queries over 1 s slowest first,
    and the profile report of the `PROFILED` slowest; two statements in all, run on `warehouse`."""
    history = query_profile.history_rows("true", started, warehouse)
    by_id = {r["QUERY_ID"]: r for r in history}
    sessions = {}
    for result in run_results["results"]:
        if not result["unique_id"].startswith("model."):
            continue
        outer = by_id.get((result.get("adapter_response") or {}).get("query_id"))
        if outer is None:
            continue
        inner = [r for r in history if r["SESSION_ID"] == outer["SESSION_ID"] and outer["S"] <= r["S"] <= outer["E"]]
        heavy = [r for r in inner if r["EXECUTION_TIME"] > 1000 and r["QUERY_ID"] != outer["QUERY_ID"]]
        sessions[result["unique_id"].split(".")[-1]] = (outer, inner, heavy)
    heavy_all = sorted((r for _, _, heavy in sessions.values() for r in heavy), key=lambda r: -r["EXECUTION_TIME"])
    ops = query_profile.operator_rows([r["QUERY_ID"] for r in heavy_all], warehouse)
    timings = {}
    for model, (outer, inner, heavy) in sessions.items():
        elapsed = outer["TOTAL_ELAPSED_TIME"] / 1000
        queued = sum(r["QUEUED_OVERLOAD_TIME"] for r in inner) / 1000
        timings[model] = {"elapsed": elapsed, "queued": queued, "net": elapsed - queued,
                          "udtf_handler": sum(handler_seconds(ops[r["QUERY_ID"]]) for r in heavy)}
    slow = [r["QUERY_ID"] for r in heavy_all]
    profile = "\n\n".join(query_profile.format_report(q, by_id[q], ops[q]) for q in slow[:PROFILED])
    return timings, slow, profile


def wall_clock(run_results: dict) -> float:
    spans = [t for r in run_results["results"] if r["unique_id"].startswith("model.")
             for t in r["timing"] if t["name"] == "execute"]
    start = min(datetime.fromisoformat(t["started_at"].replace("Z", "+00:00")) for t in spans)
    end = max(datetime.fromisoformat(t["completed_at"].replace("Z", "+00:00")) for t in spans)
    return (end - start).total_seconds()


# ---------------------------------------------------------------- build

def build(tag: str, fl_rev: str, pe_rev: str, upstream: str, sid: str | None, workdir: Path) -> dict:
    """One build of one version on a snapshot; returns its run record."""
    refuse_if_active()
    fl_commit, pe_commit = commit(FL, fl_rev), commit(PE, pe_rev)
    build_id = "B" + stamp()
    workdir.mkdir(parents=True, exist_ok=True)
    project = export_feature_lab(fl_commit, workdir)
    deployed = deploy(tag, pe_commit)
    manifest = parse(project, upstream, workdir / "artifacts" / "parsed")
    wanted = reads(manifest)
    snapshot = load_snapshot(tag, sid) if sid else {"id": "S" + stamp(), "upstream": upstream, "tables": {}}
    added = extend_snapshot(tag, snapshot, wanted)
    log(f"version fl {fl_commit[:7]} pe {pe_commit[:7]}; snapshot {snapshot['id']} "
        f"({len(snapshot['tables'])} relations, {len(added)} added now)")
    state = workdir / "artifacts" / "state"
    rewrite_state(manifest, snapshot, state)
    record = {"build_id": build_id, "tag": tag, "upstream": upstream, "snapshot": snapshot["id"], "added": added,
              "reads": wanted, "feature_lab": fl_commit, "preprocess_evaluate": pe_commit,
              "bundle": deployed["bundle"], "procedure": deployed["procedure"], "warehouse": pick_warehouse()}
    use_warehouse(project, record["warehouse"])
    record["started"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log(f"dbt build {build_id} on {record['warehouse']}")
    record["dbt_exit"] = dbt(project, "build --target personal --full-refresh --select path:models/preprocess "
                                      f"--target-path '{workdir}/target' --log-path '{workdir}/logs' "
                                      f"--defer --state '{state}' --favor-state --vars '{deployed['vars']}'")
    record["ended"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results = json.loads((workdir / "target" / "run_results.json").read_text())
    record["failed_models"] = [r["unique_id"] for r in results["results"]
                               if r["unique_id"].startswith("model.") and r["status"] != "success"]
    record["failed_tests"] = [r["unique_id"] for r in results["results"]
                              if r["unique_id"].startswith("test.") and r["status"] not in ("pass", "success")]
    run_dir = tag_dir(tag) / "runs" / build_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(json.dumps(record, indent=1))
    if record["failed_models"]:
        raise RuntimeError(f"models failed: {record['failed_models']}")
    tables = layer_tables(manifest, project)
    existing = {r["name"] for r in sf.sql(f"show tables in schema FEATURELAB.{sf.PREPROCESS_SCHEMA}")}
    record["clones"] = {t: test_tag.table_name(t, tag, build_id) for t in tables if t in existing}
    sf.sql(";\n".join(f"create transient table FEATURELAB.{sf.PREPROCESS_SCHEMA}.{c} "
                      f"clone FEATURELAB.{sf.PREPROCESS_SCHEMA}.{t}" for t, c in record["clones"].items()))
    record["timings"], slow, profile = model_timings(results, record["started"], record["warehouse"])
    record["wall_clock"] = wall_clock(results)
    (run_dir / "run.json").write_text(json.dumps(record, indent=1))
    (run_dir / "profile.txt").write_text(profile + "\n")
    lines = [f"build {build_id}: feature-lab {fl_commit[:7]}, preprocess_evaluate {pe_commit[:7]}, "
             f"snapshot {snapshot['id']}, warehouse {record['warehouse']}, {record['started']} to {record['ended']}",
             f"layer wall clock {record['wall_clock']:.0f} s; failed tests {record['failed_tests']}",
             "per model, elapsed - queued:"]
    lines += [f"  {m}: {t['net']:.0f} s" for m, t in sorted(record["timings"].items(), key=lambda kv: -kv[1]["net"])]
    lines.append(f"profiles of the {min(PROFILED, len(slow))} slowest queries: {run_dir / 'profile.txt'}")
    (run_dir / "summary.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)
    log(f"BUILD DONE {build_id}")
    return record


# ---------------------------------------------------------------- verify

def bundle_paths(pe_commit: str) -> list[str]:
    """Return the repository paths scripts/build_bundle.py puts in the bundle at that commit."""
    tree = ast.parse(git(PE, "show", f"{pe_commit}:scripts/build_bundle.py"))
    values = {t.id: ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
              for t in node.targets if isinstance(t, ast.Name) and t.id in ("MODULES", "CONFIGURATION")}
    return sorted(set(values["MODULES"].values()) | {values["CONFIGURATION"], "scripts/build_bundle.py"})


def stands_for(run: dict, fl_commit: str, pe_commit: str) -> list[str]:
    """Return the files by which an earlier build's version differs from this one in what the layer runs."""
    fl = git(FL, "diff", "--name-only", run["feature_lab"], fl_commit, "--", *FL_LAYER_PATHS).split()
    pe = git(PE, "diff", "--name-only", run["preprocess_evaluate"], pe_commit, "--", *bundle_paths(pe_commit)).split()
    return fl + pe


def recorded_runs(tag: str) -> list[dict]:
    runs = [json.loads(p.read_text()) for p in sorted((tag_dir(tag) / "runs").glob("*/run.json"), reverse=True)]
    return [r for r in runs if r.get("clones")]


def clones_alive(run: dict) -> bool:
    existing = {r["name"] for r in sf.sql(f"show tables like '%{run['build_id']}' in schema FEATURELAB.{sf.PREPROCESS_SCHEMA}")}
    return all(c in existing for c in run["clones"].values())


def current_columns(wanted: dict[str, str]) -> dict[str, list]:
    found = columns(set(wanted.values()))
    return {i: found[rel] for i, rel in wanted.items()}


def verify(tag: str, base: tuple[str, str], new: tuple[str, str], exclude: str, upstream: str, workdir: Path):
    base_fl, base_pe = commit(FL, base[0]), commit(PE, base[1])
    new_fl, new_pe = commit(FL, new[0]), commit(PE, new[1])
    if (base_fl, base_pe) == (new_fl, new_pe):
        raise RuntimeError("base and new name the same version")
    workdir.mkdir(parents=True, exist_ok=True)
    wanted = {}
    for side, fl_commit in (("base", base_fl), ("new", new_fl)):
        wanted[side] = reads(parse(export_feature_lab(fl_commit, workdir / side), upstream, workdir / side / "parsed"))
    current = current_columns({**wanted["base"], **wanted["new"]})
    plan, reason, base_run, sid = "C", "no recorded snapshot fits", None, None
    for run in recorded_runs(tag):
        if run["upstream"] != upstream or not snapshot_path(tag, run["snapshot"]).exists():
            continue
        snapshot = load_snapshot(tag, run["snapshot"])
        if not snapshot_alive(snapshot):
            continue
        misfit_new = fits(snapshot, wanted["new"], current)
        if misfit_new:
            reason = f"snapshot {snapshot['id']} differs from the current upstream in {misfit_new}"
            continue
        differs = stands_for(run, base_fl, base_pe)
        if not differs and clones_alive(run):
            plan, base_run, sid = "A", run, snapshot["id"]
            reason = f"build {run['build_id']} on snapshot {sid} stands for the base"
            break
        if not fits(snapshot, wanted["base"], current) and plan == "C":
            plan, sid = "B", snapshot["id"]
            reason = f"snapshot {sid} fits both; build {run['build_id']} differs from the base in {differs[:5]}"
    log(f"plan {plan}: {reason}")
    if plan != "A":
        base_run = build(tag, base_fl, base_pe, upstream, sid, workdir / "build-base")
        sid = base_run["snapshot"]
    new_run = build(tag, new_fl, new_pe, upstream, sid, workdir / "build-new")
    names = sorted(t for t in set(base_run["clones"]) & set(new_run["clones"]) if not (exclude and re.search(exclude, t, re.I)))
    schema = f"FEATURELAB.{sf.PREPROCESS_SCHEMA}"
    compared = {t: compare_tables.compare(f"{schema}.{base_run['clones'][t]}", f"{schema}.{new_run['clones'][t]}")
                for t in names}
    report = {"plan": plan, "reason": reason, "snapshot": sid, "base_build": base_run["build_id"],
              "new_build": new_run["build_id"], "only_base": sorted(set(base_run["clones"]) - set(new_run["clones"])),
              "only_new": sorted(set(new_run["clones"]) - set(base_run["clones"])), "tables": compared}
    (workdir / "verify.json").write_text(json.dumps(report, indent=1))
    lines = [f"base fl {base_fl[:7]} pe {base_pe[:7]} (build {base_run['build_id']}); "
             f"new fl {new_fl[:7]} pe {new_pe[:7]} (build {new_run['build_id']}); snapshot {sid}",
             f"plan {plan}: {reason}",
             f"tables only in base: {report['only_base']}; only in new: {report['only_new']}"]
    lines += [compare_tables.summary(t, r) for t, r in compared.items()]
    lines.append(f"performance of the new version: {tag_dir(tag) / 'runs' / new_run['build_id'] / 'summary.txt'}")
    (workdir / "summary.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)
    log("VERIFY DONE")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["build", "verify"])
    parser.add_argument("tag")
    parser.add_argument("--fl", default="HEAD")
    parser.add_argument("--pe", default="HEAD")
    parser.add_argument("--snapshot")
    parser.add_argument("--base-fl")
    parser.add_argument("--base-pe")
    parser.add_argument("--new-fl", default="HEAD")
    parser.add_argument("--new-pe", default="HEAD")
    parser.add_argument("--exclude", default="")
    parser.add_argument("--upstream", choices=["dev", "prod"], default="dev")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--workdir")
    args = parser.parse_args()
    test_tag.check(args.tag)
    if args.background:
        workdir = tag_dir(args.tag) / f"{args.command}-{stamp()}"
        workdir.mkdir(parents=True)
        argv = [a for a in sys.argv[1:] if a != "--background"] + ["--workdir", str(workdir)]
        shell = (f"python3 -B {shlex.quote(str(Path(__file__).resolve()))} {' '.join(map(shlex.quote, argv))}; "
                 f"echo \"EXIT=$?\" > {shlex.quote(str(workdir / 'exit_code'))}")
        with open(workdir / "run.log", "w") as out:
            process = subprocess.Popen(["bash", "-c", shell], stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
        (workdir / "run.pid").write_text(str(process.pid))
        time.sleep(1)
        print(f"workdir {workdir}\nlog {workdir / 'run.log'}\npid {process.pid}")
        return
    workdir = Path(args.workdir) if args.workdir else tag_dir(args.tag) / f"{args.command}-{stamp()}"
    try:
        if args.command == "build":
            build(args.tag, args.fl, args.pe, args.upstream, args.snapshot, workdir)
        else:
            base = (args.base_fl or args.new_fl, args.base_pe or args.new_pe)
            verify(args.tag, base, (args.new_fl, args.new_pe), args.exclude, args.upstream, workdir)
    except Exception as error:  # noqa: BLE001
        print(f"FAILED: {type(error).__name__}: {error}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    os.umask(0o022)
    main()
