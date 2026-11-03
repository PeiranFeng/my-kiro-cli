#!/usr/bin/env python3
"""Validate project-maintainer state and its model snapshot."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

WORK_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
MODES = {"review", "implement", "verify", "maintain"}
STATUSES = {"planned", "running", "blocked", "verification-failed", "completed"}
OUTCOMES = {"not-run", "pass", "findings", "blocked", "failed"}
TASK_STATUSES = {"pending", "running", "passed", "blocked", "failed"}
BLOCKER_TYPES = {"specification", "environment", "permission", "implementation"}
EVIDENCE_KINDS = {
    "model-validation",
    "focused-test",
    "integration-test",
    "regression-test",
    "build",
    "static-check",
    "review",
    "git-status",
}
EVIDENCE_RESULTS = {"passed", "failed", "not-run"}
REQUIRED_STATE_FIELDS = {
    "schemaVersion",
    "workId",
    "mode",
    "status",
    "outcome",
    "modelFingerprint",
    "modelSemanticFingerprint",
    "scope",
    "baseline",
    "tasks",
    "blockers",
    "evidence",
}


def _inside(root: Path, relative: str) -> Path:
    if "\\" in relative or ":" in relative:
        raise ValueError("路径必须使用 / 分隔的仓库相对路径")
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ValueError("路径必须是目标仓库内的相对路径")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("路径必须位于目标仓库内") from exc
    return resolved


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _require_string_list(
    owner: Dict[str, Any], field: str, location: str, errors: List[str]
) -> List[str]:
    value = owner.get(field)
    if not _string_list(value):
        errors.append(f"{location}.{field}: 必须是字符串数组")
        return []
    if len(value) != len(set(value)):
        errors.append(f"{location}.{field}: 包含重复值")
    return value


def _load_json(path: Path, label: str, errors: List[str]) -> Optional[Dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label}: 文件不存在")
        return None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: 无法读取有效 JSON：{exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label}: 顶层必须是 JSON object")
        return None
    return value


def validate_state(
    project_root: Path,
    state_relative: str,
    model_report_relative: str,
) -> Dict[str, Any]:
    root = project_root.resolve()
    errors: List[str] = []
    warnings: List[str] = []

    try:
        state_path = _inside(root, state_relative)
    except ValueError as exc:
        return {"valid": False, "errors": [f"state: {exc}"], "warnings": []}

    state = _load_json(state_path, "state", errors)
    if state is None:
        return {"valid": False, "errors": sorted(set(errors)), "warnings": []}

    for field in sorted(REQUIRED_STATE_FIELDS - state.keys()):
        errors.append(f"state.{field}: 缺少必需字段")

    if state.get("schemaVersion") != 1:
        errors.append("state.schemaVersion: 必须为 1")

    work_id = state.get("workId")
    if not isinstance(work_id, str) or not WORK_ID_PATTERN.fullmatch(work_id):
        errors.append("state.workId: 必须使用小写 kebab-case")
    elif state_path.name == "state.json" and state_path.parent.name != work_id:
        errors.append("state.workId: 必须与 state.json 的父目录名一致")

    if state.get("mode") not in MODES:
        errors.append("state.mode: 无效")
    status = state.get("status")
    outcome = state.get("outcome")
    if status not in STATUSES:
        errors.append("state.status: 无效")
    if outcome not in OUTCOMES:
        errors.append("state.outcome: 无效")

    allowed_pairs = {
        "planned": {"not-run"},
        "running": {"not-run", "findings", "failed"},
        "blocked": {"blocked"},
        "verification-failed": {"failed"},
        "completed": {"pass", "findings"},
    }
    if status in allowed_pairs and outcome not in allowed_pairs[status]:
        errors.append(f"state: status={status!r} 与 outcome={outcome!r} 不一致")
    mode = state.get("mode")
    if status == "completed" and mode in {"implement", "verify", "maintain"} and outcome != "pass":
        errors.append(f"state: mode={mode!r} 完成时 outcome 必须为 'pass'")

    fingerprint = state.get("modelFingerprint")
    if not isinstance(fingerprint, str) or not FINGERPRINT_PATTERN.fullmatch(fingerprint):
        errors.append("state.modelFingerprint: 必须是 sha256 指纹")
    semantic_fingerprint = state.get("modelSemanticFingerprint")
    if not isinstance(semantic_fingerprint, str) or not FINGERPRINT_PATTERN.fullmatch(
        semantic_fingerprint
    ):
        errors.append("state.modelSemanticFingerprint: 必须是 sha256 指纹")

    scope_architecture_ids: List[str] = []
    scope_use_case_ids: List[str] = []
    scope = state.get("scope")
    if not isinstance(scope, dict):
        errors.append("state.scope: 必须是 object")
    else:
        scope_architecture_ids = _require_string_list(
            scope, "architectureIds", "state.scope", errors
        )
        scope_use_case_ids = _require_string_list(
            scope, "useCaseIds", "state.scope", errors
        )

    baseline = state.get("baseline")
    if not isinstance(baseline, dict):
        errors.append("state.baseline: 必须是 object")
    else:
        _require_string_list(baseline, "gitStatus", "state.baseline", errors)
        head = baseline.get("head")
        if head is not None and not isinstance(head, str):
            errors.append("state.baseline.head: 必须是字符串或 null")

    evidence = state.get("evidence")
    evidence_ids: Set[str] = set()
    if not isinstance(evidence, list):
        errors.append("state.evidence: 必须是数组")
        evidence = []
    for index, item in enumerate(evidence):
        location = f"state.evidence[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{location}: 必须是 object")
            continue
        evidence_id = item.get("id")
        if not isinstance(evidence_id, str) or not evidence_id:
            errors.append(f"{location}.id: 必须是非空字符串")
        elif evidence_id in evidence_ids:
            errors.append(f"{location}.id: 重复 {evidence_id!r}")
        else:
            evidence_ids.add(evidence_id)
        if item.get("kind") not in EVIDENCE_KINDS:
            errors.append(f"{location}.kind: 无效")
        if item.get("result") not in EVIDENCE_RESULTS:
            errors.append(f"{location}.result: 无效")
        exit_code = item.get("exitCode")
        if exit_code is not None and (not isinstance(exit_code, int) or isinstance(exit_code, bool)):
            errors.append(f"{location}.exitCode: 必须是整数或 null")
        if not isinstance(item.get("command"), str):
            errors.append(f"{location}.command: 必须是字符串")
        _require_string_list(item, "scope", location, errors)
        if not isinstance(item.get("outputRef"), str):
            errors.append(f"{location}.outputRef: 必须是字符串")

    tasks = state.get("tasks")
    task_ids: Set[str] = set()
    task_items: List[Dict[str, Any]] = []
    if not isinstance(tasks, list):
        errors.append("state.tasks: 必须是数组")
        tasks = []
    for index, item in enumerate(tasks):
        location = f"state.tasks[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{location}: 必须是 object")
            continue
        task_items.append(item)
        task_id = item.get("id")
        if not isinstance(task_id, str) or not task_id:
            errors.append(f"{location}.id: 必须是非空字符串")
        elif task_id in task_ids:
            errors.append(f"{location}.id: 重复 {task_id!r}")
        else:
            task_ids.add(task_id)
        if not isinstance(item.get("title"), str) or not item.get("title"):
            errors.append(f"{location}.title: 必须是非空字符串")
        if item.get("status") not in TASK_STATUSES:
            errors.append(f"{location}.status: 无效")
        for field in ("architectureIds", "useCaseIds", "dependsOn", "files", "evidenceIds"):
            _require_string_list(item, field, location, errors)

    for index, item in enumerate(task_items):
        for dependency in item.get("dependsOn", []):
            if dependency not in task_ids:
                errors.append(f"state.tasks[{index}].dependsOn: 未知任务 {dependency!r}")
        for evidence_id in item.get("evidenceIds", []):
            if evidence_id not in evidence_ids:
                errors.append(f"state.tasks[{index}].evidenceIds: 未知证据 {evidence_id!r}")

    blockers = state.get("blockers")
    if not isinstance(blockers, list):
        errors.append("state.blockers: 必须是数组")
        blockers = []
    for index, item in enumerate(blockers):
        location = f"state.blockers[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{location}: 必须是 object")
            continue
        if item.get("type") not in BLOCKER_TYPES:
            errors.append(f"{location}.type: 无效")
        for field in ("summary", "requiredAction"):
            if not isinstance(item.get(field), str) or not item.get(field):
                errors.append(f"{location}.{field}: 必须是非空字符串")
        for evidence_id in _require_string_list(item, "evidenceRefs", location, errors):
            if evidence_id not in evidence_ids:
                errors.append(f"{location}.evidenceRefs: 未知证据 {evidence_id!r}")
        _require_string_list(item, "attempts", location, errors)

    if status == "blocked" and not blockers:
        errors.append("state.blockers: blocked 状态必须至少有一个阻塞项")
    if status == "completed" and any(item.get("status") != "passed" for item in task_items):
        errors.append("state.tasks: completed 状态下所有任务必须为 passed")

    try:
        report_path = _inside(root, model_report_relative)
    except ValueError as exc:
        errors.append(f"model-report: {exc}")
    else:
        model_report = _load_json(report_path, "model-report", errors)
        if model_report is not None:
            if model_report.get("valid") is not True:
                errors.append("model-report.valid: 必须为 true")
            if model_report.get("modelFingerprint") != fingerprint:
                errors.append("state.modelFingerprint: 与当前模型报告不一致")
            if model_report.get("modelSemanticFingerprint") != semantic_fingerprint:
                errors.append(
                    "state.modelSemanticFingerprint: 规范语义已变化，必须重新规划"
                )
            nodes = model_report.get("nodes")
            if not isinstance(nodes, dict):
                errors.append("model-report.nodes: 必须是 object")
            else:
                architecture_nodes = nodes.get("architecture")
                use_case_nodes = nodes.get("useCases")
                if not isinstance(architecture_nodes, dict) or any(
                    not isinstance(key, str) or not isinstance(value, str)
                    for key, value in architecture_nodes.items()
                ):
                    errors.append("model-report.nodes.architecture: 必须是 ID 到状态的 object")
                else:
                    for node_id in scope_architecture_ids:
                        status_value = architecture_nodes.get(node_id)
                        if status_value is None:
                            errors.append(
                                f"state.scope.architectureIds: 当前模型不存在 {node_id!r}"
                            )
                        elif status_value != "approved":
                            errors.append(
                                f"state.scope.architectureIds: {node_id!r} 状态不是 approved"
                            )
                if not isinstance(use_case_nodes, dict) or any(
                    not isinstance(key, str) or not isinstance(value, str)
                    for key, value in use_case_nodes.items()
                ):
                    errors.append("model-report.nodes.useCases: 必须是 ID 到状态的 object")
                else:
                    for node_id in scope_use_case_ids:
                        status_value = use_case_nodes.get(node_id)
                        if status_value is None:
                            errors.append(
                                f"state.scope.useCaseIds: 当前模型不存在 {node_id!r}"
                            )
                        elif status_value != "approved":
                            errors.append(
                                f"state.scope.useCaseIds: {node_id!r} 状态不是 approved"
                            )

    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--state", required=True, help="目标仓库内的 state.json 相对路径")
    parser.add_argument(
        "--model-report",
        required=True,
        help="目标仓库内的当前模型校验 JSON 相对路径",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root)
    if not project_root.is_dir():
        print(f"ERROR: 目标仓库目录不存在：{project_root}", file=sys.stderr)
        return 2

    report = validate_state(project_root, args.state, args.model_report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        state = "VALID" if report["valid"] else "INVALID"
        print(
            f"Maintenance state: {state} | errors={len(report['errors'])} "
            f"warnings={len(report['warnings'])}"
        )
        for message in report["errors"]:
            print(f"ERROR: {message}")
        for message in report["warnings"]:
            print(f"WARNING: {message}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
