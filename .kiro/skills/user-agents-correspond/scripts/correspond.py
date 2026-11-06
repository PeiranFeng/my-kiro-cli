#!/usr/bin/env python3
"""Deterministic file protocol helper for user-agents-correspond."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{9}Z)\.md$")
WORK_ID_RE = re.compile(r"^([a-z0-9][a-z0-9-]*)-(\d+|_)-(\d+|_)-([1-9]\d*)$")
SENSITIVE_RE = re.compile(r"(?i)\b(password|passphrase|secret|token|api[ _-]?key|private[ _-]?key|connection[ _-]?string)\b")
POLL_INTERVAL_SECONDS = 10
STATE_SCHEMA = "user-agents-correspond-state/v2"
MESSAGE_SCHEMA = "user-agents-correspond/v2"


def fail(message: str) -> None:
    raise ValueError(message)


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail(f"{path.name} has no frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        fail(f"{path.name} has unterminated frontmatter")
    values: dict[str, Any] = {}
    current_list: str | None = None
    for line in text[4:end].splitlines():
        if line.startswith("  - "):
            if current_list is None:
                fail(f"{path.name} has an orphan list item")
            values[current_list].append(json.loads(line[4:]))
        elif line.endswith(":"):
            current_list = line[:-1]
            values[current_list] = []
        elif ": " in line:
            key, value = line.split(": ", 1)
            if value == "[]":
                values[key] = []
                current_list = key
            else:
                values[key] = json.loads(value) if value.startswith('"') else int(value) if re.fullmatch(r"-?\d+", value) else value
                current_list = None
        else:
            fail(f"{path.name} has invalid frontmatter")
    return values, text[end + 5 :]


def write_frontmatter(values: dict[str, Any], body: str = "") -> str:
    lines = ["---"]
    for key, value in values.items():
        if isinstance(value, list):
            lines.append(f"{key}: []" if not value else f"{key}:")
            lines.extend(f"  - {json.dumps(item, ensure_ascii=False)}" for item in value)
        elif isinstance(value, str):
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n---\n" + body


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    temporary = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_publish(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(path)
    atomic_write(path, content)


def filename_timestamp(filename: str) -> int:
    match = FILENAME_RE.fullmatch(filename)
    if match is None:
        fail(f"invalid message filename: {filename}")
    value = match.group(1)
    seconds = datetime.strptime(value[:19], "%Y-%m-%dT%H-%M-%S").replace(tzinfo=UTC)
    return int(seconds.timestamp()) * 1_000_000_000 + int(value[20:29])


def utc_from_filename(filename: str) -> str:
    filename_timestamp(filename)
    value = filename[:-3]
    return f"{value[:10]}T{value[11:13]}:{value[14:16]}:{value[17:19]}.{value[20:29]}Z"


def new_filename() -> str:
    seconds, nanos = divmod(time.time_ns(), 1_000_000_000)
    return f"{datetime.fromtimestamp(seconds, UTC):%Y-%m-%dT%H-%M-%S}-{nanos:09d}Z.md"


def split_work_id(work_id: str) -> tuple[str, str, str, int]:
    match = WORK_ID_RE.fullmatch(work_id)
    if match is None:
        fail(f"invalid work_id: {work_id}")
    return match.group(1), match.group(2), match.group(3), int(match.group(4))


def repo_name(path: str) -> str:
    return "not-applicable" if path == "not-applicable" else Path(path).name.lower().replace("_", "-")


def require_safe_text(value: str, field: str) -> None:
    if not value.strip() or SENSITIVE_RE.search(value):
        fail(f"{field} is empty or sensitive")


def state_path(root: Path, work_id: str) -> Path:
    return root / "state" / "active" / f"{work_id}.md"


def validate_state(state: dict[str, Any], work_id: str) -> None:
    required = {"schema", "work_id", "repo", "issue", "pr", "sub_worker", "user_requirement", "updated_at_utc", "lifecycle", "last_read_file", "accepted_files", "progress"}
    if state.get("schema") != STATE_SCHEMA or set(state) != required or state.get("work_id") != work_id:
        fail("state schema or fields are invalid")
    repo, issue, pr, worker = split_work_id(work_id)
    if repo_name(str(state["repo"])) != repo or state["issue"] != issue or state["pr"] != pr or state["sub_worker"] != worker:
        fail("state scope does not match work_id")
    if state["lifecycle"] not in {"active", "blocked"} or state["last_read_file"] != "none" and not FILENAME_RE.fullmatch(state["last_read_file"]):
        fail("state lifecycle or cursor is invalid")
    if not isinstance(state["accepted_files"], list) or any(not isinstance(name, str) or not FILENAME_RE.fullmatch(name) for name in state["accepted_files"]):
        fail("state accepted records are invalid")


def load_state(root: Path, work_id: str) -> tuple[Path, dict[str, Any]]:
    path = state_path(root, work_id)
    if not path.is_file():
        fail(f"active state does not exist: {path}")
    state, _ = parse_frontmatter(path)
    validate_state(state, work_id)
    return path, state


def save_state(path: Path, state: dict[str, Any]) -> None:
    state["updated_at_utc"] = utc_from_filename(new_filename())
    atomic_write(path, write_frontmatter(state))


def update_work(arguments: argparse.Namespace) -> None:
    root = Path(arguments.correspondence_dir).resolve()
    repo, issue, pr, worker = split_work_id(arguments.work_id)
    if repo_name(arguments.repo) != repo or arguments.issue != issue or arguments.pr != pr or arguments.sub_worker != worker:
        fail("work metadata does not match work_id")
    require_safe_text(arguments.user_requirement, "user_requirement")
    require_safe_text(arguments.progress, "progress")
    path = state_path(root, arguments.work_id)
    if path.exists():
        _, state = load_state(root, arguments.work_id)
    else:
        state = {"lifecycle": "active", "last_read_file": "none", "accepted_files": []}
    state.pop("read_files", None)
    if arguments.last_read_file is not None:
        if arguments.last_read_file != "none":
            filename_timestamp(arguments.last_read_file)
        state["last_read_file"] = arguments.last_read_file
    for name in arguments.accepted_file:
        filename_timestamp(name)
        if name not in state["accepted_files"]:
            state["accepted_files"].append(name)
    state.update({"schema": STATE_SCHEMA, "work_id": arguments.work_id, "repo": arguments.repo, "issue": issue, "pr": pr, "sub_worker": worker, "user_requirement": arguments.user_requirement, "lifecycle": state["lifecycle"], "progress": arguments.progress})
    save_state(path, state)
    print(path)


def publish(arguments: argparse.Namespace) -> None:
    root = Path(arguments.correspondence_dir).resolve()
    _, state = load_state(root, arguments.work_id)
    body = Path(arguments.body_file).read_text(encoding="utf-8").rstrip("\n")
    require_safe_text(arguments.source_agent, "source_agent")
    require_safe_text(body, "message body")
    if arguments.target_work_id != "broadcast":
        split_work_id(arguments.target_work_id)
    if arguments.action not in {"information", "handoff", "request", "acknowledgement"}:
        fail("invalid action")
    filename = new_filename()
    message: dict[str, Any] = {"schema": MESSAGE_SCHEMA, "created_at_utc": utc_from_filename(filename), "source_agent": arguments.source_agent, "work_id": arguments.work_id, "target_work_id": arguments.target_work_id, "repo": state["repo"], "issue": state["issue"], "pr": state["pr"], "sub_worker": state["sub_worker"], "user_requirement": state["user_requirement"], "progress": state["progress"], "action": arguments.action}
    if arguments.action == "request":
        if not arguments.requested_acknowledgement_from_work_id or arguments.requested_acknowledgement is None:
            fail("request acknowledgement is required")
        if arguments.target_work_id != arguments.requested_acknowledgement_from_work_id:
            fail("request target differs from acknowledgement worker")
        split_work_id(arguments.requested_acknowledgement_from_work_id)
        require_safe_text(arguments.requested_acknowledgement, "requested acknowledgement")
        message["requested_acknowledgement_from_work_id"] = arguments.requested_acknowledgement_from_work_id
        message["requested_acknowledgement"] = arguments.requested_acknowledgement
    if arguments.action == "acknowledgement":
        if not arguments.in_reply_to:
            fail("acknowledgement needs in_reply_to")
        filename_timestamp(arguments.in_reply_to)
        message["in_reply_to"] = arguments.in_reply_to
    path = root / "messages" / filename
    atomic_publish(path, write_frontmatter(message, "\n## Message\n\n" + body + "\n"))
    print(path)


def valid_message(path: Path) -> tuple[dict[str, Any], str]:
    filename_timestamp(path.name)
    message, rest = parse_frontmatter(path)
    required = {"schema", "created_at_utc", "source_agent", "work_id", "target_work_id", "repo", "issue", "pr", "sub_worker", "user_requirement", "progress", "action"}
    if not required <= set(message) or message.get("schema") != MESSAGE_SCHEMA:
        fail(f"{path.name} has invalid message schema")
    repo, issue, pr, worker = split_work_id(str(message["work_id"]))
    if repo_name(str(message["repo"])) != repo or message["issue"] != issue or message["pr"] != pr or message["sub_worker"] != worker or message["created_at_utc"] != utc_from_filename(path.name):
        fail(f"{path.name} has inconsistent scope")
    if message["target_work_id"] != "broadcast":
        split_work_id(str(message["target_work_id"]))
    marker = "\n## Message\n\n"
    if not rest.startswith(marker):
        fail(f"{path.name} has invalid body")
    body = rest[len(marker):].rstrip("\n")
    require_safe_text(body, "message body")
    return message, body


def acknowledgement_matches(root: Path, local: str, message: dict[str, Any], body: str) -> bool:
    if message.get("action") != "acknowledgement" or message.get("target_work_id") != local or not isinstance(message.get("in_reply_to"), str):
        return False
    request_path = root / "messages" / message["in_reply_to"]
    if not request_path.is_file():
        return False
    try:
        request, _ = valid_message(request_path)
    except ValueError:
        return False
    return request.get("action") == "request" and request.get("work_id") == local and request.get("target_work_id") == message["work_id"] and request.get("requested_acknowledgement_from_work_id") == message["work_id"] and request.get("requested_acknowledgement") == body


def receive(arguments: argparse.Namespace) -> None:
    root = Path(arguments.correspondence_dir).resolve()
    _, state = load_state(root, arguments.work_id)
    accepted_files = set(state["accepted_files"]) | set(arguments.accepted_file)
    cursor = arguments.cursor if arguments.cursor is not None else state["last_read_file"]
    if cursor != "none":
        filename_timestamp(cursor)
    deadline = time.monotonic() + arguments.timeout_seconds
    while True:
        has_read_message = False
        events: list[dict[str, Any]] = []
        for path in sorted((item for item in (root / "messages").glob("*.md") if FILENAME_RE.fullmatch(item.name)), key=lambda item: item.name):
            if cursor != "none" and path.name <= cursor:
                continue
            cursor = path.name
            has_read_message = True
            try:
                message, body = valid_message(path)
            except ValueError:
                continue
            if path.name in accepted_files:
                continue
            if message["work_id"] == arguments.work_id:
                continue
            direct = message["target_work_id"] == arguments.work_id
            broadcast = message["target_work_id"] == "broadcast" and split_work_id(message["work_id"])[:3] == split_work_id(arguments.work_id)[:3]
            if not direct and not broadcast:
                continue
            if message["action"] == "acknowledgement" and not acknowledgement_matches(root, arguments.work_id, message, body):
                continue
            events.append({"filename": path.name, "action": message["action"], "source_work_id": message["work_id"], "target_work_id": message["target_work_id"], "body": body})
        if has_read_message or time.monotonic() >= deadline:
            print(json.dumps({"cursor": cursor, "events": events}, ensure_ascii=False))
            return
        time.sleep(min(POLL_INTERVAL_SECONDS, max(0, deadline - time.monotonic())))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--correspondence-dir", default=str(Path(__file__).resolve().parents[3] / "agent-correspondence"))
    commands = result.add_subparsers(dest="command", required=True)
    update = commands.add_parser("update-work")
    for name in ("work-id", "repo", "issue", "pr", "user-requirement", "progress"):
        update.add_argument(f"--{name}", required=True)
    update.add_argument("--sub-worker", type=int, required=True)
    update.add_argument("--last-read-file")
    update.add_argument("--accepted-file", action="append", default=[])
    update.set_defaults(handler=update_work)
    broadcast = commands.add_parser("broadcast")
    for name in ("work-id", "source-agent", "action", "body-file"):
        broadcast.add_argument(f"--{name}", required=True)
    broadcast.add_argument("--target-work-id", default="broadcast")
    broadcast.add_argument("--requested-acknowledgement-from-work-id")
    broadcast.add_argument("--requested-acknowledgement")
    broadcast.add_argument("--in-reply-to")
    broadcast.set_defaults(handler=publish)
    receiver = commands.add_parser("receive")
    receiver.add_argument("--work-id", required=True)
    receiver.add_argument("--cursor")
    receiver.add_argument("--accepted-file", action="append", default=[])
    receiver.add_argument("--timeout-seconds", type=float, default=POLL_INTERVAL_SECONDS)
    receiver.set_defaults(handler=receive)
    return result


def main() -> None:
    try:
        arguments = parser().parse_args()
        if getattr(arguments, "timeout_seconds", 0) < 0:
            fail("timeout_seconds must not be negative")
        arguments.handler(arguments)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"user-agents-correspond: {error}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
