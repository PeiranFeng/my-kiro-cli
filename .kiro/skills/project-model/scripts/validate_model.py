#!/usr/bin/env python3
"""Validate a project-model Markdown architecture tree and use-case tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

MODEL_VERSION = 1
ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z0-9][a-z0-9-]*)+$")
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
PATH_PART_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

ARCHITECTURE_KINDS = {
    "requirement",
    "constraint",
    "system",
    "domain",
    "module",
    "component",
    "class",
    "interface",
    "event",
    "data-model",
}
USE_CASE_KINDS = {
    "interface-cases",
    "component-cases",
    "journey",
    "quality-cases",
}
STATUSES = {"draft", "approved", "deprecated"}
ORIGINS = {"explicit", "inferred", "reconciled"}
LIST_FIELDS = {
    "requirements",
    "depends-on",
    "implementation",
    "targets",
    "verifies",
    "automation",
}
REQUIRED_FIELDS = {"id", "kind", "status", "origin"}


@dataclass(frozen=True)
class Node:
    tree: str
    relative_path: str
    source_path: Path
    metadata: Dict[str, Any]

    @property
    def node_id(self) -> str:
        value = self.metadata.get("id")
        return value if isinstance(value, str) else ""

    @property
    def kind(self) -> str:
        value = self.metadata.get("kind")
        return value if isinstance(value, str) else ""

    @property
    def status(self) -> str:
        value = self.metadata.get("status")
        return value if isinstance(value, str) else ""

    def values(self, field: str) -> List[str]:
        value = self.metadata.get(field, [])
        return value if isinstance(value, list) else []


class Result:
    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def error(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def warning(self, path: str, message: str) -> None:
        self.warnings.append(f"{path}: {message}")


def _parse_scalar(raw: str, path: str, key: str, result: Result) -> Optional[str]:
    if raw.startswith('"'):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            result.error(path, f"字段 {key!r} 不是有效的 JSON 字符串：{exc.msg}")
            return None
        if not isinstance(value, str):
            result.error(path, f"字段 {key!r} 必须是字符串")
            return None
        return value
    if raw.startswith("[") or raw.startswith("{"):
        result.error(path, f"字段 {key!r} 必须是标量")
        return None
    return raw


def parse_frontmatter(path: Path, display_path: str, result: Result) -> Optional[Dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        result.error(display_path, f"无法按 UTF-8 读取：{exc}")
        return None

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        result.error(display_path, "第一行必须是 frontmatter 起始符 ---")
        return None

    closing_index: Optional[int] = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        result.error(display_path, "缺少 frontmatter 结束符 ---")
        return None

    metadata: Dict[str, Any] = {}
    for line_number, line in enumerate(lines[1:closing_index], start=2):
        if not line.strip():
            continue
        if line[:1].isspace():
            result.error(display_path, f"第 {line_number} 行使用了不支持的缩进结构")
            continue
        if ":" not in line:
            result.error(display_path, f"第 {line_number} 行缺少 key: value 分隔符")
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if not KEY_PATTERN.fullmatch(key):
            result.error(display_path, f"第 {line_number} 行的键 {key!r} 无效")
            continue
        if key in metadata:
            result.error(display_path, f"字段 {key!r} 重复")
            continue
        if not raw_value:
            result.error(display_path, f"字段 {key!r} 不能为空")
            continue

        if key in LIST_FIELDS:
            try:
                value = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                result.error(display_path, f"字段 {key!r} 必须是单行 JSON 字符串数组：{exc.msg}")
                continue
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                result.error(display_path, f"字段 {key!r} 必须是单行 JSON 字符串数组")
                continue
            if len(value) != len(set(value)):
                result.error(display_path, f"字段 {key!r} 包含重复值")
            metadata[key] = value
        else:
            value = _parse_scalar(raw_value, display_path, key, result)
            if value is not None:
                metadata[key] = value

    return metadata


def _validate_relative_path(relative_path: str, result: Result) -> None:
    path = Path(relative_path)
    for directory in path.parts[:-1]:
        if not PATH_PART_PATTERN.fullmatch(directory):
            result.error(relative_path, f"目录名 {directory!r} 必须使用小写 kebab-case")
    if path.name == "README.md":
        result.error(relative_path, "README.md 只允许位于 docs/project-model/ 根目录")
        return
    if path.suffix != ".md" or not PATH_PART_PATTERN.fullmatch(path.stem):
        result.error(relative_path, "Markdown 文件名必须使用小写 kebab-case")


def _load_tree(tree_root: Path, tree_name: str, model_root: Path, result: Result) -> List[Node]:
    nodes: List[Node] = []
    if not tree_root.is_dir():
        result.error(tree_name, "缺少必需目录")
        return nodes

    for path in sorted(tree_root.rglob("*.md"), key=lambda item: item.as_posix()):
        tree_relative = path.relative_to(tree_root).as_posix()
        display_path = path.relative_to(model_root).as_posix()
        _validate_relative_path(tree_relative, result)
        metadata = parse_frontmatter(path, display_path, result)
        if metadata is None:
            continue
        nodes.append(Node(tree_name, tree_relative, path, metadata))
    return nodes


def _validate_node_shape(node: Node, result: Result) -> None:
    display_path = f"{node.tree}/{node.relative_path}"
    missing = sorted(REQUIRED_FIELDS - node.metadata.keys())
    for field in missing:
        result.error(display_path, f"缺少必需字段 {field!r}")

    node_id = node.node_id
    if node_id and not ID_PATTERN.fullmatch(node_id):
        result.error(display_path, f"id {node_id!r} 必须是稳定的小写点分 ID")

    kind = node.kind
    allowed_kinds = ARCHITECTURE_KINDS if node.tree == "architecture" else USE_CASE_KINDS
    if kind and kind not in allowed_kinds:
        result.error(display_path, f"kind {kind!r} 不属于 {node.tree} 节点类型")

    status = node.status
    if status and status not in STATUSES:
        result.error(display_path, f"status {status!r} 无效")

    origin = node.metadata.get("origin")
    if isinstance(origin, str) and origin not in ORIGINS:
        result.error(display_path, f"origin {origin!r} 无效")

    for field in LIST_FIELDS:
        if field in node.metadata and not isinstance(node.metadata[field], list):
            result.error(display_path, f"字段 {field!r} 必须是字符串数组")


def _check_source_references(
    node: Node,
    field: str,
    project_root: Path,
    result: Result,
) -> None:
    display_path = f"{node.tree}/{node.relative_path}"
    for reference in node.values(field):
        file_part = reference.split("#", 1)[0]
        if "\\" in file_part or ":" in file_part:
            result.error(display_path, f"{field} 引用必须使用 / 分隔的仓库相对路径：{reference!r}")
            continue
        ref_path = PurePosixPath(file_part)
        if ref_path.is_absolute() or ".." in ref_path.parts:
            result.error(display_path, f"{field} 引用必须是目标仓库内的相对路径：{reference!r}")
            continue
        local_path = project_root.joinpath(*ref_path.parts)
        if not local_path.is_file():
            result.warning(display_path, f"{field} 尚未定位到文件：{reference!r}")


def validate_project(project_root: Path, model_relative: str = "docs/project-model") -> Dict[str, Any]:
    project_root = project_root.resolve()
    model_root = (project_root / model_relative).resolve()
    result = Result()

    try:
        model_root.relative_to(project_root)
    except ValueError:
        result.error(model_relative, "模型目录必须位于目标仓库内")
        return _build_report([], [], result)

    architecture = _load_tree(model_root / "architecture", "architecture", model_root, result)
    use_cases = _load_tree(model_root / "use-cases", "use-cases", model_root, result)
    all_nodes = architecture + use_cases

    for node in all_nodes:
        _validate_node_shape(node, result)

    by_id: Dict[str, Node] = {}
    for node in all_nodes:
        if not node.node_id:
            continue
        previous = by_id.get(node.node_id)
        if previous is not None:
            result.error(
                f"{node.tree}/{node.relative_path}",
                f"id {node.node_id!r} 与 {previous.tree}/{previous.relative_path} 重复",
            )
        else:
            by_id[node.node_id] = node

    architecture_by_id = {node.node_id: node for node in architecture if node.node_id}
    requirements = {
        node.node_id: node
        for node in architecture
        if node.node_id and node.kind in {"requirement", "constraint"}
    }
    use_cases_by_relative = {node.relative_path: node for node in use_cases}
    interfaces_by_relative = {
        node.relative_path: node
        for node in architecture
        if node.kind == "interface" and node.status != "deprecated"
    }

    for node in architecture:
        display_path = f"architecture/{node.relative_path}"
        if node.status == "deprecated":
            continue
        for requirement_id in node.values("requirements"):
            target = requirements.get(requirement_id)
            if target is None or target.status == "deprecated":
                result.error(display_path, f"requirements 引用了不存在或已废弃的需求 {requirement_id!r}")
        for dependency_id in node.values("depends-on"):
            target = architecture_by_id.get(dependency_id)
            if target is None or target.status == "deprecated":
                result.error(display_path, f"depends-on 引用了不存在或已废弃的架构节点 {dependency_id!r}")
        _check_source_references(node, "implementation", project_root, result)

    for node in use_cases:
        display_path = f"use-cases/{node.relative_path}"
        if node.status == "deprecated":
            continue
        if not node.values("targets"):
            result.error(display_path, "未废弃用例必须至少声明一个 targets")
        if not node.values("verifies"):
            result.error(display_path, "未废弃用例必须至少声明一个 verifies")
        for target_id in node.values("targets"):
            target = architecture_by_id.get(target_id)
            if target is None or target.status == "deprecated":
                result.error(display_path, f"targets 引用了不存在或已废弃的架构节点 {target_id!r}")
        for requirement_id in node.values("verifies"):
            target = requirements.get(requirement_id)
            if target is None or target.status == "deprecated":
                result.error(display_path, f"verifies 引用了不存在或已废弃的需求 {requirement_id!r}")
        if node.status == "approved" and not node.values("automation"):
            result.warning(display_path, "已批准用例尚未关联自动化测试")
        _check_source_references(node, "automation", project_root, result)

        if node.kind == "interface-cases":
            interface = interfaces_by_relative.get(node.relative_path)
            if interface is None:
                result.error(display_path, "interface-cases 没有同相对路径的未废弃 interface")
            elif interface.node_id not in node.values("targets"):
                result.error(display_path, f"targets 必须包含镜像接口 {interface.node_id!r}")

    for relative_path, interface in sorted(interfaces_by_relative.items()):
        mirror = use_cases_by_relative.get(relative_path)
        display_path = f"architecture/{relative_path}"
        if mirror is None or mirror.status == "deprecated":
            result.error(display_path, "公开接口缺少同相对路径的用例文件")
        elif mirror.kind != "interface-cases":
            result.error(display_path, "镜像用例文件的 kind 必须是 interface-cases")

    active_architecture = [node for node in architecture if node.status != "deprecated"]
    active_use_cases = [node for node in use_cases if node.status != "deprecated"]
    for requirement_id, requirement in sorted(requirements.items()):
        if requirement.status != "approved":
            continue
        implemented = any(
            node.kind not in {"requirement", "constraint"}
            and requirement_id in node.values("requirements")
            for node in active_architecture
        )
        verified = any(requirement_id in node.values("verifies") for node in active_use_cases)
        display_path = f"architecture/{requirement.relative_path}"
        if not implemented:
            result.error(display_path, "已批准需求没有架构节点声明实现关系")
        if not verified:
            result.error(display_path, "已批准需求没有用例声明验证关系")

    return _build_report(architecture, use_cases, result)


def _node_fingerprint_content(node: Node, semantic: bool) -> bytes:
    try:
        raw = node.source_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return b"<unreadable>"
    if not semantic:
        return raw.encode("utf-8")

    excluded_field = "implementation" if node.tree == "architecture" else "automation"
    lines = raw.splitlines()
    in_frontmatter = bool(lines and lines[0].strip() == "---")
    output: List[str] = []
    closing_seen = False
    for index, line in enumerate(lines):
        if index > 0 and in_frontmatter and line.strip() == "---":
            closing_seen = True
            output.append(line)
            continue
        if in_frontmatter and not closing_seen and line.startswith(f"{excluded_field}:"):
            continue
        output.append(line)
    return ("\n".join(output) + "\n").encode("utf-8")


def _model_fingerprint(
    architecture: Sequence[Node], use_cases: Sequence[Node], semantic: bool = False
) -> str:
    digest = hashlib.sha256()
    nodes = sorted(
        [*architecture, *use_cases],
        key=lambda node: (node.tree, node.relative_path),
    )
    for node in nodes:
        digest.update(node.tree.encode("utf-8"))
        digest.update(b"\0")
        digest.update(node.relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_node_fingerprint_content(node, semantic))
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _build_report(architecture: Sequence[Node], use_cases: Sequence[Node], result: Result) -> Dict[str, Any]:
    errors = sorted(set(result.errors))
    warnings = sorted(set(result.warnings))
    return {
        "modelVersion": MODEL_VERSION,
        "modelFingerprint": _model_fingerprint(architecture, use_cases),
        "modelSemanticFingerprint": _model_fingerprint(
            architecture, use_cases, semantic=True
        ),
        "valid": not errors,
        "counts": {
            "architectureNodes": len(architecture),
            "useCaseNodes": len(use_cases),
            "errors": len(errors),
            "warnings": len(warnings),
        },
        "nodes": {
            "architecture": {
                node.node_id: node.status for node in sorted(architecture, key=lambda item: item.node_id) if node.node_id
            },
            "useCases": {
                node.node_id: node.status for node in sorted(use_cases, key=lambda item: item.node_id) if node.node_id
            },
        },
        "errors": errors,
        "warnings": warnings,
    }


def _print_text(report: Dict[str, Any]) -> None:
    counts = report["counts"]
    state = "VALID" if report["valid"] else "INVALID"
    print(
        f"Project model: {state} | architecture={counts['architectureNodes']} "
        f"use-cases={counts['useCaseNodes']} errors={counts['errors']} "
        f"warnings={counts['warnings']}"
    )
    for message in report["errors"]:
        print(f"ERROR: {message}")
    for message in report["warnings"]:
        print(f"WARNING: {message}")


def _write_report(project_root: Path, report_path: str, report: Dict[str, Any]) -> None:
    if "\\" in report_path or ":" in report_path:
        raise ValueError("--report 必须使用 / 分隔的仓库相对路径")
    candidate = Path(report_path)
    if candidate.is_absolute():
        raise ValueError("--report 必须是目标仓库内的相对路径")
    destination = (project_root.resolve() / candidate).resolve()
    try:
        destination.relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError("--report 必须位于目标仓库内") from exc
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".", help="目标仓库根目录，默认当前目录")
    parser.add_argument(
        "--model-path",
        default="docs/project-model",
        help="相对目标仓库的模型目录",
    )
    parser.add_argument("--report", help="将 JSON 报告写到目标仓库内的相对路径")
    parser.add_argument("--json", action="store_true", help="在标准输出打印 JSON")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_argument_parser().parse_args(argv)
    project_root = Path(args.project_root)
    if not project_root.is_dir():
        print(f"ERROR: 目标仓库目录不存在：{project_root}", file=sys.stderr)
        return 2

    report = validate_project(project_root, args.model_path)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_text(report)

    if args.report:
        try:
            _write_report(project_root, args.report, report)
        except (OSError, ValueError) as exc:
            print(f"ERROR: 无法写入报告：{exc}", file=sys.stderr)
            return 2

    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
