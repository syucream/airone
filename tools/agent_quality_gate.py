#!/usr/bin/env python3
"""Enforce the minimum repository quality gate at an AI agent's Stop event."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

GATE_TIMEOUT_SECONDS = 55
MAX_FAILURE_OUTPUT_CHARS = 5_000
STATE_VERSION = 1
UNTRACKED_EXCLUDED_PREFIXES = (
    ".artifacts/",
    "e2e/test-results/",
)


def run_git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        stderr=subprocess.DEVNULL,
    )


def resolve_root(cwd: str) -> Path:
    output = subprocess.check_output(
        ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return Path(output.strip()).resolve()


def add_file_to_hash(digest: Any, root: Path, relative_path: str) -> None:
    path = root / relative_path
    digest.update(relative_path.encode())
    digest.update(b"\0")

    if path.is_symlink():
        digest.update(os.readlink(path).encode())
        return

    if not path.is_file():
        digest.update(b"<missing>")
        return

    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)


def worktree_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    digest.update(run_git(root, "rev-parse", "HEAD").strip())

    diff = subprocess.Popen(
        ["git", "-C", str(root), "diff", "--binary", "HEAD", "--"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert diff.stdout is not None
    while chunk := diff.stdout.read(1024 * 1024):
        digest.update(chunk)
    if diff.wait() != 0:
        raise RuntimeError("git diff failed while computing the quality-gate fingerprint")

    untracked = run_git(root, "ls-files", "--others", "--exclude-standard", "-z")
    for encoded_path in sorted(path for path in untracked.split(b"\0") if path):
        relative_path = os.fsdecode(encoded_path)
        if relative_path.startswith(UNTRACKED_EXCLUDED_PREFIXES):
            continue
        add_file_to_hash(digest, root, relative_path)

    return digest.hexdigest()


def state_path(root: Path, session_id: str) -> Path:
    root_key = hashlib.sha256(str(root).encode()).hexdigest()[:20]
    session_key = hashlib.sha256(session_id.encode()).hexdigest()[:20]
    return (
        Path(tempfile.gettempdir())
        / "pagoda-agent-quality-gate"
        / f"v{STATE_VERSION}"
        / root_key
        / f"{session_key}.json"
    )


def read_state(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f".{os.getpid()}.tmp")
    temporary_path.write_text(json.dumps(state, sort_keys=True))
    temporary_path.replace(path)


def emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload))


def failure_reason(output: str) -> str:
    tail = output[-MAX_FAILURE_OUTPUT_CHARS:].strip()
    if not tail:
        tail = "The quality command failed without output."
    return (
        "The minimum repository quality gate failed. Fix the reported issues, "
        "then finish the task again.\n\n"
        f"{tail}"
    )


def run_gate(root: Path) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            ["bash", "tools/quality_fast.sh"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=GATE_TIMEOUT_SECONDS,
            check=False,
        )
        return completed.returncode, completed.stdout
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        return 124, f"{output}\nQuality gate timed out after {GATE_TIMEOUT_SECONDS} seconds."


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
        if not isinstance(hook_input, dict):
            raise ValueError("hook input must be a JSON object")

        event = hook_input.get("hook_event_name")
        session_id = str(hook_input.get("session_id") or "unknown-session")
        root = resolve_root(str(hook_input.get("cwd") or os.getcwd()))
        fingerprint = worktree_fingerprint(root)
        path = state_path(root, session_id)
        state = read_state(path)

        if event == "SessionStart":
            write_state(path, {"baseline": fingerprint})
            return 0

        if event != "Stop":
            return 0

        if state.get("baseline") == fingerprint or state.get("passed") == fingerprint:
            return 0

        returncode, output = run_gate(root)
        if returncode == 0:
            write_state(path, {"baseline": fingerprint, "passed": fingerprint})
            return 0

        if hook_input.get("stop_hook_active") and state.get("failed") == fingerprint:
            emit(
                {
                    "continue": False,
                    "stopReason": (
                        "The minimum quality gate is still failing and the worktree "
                        "did not change after the agent was asked to fix it."
                    ),
                    "systemMessage": "The agent stopped with an unresolved quality-gate failure.",
                }
            )
            return 0

        write_state(path, {"baseline": state.get("baseline"), "failed": fingerprint})
        emit({"decision": "block", "reason": failure_reason(output)})
        return 0
    except Exception as error:
        emit(
            {
                "decision": "block",
                "reason": (
                    "The minimum repository quality gate could not run. "
                    f"Diagnose the hook failure before finishing: {error}"
                ),
            }
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
