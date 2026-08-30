"""Forbid production code from reading persisted job parameters directly.

Job parameters are persisted as JSON, but task modules must consume the
validated DTO exposed by ``Job.get_typed_params``. Their ``params`` attribute
is reserved so aliases and alternative parsers cannot bypass the operation
registry. Outside task modules, explicitly Job-named values are also checked.
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

_SKIPPED_PARTS = frozenset(
    {
        ".git",
        ".agents",
        ".claude",
        ".codex",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "migrations",
        "node_modules",
        "tests",
        "virtualenv_old",
    }
)


@dataclass(frozen=True)
class Violation:
    """A direct Job.params read found in a production Python module."""

    path: Path
    line: int
    column: int
    expression: str

    def format(self, root: Path) -> str:
        """Render a violation in a format understood by CI log viewers."""

        try:
            path = self.path.relative_to(root)
        except ValueError:
            path = self.path
        return f"{path}:{self.line}:{self.column}: direct Job.params access ({self.expression})"


def find_violations(source: str, path: Path) -> list[Violation]:
    """Return direct reads of the reserved params attribute in one source file."""

    tree = ast.parse(source, filename=str(path))
    is_task_module = path.name == "tasks.py" or "tasks" in path.parts
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or node.attr != "params":
            continue
        if not is_task_module:
            if not isinstance(node.value, ast.Name):
                continue
            name = node.value.id
            if name != "job" and not name.endswith("_job"):
                continue
        violations.append(
            Violation(
                path=path,
                line=node.lineno,
                column=node.col_offset + 1,
                expression=ast.unparse(node),
            )
        )
    return violations


def _is_production_file(path: Path) -> bool:
    parts = set(path.parts)
    if parts & _SKIPPED_PARTS:
        return False
    return not path.name.startswith("test_")


def iter_production_python_files(root: Path) -> Iterable[Path]:
    """Yield production Python files while excluding test and generated trees."""

    for current_root, directories, files in os.walk(root):
        directories[:] = [name for name in directories if name not in _SKIPPED_PARTS]
        directory = Path(current_root)
        for name in files:
            if name.endswith(".py"):
                path = directory / name
                if _is_production_file(path):
                    yield path


def check_repository(root: Path) -> list[Violation]:
    """Scan production Python files under ``root``."""

    violations: list[Violation] = []
    for path in iter_production_python_files(root):
        if path.relative_to(root) == Path("job/models.py"):
            continue
        violations.extend(find_violations(path.read_text(encoding="utf-8"), path))
    return sorted(violations, key=lambda item: (item.path, item.line, item.column))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root to scan (default: the current repository)",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    violations = check_repository(root)
    if violations:
        for violation in violations:
            sys.stderr.write(f"{violation.format(root)}\n")
        sys.stderr.write(f"Found {len(violations)} direct Job.params access(es).\n")
        return 1
    sys.stdout.write("No direct Job.params access found in production code.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
