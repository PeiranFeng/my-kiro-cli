#!/usr/bin/env python3
"""Tests for list_probes.py using only the Python standard library."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from list_probes import find  # noqa: E402

SOURCE = '''
def overrides(cls, name):
    return True


class Plugin:
    def render(self):
        pass


def pick(slot, config):
    a = overrides(type(slot), "render")
    b = getattr(slot, "render", None)
    c = config.get("render")
    d = overrides(type(slot), "unknown")
    return a, b, c, d
'''


class ListProbesTests(unittest.TestCase):
    def test_lists_string_arguments_naming_defined_functions_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            config = {
                "schemaVersion": 2,
                "sourceSuffixes": [".py"],
                "modules": {"m": {"source": "app", "tests": "tests", "testFile": "test_{stem}.py"}},
            }
            (root / "docs/project-spec.json").write_text(json.dumps(config), encoding="utf-8")
            (root / "app").mkdir()
            (root / "app/plugin.py").write_text(SOURCE, encoding="utf-8")
            found = find(root, root / "docs")
        self.assertEqual([(line, call, name) for _, line, call, name in found], [(12, "overrides", "render"), (13, "getattr", "render")])


if __name__ == "__main__":
    unittest.main()
