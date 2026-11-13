"""Test-only barriers around real Job execution, loaded explicitly by the worker."""

import json
import os
import time
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch
from uuid import uuid4

from celery import current_task
from celery.signals import task_postrun, task_prerun, worker_process_init, worker_ready

from airone.celery import app
from airone.lib import job as job_module
from job import tasks as job_tasks
from job.models import Job, TaskHandler
from user.import_service import import_users

if os.environ.get("PAGODA_WORKER_TEST") != "1":
    raise RuntimeError("Fault probes must never be loaded outside the test lane")

ROOT = Path(os.environ["PAGODA_WORKER_TEST_DIR"]) / "events"
ROOT.mkdir(parents=True, exist_ok=True)
GENERATION = os.environ["PAGODA_WORKER_GENERATION"]
original_ready = Job.proceed_if_ready
original_handle = job_module._handle_task


def record(kind: str, key: object, **data: Any) -> None:
    destination = ROOT / f"{kind}-{key}-{uuid4().hex}.json"
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps({"pid": os.getpid(), **data}))
    temporary.replace(destination)


def wait_for(predicate: Callable[[], bool], description: str) -> None:
    deadline = time.monotonic() + 45
    while not predicate():
        if time.monotonic() > deadline:
            raise TimeoutError(description)
        time.sleep(0.05)


def gate(job: Job) -> str:
    path = ROOT / f"gate-{job.pk}.txt"
    return path.read_text() if path.exists() else ""


def readiness_barrier(job: Job) -> bool:
    ready = original_ready(job)
    if ready and gate(job) == "duplicate":
        record("ready", job.pk)
        wait_for(lambda: len(list(ROOT.glob(f"ready-{job.pk}-*.json"))) == 2, "two readers")
    return ready


def audited_handle(
    kls: object,
    func: TaskHandler,
    job: Job,
    on_cancelled: Callable[[Job], None] | None = None,
) -> None:
    def body(task: Any, claimed: Job) -> Any:
        record("body", claimed.pk, task_id=current_task.request.id)
        result = func(task, claimed)
        if gate(claimed) == "after_body":
            record("held", claimed.pk)
            wait_for(lambda: (ROOT / f"release-{claimed.pk}").exists(), "release after body")
        return result

    original_handle(kls, body, job, on_cancelled)


# Gate after the first *real* user import has committed, before the second.
# Splitting the list only changes scheduling; production import_users already
# loops over records without an encompassing transaction.
original_import_users = import_users


def interrupted_import_users(data: list[dict[str, Any]]) -> None:
    args = current_task.request.args
    assert args is not None
    job_id = args[0]
    path = ROOT / f"gate-{job_id}.txt"
    if path.exists() and path.read_text() == "partial_import":
        original_import_users(data[:1])
        record("held", job_id)
        wait_for(lambda: (ROOT / f"release-{job_id}").exists(), "release partial import")
        original_import_users(data[1:])
    else:
        original_import_users(data)


@task_postrun.connect
def task_completed(task_id: str, state: str, **kwargs: Any) -> None:
    record("finished", task_id, state=state)


@task_prerun.connect
def task_received(task_id: str, args: list[Any], **kwargs: Any) -> None:
    if args:
        record("received", args[0], task_id=task_id)


@app.task(name="tools.celery_worker.fence")
def fence(startup_generation: str | None = None) -> None:
    """Prove consumption; startup fences require both initialized pool children."""
    if startup_generation is not None:
        if startup_generation != GENERATION:
            raise RuntimeError("Startup fence reached a different worker generation")
        record("startup-fence", GENERATION, task_id=current_task.request.id)
        wait_for(
            lambda: len(
                {
                    json.loads(path.read_text())["pid"]
                    for path in ROOT.glob(f"startup-fence-{GENERATION}-*.json")
                }
            )
            == 2,
            "startup fence execution in both children",
        )


@worker_process_init.connect
def initialized_child(**kwargs: Any) -> None:
    record("child-init", GENERATION, parent_pid=os.getppid())


@worker_ready.connect
def ready_worker(**kwargs: Any) -> None:
    record("worker", os.getpid())


patch.object(Job, "proceed_if_ready", readiness_barrier).start()
patch.object(job_module, "_handle_task", audited_handle).start()
# The decorated function's globals are in airone.lib.job, so patch the actual
# task module rather than replacing the Celery task or its delivery path.
patch.object(job_tasks, "import_users", interrupted_import_users).start()
