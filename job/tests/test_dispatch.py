from unittest import mock

from django.db import transaction
from django.test import TestCase, TransactionTestCase

from airone.lib.job import _handle_task
from job.models import Job, JobOperation, JobStatus
from user.models import User


class JobDispatchTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="dispatch-user")
        self.job = Job.new_export_job_history(self.user, {})
        self.task = mock.Mock()
        patcher = mock.patch.object(
            Job, "method_table", return_value={self.job.operation: self.task}
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_dispatch_waits_for_commit(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with transaction.atomic():
                self.assertIsNone(self.job.run())
                self.task.delay.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        self.task.delay.assert_called_once_with(self.job.id)

    def test_rollback_discards_dispatch(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with self.assertRaises(RuntimeError), transaction.atomic():
                self.job.run()
                raise RuntimeError("rollback")
        self.assertEqual(callbacks, [])
        self.task.delay.assert_not_called()

    def test_dispatch_uses_write_transaction_for_replica_loaded_job(self):
        self.job._state.db = "replica"
        with (
            mock.patch("job.models.router.db_for_write", return_value="default"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.assertIsNone(self.job.run())
            self.task.delay.assert_not_called()
        self.task.delay.assert_called_once_with(self.job.id)

    def test_sync_dispatch_runs_immediately_inside_transaction(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with transaction.atomic():
                self.assertIs(self.job.run(will_delay=False), self.task.return_value)
                self.task.assert_called_once_with(self.job.id)
        self.assertEqual(callbacks, [])
        self.task.delay.assert_not_called()


class JobAutocommitDispatchTest(TransactionTestCase):
    def test_autocommit_returns_async_result(self):
        user = User.objects.create(username="autocommit-dispatch-user")
        job = Job.new_export_job_history(user, {})
        task = mock.Mock()
        with mock.patch.object(Job, "method_table", return_value={job.operation: task}):
            self.assertIs(job.run(), task.delay.return_value)
        task.delay.assert_called_once_with(job.id)

    def test_outer_commit_dispatches_after_inner_commit(self):
        user = User.objects.create(username="commit-dispatch-user")
        task = mock.Mock()
        with mock.patch.object(
            Job, "method_table", return_value={JobOperation.EXPORT_JOB_HISTORY: task}
        ):
            with transaction.atomic():
                with transaction.atomic():
                    job = Job.new_export_job_history(user, {})
                    self.assertIsNone(job.run())
                task.delay.assert_not_called()
            task.delay.assert_called_once_with(job.id)


class JobClaimTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="claim-user")
        self.job = Job.new_export_job_history(self.user, {})

    def test_two_ready_stale_copies_only_claim_once(self):
        other = Job.objects.get(pk=self.job.pk)
        # Both workers have passed readiness before either attempts the update.
        self.assertTrue(self.job.proceed_if_ready())
        self.assertTrue(other.proceed_if_ready())
        with mock.patch.object(Job, "proceed_if_ready", return_value=True):
            self.assertTrue(self.job.claim_for_processing())
            self.assertFalse(other.claim_for_processing())
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.PROCESSING)
        self.assertEqual(other.status, JobStatus.PROCESSING)

    def test_claim_uses_write_router_for_replica_loaded_job(self):
        self.job._state.db = "replica"
        with (
            mock.patch.object(self.job, "proceed_if_ready", return_value=True),
            mock.patch("job.models.router.db_for_write", return_value="default"),
        ):
            self.assertTrue(self.job.claim_for_processing())
        self.assertEqual(Job.objects.get(pk=self.job.pk).status, JobStatus.PROCESSING)

    def test_cancellation_between_readiness_and_claim_is_preserved(self):
        def cancel():
            Job.objects.filter(pk=self.job.pk).update(status=JobStatus.CANCELED)
            return True

        with mock.patch.object(self.job, "proceed_if_ready", side_effect=cancel):
            self.assertFalse(self.job.claim_for_processing())
        self.assertEqual(self.job.status, JobStatus.CANCELED)

    def test_terminal_and_processing_jobs_are_not_claimed(self):
        for status in JobStatus:
            if status == JobStatus.PREPARING:
                continue
            with self.subTest(status=status):
                Job.objects.filter(pk=self.job.pk).update(status=status)
                self.assertFalse(self.job.claim_for_processing())
                self.job.refresh_from_db()
                self.assertEqual(self.job.status, status)

    def test_handler_is_not_called_for_duplicate_delivery(self):
        other = Job.objects.get(pk=self.job.pk)
        handler = mock.Mock(return_value=JobStatus.DONE)
        _handle_task(object(), handler, self.job)
        _handle_task(object(), handler, other)
        handler.assert_called_once()

    def test_canceled_handler_is_still_called(self):
        self.job.update(JobStatus.CANCELED)
        handler = mock.Mock()
        on_cancelled = mock.Mock()
        _handle_task(object(), handler, self.job, on_cancelled)
        handler.assert_not_called()
        on_cancelled.assert_called_once_with(self.job)

    def test_unfinished_dependency_reschedules_without_claiming(self):
        dependency = Job.new_export_job_history(self.user, {})
        self.job.dependent_job = dependency
        self.job.operation = JobOperation.EDIT_ENTITY
        self.job.params = '{"name":"entity","note":"","is_toplevel":false,"attrs":[]}'
        self.job.save()
        with mock.patch.object(Job, "run") as run, mock.patch("job.models.time.sleep"):
            self.assertFalse(self.job.claim_for_processing())
        run.assert_called_once_with()
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.PREPARING)
