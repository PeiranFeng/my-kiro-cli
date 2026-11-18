"""Naming of everything a test writes to the personal schemas or to local disk, keyed by a test tag.

A tag names the issue, PR or commit a test belongs to: <REPO>_<PR|IS|C><id>, REPO being PE
(preprocess_evaluate) or FL (feature-lab), e.g. PE_PR95, FL_IS120, PE_CA1D1528.

Usage: python3 test_tag.py check <TAG>      exits 1 unless TAG is well formed
       python3 test_tag.py names <TAG>      prints the name patterns the tag owns
"""

import re
import sys
from pathlib import Path

TAG_BODY = r"(?:PE|FL)_(?:PR[0-9]+|IS[0-9]+|C[0-9A-F]{7,40})"
TAG = re.compile(rf"^{TAG_BODY}$")
LOCAL_ROOT = Path.home() / "data" / "test" / "snowflake"


def check(tag: str) -> str:
    if not TAG.match(tag):
        raise ValueError(f"bad test tag {tag!r}: expected <PE|FL>_<PR<n>|IS<n>|C<hash>>, upper case")
    return tag


def procedure_name(prefix: str, tag: str, commit: str) -> str:
    """Procedures are <PREFIX>_<TAG>_<HASH>, the hash being the deployed commit's short hash."""
    return f"{prefix}_{check(tag)}_{commit.upper()}"


def table_name(name: str, tag: str, label: str) -> str:
    """Tables and views a test creates are <NAME>__<TAG>__<LABEL>."""
    return f"{name}__{check(tag)}__{label}"


def stage_dir(lib: str, tag: str) -> str:
    """Bundles go to PYTHON_STAGE/<lib>/<tag lower>/<hash>/."""
    return f"{lib}/{check(tag).lower()}/"


def local_dir(tag: str) -> Path:
    """Work directories, dbt target and logs included, live under ~/data/test/snowflake/<TAG>/."""
    return LOCAL_ROOT / check(tag)


def owner(name: str):
    """Return the tag a Snowflake object name belongs to, or None when it carries no tag."""
    match = re.search(rf"__({TAG_BODY})__", name) or re.search(rf"_({TAG_BODY})_[0-9A-F]{{7}}$", name)
    return match.group(1) if match else None


def stage_owner(path: str):
    """Return the tag a PYTHON_STAGE file path belongs to, or None."""
    match = re.match(r"python_stage/[a-z0-9_]+/([a-z0-9_]+)/", path)
    return match.group(1).upper() if match and TAG.match(match.group(1).upper()) else None


if __name__ == "__main__":
    action, tag = sys.argv[1], sys.argv[2]
    try:
        check(tag)
    except ValueError as error:
        print(error, file=sys.stderr)
        sys.exit(1)
    if action == "names":
        print(f"procedures  <PREFIX>_{tag}_<HASH>")
        print(f"tables      {table_name('<NAME>', tag, '<LABEL>')}")
        print(f"stage       PYTHON_STAGE/{stage_dir('<lib>', tag)}<hash>/")
        print(f"local       {local_dir(tag)}/")
