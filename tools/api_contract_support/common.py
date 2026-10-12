"""Shared failures and bounded subprocess execution for contract inspection."""

import subprocess
from pathlib import Path


class ContractError(RuntimeError):
    """The comparison could not be completed reliably."""


def run_command(
    command: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Run without a shell and preserve exit status separately from diagnostics."""
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            timeout=timeout,
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ContractError(f"Command timed out after {timeout}s: {command[0]}") from exc
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"Cannot execute {command[0]}: {exc}") from exc
