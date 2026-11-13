from unittest import mock

from django.db import transaction
from django.http import HttpResponse
from django.test import Client, TestCase

from airone.lib.test import CommitCallbacksClient


class CommitCallbacksClientTest(TestCase):
    client_class = CommitCallbacksClient

    def request_with(self, handler):
        with mock.patch.object(Client, "request", side_effect=handler):
            return self.client.get("/")

    def test_request_callbacks_execute_once_under_outer_capture(self):
        callback = mock.Mock()

        def handler(**request):
            with transaction.atomic():
                transaction.on_commit(callback)
                callback.assert_not_called()
            return HttpResponse()

        with self.captureOnCommitCallbacks(execute=True):
            self.request_with(handler)
            callback.assert_called_once_with()
        callback.assert_called_once_with()

    def test_nested_callbacks_are_drained_but_previous_callbacks_are_untouched(self):
        previous = mock.Mock()
        nested = mock.Mock()
        transaction.on_commit(previous)

        def handler(**request):
            transaction.on_commit(lambda: transaction.on_commit(nested))
            return HttpResponse()

        self.request_with(handler)
        previous.assert_not_called()
        nested.assert_called_once_with()

    def test_rolled_back_request_callbacks_are_discarded(self):
        callback = mock.Mock()

        def handler(**request):
            try:
                with transaction.atomic():
                    transaction.on_commit(callback)
                    raise ValueError("rollback")
            except ValueError:
                return HttpResponse(status=400)

        self.assertEqual(self.request_with(handler).status_code, 400)
        callback.assert_not_called()

    def test_explicit_outer_transaction_retains_rollback_behavior(self):
        callback = mock.Mock()

        def handler(**request):
            transaction.on_commit(callback)
            return HttpResponse()

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(ValueError), transaction.atomic():
                self.request_with(handler)
                callback.assert_not_called()
                raise ValueError("rollback")
        callback.assert_not_called()
