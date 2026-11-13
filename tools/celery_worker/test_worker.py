"""Real AMQP/prefork/MySQL scenarios. Run through tools/test_celery_worker.sh."""

import atexit
import csv
import io
import json
import os
import platform
import signal
import subprocess
import sys
import time
import unittest
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from django.core.files.storage import default_storage
from django.db import connection, transaction
from django.utils import timezone
from kombu.exceptions import OperationalError

from airone.celery import app
from group.models import Group
from job.api_v2.serializers import JobSerializers
from job.models import Job, JobStatus
from user.models import User

if os.environ.get("PAGODA_WORKER_TEST") != "1":
    raise unittest.SkipTest("Run real-worker scenarios with tools/test_celery_worker.sh")

ROOT = Path(os.environ["PAGODA_WORKER_TEST_DIR"])
EVENTS = ROOT / "events"
EVENTS.mkdir(exist_ok=True)
WORKERS: list[subprocess.Popen[bytes]] = []


def wait_for(predicate: Callable[[], Any], description: str, timeout: float = 45) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for {description}; see {ROOT}")


def events(kind: str, key: object) -> list[dict[str, Any]]:
    return [json.loads(p.read_text()) for p in EVENTS.glob(f"{kind}-{key}-*.json")]


def stop_worker(worker: subprocess.Popen[bytes]) -> None:
    # Kill the complete owned process group even if its parent has exited.
    try:
        os.killpg(worker.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    worker.wait(timeout=10)


def cleanup_workers() -> None:
    for worker in WORKERS:
        stop_worker(worker)


def interrupted(signum: int, frame: Any) -> None:
    raise SystemExit(128 + signum)


atexit.register(cleanup_workers)
signal.signal(signal.SIGTERM, interrupted)


class WorkerFaultTests(unittest.TestCase):
    worker: subprocess.Popen[bytes]
    worker_log: Path
    worker_generation: str

    @classmethod
    def start_worker(cls) -> None:
        cls.worker_generation = uuid4().hex
        cls.worker_log = ROOT / f"worker-{cls.worker_generation}.log"
        with cls.worker_log.open("wb") as output:
            cls.worker = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "celery",
                    "-A",
                    "airone",
                    "worker",
                    "--pool=prefork",
                    "--concurrency=2",
                    "--loglevel=INFO",
                    "--without-gossip",
                    "--without-mingle",
                    "--hostname=fault-test@%h",
                    "--queues=worker-fault-tests",
                    "--include=tools.celery_worker.probes",
                ],
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env={**os.environ, "PAGODA_WORKER_GENERATION": cls.worker_generation},
            )
        WORKERS.append(cls.worker)

        def ready() -> bool:
            if cls.worker.poll() is not None:
                raise AssertionError(f"Worker exited at startup; see {cls.worker_log}")
            return bool(events("worker", cls.worker.pid))

        wait_for(ready, "worker ready")

        def initialized_children() -> set[int]:
            ready()
            return {
                item["pid"]
                for item in events("child-init", cls.worker_generation)
                if item["parent_pid"] == cls.worker.pid
            }

        child_pids = wait_for(
            lambda: (pids if len(pids := initialized_children()) == 2 else None),
            "both prefork children initialized",
        )
        fences = [
            app.send_task("tools.celery_worker.fence", args=[cls.worker_generation])
            for _ in range(2)
        ]
        for fence in fences:
            outcome = wait_for(lambda: events("finished", fence.id), "startup fence roundtrip")
            if outcome[0]["state"] != "SUCCESS":
                raise AssertionError(f"Startup fence failed: {outcome}")
        fence_pids = {item["pid"] for item in events("startup-fence", cls.worker_generation)}
        if fence_pids != child_pids:
            raise AssertionError(f"Startup fence PIDs {fence_pids} differ from {child_pids}")
        (ROOT / f"startup-{cls.worker_generation}.json").write_text(
            json.dumps(
                {
                    "generation": cls.worker_generation,
                    "parent_pid": cls.worker.pid,
                    "initialized_child_pids": sorted(child_pids),
                    "fence_child_pids": sorted(fence_pids),
                    "fence_task_ids": [fence.id for fence in fences],
                },
                indent=2,
            )
        )

    @classmethod
    def setUpClass(cls) -> None:
        if os.environ.get("PAGODA_WORKER_TEST") != "1" or connection.vendor != "mysql":
            raise RuntimeError("Disposable real MySQL and RabbitMQ are required")
        if app.conf.task_always_eager or not app.conf.broker_url.startswith("amqp://"):
            raise RuntimeError("The lane must use real AMQP delivery")
        (ROOT / "media").mkdir(exist_ok=True)
        cls.start_worker()
        (ROOT / "runtime.json").write_text(
            json.dumps(
                {
                    "python": sys.version,
                    "system": platform.system(),
                    "machine": platform.machine(),
                    "database_vendor": connection.vendor,
                    "pool": "prefork",
                    "concurrency": 2,
                    "task_acks_late": app.conf.task_acks_late,
                    "task_reject_on_worker_lost": app.conf.task_reject_on_worker_lost,
                },
                indent=2,
            )
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cleanup_workers()
        connection.close()

    def setUp(self) -> None:
        self.prefix = uuid4().hex[:12]
        self.user = User.objects.create(username=f"owner-{self.prefix}", is_superuser=True)
        self.export_sources: dict[int, int] = {}

    def observe(self, **facts: Any) -> None:
        with (ROOT / "observations.jsonl").open("a") as output:
            output.write(json.dumps({"test": self.id(), **facts}) + "\n")

    def make_job(self, kind: str) -> Job:
        if kind == "export":
            source = Job.new_import_general_v2(self.user, "group", [])
            source.update(JobStatus.DONE, text="export-fixture")
            exported = Job.new_export_job_history(self.user, {})
            self.export_sources[exported.pk] = source.pk
            return exported
        data: list[dict[str, Any]]
        if kind == "user":
            data = [
                {"username": f"import-{self.prefix}", "email": "worker@example.test", "groups": ""}
            ]
        else:
            data = [{"name": f"group-{self.prefix}"}]
        return Job.new_import_general_v2(self.user, kind, data)

    def completed(self, task_id: str) -> None:
        outcome = wait_for(lambda: events("finished", task_id), f"task {task_id} completion")
        self.assertEqual(outcome[0]["state"], "SUCCESS", outcome)

    def done(self, job: Job) -> None:
        def finished() -> bool:
            job.refresh_from_db()
            return job.status in (JobStatus.DONE, JobStatus.ERROR)

        wait_for(finished, f"Job {job.pk} completion")
        self.assertEqual(job.status, JobStatus.DONE, job.text)

    def fence(self) -> None:
        result = app.send_task("tools.celery_worker.fence")
        self.completed(result.id)

    def configure_gate(self, job: Job, stage: str) -> None:
        (EVENTS / f"gate-{job.pk}.txt").write_text(stage)

    def release(self, job: Job) -> None:
        (EVENTS / f"release-{job.pk}").touch()

    def assert_effect(self, kind: str, job: Job) -> None:
        if kind == "user":
            imported = User.objects.get(username=f"import-{self.prefix}")
            self.assertEqual(imported.email, "worker@example.test")
        elif kind == "group":
            self.assertTrue(Group.objects.filter(name=f"group-{self.prefix}").exists())
        else:
            with default_storage.open(job.text, "rb") as artifact:
                rows = list(csv.reader(io.StringIO(artifact.read().decode("utf-8-sig"))))
            self.assertEqual(rows[0][0], "job_id")
            self.assertNotIn(str(job.pk), [row[0] for row in rows[1:]])
            source = [row for row in rows[1:] if row[0] == str(self.export_sources[job.pk])]
            self.assertEqual(len(source), 1)
            self.assertEqual(source[0][1], self.user.username)
            self.assertEqual(source[0][4:6], ["DONE", "IMPORT_GENERAL_V2"])
            self.assertEqual(source[0][-1], "export-fixture")

    def test_concurrent_duplicate_and_replay(self) -> None:
        for kind in ("user", "group", "export"):
            with self.subTest(kind=kind):
                job = self.make_job(kind)
                self.configure_gate(job, "duplicate")
                first, second = job.run(), job.run()
                self.completed(first.id)
                self.completed(second.id)
                self.done(job)
                arrivals = events("ready", job.pk)
                self.assertEqual(len({item["pid"] for item in arrivals}), 2)
                self.assertEqual(len(events("body", job.pk)), 1)
                self.assert_effect(kind, job)
                self.completed(job.run().id)
                self.assertEqual(len(events("body", job.pk)), 1)
                self.observe(
                    operation=kind, competing_processes=2, executions=1, replay_skipped=True
                )

    def test_commit_and_rollback(self) -> None:
        with transaction.atomic():
            job = self.make_job("user")
            self.assertIsNone(job.run())
            self.fence()
            self.assertEqual(events("received", job.pk), [])
            self.assertFalse(User.objects.filter(username=f"import-{self.prefix}").exists())
        self.done(job)
        self.assert_effect("user", job)

        with self.assertRaisesRegex(RuntimeError, "rollback"), transaction.atomic():
            rolled_back = self.make_job("group")
            rolled_back.run()
            self.fence()
            self.assertEqual(events("received", rolled_back.pk), [])
            raise RuntimeError("rollback")
        self.fence()
        self.assertFalse(Job.objects.filter(pk=rolled_back.pk).exists())
        self.assertEqual(events("received", rolled_back.pk), [])
        self.assertFalse(Group.objects.filter(name=f"group-{self.prefix}").exists())
        self.observe(commit_completed=True, rollback_not_published=True)

    def test_warm_shutdown(self) -> None:
        job = self.make_job("export")
        self.configure_gate(job, "after_body")
        result = job.run()
        wait_for(lambda: events("held", job.pk), "export held before DONE")
        self.worker.send_signal(signal.SIGTERM)
        try:
            wait_for(lambda: "Warm shutdown" in self.worker_log.read_text(), "warm shutdown")
            self.assertIsNone(self.worker.poll())
        finally:
            self.release(job)
        self.worker.wait(timeout=45)
        self.assertEqual(self.worker.returncode, 0)
        self.completed(result.id)
        self.done(job)
        self.assert_effect("export", job)
        self.observe(warm_shutdown_completed=True)
        self.start_worker()

    def kill_held_child(self, job: Job) -> None:
        marker = wait_for(lambda: events("held", job.pk), "task held at fault boundary")[0]
        # A request/reply to the parent confirms it has processed acceptance
        # (including the early ack) before the child is killed.
        active = app.control.inspect(timeout=5).active()
        self.assertTrue(active)
        assert active is not None
        self.assertIn(
            marker["pid"], [task["worker_pid"] for tasks in active.values() for task in tasks]
        )
        log_offset = len(self.worker_log.read_text())
        os.kill(marker["pid"], signal.SIGKILL)
        wait_for(
            lambda: "WorkerLostError" in self.worker_log.read_text()[log_offset:],
            "child loss recorded",
        )
        self.fence()
        self.assertIsNone(self.worker.poll())
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.PROCESSING)
        self.assertEqual(len(events("received", job.pk)), 1)
        self.completed(job.run().id)
        self.assertEqual(len(events("body", job.pk)), 1)
        # Exercise the actual API representation, without waiting a day.
        Job.objects.filter(pk=job.pk).update(
            updated_at=timezone.now() - timedelta(seconds=Job._get_job_timeout() + 1)
        )
        job.refresh_from_db()
        self.assertEqual(JobSerializers(job).data["status"], JobStatus.TIMEOUT)
        self.assertEqual(job.status, JobStatus.PROCESSING)
        self.observe(
            killed_child=marker["pid"],
            database_status="PROCESSING",
            api_status="TIMEOUT",
            automatic_recovery=False,
        )

    def test_killed_child_leaves_partial_import_visible(self) -> None:
        first = User.objects.create(username=f"first-{self.prefix}", email="old@example.test")
        second = User.objects.create(username=f"second-{self.prefix}", email="old@example.test")
        data = [
            {"username": item.username, "email": "new@example.test", "groups": ""}
            for item in (first, second)
        ]
        job = Job.new_import_general_v2(self.user, "user", data)
        self.configure_gate(job, "partial_import")
        job.run()
        self.kill_held_child(job)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.email, "new@example.test")
        self.assertEqual(second.email, "old@example.test")

    def test_killed_export_after_write_is_not_replayed(self) -> None:
        job = self.make_job("export")
        self.configure_gate(job, "after_body")
        job.run()
        self.kill_held_child(job)
        self.assert_effect("export", job)

    def test_broker_outage_surfaces_publish_failure(self) -> None:
        def broker_action(action: str) -> None:
            # The host controller only accepts stop_app/start_app and operates
            # on this invocation's broker. No Docker socket enters the runner.
            directory = ROOT / "control"
            directory.mkdir(exist_ok=True)
            request = directory / str(uuid4())
            request.with_suffix(".tmp").write_text(json.dumps({"action": action}))
            request.with_suffix(".tmp").replace(request.with_suffix(".request"))
            response = request.with_suffix(".response")
            wait_for(response.exists, f"broker {action}", timeout=120)
            self.assertEqual(json.loads(response.read_text())["exit_code"], 0)

        job = self.make_job("group")
        try:
            broker_action("stop_app")
            with self.assertRaises(OperationalError):
                with transaction.atomic():
                    job.run()
            job.refresh_from_db()
            self.assertEqual(job.status, JobStatus.PREPARING)
            self.assertEqual(events("body", job.pk), [])
        finally:
            broker_action("start_app")

        def broker_ready() -> bool:
            try:
                with app.connection_for_write() as broker:
                    broker.ensure_connection(max_retries=0)
                return True
            except OperationalError:
                return False

        wait_for(broker_ready, "AMQP listener restored")
        # Explicit retry only: there is currently no transactional outbox.
        self.completed(job.run().id)
        self.done(job)
        self.assert_effect("group", job)
        self.observe(publish_error_visible=True, committed_job_retained=True, manual_retry=True)
