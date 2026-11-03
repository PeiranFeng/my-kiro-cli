#!/usr/bin/env python3
"""Tests for project-maintainer state validation."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from validate_state import validate_state  # noqa: E402

FINGERPRINT = "sha256:" + "a" * 64
SEMANTIC_FINGERPRINT = "sha256:" + "c" * 64


def valid_model_report(
    fingerprint: str = FINGERPRINT,
    semantic_fingerprint: str = SEMANTIC_FINGERPRINT,
) -> dict[str, object]:
    return {
        "valid": True,
        "modelFingerprint": fingerprint,
        "modelSemanticFingerprint": semantic_fingerprint,
        "nodes": {
            "architecture": {"api.auth.sign-in": "approved"},
            "useCases": {"cases.auth.sign-in": "approved"},
        },
    }


def valid_state(work_id: str = "implement-auth") -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "workId": work_id,
        "mode": "implement",
        "status": "planned",
        "outcome": "not-run",
        "modelFingerprint": FINGERPRINT,
        "modelSemanticFingerprint": SEMANTIC_FINGERPRINT,
        "scope": {
            "architectureIds": ["api.auth.sign-in"],
            "useCaseIds": ["cases.auth.sign-in"],
        },
        "baseline": {"gitStatus": [], "head": None},
        "tasks": [],
        "blockers": [],
        "evidence": [],
    }


class ValidateStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.work_id = "implement-auth"
        self.state_relative = (
            f"docs/project-model/generated/maintenance/{self.work_id}/state.json"
        )
        self.report_relative = (
            f"docs/project-model/generated/maintenance/{self.work_id}/model-validation.json"
        )
        self.write_json(self.report_relative, valid_model_report())

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_json(self, relative: str, value: object) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_valid_planned_state_passes(self) -> None:
        self.write_json(self.state_relative, valid_state())

        report = validate_state(self.root, self.state_relative, self.report_relative)

        self.assertTrue(report["valid"])
        self.assertEqual(report["errors"], [])

    def test_completed_state_requires_passed_tasks(self) -> None:
        state = valid_state()
        state["status"] = "completed"
        state["outcome"] = "pass"
        state["tasks"] = [
            {
                "id": "task-001",
                "title": "Implement sign in",
                "status": "pending",
                "architectureIds": ["api.auth.sign-in"],
                "useCaseIds": ["cases.auth.sign-in"],
                "dependsOn": [],
                "files": [],
                "evidenceIds": [],
            }
        ]
        self.write_json(self.state_relative, state)

        report = validate_state(self.root, self.state_relative, self.report_relative)

        self.assertFalse(report["valid"])
        self.assertTrue(any("所有任务必须为 passed" in item for item in report["errors"]))

    def test_blocked_state_requires_blocker(self) -> None:
        state = valid_state()
        state["status"] = "blocked"
        state["outcome"] = "blocked"
        self.write_json(self.state_relative, state)

        report = validate_state(self.root, self.state_relative, self.report_relative)

        self.assertFalse(report["valid"])
        self.assertTrue(any("至少有一个阻塞项" in item for item in report["errors"]))

    def test_unknown_task_evidence_fails(self) -> None:
        state = valid_state()
        state["tasks"] = [
            {
                "id": "task-001",
                "title": "Implement sign in",
                "status": "running",
                "architectureIds": ["api.auth.sign-in"],
                "useCaseIds": ["cases.auth.sign-in"],
                "dependsOn": [],
                "files": [],
                "evidenceIds": ["evidence-missing"],
            }
        ]
        self.write_json(self.state_relative, state)

        report = validate_state(self.root, self.state_relative, self.report_relative)

        self.assertFalse(report["valid"])
        self.assertTrue(any("未知证据" in item for item in report["errors"]))

    def test_model_fingerprint_mismatch_fails(self) -> None:
        self.write_json(self.state_relative, valid_state())
        report_relative = (
            f"docs/project-model/generated/maintenance/{self.work_id}/model-validation.json"
        )
        self.write_json(
            report_relative,
            valid_model_report("sha256:" + "b" * 64),
        )

        report = validate_state(self.root, self.state_relative, report_relative)

        self.assertFalse(report["valid"])
        self.assertTrue(any("与当前模型报告不一致" in item for item in report["errors"]))

    def test_matching_model_report_passes(self) -> None:
        self.write_json(self.state_relative, valid_state())
        report_relative = (
            f"docs/project-model/generated/maintenance/{self.work_id}/model-validation.json"
        )
        self.write_json(report_relative, valid_model_report())

        report = validate_state(self.root, self.state_relative, report_relative)

        self.assertTrue(report["valid"])

    def test_state_path_cannot_escape_project(self) -> None:
        report = validate_state(self.root, "../state.json", self.report_relative)

        self.assertFalse(report["valid"])
        self.assertTrue(any("必须位于目标仓库内" in item for item in report["errors"]))

        windows_report = validate_state(
            self.root, "C:/state.json", self.report_relative
        )
        self.assertFalse(windows_report["valid"])
        self.assertTrue(
            any("必须使用 / 分隔" in item for item in windows_report["errors"])
        )

    def test_draft_scope_id_fails_against_model_report(self) -> None:
        self.write_json(self.state_relative, valid_state())
        model_report = valid_model_report()
        model_report["nodes"]["architecture"]["api.auth.sign-in"] = "draft"
        self.write_json(self.report_relative, model_report)

        report = validate_state(self.root, self.state_relative, self.report_relative)

        self.assertFalse(report["valid"])
        self.assertTrue(any("状态不是 approved" in item for item in report["errors"]))

    def test_semantic_fingerprint_change_requires_replanning(self) -> None:
        self.write_json(self.state_relative, valid_state())
        self.write_json(
            self.report_relative,
            valid_model_report(semantic_fingerprint="sha256:" + "d" * 64),
        )

        report = validate_state(self.root, self.state_relative, self.report_relative)

        self.assertFalse(report["valid"])
        self.assertTrue(any("规范语义已变化" in item for item in report["errors"]))

    def test_unknown_scope_id_fails_against_model_report(self) -> None:
        state = valid_state()
        state["scope"]["architectureIds"] = ["api.auth.missing"]
        self.write_json(self.state_relative, state)
        report_relative = (
            f"docs/project-model/generated/maintenance/{self.work_id}/model-validation.json"
        )
        self.write_json(report_relative, valid_model_report())

        report = validate_state(self.root, self.state_relative, report_relative)

        self.assertFalse(report["valid"])
        self.assertTrue(any("当前模型不存在" in item for item in report["errors"]))

    def test_implement_cannot_complete_with_findings(self) -> None:
        state = valid_state()
        state["status"] = "completed"
        state["outcome"] = "findings"
        self.write_json(self.state_relative, state)

        report = validate_state(self.root, self.state_relative, self.report_relative)

        self.assertFalse(report["valid"])
        self.assertTrue(any("完成时 outcome 必须为 'pass'" in item for item in report["errors"]))


if __name__ == "__main__":
    unittest.main()
