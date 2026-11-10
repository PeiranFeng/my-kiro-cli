#!/usr/bin/env python3
"""Tests for gen_structure.py using only the Python standard library."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from gen_structure import process, render_body, skeleton  # noqa: E402

SOURCE = '''"""Loads prices."""

LIMIT: int = 5  # Maximum rows.
_HIDDEN = 1
NAME = "x"


class Loader(Base):
    """Reads rows."""

    path: str  # Where to read.

    def __init__(self, path: str) -> None:
        self.path = path

    @classmethod
    def build(cls, *, path: str = "a") -> "Loader":
        """Builds one."""
        return cls(path)

    def _private(self) -> None:
        pass

    def load(self):
        return getattr(self, "reader", None)


def fit(epochs: int = 1) -> None:
    pass


def _skip() -> None:
    pass
'''


class RenderTests(unittest.TestCase):
    def test_render_lists_public_symbols_with_anchors_and_descriptions(self) -> None:
        body = render_body(SOURCE, "data", "_Loader_")
        self.assertIn("# _Loader_ 结构", body)
        self.assertIn("> Loads prices.", body)
        self.assertIn("LIMIT: int  # Maximum rows.", body)
        self.assertIn("NAME  # (无说明)", body)
        self.assertNotIn("_HIDDEN", body)
        self.assertIn("## Loader(Base) {#api.data.loader.loader}", body)
        self.assertIn("> Reads rows.", body)
        self.assertIn("path: str  # Where to read.", body)
        self.assertIn("### Loader.__init__ {#api.data.loader.loader.init}", body)
        self.assertIn("@classmethod\ndef build(cls, *, path: str='a') -> 'Loader'  # Builds one.", body)
        self.assertNotIn("_private", body)
        self.assertIn("## fit {#api.data.loader.fit}", body)
        self.assertNotIn("_skip", body)

    def test_render_lists_dynamic_probes_with_scope(self) -> None:
        body = render_body(SOURCE, "data", "loader")
        self.assertIn("| Loader.load | getattr | `reader` |", body)

    def test_empty_sections_are_omitted(self) -> None:
        body = render_body('"""Only text."""\n', "data", "x")
        self.assertNotIn("## 模块变量", body)
        self.assertNotIn("## 动态探测", body)

    def test_duplicate_method_names_render_once(self) -> None:
        source = "class A:\n    @property\n    def v(self): ...\n    @v.setter\n    def v(self, x): ...\n"
        self.assertEqual(render_body(source, "m", "s").count("{#api.m.s.a.v}"), 1)

    def test_skeleton_ignores_descriptions_only(self) -> None:
        first = render_body(SOURCE, "data", "loader")
        described = first.replace("Reads rows.", "Other text.").replace("(无说明)", "Edited.")
        self.assertEqual(skeleton(first), skeleton(described))
        self.assertNotEqual(skeleton(first), skeleton(render_body(SOURCE.replace("epochs", "steps"), "data", "loader")))


class ProcessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        config = {
            "schemaVersion": 2,
            "sourceSuffixes": [".py"],
            "modules": {"data": {"source": "app/data", "tests": "tests/data", "testFile": "test_{stem}.py"}},
        }
        (self.root / "docs").mkdir()
        (self.root / "docs/project-spec.json").write_text(json.dumps(config), encoding="utf-8")
        (self.root / "app/data").mkdir(parents=True)
        (self.root / "app/data/loader.py").write_text(SOURCE, encoding="utf-8")
        (self.root / "app/data/__init__.py").write_text("", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def doc(self) -> Path:
        return self.root / "docs/architecture/data/loader.structure.md"

    def test_check_reports_missing_then_write_creates_then_check_passes(self) -> None:
        self.assertEqual(process(self.root, write=False), ["docs/architecture/data/loader.structure.md: missing"])
        self.assertFalse(self.doc().exists())
        process(self.root, write=True)
        text = self.doc().read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nid: struct.data.loader\nkind: structure\nstatus: draft\n---\n\n# loader 结构"))
        self.assertEqual(process(self.root, write=False), [])

    def test_empty_modules_get_no_document(self) -> None:
        process(self.root, write=True)
        self.assertFalse((self.root / "docs/architecture/data/__init__.structure.md").exists())

    def test_empty_module_with_source_document_gets_structure_document(self) -> None:
        source_doc = self.root / "docs/architecture/data/__init__.md"
        source_doc.parent.mkdir(parents=True)
        source_doc.write_text("---\nid: arch.data.init\n---\n", encoding="utf-8")
        process(self.root, write=True)
        self.assertTrue((self.root / "docs/architecture/data/__init__.structure.md").is_file())

    def test_hand_written_descriptions_survive_when_structure_matches(self) -> None:
        process(self.root, write=True)
        edited = self.doc().read_text(encoding="utf-8").replace("Reads rows.", "Mine.")
        self.doc().write_text(edited, encoding="utf-8")
        self.assertEqual(process(self.root, write=True), [])
        self.assertIn("Mine.", self.doc().read_text(encoding="utf-8"))

    def test_stale_document_is_rewritten_and_keeps_frontmatter(self) -> None:
        process(self.root, write=True)
        self.doc().write_text(self.doc().read_text(encoding="utf-8").replace("status: draft", "status: approved") + "\nextra\n", encoding="utf-8")
        self.assertEqual(process(self.root, write=True), ["docs/architecture/data/loader.structure.md: stale"])
        text = self.doc().read_text(encoding="utf-8")
        self.assertIn("status: approved", text)
        self.assertNotIn("extra", text)

    def test_unparsable_source_is_reported(self) -> None:
        (self.root / "app/data/loader.py").write_text("def (:\n", encoding="utf-8")
        problems = process(self.root, write=False)
        self.assertEqual(len(problems), 1)
        self.assertIn("无法解析", problems[0])


if __name__ == "__main__":
    unittest.main()
