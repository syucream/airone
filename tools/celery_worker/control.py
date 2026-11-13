"""Run the Linux test producer and mediate allowlisted broker fault requests."""

from __future__ import annotations

import json
import os
import re
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from types import FrameType
from uuid import uuid4


class Interrupted(Exception):
    def __init__(self, signum: int) -> None:
        super().__init__(signum)
        self.signum = signum


def interrupted(signum: int, _frame: FrameType | None) -> None:
    raise Interrupted(signum)


def read_request(directory: int, name: str) -> object:
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with os.fdopen(descriptor, "rb") as request:
        if not stat.S_ISREG(os.fstat(request.fileno()).st_mode):
            raise ValueError("Request must be a regular file")
        data = request.read(1025)
        if len(data) > 1024:
            raise ValueError("Request exceeds 1 KiB")
    return json.loads(data)


def write_response(directory: int, name: str, code: int) -> None:
    temporary = f"{uuid4()}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=directory,
    )
    try:
        with os.fdopen(descriptor, "w") as response:
            response.write(json.dumps({"exit_code": code}) + "\n")
        os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass


def main() -> int:
    artifacts = Path(os.environ["PAGODA_WORKER_TEST_DIR"])
    control = artifacts / "control"
    control.mkdir(exist_ok=True)
    compose = [
        "docker",
        "compose",
        "--env-file",
        "/dev/null",
        "-p",
        os.environ["PAGODA_WORKER_COMPOSE_PROJECT"],
        "-f",
        os.environ["PAGODA_WORKER_COMPOSE_FILE"],
    ]
    target = sys.argv[1] if len(sys.argv) > 1 else "tools.celery_worker.test_worker"
    command = [
        *compose,
        "run",
        "--rm",
        "--no-deps",
        "-T",
        "runner",
        "bash",
        "-c",
        "set -euo pipefail; "
        "python manage.py makemigrations --noinput 2>&1 | tee /artifacts/migrations.log; "
        "python manage.py migrate --noinput 2>&1 | tee -a /artifacts/migrations.log; "
        'python -m unittest -v "$1"',
        "worker-tests",
        target,
    ]
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    process: subprocess.Popen[bytes] | None = None
    directory = os.open(control, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        # Hold host-created handles before the runner can write to the shared mount.
        with (artifacts / "control.log").open("a") as log:
            process = subprocess.Popen(command)
            while process.poll() is None:
                for request in sorted(os.listdir(directory)):
                    if not re.fullmatch(r"[0-9a-fA-F-]{36}\.request", request):
                        continue
                    response = request.removesuffix(".request") + ".response"
                    try:
                        os.stat(response, dir_fd=directory, follow_symlinks=False)
                    except FileNotFoundError:
                        pass
                    else:
                        continue
                    code = 2
                    try:
                        payload = read_request(directory, request)
                        action = payload.get("action") if isinstance(payload, dict) else None
                        if action not in {"stop_app", "start_app"}:
                            log.write(f"Rejected action in {request}\n")
                        else:
                            log.write(f"{request}: rabbitmqctl {action}\n")
                            log.flush()
                            result = subprocess.run(
                                [*compose, "exec", "-T", "rabbitmq", "rabbitmqctl", action],
                                stdout=log,
                                stderr=subprocess.STDOUT,
                                timeout=60,
                            )
                            code = result.returncode
                    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
                        log.write(f"{request}: {type(error).__name__}\n")
                        code = 1
                    log.flush()
                    write_response(directory, response, code)
                time.sleep(0.1)
        return process.wait()
    except Interrupted as error:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        # The launcher's compose down also removes the container and all workers.
        return 128 + error.signum
    finally:
        os.close(directory)


if __name__ == "__main__":
    sys.exit(main())
