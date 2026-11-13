"""Bound one launcher stage while allowing worker harness exit handlers to run."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from types import FrameType


class Interrupted(Exception):
    def __init__(self, signum: int) -> None:
        super().__init__(signum)
        self.signum = signum


def interrupted(signum: int, _frame: FrameType | None) -> None:
    raise Interrupted(signum)


def main() -> int:
    if len(sys.argv) < 3:
        sys.stderr.write("Usage: timeout.py SECONDS COMMAND [ARG ...]\n")
        return 2
    seconds = int(sys.argv[1])
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(sys.argv[2:], start_new_session=True)
        return process.wait(timeout=seconds)
    except (subprocess.TimeoutExpired, Interrupted) as error:
        # Ignore repeat interrupts while the harness cleans up its worker sessions.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
        if isinstance(error, Interrupted):
            return 128 + error.signum
        sys.stderr.write(f"Stage exceeded {seconds} seconds\n")
        return 124


if __name__ == "__main__":
    sys.exit(main())
