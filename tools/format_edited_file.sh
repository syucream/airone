#!/bin/bash
#
# Format a single file after an agent edits it.
#
# Wired up as a Claude Code PostToolUse hook (see .claude/settings.json). The
# hook protocol passes the tool invocation as JSON on stdin; the edited path is
# at .tool_input.file_path.
#
# The point is that a formatting-only diff should never reach a reviewer, and
# should never be the reason a push fails. This mirrors the pre-commit jobs in
# lefthook.yml for the human workflow.
#
# Always exits 0: a formatter that is unavailable (no venv, no node_modules)
# must not block the agent. lefthook and CI remain the enforcing gates.

set -u

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

file_path=$(python3 -c '
import json
import sys

try:
    payload = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)
print(payload.get("tool_input", {}).get("file_path", ""))
' 2>/dev/null)

[ -n "${file_path}" ] || exit 0
[ -f "${file_path}" ] || exit 0

case "${file_path}" in
    "${BASE_DIR}"/*) ;;
    *) exit 0 ;;
esac

case "${file_path}" in
    *.py)
        # --force-exclude: ruff ignores `extend-exclude` for paths passed
        # explicitly on the command line, so without it this reformats
        # manage.py and the migration trees.
        if [ -x "${BASE_DIR}/.venv/bin/ruff" ]; then
            "${BASE_DIR}/.venv/bin/ruff" format --quiet --force-exclude "${file_path}"
        elif command -v ruff >/dev/null 2>&1; then
            ruff format --quiet --force-exclude "${file_path}"
        fi
        ;;
    *.ts | *.tsx)
        # --no-errors-on-unmatched: biome exits 1 when the path is outside the
        # `files.includes` globs in biome.json.
        if [ -x "${BASE_DIR}/node_modules/.bin/biome" ]; then
            "${BASE_DIR}/node_modules/.bin/biome" format --write \
                --no-errors-on-unmatched "${file_path}" >/dev/null 2>&1
        fi
        ;;
esac

exit 0
