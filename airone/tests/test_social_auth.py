from unittest.mock import Mock

from django.test import TestCase
from social_core.exceptions import AuthForbidden
from social_core.pipeline.social_auth import associate_user, social_user
from social_django.models import UserSocialAuth

from airone.auth.social_auth import create_user
from user.models import User


class SocialAuthTest(TestCase):
    def setUp(self):
        self.backend = Mock(name="backend")
        self.backend.name = "saml"
        self.backend.strategy.storage.user = UserSocialAuth
        self.details = {"username": "sso-user", "email": "sso@example.com"}

    def run_pipeline(self, uid="idp:new-id", user=None):
        state = social_user(self.backend, uid, user=user)
        state.update(create_user(self.details, backend=self.backend, **state))
        association = associate_user(self.backend, uid, **state)
        if association:
            state.update(association)
        return state

    def test_new_identity_creates_user_and_association(self):
        state = self.run_pipeline()
        user = state["user"]
        self.assertEqual(user.username, self.details["username"])
        self.assertEqual(user.email, self.details["email"])
        self.assertFalse(user.has_usable_password())
        self.assertEqual(UserSocialAuth.objects.get(uid="idp:new-id").user, user)

    def test_previously_associated_identity_can_login_despite_username_change(self):
        user = User.objects.create(username="original-name")
        social = UserSocialAuth.objects.create(user=user, provider="saml", uid="idp:known")
        self.details["username"] = "changed-at-provider"
        state = self.run_pipeline(uid=social.uid)
        self.assertEqual(state["user"], user)
        self.assertFalse(state["is_new"])
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(UserSocialAuth.objects.count(), 1)

    def test_same_name_never_links_an_unassociated_identity(self):
        for auth_type, associated, active in (
            (User.AuthenticateType.AUTH_TYPE_LOCAL, False, True),
            (User.AuthenticateType.AUTH_TYPE_LDAP, False, True),
            (User.AuthenticateType.AUTH_TYPE_LOCAL, True, True),
            (User.AuthenticateType.AUTH_TYPE_LOCAL, False, False),
        ):
            with self.subTest(auth_type=auth_type, associated=associated, active=active):
                user = User.objects.create(
                    username=self.details["username"],
                    email="original@example.com",
                    authenticate_type=auth_type,
                    is_active=active,
                    is_superuser=True,
                )
                if associated:
                    UserSocialAuth.objects.create(user=user, provider="saml", uid="idp:other")
                before = UserSocialAuth.objects.count()
                with self.assertRaises(AuthForbidden):
                    self.run_pipeline()
                user.refresh_from_db()
                self.assertEqual(user.email, "original@example.com")
                self.assertTrue(user.is_superuser)
                self.assertEqual(User.objects.count(), 1)
                self.assertEqual(UserSocialAuth.objects.count(), before)
                UserSocialAuth.objects.all().delete()
                User.objects.filter(pk=user.pk).delete()

    def test_authenticated_user_cannot_link_new_identity(self):
        user = User.objects.create(username="logged-in")
        with self.assertRaises(AuthForbidden):
            self.run_pipeline(user=user)
        self.assertFalse(UserSocialAuth.objects.exists())
        self.assertEqual(User.objects.count(), 1)

    def test_authenticated_user_can_reuse_their_existing_identity(self):
        user = User.objects.create(username="logged-in")
        social = UserSocialAuth.objects.create(user=user, provider="saml", uid="idp:known")
        self.assertEqual(self.run_pipeline(uid=social.uid, user=user)["user"], user)

    def test_mismatched_social_user_is_rejected(self):
        user = User.objects.create(username="logged-in")
        other = User.objects.create(username="other")
        social = UserSocialAuth.objects.create(user=other, provider="saml", uid="idp:other")
        with self.assertRaises(AuthForbidden):
            create_user(self.details, user=user, social=social, backend=self.backend)
