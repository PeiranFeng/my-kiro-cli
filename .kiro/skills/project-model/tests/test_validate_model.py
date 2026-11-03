#!/usr/bin/env python3
"""Tests for validate_model.py using only the Python standard library."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from validate_model import _write_report, validate_project  # noqa: E402


def write_node(root: Path, relative_path: str, metadata: dict[str, object]) -> None:
    path = root / "docs" / "project-model" / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for key, value in metadata.items():
        encoded = json.dumps(value, ensure_ascii=False) if isinstance(value, list) else str(value)
        lines.append(f"{key}: {encoded}")
    lines.extend(["---", "", "# 节点", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def create_valid_model(root: Path, automation: bool = False) -> None:
    write_node(
        root,
        "architecture/domains/identity/requirements/login.md",
        {
            "id": "req.identity.login",
            "kind": "requirement",
            "status": "approved",
            "origin": "explicit",
        },
    )
    write_node(
        root,
        "architecture/domains/identity/interfaces/login.md",
        {
            "id": "api.identity.login",
            "kind": "interface",
            "status": "approved",
            "origin": "inferred",
            "requirements": ["req.identity.login"],
            "depends-on": [],
            "implementation": [],
        },
    )
    if automation:
        test_path = root / "tests" / "identity" / "test_login.py"
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text("def test_login():\n    assert True\n", encoding="utf-8")
        automation_refs = ["tests/identity/test_login.py#test_login"]
    else:
        automation_refs = []
    write_node(
        root,
        "use-cases/domains/identity/interfaces/login.md",
        {
            "id": "cases.identity.login",
            "kind": "interface-cases",
            "status": "approved",
            "origin": "inferred",
            "targets": ["api.identity.login"],
            "verifies": ["req.identity.login"],
            "automation": automation_refs,
        },
    )


class ValidateProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_model_passes_with_missing_automation_warning(self) -> None:
        create_valid_model(self.root)

        report = validate_project(self.root)

        self.assertTrue(report["valid"])
        self.assertEqual(report["counts"]["errors"], 0)
        self.assertEqual(report["counts"]["warnings"], 1)
        self.assertEqual(
            report["nodes"]["architecture"]["api.identity.login"], "approved"
        )
        self.assertEqual(
            report["nodes"]["useCases"]["cases.identity.login"], "approved"
        )
        self.assertIn("尚未关联自动化测试", report["warnings"][0])

    def test_existing_automation_path_removes_warning(self) -> None:
        create_valid_model(self.root, automation=True)

        report = validate_project(self.root)

        self.assertTrue(report["valid"])
        self.assertEqual(report["counts"]["warnings"], 0)

    def test_missing_interface_mirror_fails(self) -> None:
        create_valid_model(self.root)
        mirror = (
            self.root
            / "docs/project-model/use-cases/domains/identity/interfaces/login.md"
        )
        mirror.unlink()

        report = validate_project(self.root)

        self.assertFalse(report["valid"])
        self.assertTrue(any("缺少同相对路径" in error for error in report["errors"]))

    def test_dangling_target_fails(self) -> None:
        create_valid_model(self.root)
        mirror = (
            self.root
            / "docs/project-model/use-cases/domains/identity/interfaces/login.md"
        )
        text = mirror.read_text(encoding="utf-8")
        mirror.write_text(
            text.replace('targets: ["api.identity.login"]', 'targets: ["api.identity.missing"]'),
            encoding="utf-8",
        )

        report = validate_project(self.root)

        self.assertFalse(report["valid"])
        self.assertTrue(any("targets 引用了不存在" in error for error in report["errors"]))

    def test_duplicate_id_across_trees_fails(self) -> None:
        create_valid_model(self.root)
        mirror = (
            self.root
            / "docs/project-model/use-cases/domains/identity/interfaces/login.md"
        )
        text = mirror.read_text(encoding="utf-8")
        mirror.write_text(
            text.replace("id: cases.identity.login", "id: api.identity.login"),
            encoding="utf-8",
        )

        report = validate_project(self.root)

        self.assertFalse(report["valid"])
        self.assertTrue(any("重复" in error for error in report["errors"]))

    def test_approved_requirement_without_implementation_link_fails(self) -> None:
        create_valid_model(self.root)
        interface = (
            self.root
            / "docs/project-model/architecture/domains/identity/interfaces/login.md"
        )
        text = interface.read_text(encoding="utf-8")
        interface.write_text(
            text.replace('requirements: ["req.identity.login"]', "requirements: []"),
            encoding="utf-8",
        )

        report = validate_project(self.root)

        self.assertFalse(report["valid"])
        self.assertTrue(any("没有架构节点" in error for error in report["errors"]))

    def test_non_kebab_case_path_fails(self) -> None:
        create_valid_model(self.root)
        source = (
            self.root
            / "docs/project-model/architecture/domains/identity/interfaces/login.md"
        )
        destination = source.with_name("Login.md")
        source.rename(destination)

        report = validate_project(self.root)

        self.assertFalse(report["valid"])
        self.assertTrue(any("小写 kebab-case" in error for error in report["errors"]))

    def test_report_is_written_as_deterministic_json(self) -> None:
        create_valid_model(self.root, automation=True)
        report = validate_project(self.root)

        _write_report(self.root, "docs/project-model/generated/validation.json", report)

        destination = self.root / "docs/project-model/generated/validation.json"
        loaded = json.loads(destination.read_text(encoding="utf-8"))
        self.assertEqual(loaded, report)
        self.assertTrue(destination.read_text(encoding="utf-8").endswith("\n"))

    def test_report_cannot_escape_project_root(self) -> None:
        create_valid_model(self.root)
        report = validate_project(self.root)

        with self.assertRaises(ValueError):
            _write_report(self.root, "../validation.json", report)
        with self.assertRaises(ValueError):
            _write_report(self.root, "C:/validation.json", report)

    def test_windows_style_source_reference_is_rejected(self) -> None:
        create_valid_model(self.root, automation=True)
        interface = (
            self.root
            / "docs/project-model/architecture/domains/identity/interfaces/login.md"
        )
        text = interface.read_text(encoding="utf-8")
        interface.write_text(
            text.replace("implementation: []", 'implementation: ["src\\\\identity\\\\Login.py#login"]'),
            encoding="utf-8",
        )

        report = validate_project(self.root)

        self.assertFalse(report["valid"])
        self.assertTrue(any("必须使用 / 分隔" in error for error in report["errors"]))

    def test_model_fingerprints_distinguish_mapping_from_semantics(self) -> None:
        create_valid_model(self.root, automation=True)
        first_report = validate_project(self.root)
        repeated_report = validate_project(self.root)
        self.assertEqual(
            first_report["modelFingerprint"], repeated_report["modelFingerprint"]
        )
        self.assertEqual(
            first_report["modelSemanticFingerprint"],
            repeated_report["modelSemanticFingerprint"],
        )

        interface = (
            self.root
            / "docs/project-model/architecture/domains/identity/interfaces/login.md"
        )
        interface.write_text(
            interface.read_text(encoding="utf-8").replace(
                "implementation: []",
                'implementation: ["src/identity/login.py#login"]',
            ),
            encoding="utf-8",
        )
        mapping_report = validate_project(self.root)
        self.assertNotEqual(
            first_report["modelFingerprint"], mapping_report["modelFingerprint"]
        )
        self.assertEqual(
            first_report["modelSemanticFingerprint"],
            mapping_report["modelSemanticFingerprint"],
        )

        requirement = (
            self.root
            / "docs/project-model/architecture/domains/identity/requirements/login.md"
        )
        requirement.write_text(
            requirement.read_text(encoding="utf-8") + "\n## New acceptance condition\n",
            encoding="utf-8",
        )
        semantic_report = validate_project(self.root)
        self.assertNotEqual(
            mapping_report["modelSemanticFingerprint"],
            semantic_report["modelSemanticFingerprint"],
        )


if __name__ == "__main__":
    unittest.main()
