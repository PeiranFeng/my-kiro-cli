"""Render one feature-lab layer's data flow from a git ref, so the skill never hand-copies it.

Usage: python3 layer_flow.py [--ref origin/dev] [--layer preprocess] [--against <ref>]

Fetches origin, exports <ref> with git archive (the working tree is not touched), runs dbt parse --target dev
on the export, and prints, for every model under models/<layer>/:
  materialization, language, the relations it ref()s, and for Python models the relations it reads or writes
  by name through sibling_relation (which dbt's graph does not contain).
Upstream relations outside the layer are listed once at the top. With --against, it also prints the models
and edges present in one ref but not the other, e.g. what an unmerged branch will change once merged.
The parsed export is cached under ~/data/test/snowflake/_layer_flow/<commit>/.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sf  # noqa: E402

CACHE = Path.home() / "data" / "test" / "snowflake" / "_layer_flow"
SIBLING = re.compile(r'sibling_relation\(\s*dbt\.this,\s*"([a-z0-9_]+)"')


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(sf.FEATURE_LAB), *args], capture_output=True, text=True, check=True).stdout.strip()


def parse(ref: str) -> tuple[str, dict, Path]:
    commit = git("rev-parse", f"{ref}^{{commit}}")
    root = CACHE / commit[:12]
    manifest = root / "target" / "manifest.json"
    if not manifest.exists():
        shutil.rmtree(root, ignore_errors=True)
        (root / "src").mkdir(parents=True)
        archive = subprocess.run(["git", "-C", str(sf.FEATURE_LAB), "archive", commit], capture_output=True, check=True)
        subprocess.run(["tar", "-x", "-C", str(root / "src")], input=archive.stdout, check=True)
        command = (f"source '{sf.LOCAL_CONTEXT}' >/dev/null 2>&1; "
                   f"uv run --project '{sf.FEATURE_LAB}' dbt parse --target dev --no-partial-parse "
                   f"--project-dir '{root / 'src'}' --profiles-dir '{root / 'src'}' "
                   f"--target-path '{root / 'target'}' --log-path '{root / 'logs'}'")
        run = subprocess.run(["bash", "-c", command], capture_output=True, text=True)
        if run.returncode:
            raise SystemExit(f"dbt parse failed for {ref}:\n{run.stdout[-1500:]}")
    return commit, json.loads(manifest.read_text()), root / "src"


def flow(manifest: dict, src: Path, layer: str) -> dict:
    nodes = {**manifest["nodes"], **manifest["sources"]}
    prefix = f"models/{layer}/"
    models = {}
    for node in manifest["nodes"].values():
        if node["resource_type"] != "model" or not node["original_file_path"].startswith(prefix):
            continue
        siblings = []
        if node["language"] == "python":
            siblings = sorted(set(SIBLING.findall((src / node["original_file_path"]).read_text())))
        models[node["name"]] = {
            "materialized": node["config"]["materialized"], "language": node["language"],
            "refs": sorted(nodes[d]["name"] for d in node["depends_on"]["nodes"] if d in nodes),
            "by_name": siblings,
        }
    return models


def edges(models: dict) -> set[tuple[str, str, str]]:
    return {(m, kind, r) for m, v in models.items() for kind in ("refs", "by_name") for r in v[kind]}


def render(ref: str, commit: str, models: dict, layer: str) -> str:
    upstream = sorted({r for v in models.values() for r in v["refs"]} - set(models))
    lines = [f"# {layer} layer at {ref} ({commit[:7]})", "", "upstream outside the layer: " + ", ".join(upstream), ""]
    for name, v in sorted(models.items()):
        lines.append(f"- {name} ({v['materialized']}, {v['language']})")
        if v["refs"]:
            lines.append(f"    ref:     {', '.join(v['refs'])}")
        if v["by_name"]:
            lines.append(f"    by name: {', '.join(v['by_name'])}")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ref", default="origin/dev")
    parser.add_argument("--layer", default="preprocess")
    parser.add_argument("--against")
    args = parser.parse_args()
    git("fetch", "-q", "origin")
    commit, manifest, src = parse(args.ref)
    models = flow(manifest, src, args.layer)
    print(render(args.ref, commit, models, args.layer))
    if args.against:
        other_commit, other_manifest, other_src = parse(args.against)
        other = flow(other_manifest, other_src, args.layer)
        print(f"\n# {args.against} ({other_commit[:7]}) compared with {args.ref}")
        for name in sorted(set(other) - set(models)):
            print(f"+ model {name}")
        for name in sorted(set(models) - set(other)):
            print(f"- model {name}")
        for m, kind, r in sorted(edges(other) - edges(models)):
            print(f"+ {m} {kind} {r}")
        for m, kind, r in sorted(edges(models) - edges(other)):
            print(f"- {m} {kind} {r}")
