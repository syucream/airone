from unittest.mock import Mock

from django.core import mail
from django.test import RequestFactory

from airone.lib.test import AironeViewTest
from airone.middleware.log import LoggingRequestMiddleware


class AirOneLogTest(AironeViewTest):
    def test_logging_request_middleware(self):
        user = self.guest_login()
        request = RequestFactory().get("/test/")
        request.user = user

        for status_code, level in [(200, "INFO"), (400, "WARNING"), (500, "ERROR")]:

            def get_response(request):
                return Mock(status_code=status_code)

            with self.assertLogs("airone") as log:
                middleware = LoggingRequestMiddleware(get_response)
                middleware(request)

            self.assertEqual(len(log.output), 1)
            self.assertRegex(
                log.output[0],
                rf"{level}:airone:\(Profiling result: 0.[0-9]+s\) \(user-id: {user.id}\) "
                rf"GET /test/ {status_code}$",
            )

    def test_logging_request_middleware_without_user(self):
        request = RequestFactory().get("/test/")

        def get_response(request):
            return Mock(status_code=200)

        with self.assertLogs("airone") as log:
            middleware = LoggingRequestMiddleware(get_response)
            middleware(request)

        self.assertEqual(len(log.output), 1)
        self.assertRegex(
            log.output[0],
            rf"INFO:airone:\(Profiling result: 0.[0-9]+s\) \(user-id: {None}\) GET /test/ {200}$",
        )

    def test_logging_request_middleware_with_exception(self):
        user = self.guest_login()
        path = "/test/"
        request = RequestFactory().get(path)
        request.user = user
        exception = Mock(side_effect=Exception("MockException"))
        admins = [("admin", "airone@example.com")]

        with self.settings(ADMINS=admins, EMAIL_SUBJECT_PREFIX=""):
            middleware = LoggingRequestMiddleware(Mock())
            resp = middleware.process_exception(request, exception)

            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(mail.outbox[0].to, [a[1] for a in admins])
            self.assertEqual(mail.outbox[0].subject, f"ERROR Django Request {path}")
            self.assertEqual(resp.status_code, 500)
            self.assertEqual(resp.content.decode("utf-8"), "Internal Server Error")
