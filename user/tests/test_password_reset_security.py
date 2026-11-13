from smtplib import SMTPException
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from user.forms import UsernameBasedPasswordResetForm
from user.models import User


class PasswordResetSecurityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            {"username": "local-user", "email": "local@example.com", "password": "old-password"}
        )

    def _requests(self, username):
        return (
            self.client.post(
                "/user/api/v2/password_reset",
                {"username": username},
                content_type="application/json",
            ),
            self.client.post(reverse("user:password_reset"), {"username": username}),
        )

    def _assert_generic_response(self, responses, username):
        api, legacy = responses
        self.assertEqual(api.status_code, 200)
        self.assertEqual(api.json(), {"username": username})
        self.assertRedirects(
            legacy, reverse("user:password_reset_done"), fetch_redirect_response=False
        )

    def _confirm_params(self):
        return {
            "uidb64": urlsafe_base64_encode(force_bytes(self.user.pk)),
            "token": default_token_generator.make_token(self.user),
            "password1": "new-secure-password-123",
            "password2": "new-secure-password-123",
        }

    def _make_ineligible(self, condition):
        if condition == "inactive":
            self.user.is_active = False
        elif condition == "ldap":
            self.user.authenticate_type = User.AuthenticateType.AUTH_TYPE_LDAP
        elif condition == "empty":
            self.user.password = ""
        elif condition == "unusable":
            self.user.set_unusable_password()
        elif condition == "no-email":
            self.user.email = ""
        self.user.save()

    def test_eligible_local_account_receives_reset_mail_from_both_routes(self):
        self._assert_generic_response(self._requests(self.user.username.upper()), "LOCAL-USER")
        self.assertEqual(len(mail.outbox), 2)
        for message in mail.outbox:
            self.assertEqual(message.to, [self.user.email])
            self.assertIn(self._confirm_params()["uidb64"], message.body)

    def test_unknown_account_has_the_same_response_without_mail(self):
        self._assert_generic_response(self._requests("unknown"), "unknown")
        self.assertEqual(len(mail.outbox), 0)

    def test_mail_transport_failure_does_not_disclose_recipient(self):
        for failure in (SMTPException("transport unavailable"), OSError("connection failed")):
            with self.subTest(failure=type(failure).__name__):
                with (
                    patch("django.core.mail.EmailMultiAlternatives.send", side_effect=failure),
                    self.assertLogs("user.password_reset", level="ERROR") as logs,
                ):
                    self._assert_generic_response(
                        self._requests(self.user.username), self.user.username
                    )
                self.assertEqual(len(logs.records), 2)

    def test_ineligible_accounts_have_the_same_response_without_mail(self):
        for condition in ("inactive", "ldap", "empty", "unusable", "no-email"):
            with self.subTest(condition=condition):
                self._make_ineligible(condition)
                password = self.user.password
                self._assert_generic_response(
                    self._requests(self.user.username), self.user.username
                )
                self.assertEqual(len(mail.outbox), 0)
                self.user.refresh_from_db()
                self.assertEqual(self.user.password, password)
                # Restore eligibility so every condition is exercised independently.
                self.user.is_active = True
                self.user.authenticate_type = User.AuthenticateType.AUTH_TYPE_LOCAL
                self.user.email = "local@example.com"
                self.user.set_password("old-password")
                self.user.save()

    def test_disabled_requests_do_not_send_mail_even_when_form_is_used_directly(self):
        with patch.dict(settings.AIRONE, PASSWORD_RESET_DISABLED=True):
            self._assert_generic_response(self._requests(self.user.username), self.user.username)
            self._assert_generic_response(self._requests("unknown"), "unknown")
            form = UsernameBasedPasswordResetForm({"username": self.user.username})
            self.assertTrue(form.is_valid())
            form.save(domain_override="example.com")
        self.assertEqual(len(mail.outbox), 0)

    def test_api_confirm_rejects_disabled_reset_with_previously_issued_token(self):
        params = self._confirm_params()
        old_password = self.user.password
        with patch.dict(settings.AIRONE, PASSWORD_RESET_DISABLED=True):
            response = self.client.post(
                "/user/api/v2/password_reset/confirm", params, content_type="application/json"
            )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, old_password)

    def test_both_confirm_routes_reject_ineligible_accounts_with_valid_tokens(self):
        for condition in ("inactive", "ldap", "empty", "unusable"):
            with self.subTest(condition=condition):
                self._make_ineligible(condition)
                params = self._confirm_params()
                old_password = self.user.password
                response = self.client.post(
                    "/user/api/v2/password_reset/confirm", params, content_type="application/json"
                )
                self.assertEqual(response.status_code, 400)
                url = reverse(
                    "user:password_reset_confirm",
                    kwargs={key: params[key] for key in ("uidb64", "token")},
                )
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.context["validlink"])
                self.user.refresh_from_db()
                self.assertEqual(self.user.password, old_password)
                self.user.is_active = True
                self.user.authenticate_type = User.AuthenticateType.AUTH_TYPE_LOCAL
                self.user.set_password("old-password")
                self.user.save()

    def test_legacy_confirm_rechecks_policy_after_opening_link(self):
        params = self._confirm_params()
        url = reverse(
            "user:password_reset_confirm",
            kwargs={key: params[key] for key in ("uidb64", "token")},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        form_url = response.url
        old_password = self.user.password
        with patch.dict(settings.AIRONE, PASSWORD_RESET_DISABLED=True):
            response = self.client.post(
                form_url,
                {"new_password1": params["password1"], "new_password2": params["password2"]},
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["validlink"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, old_password)

    def test_both_confirm_routes_reject_ldap_switch_after_token_issuance(self):
        params = self._confirm_params()
        url = reverse(
            "user:password_reset_confirm",
            kwargs={key: params[key] for key in ("uidb64", "token")},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        form_url = response.url
        old_password = self.user.password
        self._make_ineligible("ldap")
        response = self.client.post(
            form_url,
            {"new_password1": params["password1"], "new_password2": params["password2"]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["validlink"])
        response = self.client.post(
            "/user/api/v2/password_reset/confirm", params, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, old_password)

    def test_legacy_local_confirm_succeeds_and_token_cannot_be_reused(self):
        params = self._confirm_params()
        url = reverse(
            "user:password_reset_confirm",
            kwargs={key: params[key] for key in ("uidb64", "token")},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            response.url,
            {"new_password1": params["password1"], "new_password2": params["password2"]},
        )
        self.assertRedirects(
            response, reverse("user:password_reset_complete"), fetch_redirect_response=False
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(params["password1"]))
        response = self.client.get(url)
        self.assertFalse(response.context["validlink"])
