"""Password, authentication, and API token tests."""

import json
from unittest import mock
from unittest.mock import Mock, patch

from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.authtoken.models import Token

from airone.lib.test import AironeViewTest, with_airone_settings
from user.models import User
from user.tests.helpers import UserFixtureMixin


class UserAuthenticationAPITest(UserFixtureMixin, AironeViewTest):
    def test_update_co_user_token_lifetime_by_parent_user(self):
        parent_user = self.guest_login()
        co_user = self._create_user("co_user", parent_user=parent_user)
        Token.objects.create(user=co_user)

        resp = self.client.put(
            "/user/api/v2/%d/" % co_user.id,
            json.dumps(
                {
                    "username": co_user.username,
                    "email": co_user.email,
                    "is_superuser": co_user.is_superuser,
                    "token_lifetime": 3600,
                }
            ),
            "application/json",
        )

        self.assertEqual(resp.status_code, 200)
        co_user.refresh_from_db()
        self.assertEqual(co_user.token_lifetime, 3600)

    def test_get_user_token_via_apiv2_without_creation(self):
        self.guest_login()

        resp = self.client.get("/user/api/v2/token/")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(
            resp.json(), {"message": "No Token matches the given query.", "code": "AE-230000"}
        )

    def test_get_user_token_via_apiv2(self):
        user = self.guest_login()
        token = Token.objects.create(user=user)

        resp = self.client.get("/user/api/v2/token/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"key": str(token)})

    def test_refresh_user_token_via_apiv2(self):
        user = self.guest_login()

        resp = self.client.post("/user/api/v2/token/")
        self.assertEqual(resp.status_code, 200)

        # get user token to compare with response data
        token = Token.objects.get(user=user)
        self.assertEqual(resp.json(), {"key": str(token)})

    @mock.patch("user.api_v2.views.EmailMultiAlternatives")
    def test_password_reset(self, mock_email):
        user = self._create_user("user")

        params = {
            "username": user.username,
        }
        resp = self.client.post(
            "/user/api/v2/password_reset", json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 200)

        mock_email.assert_called_once()

    def test_password_reset_with_unknown_user(self):
        params = {
            "username": "unknown",
        }
        resp = self.client.post(
            "/user/api/v2/password_reset", json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_password_reset_confirm(self):
        user = self._create_user("user")
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        password = "new-password"
        params = {
            "uidb64": uidb64,
            "token": token,
            "password1": password,
            "password2": password,
        }
        resp = self.client.post(
            "/user/api/v2/password_reset/confirm", json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 200)

        updated_user = User.objects.filter(id=user.id).first()
        self.assertIsNotNone(updated_user)
        self.assertTrue(updated_user.check_password(password))

    def test_password_reset_confirm_with_invalid_user(self):
        user = self._create_user("user")
        token = default_token_generator.make_token(user)

        password = "new-password"
        params = {
            "uidb64": "invalid",
            "token": token,
            "password1": password,
            "password2": password,
        }
        resp = self.client.post(
            "/user/api/v2/password_reset/confirm", json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_password_reset_confirm_with_invalid_token(self):
        user = self._create_user("user")
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

        password = "new-password"
        params = {
            "uidb64": uidb64,
            "token": "invalid",
            "password1": password,
            "password2": password,
        }
        resp = self.client.post(
            "/user/api/v2/password_reset/confirm", json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_password_reset_confirm_with_invalid_password(self):
        user = self._create_user("user")
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        # too common
        password = "password"
        params = {
            "uidb64": uidb64,
            "token": token,
            "password1": password,
            "password2": password,
        }
        resp = self.client.post(
            "/user/api/v2/password_reset/confirm", json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 400)

        # too short
        password = "pw"
        params = {
            "uidb64": uidb64,
            "token": token,
            "password1": password,
            "password2": password,
        }
        resp = self.client.post(
            "/user/api/v2/password_reset/confirm", json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 400)

        # unmatch 2 password fields
        params = {
            "uidb64": uidb64,
            "token": token,
            "password1": "new-password",
            "password2": "unmatched-password",
        }
        resp = self.client.post(
            "/user/api/v2/password_reset/confirm", json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_patch_user_password(self):
        user = self.guest_login()
        old_passwd = user.username
        new_passwd = "new-passwd"

        params = {
            "old_passwd": old_passwd,
            "new_passwd": new_passwd,
            "chk_passwd": new_passwd,
        }
        resp = self.client.patch(
            "/user/api/v2/%d/edit_passwd" % user.id, json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 200)

        updated_user = User.objects.filter(id=user.id).first()
        self.assertIsNotNone(updated_user)
        self.assertTrue(updated_user.check_password(new_passwd))

    def test_patch_co_user_password_by_guest(self):
        user = self.guest_login()

        co_user = self._create_user("co_user", parent_user=user)
        params = {
            "old_passwd": co_user.username,
            "new_passwd": "new-passwd",
            "chk_passwd": "new-passwd",
        }
        resp = self.client.patch(
            "/user/api/v2/%d/edit_passwd" % co_user.id, json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_patch_other_user_password_by_guest(self):
        self.guest_login()

        other_user = self._create_user("other")
        params = {
            "old_passwd": "other",
            "new_passwd": "new-passwd",
            "chk_passwd": "new-passwd",
        }
        resp = self.client.patch(
            "/user/api/v2/%d/edit_passwd" % other_user.id, json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json()["non_field_errors"][0]["message"],
            "You don't have permission to access this object",
        )

    @with_airone_settings(
        {
            "PASSWORD_RESET_DISABLED": True,
        }
    )
    def test_patch_user_password_when_PASSWORD_RESET_DISABLED_is_set(self):
        user = self.guest_login()
        old_passwd = user.username
        new_passwd = "new-passwd"

        params = {
            "old_passwd": old_passwd,
            "new_passwd": new_passwd,
            "chk_passwd": new_passwd,
        }
        resp = self.client.patch(
            "/user/api/v2/%d/edit_passwd" % user.id, json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 403)

        # check password wasn't changed
        self.assertEqual(
            resp.json(), {"message": "It is not allowed to change password", "code": "AE-210000"}
        )
        self.assertFalse(user.check_password(new_passwd))
        self.assertTrue(user.check_password(old_passwd))

    def test_patch_user_password_with_invalid_params(self):
        user = self.guest_login()
        old_passwd = user.username
        new_passwd = "new-passwd"

        # old_passwd is wrong
        params = {
            "old_passwd": "invalid-old-passwd",
            "new_passwd": new_passwd,
            "chk_passwd": new_passwd,
        }
        resp = self.client.patch(
            "/user/api/v2/%d/edit_passwd" % user.id, json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 400)

        # new_passwd doesn't match with chk_passwd
        params = {
            "old_passwd": old_passwd,
            "new_passwd": new_passwd,
            "chk_passwd": "unmatched-passwd",
        }
        resp = self.client.patch(
            "/user/api/v2/%d/edit_passwd" % user.id, json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 400)

        # new_passwd matches with old_passwd
        params = {
            "old_passwd": old_passwd,
            "new_passwd": old_passwd,
            "chk_passwd": old_passwd,
        }
        resp = self.client.patch(
            "/user/api/v2/%d/edit_passwd" % user.id, json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 400)

        # target user doesn't match with a request user
        other = self._create_user("other")
        other_old_passwd = other.username
        params = {
            "old_passwd": other_old_passwd,
            "new_passwd": new_passwd,
            "chk_passwd": new_passwd,
        }
        resp = self.client.patch(
            "/user/api/v2/%d/edit_passwd" % other.id, json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_patch_user_password_by_superuser(self):
        self.admin_login()

        user = self._create_user("user")
        new_passwd = "new-passwd"

        params = {
            "new_passwd": new_passwd,
            "chk_passwd": new_passwd,
        }
        resp = self.client.patch(
            "/user/api/v2/%d/su_edit_passwd" % user.id, json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 200)

        updated_user = User.objects.filter(id=user.id).first()
        self.assertIsNotNone(updated_user)
        self.assertTrue(updated_user.check_password(new_passwd))

    def test_patch_user_password_by_superuser_with_invalid_params(self):
        self.admin_login()

        user = self._create_user("user")
        new_passwd = "new-passwd"

        # new_passwd doesn't match with chk_passwd
        params = {
            "new_passwd": new_passwd,
            "chk_passwd": "invalid-chk-passwd",
        }
        resp = self.client.patch(
            "/user/api/v2/%d/su_edit_passwd" % user.id, json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 400)

        # request user is not an admin
        self.guest_login()
        params = {
            "new_passwd": new_passwd,
            "chk_passwd": "invalid-chk-passwd",
        }
        resp = self.client.patch(
            "/user/api/v2/%d/su_edit_passwd" % user.id, json.dumps(params), "application/json"
        )
        self.assertEqual(resp.status_code, 403)

    @patch("user.api_v2.serializers.LDAPBackend.is_authenticated", Mock(return_value=True))
    def test_post_change_auth_with_correct_password(self):
        login_user = self.guest_login()

        resp = self.client.patch(
            "/user/api/v2/%d/auth" % login_user.id,
            json.dumps({"ldap_password": "CORRECT_PASSWORD"}),
            "application/json",
        )
        login_user.refresh_from_db()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(login_user.authenticate_type, User.AuthenticateType.AUTH_TYPE_LDAP)

    def test_post_change_auth_with_user_already_enables_ldap(self):
        login_user = self.guest_login()
        login_user.authenticate_type = User.AuthenticateType.AUTH_TYPE_LDAP
        login_user.save(update_fields=["authenticate_type"])

        resp = self.client.patch(
            "/user/api/v2/%d/auth" % login_user.id,
            json.dumps({"ldap_password": "CORRECT_PASSWORD"}),
            "application/json",
        )
        self.assertEqual(resp.status_code, 400)

    @patch("user.api_v2.serializers.LDAPBackend.is_authenticated", Mock(return_value=False))
    def test_post_change_auth_with_incorrect_password(self):
        login_user = self.guest_login()

        resp = self.client.patch(
            "/user/api/v2/%d/auth" % login_user.id,
            json.dumps({"ldap_password": "INCORRECT_PASSWORD"}),
            "application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_post_change_auth_with_invalid_parameters(self):
        login_user = self.guest_login()

        invalid_parameters = [
            {"invalid_parameter": "value"},
            [{"invalid_parameter": "value"}],
            {"ldap_password": {"invalid_value_type": "value"}},
            {"ldap_password": [1, 2, 3, 4]},
            {"ldap_password": ""},
        ]
        for _param in invalid_parameters:
            resp = self.client.patch(
                "/user/api/v2/%d/auth" % login_user.id, json.dumps(_param), "application/json"
            )
            self.assertEqual(resp.status_code, 400)

    def test_refresh_co_user_token_by_parent(self):
        parent_user = self.guest_login()
        co_user = self._create_user("co_user", parent_user=parent_user)

        resp = self.client.post("/user/api/v2/%d/token/" % co_user.id)
        self.assertEqual(resp.status_code, 200)

        token = Token.objects.get(user=co_user)
        self.assertEqual(resp.json(), {"key": str(token)})

    def test_refresh_co_user_token_by_non_parent(self):
        self.guest_login()
        other_user = self._create_user("other_user")

        resp = self.client.post("/user/api/v2/%d/token/" % other_user.id)
        self.assertEqual(resp.status_code, 403)
