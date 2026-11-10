#!/usr/bin/env python3
"""Tests for collect_issues.py using only the Python standard library."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from collect_issues import collect, main, render  # noqa: E402


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class CollectIssuesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_collects_pending_items_only_from_the_pending_section(self) -> None:
        write(self.root, "docs/requirements/a.md", "---\nid: req.a\n---\n\n## 需求\n\n- r1 应做。\n\n## 待确认\n\n- 问题一\n- 问题二\n")
        write(self.root, "docs/requirements/b.md", "## 待确认\n\n```\n- 围栏内\n```\n\n## 其他\n\n- 不是待确认\n")
        pending = collect(self.root, self.root / "reports")["pending"]
        self.assertEqual(pending, ["docs/requirements/a.md：问题一", "docs/requirements/a.md：问题二"])

    def test_collects_report_items_and_skips_unverifiable_section(self) -> None:
        write(self.root, "reports/bootstrap-report.md", "# r\n\n## 架构与代码\n\n- 偏离一\n\n## 无法验证\n\n- 未运行测试\n")
        write(self.root, "reports/maintain-report.md", "## 结构\n\n- 缺文档\n")
        reports = collect(self.root, self.root / "reports")["reports"]
        self.assertEqual(reports, ["bootstrap-report.md 「架构与代码」：偏离一", "maintain-report.md 「结构」：缺文档"])

    def test_collects_validation_and_untested_counts(self) -> None:
        write(self.root, "reports/validation.json", json.dumps({"errors": ["e"], "inconsistencies": ["i"], "unmappedSources": ["s.py"]}))
        write(self.root, "docs/test-cases/m/x.md", "## a\n\n无现有测试\n\n## b\n\n无现有测试\n")
        write(self.root, "docs/architecture/m/x.md", "无现有测试\n")
        result = collect(self.root, self.root / "reports")
        self.assertEqual(result["validation"], ["校验错误：e", "文档与代码不一致：i", "没有架构文档的源文件：s.py"])
        self.assertEqual(result["untested"], ["docs/test-cases/m/x.md：2 处标注「无现有测试」"])

    def test_missing_inputs_give_empty_sections(self) -> None:
        text = render(collect(self.root, self.root / "reports"))
        self.assertIn("## 文档中的待确认问题（0）", text)
        self.assertEqual(main(["--project-root", str(self.root)]), 0)
        self.assertEqual(main(["--project-root", str(self.root / "missing")]), 2)


if __name__ == "__main__":
    unittest.main()
