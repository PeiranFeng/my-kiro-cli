#!/usr/bin/env python3
"""List, check, add, update, remove and restore principles stored under references/principles/."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1] / "references" / "principles"
TRASH = "trash"
CATEGORIES = {"requirement": "Q", "architecture": "A", "code": "C", "test": "T", "review": "R"}
STAGES = ("requirement", "design", "code", "test", "review")
ID_PATTERN = re.compile(r"^([A-Z])([1-9][0-9]*)$")


@dataclass
class Principle:
    path: Path
    principle_id: str
    title: str
    summary: str
    stages: List[str]
    body: str


def parse(path: Path, errors: List[str]) -> Optional[Principle]:
    lines = path.read_text(encoding="utf-8").splitlines()
    closing = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None) if lines[:1] == ["---"] else None
    if closing is None:
        errors.append(f"{path}: 必须以 --- 包围的 frontmatter 开头")
        return None
    fields = {}
    for line in lines[1:closing]:
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    if set(fields) != {"id", "title", "summary", "stages"}:
        errors.append(f"{path}: frontmatter 字段必须恰为 id、title、summary、stages")
        return None
    try:
        stages = json.loads(fields["stages"])
    except json.JSONDecodeError:
        stages = None
    if not isinstance(stages, list) or not stages or any(item not in STAGES for item in stages) or len(stages) != len(set(stages)):
        errors.append(f"{path}: stages 必须是 {list(STAGES)} 中不重复取值的非空 JSON 数组")
        return None
    body = "\n".join(lines[closing + 1 :]).strip()
    if not fields["id"] or not fields["title"] or not fields["summary"] or not body:
        errors.append(f"{path}: id、title、summary 和正文都不能为空")
        return None
    return Principle(path, fields["id"], fields["title"], fields["summary"], stages, body)


def load(errors: List[str]) -> List[Principle]:
    found: List[Principle] = []
    for category, letter in CATEGORIES.items():
        for path in sorted((ROOT / category).glob("*.md")):
            item = parse(path, errors)
            if item is None:
                continue
            match = ID_PATTERN.match(item.principle_id)
            if match is None or match.group(1) != letter or path.stem != item.principle_id:
                errors.append(f"{path}: id 必须是 {letter}<编号> 且与文件名一致")
                continue
            found.append(item)
    seen = set()
    for item in found:
        if item.principle_id in seen:
            errors.append(f"{item.path}: id {item.principle_id!r} 重复")
        seen.add(item.principle_id)
    return found


def next_id(category: str) -> str:
    letter = CATEGORIES[category]
    paths = [*(ROOT / category).glob("*.md"), *(ROOT / TRASH).glob(f"{letter}*.md")]
    numbers = [int(ID_PATTERN.match(path.stem).group(2)) for path in paths if ID_PATTERN.match(path.stem)]
    return f"{CATEGORIES[category]}{max(numbers, default=0) + 1}"


def find(principle_id: str) -> Principle:
    errors: List[str] = []
    for item in load(errors):
        if item.principle_id == principle_id:
            return item
    raise ValueError(f"不存在原则 {principle_id!r}")


def render(principle_id: str, title: str, summary: str, stages: Sequence[str], body: str) -> str:
    if "\n" in title or "\n" in summary:
        raise ValueError("title 和 summary 必须是单行")
    return f"---\nid: {principle_id}\ntitle: {title}\nsummary: {summary}\nstages: {json.dumps(list(stages))}\n---\n\n{body.strip()}\n"


def update(principle_id: str, title: Optional[str], summary: Optional[str], stages: Optional[Sequence[str]], body: Optional[str]) -> Path:
    current = find(principle_id)
    path = current.path
    path.write_text(render(principle_id, title or current.title, summary or current.summary, stages or current.stages, body or current.body), encoding="utf-8")
    errors: List[str] = []
    if parse(path, errors) is None:
        path.write_text(render(principle_id, current.title, current.summary, current.stages, current.body), encoding="utf-8")
        raise ValueError("; ".join(errors))
    return path


def remove(principle_id: str) -> Path:
    path = find(principle_id).path
    target = ROOT / TRASH / path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    path.rename(target)
    return target


def restore(principle_id: str) -> Path:
    source = ROOT / TRASH / f"{principle_id}.md"
    match = ID_PATTERN.match(principle_id)
    category = next((name for name, letter in CATEGORIES.items() if match and match.group(1) == letter), None)
    if category is None or not source.is_file():
        raise ValueError(f"垃圾箱中不存在原则 {principle_id!r}")
    target = ROOT / category / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    source.rename(target)
    return target


def add(category: str, title: str, summary: str, stages: Sequence[str], body: str) -> Path:
    path = ROOT / category / f"{next_id(category)}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(path.stem, title, summary, stages, body), encoding="utf-8")
    errors: List[str] = []
    if parse(path, errors) is None:
        path.unlink()
        raise ValueError("; ".join(errors))
    return path


def summary(items: Sequence[Principle]) -> List[str]:
    lines: List[str] = []
    for category, letter in CATEGORIES.items():
        group = [item for item in items if item.principle_id.startswith(letter)]
        lines.append(f"{category}（{len(group)}）")
        for item in group:
            lines.append(f"- {item.principle_id} {item.title}：{item.summary}")
    return lines


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="列出原则")
    listing.add_argument("--stage", choices=STAGES)
    listing.add_argument("--summary", action="store_true", help="按分类输出「ID 名词短语：摘要」")
    listing.add_argument("--trash", action="store_true", help="只列出垃圾箱中可恢复的原则文件")
    commands.add_parser("check", help="校验全部原则文件")
    adding = commands.add_parser("add", help="新增原则，编号自动分配")
    adding.add_argument("--category", required=True, choices=sorted(CATEGORIES))
    adding.add_argument("--title", required=True)
    adding.add_argument("--summary", required=True, help="一句话摘要，单行")
    adding.add_argument("--stage", required=True, action="append", choices=STAGES)
    adding.add_argument("--body-file", required=True)
    changing = commands.add_parser("update", help="修改原则的标题、阶段或正文，只改给出的项")
    changing.add_argument("--id", required=True)
    changing.add_argument("--title")
    changing.add_argument("--summary")
    changing.add_argument("--stage", action="append", choices=STAGES)
    changing.add_argument("--body-file")
    deleting = commands.add_parser("remove", help="把原则移入垃圾箱，可用 restore 恢复")
    deleting.add_argument("--id", required=True)
    restoring = commands.add_parser("restore", help="把垃圾箱中的原则恢复到原目录")
    restoring.add_argument("--id", required=True)
    args = parser.parse_args(argv)

    errors: List[str] = []
    if args.command == "add":
        try:
            body = Path(args.body_file).read_text(encoding="utf-8")
            print(add(args.category, args.title, args.summary, args.stage, body))
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.command in {"update", "remove", "restore"}:
        try:
            if args.command == "remove":
                print(remove(args.id))
            elif args.command == "restore":
                print(restore(args.id))
            else:
                body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else None
                print(update(args.id, args.title, args.summary, args.stage, body))
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        return 0
    items = load(errors)
    if args.command == "list" and args.trash:
        for path in sorted((ROOT / TRASH).glob("*.md")):
            print(path)
        return 0
    if args.command == "list" and args.summary:
        print("\n".join(summary(items)))
    elif args.command == "list":
        for item in items:
            if args.stage is None or args.stage in item.stages:
                print(f"{item.principle_id}\t{item.title}\t{','.join(item.stages)}\t{item.path}")
    for message in errors:
        print(f"ERROR: {message}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
