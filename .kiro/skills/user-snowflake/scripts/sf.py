"""Shared helpers of this skill's scripts: the connection, the personal schema names, and running SQL through snow."""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

LOCAL_CONTEXT = Path.home() / "data" / "my-kiro-cli" / ".kiro" / "local-context.sh"
FEATURE_LAB = Path.home() / "data" / "feature-lab"
PREPROCESS_MODELS = FEATURE_LAB / "models" / "preprocess"


def _context() -> tuple[str, str]:
    out = subprocess.run(
        ["bash", "-c", f"source '{LOCAL_CONTEXT}' >/dev/null 2>&1; echo $SNOWFLAKE_CONNECTION; echo $SNOWFLAKE_USER"],
        capture_output=True, text=True, check=True,
    ).stdout.split("\n")
    return out[0], re.sub(r"[^A-Z0-9_]", "_", out[1].upper())


CONNECTION, USER = _context()
SCHEMA = f"DEV_{USER}"
PREPROCESS_SCHEMA = f"{SCHEMA}_PREPROCESS"
ROLE = f"FEATURELAB_PERSONAL_{USER}"


def sql(text: str, warehouse: str | None = None) -> list[dict]:
    """Run one or more statements and return the last statement's rows."""
    prefix = f'use warehouse "{warehouse}";\n' if warehouse else ""
    fd, name = tempfile.mkstemp(suffix=".sql")
    os.close(fd)
    Path(name).write_text(prefix + text.rstrip().rstrip(";") + ";\n")
    try:
        run = subprocess.run(["snow", "sql", "-c", CONNECTION, "--format", "json", "-f", name],
                             capture_output=True, text=True)
    finally:
        os.unlink(name)
    if run.returncode:
        raise RuntimeError(run.stdout[-1500:] + run.stderr[-1500:])
    rows = json.loads(run.stdout)
    # Several statements return one list per statement.
    if rows and isinstance(rows[0], list):
        rows = rows[-1]
    return rows


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def preprocess_layer_names() -> set[str]:
    """Return every relation the preprocess layer writes: its models and the siblings they write by name."""
    names = {p.stem.upper() for p in PREPROCESS_MODELS.glob("*.sql")}
    names |= {p.stem.upper() for p in PREPROCESS_MODELS.glob("*.py")}
    for path in PREPROCESS_MODELS.glob("*.py"):
        names |= {n.upper() for n in re.findall(r'sibling_relation\(\s*dbt\.this,\s*"([a-z0-9_]+)"', path.read_text())}
    return names
