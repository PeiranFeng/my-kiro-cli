#!/usr/bin/env python3
"""Tests for docs_cache.py using only the Python standard library and a temporary git repository."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import docs_cache  # noqa: E402

CONFIG = {
    "schemaVersion": 2,
    "sourceSuffixes": [".py"],
    "modules": {"m": {"source": "app", "tests": "tests", "testFile": "test_{stem}.py"}},
}


def run(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", *args], capture_output=True, text=True, check=True)
    return done.stdout.strip()


class DocsCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.repo = base / "sample"
        self.repo.mkdir()
        (self.repo / "app").mkdir()
        (self.repo / "app/a.py").write_text("def a():\n    pass\n", encoding="utf-8")
        (self.repo / "app/b.py").write_text("def b():\n    pass\n", encoding="utf-8")
        run(self.repo, "init", "-q")
        run(self.repo, "add", "-A")
        run(self.repo, "commit", "-q", "-m", "first")
        self.original = docs_cache.DOCS_BASE
        docs_cache.DOCS_BASE = base / "docs"

    def tearDown(self) -> None:
        docs_cache.DOCS_BASE = self.original
        self.temp.cleanup()

    def seed(self, commit: str) -> Path:
        root = docs_cache.docs_root_for(self.repo, commit)
        (root / "architecture/m").mkdir(parents=True)
        (root / "architecture/m/a.md").write_text("a", encoding="utf-8")
        (root / "architecture/m/a.structure.md").write_text("s", encoding="utf-8")
        (root / "architecture/m/b.md").write_text("b", encoding="utf-8")
        (root / "project-spec.json").write_text(json.dumps(CONFIG), encoding="utf-8")
        return root

    def commit_change(self) -> str:
        (self.repo / "app/a.py").write_text("def a(x):\n    pass\n", encoding="utf-8")
        (self.repo / "app/c.py").write_text("def c():\n    pass\n", encoding="utf-8")
        run(self.repo, "rm", "-q", "app/b.py")
        run(self.repo, "add", "-A")
        run(self.repo, "commit", "-q", "-m", "second")
        return docs_cache.head_commit(self.repo)

    def test_state_none_creates_empty_root_named_by_repo_and_head(self) -> None:
        info = docs_cache.prepare(self.repo)
        self.assertEqual(info["state"], "none")
        self.assertEqual(Path(info["docsRoot"]), docs_cache.DOCS_BASE / "sample" / docs_cache.head_commit(self.repo))
        self.assertTrue(Path(info["docsRoot"]).is_dir())

    def test_state_exact_when_head_already_has_documents(self) -> None:
        self.seed(docs_cache.head_commit(self.repo))
        self.assertEqual(docs_cache.status(self.repo)["state"], "exact")

    def test_incremental_copies_base_and_lists_changes_with_affected_documents(self) -> None:
        first = docs_cache.head_commit(self.repo)
        self.seed(first)
        second = self.commit_change()
        info = docs_cache.prepare(self.repo)
        self.assertEqual((info["state"], info["base"]), ("incremental", first))
        copied = Path(info["docsRoot"])
        self.assertEqual(copied.name, second)
        self.assertTrue((copied / "architecture/m/a.structure.md").is_file())
        by_path = {item["path"]: item for item in info["changes"]}
        self.assertEqual(by_path["app/a.py"]["status"], "M")
        self.assertEqual(by_path["app/a.py"]["docs"], ["architecture/m/a.md", "architecture/m/a.structure.md"])
        self.assertEqual(by_path["app/b.py"]["status"], "D")
        self.assertEqual(by_path["app/c.py"]["status"], "A")
        self.assertEqual(by_path["app/c.py"]["docs"], [])
        self.assertTrue((docs_cache.docs_root_for(self.repo, first) / "architecture/m/a.md").is_file())

    def test_nearest_ancestor_is_the_base_and_unrelated_commits_are_ignored(self) -> None:
        first = docs_cache.head_commit(self.repo)
        self.seed(first)
        self.commit_change()
        (self.repo / "app/d.py").write_text("", encoding="utf-8")
        run(self.repo, "add", "-A")
        run(self.repo, "commit", "-q", "-m", "third")
        second = run(self.repo, "rev-parse", "HEAD~1")
        self.seed(second)
        self.assertEqual(docs_cache.find_base(self.repo), second)
        (docs_cache.DOCS_BASE / "sample" / ("f" * 40)).mkdir(parents=True)
        self.assertEqual(docs_cache.find_base(self.repo), second)

    def test_uncommitted_changes_and_untracked_files_are_included(self) -> None:
        first = docs_cache.head_commit(self.repo)
        self.seed(first)
        (self.repo / "app/a.py").write_text("def a(y):\n    pass\n", encoding="utf-8")
        (self.repo / "app/new.py").write_text("", encoding="utf-8")
        rows = dict((path, code) for code, path in docs_cache.changed_files(self.repo, first))
        self.assertEqual(rows, {"app/a.py": "M", "app/new.py": "A"})

    def test_cli_resolve_is_read_only_and_reports_errors(self) -> None:
        self.assertEqual(docs_cache.main(["resolve", "--project-root", str(self.repo)]), 0)
        self.assertFalse((docs_cache.DOCS_BASE / "sample").exists())
        self.assertEqual(docs_cache.main(["resolve", "--project-root", self.temp.name + "/missing"]), 2)


if __name__ == "__main__":
    unittest.main()
