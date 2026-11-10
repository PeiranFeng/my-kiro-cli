#!/usr/bin/env python3
"""Generate and check structure documents (class and function outline) from Python sources."""

from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import tokenize
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Sequence, Tuple

STRUCTURE_SUFFIX = ".structure.md"
NO_DESCRIPTION = "(无说明)"
COMMENT_TAIL = re.compile(r"\s{2}#\s.*$")
PROBE_CALLS = {"getattr", "hasattr"}

FunctionNode = (ast.FunctionDef, ast.AsyncFunctionDef)


def slug(name: str) -> str:
    return name.strip("_").lower()


def is_public(name: str) -> bool:
    return not name.startswith("_") or name == "__init__"


def first_line(node: ast.AST) -> str:
    text = ast.get_docstring(node)  # type: ignore[arg-type]
    if not text:
        return NO_DESCRIPTION
    return next((line.strip() for line in text.splitlines() if line.strip()), NO_DESCRIPTION)


def line_comments(text: str) -> Dict[int, str]:
    comments: Dict[int, str] = {}
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                comments[token.start[0]] = token.string.lstrip("#").strip()
    except tokenize.TokenError:
        pass
    return comments


def signature(node: ast.AST) -> str:
    assert isinstance(node, FunctionNode)
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{prefix} {node.name}({ast.unparse(node.args)}){returns}"


def function_block(node: ast.AST) -> str:
    assert isinstance(node, FunctionNode)
    lines = [f"@{ast.unparse(item)}" for item in node.decorator_list]
    lines.append(f"{signature(node)}  # {first_line(node)}")
    return "\n".join(lines)


def variable_lines(body: Sequence[ast.stmt], comments: Dict[int, str]) -> List[str]:
    lines: List[str] = []
    seen = set()
    for stmt in body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            name, label = stmt.target.id, f"{stmt.target.id}: {ast.unparse(stmt.annotation)}"
        elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            name, label = stmt.targets[0].id, stmt.targets[0].id
        else:
            continue
        if not is_public(name) or name in seen:
            continue
        seen.add(name)
        lines.append(f"{label}  # {comments.get(stmt.lineno, NO_DESCRIPTION)}")
    return lines


def fenced(lines: Sequence[str]) -> str:
    return "```python\n" + "\n".join(lines) + "\n```"


def class_heading(node: ast.ClassDef) -> str:
    bases = [ast.unparse(item) for item in node.bases]
    bases += [f"{item.arg}={ast.unparse(item.value)}" for item in node.keywords if item.arg]
    return f"{node.name}({', '.join(bases)})" if bases else node.name


def probes(tree: ast.Module) -> List[Tuple[int, int, str, str, str]]:
    found: List[Tuple[int, int, str, str, str]] = []

    def visit(node: ast.AST, scope: Tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            inner = scope + (child.name,) if isinstance(child, (ast.ClassDef, *FunctionNode)) else scope
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id in PROBE_CALLS
                and len(child.args) >= 2
                and isinstance(child.args[1], ast.Constant)
                and isinstance(child.args[1].value, str)
            ):
                found.append((child.lineno, child.col_offset, ".".join(scope) or "(模块)", child.func.id, child.args[1].value))
            visit(child, inner)

    visit(tree, ())
    return sorted(found)


