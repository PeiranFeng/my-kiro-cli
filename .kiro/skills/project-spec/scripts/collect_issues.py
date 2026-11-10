#!/usr/bin/env python3
"""Collect open problems recorded in a repository's project-spec documents and reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from validate_spec import reports_dir

PENDING = "待确认"
NO_TEST = "无现有测试"
REPORTS = ("bootstrap-report.md", "maintain-report.md")
SKIPPED_REPORT_SECTIONS = {"无法验证"}


def bullets_under(lines: Sequence[str]) -> List[Tuple[str, str]]:
    found: List[Tuple[str, str]] = []
    section = ""
    in_fence = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif in_fence:
            continue
        elif line.startswith("## "):
            section = line[3:].strip()
        elif line.startswith("- "):
            found.append((section, line[2:].strip()))
    return found


def read_lines(path: Path) -> List[str]:
    return path.read_text(encoding="utf-8").splitlines()


def collect(project_root: Path, reports: Optional[Path] = None) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {"pending": [], "reports": [], "untested": [], "validation": []}
    reports = reports or reports_dir(project_root)
    docs = project_root / "docs"
    for path in sorted(docs.rglob("*.md")) if docs.is_dir() else []:
        relative = path.relative_to(project_root).as_posix()
        lines = read_lines(path)
        result["pending"] += [f"{relative}：{text}" for section, text in bullets_under(lines) if section == PENDING]
        count = sum(1 for line in lines if NO_TEST in line)
        if count and relative.startswith("docs/test-cases/"):
            result["untested"].append(f"{relative}：{count} 处标注「{NO_TEST}」")
    for name in REPORTS:
        path = reports / name
        if path.is_file():
            result["reports"] += [
                f"{name} 「{section}」：{text}"
                for section, text in bullets_under(read_lines(path))
                if section not in SKIPPED_REPORT_SECTIONS
            ]
    validation = reports / "validation.json"
    if validation.is_file():
        data = json.loads(validation.read_text(encoding="utf-8"))
        result["validation"] += [f"校验错误：{item}" for item in data.get("errors", [])]
        result["validation"] += [f"文档与代码不一致：{item}" for item in data.get("inconsistencies", [])]
        result["validation"] += [f"没有架构文档的源文件：{item}" for item in data.get("unmappedSources", [])]
    return result


TITLES = (
    ("pending", "文档中的待确认问题"),
    ("reports", "报告记录的问题"),
    ("validation", "校验报告"),
    ("untested", "测试缺口"),
)


def render(result: Dict[str, List[str]]) -> str:
    blocks: List[str] = []
    for key, title in TITLES:
        items = result[key]
        blocks.append(f"## {title}（{len(items)}）")
        blocks += [f"- {item}" for item in items]
    return "\n".join(blocks) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".", help="目标仓库根目录")
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    if not root.is_dir():
        print(f"ERROR: 目标仓库目录不存在：{root}", file=sys.stderr)
        return 2
    try:
        print(render(collect(root)), end="")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
