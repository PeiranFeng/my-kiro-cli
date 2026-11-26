#!/usr/bin/env python3
"""Locate, reuse and diff the per-commit document roots stored outside the repository."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Sequence, Tuple

DOCS_BASE = Path.home() / "data" / "docs"
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
CONFIG_NAME = "project-spec.json"


def git(project_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    done = subprocess.run(["git", "-C", str(project_root), *args], capture_output=True, text=True)
    if check and done.returncode != 0:
        raise ValueError(f"git {' '.join(args)} 失败：{done.stderr.strip()}")
    return done


def repo_name(project_root: Path) -> str:
    return project_root.resolve().name


def head_commit(project_root: Path) -> str:
    return git(project_root, "rev-parse", "HEAD").stdout.strip()


def docs_root_for(project_root: Path, commit: str) -> Path:
    return DOCS_BASE / repo_name(project_root) / commit


def default_docs_root(project_root: Path) -> Path:
    return docs_root_for(project_root, head_commit(project_root))


def cached_commits(project_root: Path) -> List[str]:
    base = DOCS_BASE / repo_name(project_root)
    names = [item.name for item in base.iterdir() if item.is_dir() and COMMIT_PATTERN.match(item.name)] if base.is_dir() else []
    return sorted(name for name in names if git(project_root, "cat-file", "-e", f"{name}^{{commit}}", check=False).returncode == 0)


def find_base(project_root: Path) -> Optional[str]:
    head = head_commit(project_root)
    best: Optional[Tuple[int, str]] = None
    for commit in cached_commits(project_root):
        if commit == head or git(project_root, "merge-base", "--is-ancestor", commit, head, check=False).returncode != 0:
            continue
        distance = int(git(project_root, "rev-list", "--count", f"{commit}..{head}").stdout.strip())
        if best is None or distance < best[0]:
            best = (distance, commit)
    return best[1] if best else None


def has_content(root: Path) -> bool:
    return root.is_dir() and any(root.iterdir())


def status(project_root: Path) -> Dict[str, Any]:
    head = head_commit(project_root)
    root = docs_root_for(project_root, head)
    if has_content(root):
        return {"repo": repo_name(project_root), "head": head, "docsRoot": str(root), "state": "exact", "base": None}
    base = find_base(project_root)
    return {"repo": repo_name(project_root), "head": head, "docsRoot": str(root), "state": "incremental" if base else "none", "base": base}


def changed_files(project_root: Path, base: str) -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = []
    for line in git(project_root, "diff", "--name-status", "--no-renames", base).stdout.splitlines():
        code, _, path = line.partition("\t")
        rows.append((code[:1], path))
    for path in git(project_root, "ls-files", "--others", "--exclude-standard").stdout.splitlines():
        rows.append(("A", path))
    return sorted(rows, key=lambda item: item[1])


def under(path: str, directory: str) -> Optional[PurePosixPath]:
    try:
        return PurePosixPath(path).relative_to(directory)
    except ValueError:
        return None


def classify(config: Dict[str, Any], rows: Sequence[Tuple[str, str]], root: Path) -> List[Dict[str, Any]]:
    suffixes = config.get("sourceSuffixes", [])
    result: List[Dict[str, Any]] = []
    for code, path in rows:
        for module, spec in config.get("modules", {}).items():
            inner = under(path, spec["source"])
            if inner is not None and inner.suffix in suffixes:
                stem = inner.with_suffix("")
                candidates = [
                    PurePosixPath("architecture", module, f"{stem}.md"),
                    PurePosixPath("architecture", module, f"{stem}.structure.md"),
                    PurePosixPath("test-cases", module, f"{stem}.md"),
                ]
                result.append({"status": code, "kind": "source", "module": module, "path": path, "docs": [str(item) for item in candidates if (root / item).is_file()]})
                break
            if under(path, spec["tests"]) is not None:
                result.append({"status": code, "kind": "test", "module": module, "path": path, "docs": []})
                break
    return result


def prepare(project_root: Path) -> Dict[str, Any]:
    info = status(project_root)
    root = Path(info["docsRoot"])
    if info["state"] == "none":
        root.mkdir(parents=True, exist_ok=True)
    elif info["state"] == "incremental":
        shutil.copytree(docs_root_for(project_root, info["base"]), root, dirs_exist_ok=True)
        config_path = root / CONFIG_NAME
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
        info["changes"] = classify(config, changed_files(project_root, info["base"]), root)
    return info


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("resolve", "只读：报告当前提交的缓存状态"), ("prepare", "按状态创建文档根；有可复用的基准提交时复制并列出变更")):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("--project-root", default=".", help="目标仓库根目录")
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    if not root.is_dir():
        print(f"ERROR: 目标仓库目录不存在：{root}", file=sys.stderr)
        return 2
    try:
        info = status(root) if args.command == "resolve" else prepare(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