def render_body(text: str, module: str, stem: str) -> str:
    tree = ast.parse(text)
    comments = line_comments(text)
    anchor = f"api.{module}.{slug(stem)}"
    blocks: List[str] = [f"# {stem} 结构", f"> {first_line(tree)}"]

    variables = variable_lines(tree.body, comments)
    if variables:
        blocks += ["## 模块变量", fenced(variables)]

    seen = set()
    for node in tree.body:
        if not isinstance(node, (ast.ClassDef, *FunctionNode)) or not is_public(node.name) or node.name in seen:
            continue
        seen.add(node.name)
        symbol = f"{anchor}.{slug(node.name)}"
        if isinstance(node, ast.ClassDef):
            blocks += [f"## {class_heading(node)} {{#{symbol}}}", f"> {first_line(node)}"]
            attributes = variable_lines(node.body, comments)
            if attributes:
                blocks.append(fenced(attributes))
            methods = set()
            for member in node.body:
                if isinstance(member, FunctionNode) and is_public(member.name) and member.name not in methods:
                    methods.add(member.name)
                    blocks += [f"### {node.name}.{member.name} {{#{symbol}.{slug(member.name)}}}", fenced([function_block(member)])]
        else:
            blocks += [f"## {node.name} {{#{symbol}}}", fenced([function_block(node)])]

    calls = probes(tree)
    if calls:
        rows = ["| 位置 | 调用 | 目标名 |", "| --- | --- | --- |"]
        rows += [f"| {where} | {call} | `{target}` |" for _, _, where, call, target in calls]
        blocks += ["## 动态探测", "\n".join(rows)]
    return "\n\n".join(blocks) + "\n"


def has_content(text: str) -> bool:
    tree = ast.parse(text)
    if ast.get_docstring(tree):
        return True
    return any(
        (isinstance(node, (ast.ClassDef, *FunctionNode)) and is_public(node.name)) or bool(variable_lines([node], {}))
        for node in tree.body
    )


def skeleton(body: str) -> str:
    kept: List[str] = []
    in_fence = False
    for line in body.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
        elif in_fence:
            line = COMMENT_TAIL.sub("", line)
        elif line.startswith(">"):
            continue
        if line.strip():
            kept.append(line.rstrip())
    return "\n".join(kept)


def split_frontmatter(text: str) -> Tuple[List[str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], text
    closing = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)
    if closing is None:
        return [], text
    return lines[: closing + 1], "\n".join(lines[closing + 1 :])


def structure_relative(module: str, source_inner: PurePosixPath) -> str:
    return PurePosixPath("docs", "architecture", module, source_inner.parent, source_inner.stem + STRUCTURE_SUFFIX).as_posix()


def targets(project_root: Path) -> List[Tuple[str, str, Path, Path]]:
    from validate_spec import Result, load_config

    result = Result()
    config = load_config(project_root, result)
    if result.errors:
        raise ValueError("; ".join(result.errors))
    items: List[Tuple[str, str, Path, Path]] = []
    for module, spec in config.modules.items():
        root = project_root / spec.source
        for path in sorted(root.rglob("*.py")) if root.is_dir() else []:
            inner = PurePosixPath(path.relative_to(root).as_posix())
            items.append((module, inner.stem, path, project_root / structure_relative(module, inner)))
    return items


def process(project_root: Path, write: bool) -> List[str]:
    problems: List[str] = []
    for module, stem, source, doc in targets(project_root):
        text = source.read_text(encoding="utf-8")
        try:
            if not has_content(text) and not doc.with_name(doc.name[: -len(STRUCTURE_SUFFIX)] + ".md").is_file():
                continue
            body = render_body(text, module, stem)
        except SyntaxError as exc:
            problems.append(f"{source}: 无法解析：{exc.msg}")
            continue
        relative = doc.relative_to(project_root).as_posix()
        if doc.is_file():
            head, current = split_frontmatter(doc.read_text(encoding="utf-8"))
            if skeleton(current) == skeleton(body):
                continue
            state = "stale"
        else:
            head, state = [], "missing"
        problems.append(f"{relative}: {state}")
        if write:
            if not head:
                head = ["---", f"id: struct.{module}.{slug(stem)}", "kind: structure", "status: draft", "---"]
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text("\n".join(head) + "\n\n" + body, encoding="utf-8")
    return problems


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".", help="目标仓库根目录")
    parser.add_argument("--write", action="store_true", help="写入缺失或与代码不一致的结构文档")
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    if not root.is_dir():
        print(f"ERROR: 目标仓库目录不存在：{root}", file=sys.stderr)
        return 2
    try:
        problems = process(root, args.write)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for item in problems:
        print(("WRITTEN: " if args.write else "OUTDATED: ") + item)
    return 0 if args.write or not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
