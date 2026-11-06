from group.models import Group
from user.models import User


class UserFixtureMixin:
    """Create users and groups without inheriting runnable test cases."""

    def _create_user(
        self,
        name,
        email="email@example.com",
        is_superuser=False,
        is_readonly=False,
        parent_user=None,
        authenticate_type=User.AuthenticateType.AUTH_TYPE_LOCAL,
    ):
        user = User(
            username=name,
            email=email,
            is_superuser=is_superuser,
            is_readonly=is_readonly,
            parent_user=parent_user,
            authenticate_type=authenticate_type,
        )
        user.set_password(name)
        user.save()

        return user

    def _create_group(self, name):
        return Group.objects.create(name=name)
