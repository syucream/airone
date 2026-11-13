from django.contrib.auth.models import Permission

from acl.models import ACLBase
from airone.lib.acl import ACLType
from user.models import User


class ACLReader:
    """Share a lazy role snapshot within one response without caching across requests."""

    def __init__(self, user: User):
        self.user = user
        self._role_permissions: dict[str, int] | None = None

    def _get_role_permissions(self) -> dict[str, int]:
        if self._role_permissions is None:
            roles = [belonging.role.id for belonging in self.user.belonging_roles()]
            self._role_permissions = {}
            codenames = Permission.objects.filter(
                historicalpermission__roles__id__in=roles,
                name__in=[level.name for level in ACLType.all()],
            ).values_list("codename", flat=True)
            for codename in codenames:
                object_id, separator, _ = codename.partition(".")
                if not separator:
                    continue
                level = int(codename.rsplit(".", 1)[-1])
                self._role_permissions[object_id] = max(
                    self._role_permissions.get(object_id, 0), level
                )
        return self._role_permissions

    def has_permission(self, obj: ACLBase, level: ACLType) -> bool:
        return self.user.has_permission(obj, level, role_permissions=self._get_role_permissions)
