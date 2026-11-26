# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.
#
# It partially reuses the original implementation at django.contrib.auth.forms.PasswordResetForm
# with supporting username based email resolution.
#

import logging
from smtplib import SMTPException
from typing import Any, cast

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UsernameField
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.http import HttpRequest
from django.template import loader
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from user.models import User

UserModel = get_user_model()
logger = logging.getLogger(__name__)


class UsernameBasedPasswordResetForm(forms.Form):
    """
    A customized PasswordResetForm to send only an email relating to a given username.
    """

    username = UsernameField(max_length=254)

    USERNAME_FIELD = UserModel.USERNAME_FIELD
    EMAIL_FIELD = UserModel.get_email_field_name()

    def send_mail(
        self,
        subject_template_name: str,
        email_template_name: str,
        context: dict[str, Any],
        from_email: str | None,
        to_email: str,
        html_email_template_name: str | None = None,
    ) -> None:
        """
        Sends a django.core.mail.EmailMultiAlternatives to `to_email`.
        """
        subject = cast(str, loader.render_to_string(subject_template_name, context))
        # Email subject *must not* contain newlines
        subject = "".join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        email_message = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, "text/html")

        try:
            email_message.send()
        except (SMTPException, OSError):
            # Transport failures must not disclose whether a recipient exists.
            logger.exception("Unable to send password reset email")

    def get_user(self, username: str) -> User | None:
        """
        Given a username, return matching user who should receive a reset or None.
        """
        if settings.AIRONE["PASSWORD_RESET_DISABLED"]:
            return None

        users = list(
            UserModel._default_manager.filter(
                **{f"{self.USERNAME_FIELD}__iexact": username, "is_active": True}
            )[:2]
        )
        if len(users) == 1 and users[0].can_reset_password and users[0].email:
            return users[0]
        return None

    def save(
        self,
        domain_override: str | None = None,
        subject_template_name: str = "registration/password_reset_subject.txt",
        email_template_name: str = "registration/password_reset_email.html",
        use_https: bool = False,
        token_generator: Any = default_token_generator,
        from_email: str | None = None,
        request: HttpRequest | None = None,
        html_email_template_name: str | None = None,
        extra_email_context: dict[str, Any] | None = None,
    ) -> None:
        """
        Generates a one-use only link for resetting password and sends to the
        user.
        """
        username = self.cleaned_data["username"]
        user = self.get_user(username)
        if user:
            # The reset link domain must never come from the request: with
            # django.contrib.sites uninstalled, get_current_site() would fall
            # back to the client-controlled Host header (CWE-640). Callers
            # must always pass an explicit domain_override (see
            # airone.lib.canonical.get_canonical_url_parts).
            if not domain_override:
                raise ImproperlyConfigured(
                    "A password reset link domain must be provided explicitly "
                    "via domain_override; deriving it from the request is not "
                    "allowed (reset-link poisoning, CWE-640)."
                )
            site_name = domain = domain_override
            user_email = getattr(user, self.EMAIL_FIELD)
            context = {
                "email": user_email,
                "domain": domain,
                "site_name": site_name,
                "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                "user": user,
                "token": token_generator.make_token(user),
                "protocol": "https" if use_https else "http",
            }
            if extra_email_context is not None:
                context.update(extra_email_context)
            self.send_mail(
                subject_template_name,
                email_template_name,
                context,
                from_email,
                user_email,
                html_email_template_name=html_email_template_name,
            )
