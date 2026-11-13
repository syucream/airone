from typing import Any

from social_core.exceptions import AuthForbidden  # type: ignore[import-untyped]
from social_django.models import UserSocialAuth

from user.models import User


def create_user(
    details: dict[str, str],
    user: User | None = None,
    *args: Any,
    backend: Any = None,
    social: UserSocialAuth | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    # Only a previously associated identity can authenticate an existing user.
    # A logged-in user alone is not evidence that this identity belongs to them.
    if user:
        if social is None or social.user_id != user.pk:
            raise AuthForbidden(backend)
        return {"is_new": False}

    # Provider usernames do not establish ownership of existing local accounts.
    if User.objects.filter(username=details["username"]).exists():
        raise AuthForbidden(backend)

    user = User.objects.create(username=details["username"], email=details["email"])
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return {"user": user}
