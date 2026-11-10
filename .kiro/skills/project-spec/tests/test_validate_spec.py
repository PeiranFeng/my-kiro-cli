#!/usr/bin/env python3
"""Tests for validate_spec.py using only the Python standard library."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from gen_structure import render_body  # noqa: E402
from validate_spec import section_symbol, validate_project, write_report  # noqa: E402

CONFIG = {
    "schemaVersion": 2,
    "sourceSuffixes": [".py"],
    "journeys": {"tests": "tests/journeys", "testFile": "test_{stem}.py"},
    "modules": {
        "data": {"source": "app/data", "tests": "tests/data", "testFile": "test_{stem}.py"},
        "model": {"source": "app/model", "tests": "tests/model", "testFile": "test_{stem}.py"},
    },
}
CODE = {
    "app/data/loader.py": "class Loader:\n    def load(self):\n        pass\n",
    "app/model/trainer.py": "def fit():\n    pass\n",
    "tests/data/test_loader.py": "",
    "tests/model/test_trainer.py": "",
    "tests/journeys/test_train-end-to-end.py": "",
}


def write_doc(root: Path, relative: str, metadata: dict, body: str = "") -> None:
    path = root / "docs" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for key, value in metadata.items():
        lines.append(f"{key}: {json.dumps(value) if isinstance(value, list) else value}")
    lines.extend(["---", "", "# 文档", "", body])
    path.write_text("\n".join(lines), encoding="utf-8")


REQUIREMENT_BODY = "## 需求\n\n- r1 当调用方请求时，系统应返回结果。\n"


def node(node_id: str, kind: str, **extra: object) -> dict:
    return {"id": node_id, "kind": kind, "status": "implemented", **extra}


def create_spec(root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/project-spec.json").write_text(json.dumps(CONFIG), encoding="utf-8")
    write_doc(root, "requirements/data/load-prices.md", node("req.data.load-prices", "requirement"), REQUIREMENT_BODY)
    write_doc(root, "requirements/model/fit.md", node("req.model.fit", "requirement"), REQUIREMENT_BODY)
    write_doc(root, "requirements/latency.md", node("req.latency", "constraint"), REQUIREMENT_BODY)
    write_doc(root, "architecture/data/README.md", node("arch.data", "module", requirements=[], **{"depends-on": []}))
    write_doc(root, "architecture/model/README.md", node("arch.model", "module", requirements=[], **{"depends-on": []}))
    write_doc(
        root,
        "architecture/data/loader.md",
        node("arch.data.loader", "source", requirements=["req.data.load-prices", "req.latency"], **{"depends-on": []}),
    )
    write_doc(root, "architecture/data/loader.structure.md", node("struct.data.loader", "structure"), "")
    write_doc(
        root,
        "architecture/model/trainer.md",
        node("arch.model.trainer", "source", requirements=["req.model.fit"], **{"depends-on": ["arch.data.loader"]}),
    )
    write_doc(root, "architecture/model/trainer.structure.md", node("struct.model.trainer", "structure"), "")
    write_doc(
        root,
        "test-cases/data/loader.md",
        node("cases.data.loader", "cases", verifies=["req.data.load-prices"]),
        "## Loader {#cases.data.loader.loader}\n### Loader.load {#cases.data.loader.loader.load}\n",
    )
    write_doc(
        root,
        "test-cases/model/trainer.md",
        node("cases.model.trainer", "cases", verifies=["req.model.fit"]),
        "## fit {#cases.model.trainer.fit}\n",
    )
    write_doc(
        root,
        "test-cases/journeys/train-end-to-end.md",
        node("journey.train-end-to-end", "journey", targets=["api.data.loader.loader.load", "api.model.trainer.fit"], verifies=["req.latency"]),
    )
    for relative, text in CODE.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    write_structure(root, "data", "loader")
    write_structure(root, "model", "trainer")


def write_structure(root: Path, module: str, stem: str) -> None:
    body = render_body((root / f"app/{module}/{stem}.py").read_text(encoding="utf-8"), module, stem)
    path = root / f"docs/architecture/{module}/{stem}.structure.md"
    head = path.read_text(encoding="utf-8").split("# 文档", 1)[0]
    path.write_text(head + body, encoding="utf-8")


class ValidateSpecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        create_spec(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def edit(self, relative: str, old: str, new: str) -> None:
        path = self.root / "docs" / relative
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def assert_error(self, fragment: str) -> None:
        report = validate_project(self.root)
        self.assertFalse(report["valid"])
        self.assertTrue(any(fragment in item for item in report["errors"]), report["errors"])

    def assert_inconsistent(self, fragment: str) -> None:
        report = validate_project(self.root)
        self.assertTrue(report["valid"], report["errors"])
        self.assertTrue(any(fragment in item for item in report["inconsistencies"]), report["inconsistencies"])

    def test_consistent_spec_passes_and_maps_paths(self) -> None:
        report = validate_project(self.root)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["inconsistencies"], [])
        self.assertEqual(report["unmappedSources"], [])
        self.assertEqual(report["paths"]["arch.data.loader"]["source"], "app/data/loader.py")
        self.assertEqual(report["paths"]["cases.data.loader"]["test"], "tests/data/test_loader.py")
        self.assertEqual(report["paths"]["journey.train-end-to-end"]["test"], "tests/journeys/test_train-end-to-end.py")
        self.assertEqual(report["sections"]["api.data.loader.loader.load"], "struct.data.loader")

    def test_section_symbol_extraction(self) -> None:
        self.assertEqual(section_symbol("`Loader`"), "Loader")
        self.assertEqual(section_symbol("Loader.load(path)"), "load")
        self.assertIsNone(section_symbol("()"))

    def test_approved_doc_without_code_is_pending_not_inconsistent(self) -> None:
        self.edit("architecture/data/loader.md", "status: implemented", "status: approved")
        self.edit("architecture/data/loader.structure.md", "status: implemented", "status: approved")
        self.edit("test-cases/data/loader.md", "status: implemented", "status: approved")
        (self.root / "app/data/loader.py").unlink()
        (self.root / "tests/data/test_loader.py").unlink()
        report = validate_project(self.root)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["inconsistencies"], [])

    def test_implemented_doc_without_source_is_inconsistent(self) -> None:
        (self.root / "app/model/trainer.py").unlink()
        self.assert_inconsistent("已实现但源码不存在")

    def test_implemented_interface_symbol_missing_is_inconsistent(self) -> None:
        (self.root / "app/data/loader.py").write_text("class Loader:\n    pass\n", encoding="utf-8")
        self.assert_inconsistent("符号 'load' 不在")

    def test_implemented_cases_without_test_is_inconsistent(self) -> None:
        (self.root / "tests/data/test_loader.py").unlink()
        self.assert_inconsistent("已实现但测试文件不存在")

    def test_implemented_doc_with_draft_requirement_is_inconsistent(self) -> None:
        self.edit("requirements/model/fit.md", "status: implemented", "status: draft")
        self.assert_inconsistent("依赖的需求 'req.model.fit' 是 draft")

    def test_approved_doc_with_draft_requirement_is_reminder_not_error(self) -> None:
        self.edit("requirements/model/fit.md", "status: implemented", "status: draft")
        self.edit("architecture/model/trainer.md", "status: implemented", "status: approved")
        self.assert_inconsistent("approved 文档依赖的需求")
        self.assertEqual(validate_project(self.root)["drafts"], ["req.model.fit"])

    def test_draft_doc_may_reference_draft_requirement(self) -> None:
        self.edit("requirements/model/fit.md", "status: implemented", "status: draft")
        for relative in ("architecture/model/trainer.md", "test-cases/model/trainer.md"):
            self.edit(relative, "status: implemented", "status: draft")
        self.assertTrue(validate_project(self.root)["valid"])

    def test_approved_requirement_without_architecture_is_allowed(self) -> None:
        write_doc(self.root, "requirements/model/predict.md", {"id": "req.model.predict", "kind": "requirement", "status": "approved"}, REQUIREMENT_BODY)
        self.assertTrue(validate_project(self.root)["valid"])

    def test_implemented_requirement_without_architecture_fails(self) -> None:
        write_doc(self.root, "requirements/model/predict.md", node("req.model.predict", "requirement"))
        self.assert_error("已实现需求没有架构文档声明满足关系")

    def test_unmapped_source_is_listed(self) -> None:
        (self.root / "app/data/helper.py").write_text("", encoding="utf-8")
        report = validate_project(self.root)
        self.assertEqual(report["unmappedSources"], ["app/data/helper.py"])

    def test_invalid_status_and_removed_fields_fail(self) -> None:
        self.edit("architecture/data/loader.md", "status: implemented", "status: deprecated\norigin: explicit")
        report = validate_project(self.root)
        self.assertTrue(any("status 'deprecated' 无效" in item for item in report["errors"]))
        self.assertTrue(any("不允许字段 'origin'" in item for item in report["errors"]))

    def test_missing_config_fails(self) -> None:
        (self.root / "docs/project-spec.json").unlink()
        self.assert_error("缺少配置文件")

    def test_cross_module_journey_requires_journey_config(self) -> None:
        config = dict(CONFIG)
        del config["journeys"]
        (self.root / "docs/project-spec.json").write_text(json.dumps(config), encoding="utf-8")
        self.assert_error("跨模块 journey 需要配置")

    def test_missing_module_readme_fails(self) -> None:
        (self.root / "docs/architecture/model/README.md").unlink()
        self.assert_error("模块缺少 kind 为 module 的 README.md")

    def test_requirement_outside_module_fails(self) -> None:
        write_doc(self.root, "requirements/unknown/x.md", node("req.unknown.x", "requirement"))
        self.assert_error("不是配置中的模块")

    def test_architecture_cannot_reference_other_module_requirement(self) -> None:
        self.edit("architecture/model/trainer.md", '["req.model.fit"]', '["req.model.fit", "req.data.load-prices"]')
        self.assert_error("只能引用本模块或项目级需求")

    def test_missing_mirror_case_document_fails(self) -> None:
        (self.root / "docs/test-cases/data/loader.md").unlink()
        self.assert_error("缺少同路径的用例文档")

    def test_missing_case_section_fails(self) -> None:
        self.edit("architecture/model/trainer.structure.md", "## fit {#api.model.trainer.fit}", "## save {#api.model.trainer.save}\n\n## fit {#api.model.trainer.fit}")
        self.assert_error("缺少接口 'api.model.trainer.save'")

    def test_orphan_case_section_fails(self) -> None:
        self.edit("test-cases/model/trainer.md", "## fit {#cases.model.trainer.fit}", "## fit {#cases.model.trainer.fit}\n## drop {#cases.model.trainer.drop}")
        self.assert_error("没有对应接口")

    def test_case_verifies_requirement_not_realized_by_mirror_fails(self) -> None:
        self.edit("test-cases/model/trainer.md", '["req.model.fit"]', '["req.model.fit", "req.latency"]')
        self.assert_error("不在镜像架构文档的 requirements 中")

    def test_journey_outside_common_directory_fails(self) -> None:
        source = self.root / "docs/test-cases/journeys/train-end-to-end.md"
        target = self.root / "docs/test-cases/data/journeys/train-end-to-end.md"
        target.parent.mkdir(parents=True)
        source.rename(target)
        self.assert_error("最近公共目录 test-cases/journeys/")

    def test_journey_dangling_target_fails(self) -> None:
        self.edit("test-cases/journeys/train-end-to-end.md", "api.model.trainer.fit", "api.model.trainer.missing")
        self.assert_error("targets 引用了不存在")

    def test_wrong_kind_for_location_fails(self) -> None:
        self.edit("architecture/data/loader.md", "kind: source", "kind: package")
        self.assert_error("该位置的 kind 必须是 'source'")

    def test_duplicate_id_across_documents_fails(self) -> None:
        self.edit("test-cases/data/loader.md", "id: cases.data.loader", "id: arch.data.loader")
        self.assert_error("重复")

    def test_section_id_in_fenced_code_is_ignored(self) -> None:
        self.edit("architecture/model/trainer.structure.md", "## fit {#api.model.trainer.fit}", "## fit {#api.model.trainer.fit}\n```\n## x {#api.model.trainer.x}\n```")
        self.assertTrue(validate_project(self.root)["valid"])

    def test_source_without_structure_document_fails(self) -> None:
        (self.root / "docs/architecture/model/trainer.structure.md").unlink()
        self.assert_error("缺少同路径的结构文档")

    def test_structure_without_source_document_fails(self) -> None:
        (self.root / "docs/architecture/model/trainer.md").unlink()
        self.assert_error("没有同路径的源文件架构文档")

    def test_source_document_cannot_declare_interface_sections(self) -> None:
        self.edit("architecture/model/trainer.md", "# 文档", "# 文档\n\n## fit {#api.model.trainer.other}")
        self.assert_error("kind 'source' 的文档不能声明小节 ID")

    def test_structure_drift_from_code_is_inconsistent(self) -> None:
        (self.root / "app/model/trainer.py").write_text("def fit(epochs):\n    pass\n", encoding="utf-8")
        self.assert_inconsistent("结构与源码不一致")

    def test_structure_descriptions_do_not_affect_consistency(self) -> None:
        self.edit("architecture/model/trainer.structure.md", "(无说明)", "手写说明")
        report = validate_project(self.root)
        self.assertEqual(report["inconsistencies"], [])

    def test_draft_structure_is_not_compared_with_code(self) -> None:
        self.edit("architecture/model/trainer.structure.md", "status: implemented", "status: draft")
        (self.root / "app/model/trainer.py").write_text("def fit(epochs):\n    pass\n", encoding="utf-8")
        self.assertEqual(validate_project(self.root)["inconsistencies"], [])

    def test_requirement_without_entries_fails(self) -> None:
        write_doc(self.root, "requirements/model/predict.md", node("req.model.predict", "requirement"), "")
        self.assert_error("缺少含条目的 ## 需求 小节")

    def test_requirement_entry_must_match_a_clause_pattern(self) -> None:
        self.edit("requirements/model/fit.md", "当调用方请求时，系统应返回结果。", "返回结果。")
        self.assert_error("不符合五种句式之一")

    def test_requirement_entry_must_be_one_sentence(self) -> None:
        self.edit("requirements/model/fit.md", "系统应返回结果。", "系统应返回结果。同时记录日志。")
        self.assert_error("必须恰好是一句话")

    def test_requirement_entry_needs_numbered_prefix(self) -> None:
        self.edit("requirements/model/fit.md", "- r1 ", "- ")
        self.assert_error("必须以 '- r<编号> ' 开头")

    def test_requirement_entry_numbers_are_unique(self) -> None:
        entry = REQUIREMENT_BODY.strip().splitlines()[-1]
        self.edit("requirements/model/fit.md", entry, f"{entry}\n{entry}")
        self.assert_error("编号重复")

    def test_requirement_all_clause_patterns_pass(self) -> None:
        body = "## 需求\n\n" + "\n".join(
            f"- r{index} {text}"
            for index, text in enumerate(
                (
                    "系统应返回结果。",
                    "当调用方请求时，系统应返回结果。",
                    "在维护期间，系统应拒绝写入。",
                    "若输入为空，则系统应报错。",
                    "在具备缓存的情况下，系统应复用结果。",
                ),
                start=1,
            )
        )
        write_doc(self.root, "requirements/model/fit.md", node("req.model.fit", "requirement"), body)
        self.assertTrue(validate_project(self.root)["valid"])

    def test_fingerprint_ignores_status_only(self) -> None:
        first = validate_project(self.root)["specFingerprint"]
        self.edit("architecture/data/loader.md", "status: implemented", "status: approved")
        self.assertEqual(first, validate_project(self.root)["specFingerprint"])
        self.edit("architecture/data/loader.md", "# 文档", "# 文档\n\n## 设计")
        self.assertNotEqual(first, validate_project(self.root)["specFingerprint"])

    def test_report_is_deterministic_and_stays_inside_root(self) -> None:
        report = validate_project(self.root)
        write_report(self.root, ".project-spec/validation.json", report)
        loaded = json.loads((self.root / ".project-spec/validation.json").read_text(encoding="utf-8"))
        self.assertEqual(loaded, report)
        for bad in ("../validation.json", "C:/validation.json", "/tmp/validation.json"):
            with self.assertRaises(ValueError):
                write_report(self.root, bad, report)


if __name__ == "__main__":
    unittest.main()
