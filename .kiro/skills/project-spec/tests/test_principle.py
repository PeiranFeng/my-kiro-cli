#!/usr/bin/env python3
"""Tests for principle.py using only the Python standard library."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import principle  # noqa: E402


def write(root: Path, category: str, name: str, text: str) -> Path:
    path = root / category / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def doc(principle_id: str, stages: str = '["design"]', title: str = "标题", body: str = "正文", summary: str = "摘要") -> str:
    return f"---\nid: {principle_id}\ntitle: {title}\nsummary: {summary}\nstages: {stages}\n---\n\n{body}\n"


class PrincipleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.original = principle.ROOT
        principle.ROOT = self.root

    def tearDown(self) -> None:
        principle.ROOT = self.original
        self.temp.cleanup()

    def errors(self) -> list:
        found: list = []
        principle.load(found)
        return found

    def test_valid_principles_load_without_errors(self) -> None:
        write(self.root, "architecture", "A1.md", doc("A1"))
        write(self.root, "test", "T1.md", doc("T1", '["test"]'))
        found: list = []
        items = principle.load(found)
        self.assertEqual(found, [])
        self.assertEqual([item.principle_id for item in items], ["A1", "T1"])

    def test_letter_must_match_category(self) -> None:
        write(self.root, "code", "A1.md", doc("A1"))
        self.assertTrue(any("C<编号>" in item for item in self.errors()))

    def test_id_must_match_filename(self) -> None:
        write(self.root, "code", "C1.md", doc("C2"))
        self.assertTrue(any("与文件名一致" in item for item in self.errors()))

    def test_unknown_stage_fails(self) -> None:
        write(self.root, "code", "C1.md", doc("C1", '["nope"]'))
        self.assertTrue(any("stages" in item for item in self.errors()))

    def test_duplicate_stage_fails(self) -> None:
        write(self.root, "code", "C1.md", doc("C1", '["code", "code"]'))
        self.assertTrue(any("stages" in item for item in self.errors()))

    def test_extra_or_missing_fields_fail(self) -> None:
        write(self.root, "code", "C1.md", "---\nid: C1\ntitle: t\nsummary: s\nstages: [\"code\"]\nextra: x\n---\n\n正文\n")
        self.assertTrue(any("恰为 id、title、summary、stages" in item for item in self.errors()))

    def test_missing_summary_fails(self) -> None:
        write(self.root, "code", "C1.md", doc("C1", '["code"]', summary=""))
        self.assertTrue(any("不能为空" in item for item in self.errors()))

    def test_multiline_summary_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            principle.add("code", "标题", "第一行\n第二行", ["code"], "正文")
        self.assertFalse((self.root / "code" / "C1.md").exists())

    def test_empty_body_fails(self) -> None:
        write(self.root, "code", "C1.md", doc("C1", '["code"]', body=""))
        self.assertTrue(any("不能为空" in item for item in self.errors()))

    def test_missing_frontmatter_fails(self) -> None:
        write(self.root, "code", "C1.md", "正文\n")
        self.assertTrue(any("frontmatter" in item for item in self.errors()))

    def test_add_assigns_next_number_per_category(self) -> None:
        write(self.root, "architecture", "A1.md", doc("A1"))
        write(self.root, "architecture", "A3.md", doc("A3"))
        path = principle.add("architecture", "新原则", "摘要", ["design", "code"], "一段正文。")
        self.assertEqual(path.name, "A4.md")
        self.assertEqual(self.errors(), [])
        self.assertEqual(principle.add("test", "测试原则", "摘要", ["test"], "正文").name, "T1.md")

    def test_add_rejects_invalid_stage_and_leaves_no_file(self) -> None:
        with self.assertRaises(ValueError):
            principle.add("code", "标题", "摘要", ["nope"], "正文")
        self.assertFalse((self.root / "code" / "C1.md").exists())

    def test_new_categories_use_their_letters_and_stages(self) -> None:
        self.assertEqual(principle.add("requirement", "需求原则", "摘要", ["requirement"], "正文").name, "Q1.md")
        self.assertEqual(principle.add("review", "审查原则", "摘要", ["review"], "正文").name, "R1.md")
        self.assertEqual(self.errors(), [])

    def test_update_changes_only_given_fields(self) -> None:
        write(self.root, "code", "C1.md", doc("C1", '["code"]', title="旧标题", body="旧正文"))
        principle.update("C1", "新标题", None, None, None)
        item = principle.find("C1")
        self.assertEqual((item.title, item.summary, item.stages, item.body), ("新标题", "摘要", ["code"], "旧正文"))
        principle.update("C1", None, "新摘要", ["code", "test"], "新正文")
        item = principle.find("C1")
        self.assertEqual((item.title, item.summary, item.stages, item.body), ("新标题", "新摘要", ["code", "test"], "新正文"))

    def test_update_with_invalid_stage_restores_original(self) -> None:
        path = write(self.root, "code", "C1.md", doc("C1", '["code"]'))
        before = path.read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            principle.update("C1", None, None, ["nope"], None)
        self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_update_and_remove_unknown_id_fail(self) -> None:
        with self.assertRaises(ValueError):
            principle.update("C9", "t", None, None, None)
        with self.assertRaises(ValueError):
            principle.remove("C9")

    def test_remove_moves_file_to_trash_and_restore_brings_it_back(self) -> None:
        path = write(self.root, "code", "C1.md", doc("C1", '["code"]'))
        trashed = principle.remove("C1")
        self.assertFalse(path.exists())
        self.assertEqual(trashed, self.root / "trash" / "C1.md")
        self.assertEqual(self.errors(), [])
        self.assertEqual(principle.restore("C1"), path)
        self.assertTrue(path.exists())
        self.assertFalse(trashed.exists())

    def test_trashed_ids_are_not_reused(self) -> None:
        write(self.root, "code", "C1.md", doc("C1", '["code"]'))
        principle.remove("C1")
        self.assertEqual(principle.add("code", "标题", "摘要", ["code"], "正文").name, "C2.md")

    def test_restore_unknown_or_live_id_fails(self) -> None:
        write(self.root, "code", "C1.md", doc("C1", '["code"]'))
        with self.assertRaises(ValueError):
            principle.restore("C1")
        with self.assertRaises(ValueError):
            principle.restore("X1")

    def test_summary_groups_by_category_with_first_sentence(self) -> None:
        write(self.root, "code", "C1.md", doc("C1", '["code"]', title="名词短语", body="第一句。第二句。", summary="一句话摘要。"))
        found: list = []
        lines = principle.summary(principle.load(found))
        self.assertIn("code（1）", lines)
        self.assertIn("- C1 名词短语：一句话摘要。", lines)
        self.assertIn("review（0）", lines)

    def test_cli_list_filters_by_stage(self) -> None:
        write(self.root, "architecture", "A1.md", doc("A1"))
        write(self.root, "code", "C1.md", doc("C1", '["code"]'))
        self.assertEqual(principle.main(["list", "--stage", "code"]), 0)
        self.assertEqual(principle.main(["check"]), 0)
        self.assertEqual(principle.main(["remove", "--id", "C1"]), 0)
        self.assertEqual(principle.main(["remove", "--id", "C1"]), 2)
        self.assertEqual(principle.main(["list", "--trash"]), 0)
        self.assertEqual(principle.main(["restore", "--id", "C1"]), 0)


if __name__ == "__main__":
    unittest.main()
