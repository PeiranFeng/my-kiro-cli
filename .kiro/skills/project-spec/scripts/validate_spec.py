#!/usr/bin/env python3
"""Validate project-spec documents and report their consistency with code."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Sequence, Tuple

from gen_structure import STRUCTURE_SUFFIX, render_body, skeleton, split_frontmatter

SPEC_VERSION = 2
CONFIG_RELATIVE = "docs/project-spec.json"
DEFAULT_REPORT = ".project-spec/validation.json"
TREES = ("requirements", "architecture", "test-cases")
JOURNEY_DIR = "journeys"
README = "README.md"

ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z0-9][a-z0-9_-]*)+$")
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
KEBAB_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SECTION_PATTERN = re.compile(r"^#{2,3}\s+(.*?)\s*\{#([^}\s]+)\}\s*$")
IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

KIND_PREFIX = {
    "requirement": "req.",
    "constraint": "req.",
    "module": "arch.",
    "package": "arch.",
    "source": "arch.",
    "structure": "struct.",
    "cases": "cases.",
    "journey": "journey.",
}
TREE_KINDS = {
    "requirements": {"requirement", "constraint"},
    "architecture": {"module", "package", "source", "structure"},
    "test-cases": {"cases", "journey"},
}
KIND_FIELDS = {
    "requirement": set(),
    "constraint": set(),
    "module": {"requirements", "depends-on"},
    "package": {"requirements", "depends-on"},
    "source": {"requirements", "depends-on"},
    "structure": set(),
    "cases": {"verifies"},
    "journey": {"targets", "verifies"},
}
LIST_FIELDS = {"requirements", "depends-on", "targets", "verifies"}
REQUIRED_FIELDS = ("id", "kind", "status")
STATUSES = {"draft", "approved", "implemented"}
SECTION_PREFIX = {"structure": "api.", "cases": "cases."}
REQUIREMENT_SECTION = "需求"
ENTRY_PATTERN = re.compile(r"^- r(\d+) (.+)$")
CLAUSE_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"^当.+?时，.+?应",
        r"^在.+?期间，.+?应",
        r"^若.+?，则.+?应",
        r"^在具备.+?的情况下，.+?应",
        r"^[^，。]+?应",
    )
]


@dataclass
class TestRoot:
    tests: str
    test_file: str


@dataclass
class Module:
    source: str
    root: TestRoot


@dataclass
class Config:
    suffixes: List[str] = field(default_factory=list)
    modules: Dict[str, Module] = field(default_factory=dict)
    journeys: Optional[TestRoot] = None


@dataclass
class Section:
    identifier: str
    title: str


@dataclass
class Doc:
    tree: str
    relative: str
    path: Path
    metadata: Dict[str, Any]
    sections: List[Section] = field(default_factory=list)
    body: List[str] = field(default_factory=list)

    @property
    def display(self) -> str:
        return f"docs/{self.tree}/{self.relative}"

    @property
    def parts(self) -> Tuple[str, ...]:
        return PurePosixPath(self.relative).parts

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

    @property
    def section_ids(self) -> List[str]:
        return [section.identifier for section in self.sections]

    def values(self, name: str) -> List[str]:
        value = self.metadata.get(name, [])
        return value if isinstance(value, list) else []


class Result:
    def __init__(self) -> None:
        self.errors: List[str] = []
        self.inconsistencies: List[str] = []

    def error(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def inconsistent(self, where: str, message: str) -> None:
        self.inconsistencies.append(f"{where}: {message}")


def _safe_relative(value: str) -> bool:
    if not value or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts


def _test_root(spec: Any, where: str, result: Result) -> Optional[TestRoot]:
    if not isinstance(spec, dict):
        result.error(where, "必须是 object")
        return None
    tests, test_file = spec.get("tests"), spec.get("testFile")
    valid = True
    if not isinstance(tests, str) or not _safe_relative(tests):
        result.error(where, "tests 必须是 / 分隔的仓库相对路径")
        valid = False
    if not isinstance(test_file, str) or "{stem}" not in test_file or "/" in test_file:
        result.error(where, "testFile 必须是包含 {stem} 的文件名模板")
        valid = False
    return TestRoot(tests, test_file) if valid else None


def load_config(project_root: Path, result: Result) -> Config:
    config = Config()
    path = project_root / CONFIG_RELATIVE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        result.error(CONFIG_RELATIVE, "缺少配置文件")
        return config
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        result.error(CONFIG_RELATIVE, f"无法读取有效 JSON：{exc}")
        return config
    if not isinstance(raw, dict):
        result.error(CONFIG_RELATIVE, "顶层必须是 JSON object")
        return config
    if raw.get("schemaVersion") != SPEC_VERSION:
        result.error(CONFIG_RELATIVE, f"schemaVersion 必须为 {SPEC_VERSION}")

    suffixes = raw.get("sourceSuffixes")
    if (
        not isinstance(suffixes, list)
        or not suffixes
        or any(not isinstance(item, str) or not re.fullmatch(r"\.[A-Za-z0-9]+", item) for item in suffixes)
    ):
        result.error(CONFIG_RELATIVE, "sourceSuffixes 必须是形如 \".py\" 的非空字符串数组")
    else:
        config.suffixes = suffixes

    if "journeys" in raw:
        config.journeys = _test_root(raw["journeys"], f"{CONFIG_RELATIVE}#journeys", result)

    modules = raw.get("modules")
    if not isinstance(modules, dict) or not modules:
        result.error(CONFIG_RELATIVE, "modules 必须是非空 object")
        return config
    for name, spec in modules.items():
        where = f"{CONFIG_RELATIVE}#modules.{name}"
        if not KEBAB_PATTERN.fullmatch(name) or name == JOURNEY_DIR:
            result.error(where, "模块名必须是小写 kebab-case 且不能为 journeys")
            continue
        root = _test_root(spec, where, result)
        source = spec.get("source") if isinstance(spec, dict) else None
        if not isinstance(source, str) or not _safe_relative(source):
            result.error(where, "source 必须是 / 分隔的仓库相对路径")
            continue
        if root is not None:
            config.modules[name] = Module(source, root)
    return config


def _parse_scalar(raw: str, where: str, key: str, result: Result) -> Optional[str]:
    if raw.startswith('"'):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            result.error(where, f"字段 {key!r} 不是有效的 JSON 字符串：{exc.msg}")
            return None
        if not isinstance(value, str):
            result.error(where, f"字段 {key!r} 必须是字符串")
            return None
        return value
    if raw.startswith(("[", "{")):
        result.error(where, f"字段 {key!r} 必须是标量")
        return None
    return raw


def _frontmatter_end(lines: List[str]) -> Optional[int]:
    if not lines or lines[0].strip() != "---":
        return None
    return next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)


def parse_document(path: Path, where: str, result: Result) -> Optional[Tuple[Dict[str, Any], List[Section], List[str]]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        result.error(where, f"无法按 UTF-8 读取：{exc}")
        return None
    closing = _frontmatter_end(lines)
    if closing is None:
        result.error(where, "必须以 --- 包围的 frontmatter 开头")
        return None

    metadata: Dict[str, Any] = {}
    for number, line in enumerate(lines[1:closing], start=2):
        if not line.strip():
            continue
        if line[:1].isspace() or ":" not in line:
            result.error(where, f"第 {number} 行必须是单行 key: value")
            continue
        key, raw = (part.strip() for part in line.split(":", 1))
        if not KEY_PATTERN.fullmatch(key):
            result.error(where, f"第 {number} 行的键 {key!r} 无效")
            continue
        if key in metadata:
            result.error(where, f"字段 {key!r} 重复")
            continue
        if not raw:
            result.error(where, f"字段 {key!r} 不能为空")
            continue
        if key in LIST_FIELDS:
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                value = None
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                result.error(where, f"字段 {key!r} 必须是单行 JSON 字符串数组")
                continue
            if len(value) != len(set(value)):
                result.error(where, f"字段 {key!r} 包含重复值")
            metadata[key] = value
        else:
            value = _parse_scalar(raw, where, key, result)
            if value is not None:
                metadata[key] = value

    sections: List[Section] = []
    in_fence = False
    for line in lines[closing + 1 :]:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = SECTION_PATTERN.match(line)
        if match:
            sections.append(Section(match.group(2), match.group(1)))
    return metadata, sections, lines[closing + 1 :]


def load_tree(project_root: Path, tree: str, result: Result) -> List[Doc]:
    root = project_root / "docs" / tree
    if not root.is_dir():
        result.error(f"docs/{tree}", "缺少必需目录")
        return []
    docs: List[Doc] = []
    for path in sorted(root.rglob("*.md"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        parsed = parse_document(path, f"docs/{tree}/{relative}", result)
        if parsed is not None:
            docs.append(Doc(tree, relative, path, parsed[0], parsed[1], parsed[2]))
    return docs


def _expected_kind(doc: Doc, config: Config, result: Result) -> Optional[str]:
    parts = doc.parts
    if doc.tree == "requirements":
        if parts[-1] == README or not KEBAB_PATTERN.fullmatch(PurePosixPath(parts[-1]).stem):
            result.error(doc.display, "需求文件名必须是小写 kebab-case 且不能是 README.md")
        if len(parts) == 2 and parts[0] not in config.modules:
            result.error(doc.display, f"目录 {parts[0]!r} 不是配置中的模块")
        elif len(parts) > 2:
            result.error(doc.display, "需求只能位于 requirements/ 根或 requirements/<模块>/ 下")
        return None
    if doc.tree == "architecture":
        if len(parts) < 2 or parts[0] not in config.modules:
            result.error(doc.display, "架构文档必须位于 architecture/<模块>/ 下")
            return None
        if parts[-1] == README:
            return "module" if len(parts) == 2 else "package"
        return "structure" if parts[-1].endswith(STRUCTURE_SUFFIX) else "source"
    if JOURNEY_DIR in parts[:-1]:
        if parts[-2] != JOURNEY_DIR or JOURNEY_DIR in parts[:-2]:
            result.error(doc.display, "journey 必须直接位于某个 journeys/ 目录下")
        if len(parts) > 2 and parts[0] not in config.modules:
            result.error(doc.display, f"目录 {parts[0]!r} 不是配置中的模块")
        if len(parts) == 2 and config.journeys is None:
            result.error(doc.display, "跨模块 journey 需要配置中的 journeys 测试目录")
        return "journey"
    if parts[-1] == README:
        result.error(doc.display, "test-cases 中不允许 README.md")
        return None
    if len(parts) < 2 or parts[0] not in config.modules:
        result.error(doc.display, "用例文档必须位于 test-cases/<模块>/ 下")
        return None
    return "cases"


def validate_shape(doc: Doc, config: Config, result: Result) -> None:
    for name in REQUIRED_FIELDS:
        if name not in doc.metadata:
            result.error(doc.display, f"缺少必需字段 {name!r}")
    kind = doc.kind
    if kind and kind not in TREE_KINDS[doc.tree]:
        result.error(doc.display, f"kind {kind!r} 不属于 {doc.tree}")
    expected = _expected_kind(doc, config, result)
    if expected and kind and kind != expected:
        result.error(doc.display, f"该位置的 kind 必须是 {expected!r}")
    if doc.node_id:
        if not ID_PATTERN.fullmatch(doc.node_id):
            result.error(doc.display, f"id {doc.node_id!r} 必须是小写点分 ID")
        elif kind in KIND_PREFIX and not doc.node_id.startswith(KIND_PREFIX[kind]):
            result.error(doc.display, f"kind {kind!r} 的 id 必须以 {KIND_PREFIX[kind]!r} 开头")
    if doc.status and doc.status not in STATUSES:
        result.error(doc.display, f"status {doc.status!r} 无效")
    if kind in KIND_FIELDS:
        allowed = KIND_FIELDS[kind] | set(REQUIRED_FIELDS)
        for name in sorted(set(doc.metadata) - allowed):
            result.error(doc.display, f"kind {kind!r} 不允许字段 {name!r}")
    prefix = SECTION_PREFIX.get(kind)
    for section_id in doc.section_ids:
        if prefix is None:
            result.error(doc.display, f"kind {kind!r} 的文档不能声明小节 ID {section_id!r}")
        elif not ID_PATTERN.fullmatch(section_id) or not section_id.startswith(prefix):
            result.error(doc.display, f"小节 ID {section_id!r} 必须是以 {prefix!r} 开头的小写点分 ID")


def _doc_module(doc: Doc) -> Optional[str]:
    parts = doc.parts
    if doc.tree == "requirements":
        return parts[0] if len(parts) == 2 else None
    if doc.kind == "journey" and parts[0] == JOURNEY_DIR:
        return None
    return parts[0]


def source_candidates(doc: Doc, config: Config) -> List[str]:
    module = config.modules.get(doc.parts[0])
    if module is None:
        return []
    inner = PurePosixPath(*doc.parts[1:])
    if doc.kind in {"module", "package"}:
        return [PurePosixPath(module.source, inner.parent).as_posix()]
    if doc.kind == "structure":
        inner = inner.with_name(inner.name[: -len(STRUCTURE_SUFFIX)] + ".md")
    stem = inner.with_suffix("").as_posix()
    return [PurePosixPath(module.source, f"{stem}{suffix}").as_posix() for suffix in config.suffixes]


def test_path(doc: Doc, config: Config) -> Optional[str]:
    parts = doc.parts
    if doc.kind == "journey" and len(parts) == 2:
        root, inner = config.journeys, PurePosixPath(parts[-1])
        if root is None:
            return None
        return PurePosixPath(root.tests, root.test_file.format(stem=inner.stem)).as_posix()
    module = config.modules.get(parts[0])
    if module is None:
        return None
    inner = PurePosixPath(*parts[1:])
    name = module.root.test_file.format(stem=inner.stem)
    return PurePosixPath(module.root.tests, inner.parent, name).as_posix()


def section_symbol(title: str) -> Optional[str]:
    names = IDENTIFIER_PATTERN.findall(title.replace("`", "").split("(", 1)[0])
    return names[-1] if names else None


def _common_dir(dirs: List[Tuple[str, ...]]) -> Tuple[str, ...]:
    common: List[str] = []
    for items in zip(*dirs):
        if len(set(items)) != 1:
            break
        common.append(items[0])
    return tuple(common)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def check_code(project_root: Path, docs: List[Doc], config: Config, result: Result) -> Dict[str, Dict[str, Optional[str]]]:
    paths: Dict[str, Dict[str, Optional[str]]] = {}
    for doc in docs:
        if not doc.node_id:
            continue
        entry: Dict[str, Optional[str]] = {"doc": doc.display}
        implemented = doc.status == "implemented"
        if doc.tree == "architecture":
            candidates = source_candidates(doc, config)
            found = next((item for item in candidates if (project_root / item).exists()), None)
            entry["source"] = found or (candidates[0] if candidates else None)
            if implemented and candidates and found is None:
                result.inconsistent(doc.display, f"已实现但源码不存在：{candidates[0]}")
            if implemented and found and doc.kind == "structure":
                text = _read(project_root / found)
                for section in doc.sections:
                    symbol = section_symbol(section.title)
                    if symbol and not re.search(rf"\b{re.escape(symbol)}\b", text):
                        result.inconsistent(doc.display, f"接口 {section.identifier!r} 的符号 {symbol!r} 不在 {found} 中")
                if found.endswith(".py"):
                    check_structure(doc, text, result)
        elif doc.tree == "test-cases":
            expected = test_path(doc, config)
            entry["test"] = expected
            if implemented and expected and not (project_root / expected).is_file():
                result.inconsistent(doc.display, f"已实现但测试文件不存在：{expected}")
        paths[doc.node_id] = entry
    return paths


def check_structure(doc: Doc, source_text: str, result: Result) -> None:
    stem = PurePosixPath(doc.relative).name[: -len(STRUCTURE_SUFFIX)]
    try:
        expected = render_body(source_text, doc.parts[0], stem)
    except SyntaxError as exc:
        result.inconsistent(doc.display, f"源码无法解析：{exc.msg}")
        return
    actual = split_frontmatter(_read(doc.path))[1]
    if skeleton(actual) != skeleton(expected):
        result.inconsistent(doc.display, "结构与源码不一致，运行 gen_structure.py 查看差异")


def check_requirement_entries(doc: Doc, result: Result) -> None:
    entries: List[str] = []
    in_section = in_fence = False
    for line in doc.body:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif in_fence:
            continue
        elif line.startswith("## "):
            in_section = line[3:].strip() == REQUIREMENT_SECTION
        elif in_section and line.startswith("- "):
            entries.append(line)
    if not entries:
        result.error(doc.display, f"缺少含条目的 ## {REQUIREMENT_SECTION} 小节")
        return
    numbers: List[str] = []
    for line in entries:
        match = ENTRY_PATTERN.match(line)
        if match is None:
            result.error(doc.display, f"需求条目必须以 '- r<编号> ' 开头：{line!r}")
            continue
        numbers.append(match.group(1))
        text = match.group(2)
        if not text.endswith("。") or text.count("。") != 1:
            result.error(doc.display, f"需求条目 r{match.group(1)} 必须恰好是一句话")
        if not any(pattern.match(text) for pattern in CLAUSE_PATTERNS):
            result.error(doc.display, f"需求条目 r{match.group(1)} 不符合五种句式之一")
    if len(numbers) != len(set(numbers)):
        result.error(doc.display, "需求条目编号重复")


def unmapped_sources(project_root: Path, architecture: List[Doc], config: Config) -> List[str]:
    documented = {doc.relative for doc in architecture}
    unmapped: List[str] = []
    for name, module in config.modules.items():
        root = project_root / module.source
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in config.suffixes:
                continue
            inner = path.relative_to(root).with_suffix(".md").as_posix()
            if f"{name}/{inner}" not in documented:
                unmapped.append(path.relative_to(project_root).as_posix())
    return unmapped


def validate_project(project_root: Path) -> Dict[str, Any]:
    project_root = project_root.resolve()
    result = Result()
    config = load_config(project_root, result)
    trees = {tree: load_tree(project_root, tree, result) for tree in TREES}
    all_docs = [doc for tree in TREES for doc in trees[tree]]

    for doc in all_docs:
        validate_shape(doc, config, result)
        if doc.kind in {"requirement", "constraint"}:
            check_requirement_entries(doc, result)

    owner: Dict[str, str] = {}
    section_parent: Dict[str, Doc] = {}
    for doc in all_docs:
        for identifier in [doc.node_id, *doc.section_ids]:
            if not identifier:
                continue
            if identifier in owner:
                result.error(doc.display, f"id {identifier!r} 与 {owner[identifier]} 重复")
                continue
            owner[identifier] = doc.display
        for section_id in doc.section_ids:
            section_parent.setdefault(section_id, doc)

    requirements = {doc.node_id: doc for doc in trees["requirements"] if doc.node_id}
    architecture = {doc.node_id: doc for doc in trees["architecture"] if doc.node_id}
    arch_by_relative = {doc.relative: doc for doc in trees["architecture"]}
    cases_by_relative = {doc.relative: doc for doc in trees["test-cases"] if doc.kind == "cases"}
    structure_by_relative = {doc.relative[: -len(STRUCTURE_SUFFIX)] + ".md": doc for doc in trees["architecture"] if doc.kind == "structure"}

    for module_name in config.modules:
        entry = arch_by_relative.get(f"{module_name}/{README}")
        if entry is None or entry.kind != "module":
            result.error(f"docs/architecture/{module_name}", "模块缺少 kind 为 module 的 README.md")

    def check_requirement_refs(doc: Doc, name: str, allowed: Optional[set] = None) -> None:
        module = _doc_module(doc)
        for requirement_id in doc.values(name):
            target = requirements.get(requirement_id)
            if target is None:
                result.error(doc.display, f"{name} 引用了不存在的需求 {requirement_id!r}")
                continue
            if module is not None and _doc_module(target) not in {None, module}:
                result.error(doc.display, f"{name} 只能引用本模块或项目级需求：{requirement_id!r}")
            if allowed is not None and requirement_id not in allowed:
                result.error(doc.display, f"{name} 引用的需求 {requirement_id!r} 不在镜像架构文档的 requirements 中")
            if target.status == "draft" and doc.status != "draft":
                result.inconsistent(doc.display, f"{doc.status} 文档依赖的需求 {requirement_id!r} 是 draft")

    for doc in trees["architecture"]:
        check_requirement_refs(doc, "requirements")
        for dependency in doc.values("depends-on"):
            target = architecture.get(dependency)
            if target is None or target is doc:
                result.error(doc.display, f"depends-on 引用了不存在或自身的架构文档 {dependency!r}")
        if doc.kind == "source" and doc.relative not in structure_by_relative:
            result.error(doc.display, "源文件文档缺少同路径的结构文档 <文件名>.structure.md")
        if doc.kind != "structure":
            continue
        if arch_by_relative.get(doc.relative[: -len(STRUCTURE_SUFFIX)] + ".md") is None:
            result.error(doc.display, "没有同路径的源文件架构文档")
        if not doc.sections:
            continue
        mirror = cases_by_relative.get(doc.relative[: -len(STRUCTURE_SUFFIX)] + ".md")
        if mirror is None:
            result.error(doc.display, "含公开接口的结构文档缺少同路径的用例文档")
            continue
        for api_id in doc.section_ids:
            case_id = "cases." + api_id[len("api.") :]
            if case_id not in mirror.section_ids:
                result.error(mirror.display, f"缺少接口 {api_id!r} 对应的用例小节 {case_id!r}")

    for doc in trees["test-cases"]:
        if not doc.values("verifies"):
            result.error(doc.display, "用例必须至少声明一个 verifies")
        if doc.kind == "cases":
            mirror = arch_by_relative.get(doc.relative)
            if mirror is None or mirror.kind != "source":
                result.error(doc.display, "没有同路径的源文件架构文档")
                check_requirement_refs(doc, "verifies")
                continue
            check_requirement_refs(doc, "verifies", set(mirror.values("requirements")))
            api_ids = structure_by_relative[doc.relative].section_ids if doc.relative in structure_by_relative else []
            for case_id in doc.section_ids:
                api_id = "api." + case_id[len("cases.") :]
                if api_id not in api_ids:
                    result.error(doc.display, f"用例小节 {case_id!r} 没有对应接口 {api_id!r}")
        elif doc.kind == "journey":
            check_requirement_refs(doc, "verifies")
            targets = doc.values("targets")
            if not targets:
                result.error(doc.display, "journey 必须至少声明一个 targets")
            target_dirs: List[Tuple[str, ...]] = []
            for target_id in targets:
                parent = section_parent.get(target_id) if target_id.startswith("api.") else architecture.get(target_id)
                if parent is None or parent.tree != "architecture":
                    result.error(doc.display, f"targets 引用了不存在的接口或架构文档 {target_id!r}")
                    continue
                target_dirs.append(parent.parts[:-1])
            if target_dirs and len(target_dirs) == len(targets):
                expected = PurePosixPath(*_common_dir(target_dirs), JOURNEY_DIR).as_posix()
                actual = PurePosixPath(doc.relative).parent.as_posix()
                if actual != expected:
                    result.error(doc.display, f"journey 必须位于 targets 的最近公共目录 test-cases/{expected}/")

    for requirement_id, requirement in sorted(requirements.items()):
        if requirement.status != "implemented":
            continue
        if not any(requirement_id in doc.values("requirements") for doc in trees["architecture"]):
            result.error(requirement.display, "已实现需求没有架构文档声明满足关系")
        if not any(requirement_id in doc.values("verifies") for doc in trees["test-cases"]):
            result.error(requirement.display, "已实现需求没有用例声明验证关系")

    paths = check_code(project_root, all_docs, config, result)
    unmapped = unmapped_sources(project_root, trees["architecture"], config)
    return build_report(project_root, all_docs, paths, unmapped, result)


def _content_without_status(doc: Doc) -> bytes:
    lines = _read(doc.path).splitlines()
    closing = _frontmatter_end(lines) or 0
    kept = [line for index, line in enumerate(lines) if not (0 < index < closing and line.startswith("status:"))]
    return ("\n".join(kept) + "\n").encode("utf-8")


def fingerprint(project_root: Path, docs: Sequence[Doc]) -> str:
    digest = hashlib.sha256()
    config_path = project_root / CONFIG_RELATIVE
    digest.update(config_path.read_bytes() if config_path.is_file() else b"<missing>")
    digest.update(b"\0")
    for doc in sorted(docs, key=lambda item: (item.tree, item.relative)):
        for chunk in (doc.tree.encode("utf-8"), doc.relative.encode("utf-8"), _content_without_status(doc)):
            digest.update(chunk)
            digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def build_report(
    project_root: Path,
    docs: Sequence[Doc],
    paths: Dict[str, Dict[str, Optional[str]]],
    unmapped: List[str],
    result: Result,
) -> Dict[str, Any]:
    errors = sorted(set(result.errors))
    inconsistencies = sorted(set(result.inconsistencies))
    nodes: Dict[str, str] = {}
    sections: Dict[str, str] = {}
    for doc in docs:
        if not doc.node_id:
            continue
        nodes.setdefault(doc.node_id, doc.status)
        for section_id in doc.section_ids:
            nodes.setdefault(section_id, doc.status)
            sections.setdefault(section_id, doc.node_id)
    return {
        "specVersion": SPEC_VERSION,
        "specFingerprint": fingerprint(project_root, docs),
        "valid": not errors,
        "counts": {
            "documents": len(docs),
            "sections": len(sections),
            "errors": len(errors),
            "inconsistencies": len(inconsistencies),
            "unmappedSources": len(unmapped),
        },
        "nodes": dict(sorted(nodes.items())),
        "sections": dict(sorted(sections.items())),
        "paths": dict(sorted(paths.items())),
        "unmappedSources": unmapped,
        "drafts": sorted(doc.node_id for doc in docs if doc.node_id and doc.status == "draft"),
        "errors": errors,
        "inconsistencies": inconsistencies,
    }


def write_report(project_root: Path, report_path: str, report: Dict[str, Any]) -> None:
    if not _safe_relative(report_path):
        raise ValueError("--report 必须是 / 分隔的仓库相对路径")
    destination = project_root.resolve() / report_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".", help="目标仓库根目录")
    parser.add_argument("--report", default=DEFAULT_REPORT, help="JSON 报告的仓库相对路径")
    parser.add_argument("--json", action="store_true", help="在标准输出打印 JSON")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root)
    if not project_root.is_dir():
        print(f"ERROR: 目标仓库目录不存在：{project_root}", file=sys.stderr)
        return 2
    report = validate_project(project_root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        counts = report["counts"]
        print(
            f"Project spec: {'VALID' if report['valid'] else 'INVALID'} | documents={counts['documents']} "
            f"errors={counts['errors']} inconsistencies={counts['inconsistencies']} "
            f"unmappedSources={counts['unmappedSources']} drafts={len(report['drafts'])} | {report['specFingerprint']}"
        )
        for message in report["errors"]:
            print(f"ERROR: {message}")
        for message in report["inconsistencies"]:
            print(f"INCONSISTENT: {message}")
    try:
        write_report(project_root, args.report, report)
    except (OSError, ValueError) as exc:
        print(f"ERROR: 无法写入报告：{exc}", file=sys.stderr)
        return 2
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
