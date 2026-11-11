#!/usr/bin/env python3
"""List calls that pass a string literal naming a function or class defined in the repository's modules."""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple

from docs_cache import default_docs_root


def defined_names(trees: Sequence[ast.AST]) -> Set[str]:
    names: Set[str] = set()
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("__"):
                names.add(node.name)
    return names


MAPPING_METHODS = {"get", "pop", "setdefault"}


def is_mapping_access(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr in MAPPING_METHODS


def call_name(node: ast.Call) -> str:
    return ast.unparse(node.func)


def find(project_root: Path, docs_root: Path) -> List[Tuple[str, int, str, str]]:
    from validate_spec import Result, load_config

    result = Result()
    config = load_config(docs_root, result)
    if result.errors:
        raise ValueError("; ".join(result.errors))
    parsed: List[Tuple[str, ast.AST]] = []
    for module in config.modules.values():
        root = project_root / module.source
        for path in sorted(root.rglob("*.py")) if root.is_dir() else []:
            parsed.append((path.relative_to(project_root).as_posix(), ast.parse(path.read_text(encoding="utf-8"))))
    names = defined_names([tree for _, tree in parsed])
    found: List[Tuple[str, int, str, str]] = []
    for path, tree in parsed:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or is_mapping_access(node):
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value in names:
                    found.append((path, node.lineno, call_name(node), arg.value))
    return sorted(found)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".", help="目标仓库根目录")
    parser.add_argument("--docs-root", default=None, help="文档根目录；缺省为 ~/data/docs/<仓库目录名>/<HEAD 提交哈希>")
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    if not root.is_dir():
        print(f"ERROR: 目标仓库目录不存在：{root}", file=sys.stderr)
        return 2
    try:
        docs_root = Path(args.docs_root) if args.docs_root else default_docs_root(root)
        for path, line, call, name in find(root, docs_root):
            print(f"{path}:{line}\t{call}\t{name}")
    except (OSError, ValueError, SyntaxError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
