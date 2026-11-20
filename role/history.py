"""Combine native role membership and permission histories for display and restore."""

from datetime import datetime
from typing import Literal, NotRequired, Protocol, TypedDict

from rest_framework.exceptions import ValidationError

from acl.models import ACLBase
from role.models import HistoricalPermission, Role
from user.models import User

type RoleRelation = Literal["users", "groups", "admin_users", "admin_groups"]
type RoleHistorySource = Literal["role", "permission"]

ROLE_RELATIONS: tuple[RoleRelation, ...] = ("users", "groups", "admin_users", "admin_groups")
MEMBER_FIELDS: dict[RoleRelation, tuple[str, Literal["username", "name"]]] = {
    "users": ("user", "username"),
    "groups": ("group", "name"),
    "admin_users": ("user", "username"),
    "admin_groups": ("group", "name"),
}


class RoleHistoryMember(TypedDict):
    id: int
    username: NotRequired[str]
    name: NotRequired[str]


class RoleHistoryPermission(TypedDict):
    id: int
    codename: str
    name: str | None


class RoleHistoryRelations(TypedDict):
    users: list[RoleHistoryMember]
    groups: list[RoleHistoryMember]
    admin_users: list[RoleHistoryMember]
    admin_groups: list[RoleHistoryMember]
    permissions: list[RoleHistoryPermission]


class RoleHistoryEvent(TypedDict):
    history_id: int
    history_source: RoleHistorySource
    history_date: datetime
    history_user: User | None
    history_type: str
    history_change_reason: str | None
    name: str
    description: str
    is_active: bool
    relations: RoleHistoryRelations


# django-simple-history builds these model classes at runtime.
class _HistoryRecord(Protocol):
    history_id: int
    history_date: datetime
    history_user: User | None
    history_type: str
    history_change_reason: str | None


class _RoleRecord(_HistoryRecord, Protocol):
    name: str
    description: str
    is_active: bool


class _PermissionRecord(_HistoryRecord, Protocol):
    permission_ptr_id: int
    codename: str


type _DatedRecord = (
    tuple[datetime, Literal["role"], _RoleRecord]
    | tuple[datetime, Literal["permission"], _PermissionRecord]
)


def role_history_events(role: Role) -> list[RoleHistoryEvent]:
    role_records: list[_RoleRecord] = list(role.history.select_related("history_user"))
    if not role_records:
        return []
    members_by_history: dict[int, dict[RoleRelation, list[RoleHistoryMember]]] = {
        record.history_id: {key: [] for key in ROLE_RELATIONS} for record in role_records
    }
    for key, (field, name) in MEMBER_FIELDS.items():
        through_model = getattr(Role.history.model, key).model
        links = through_model.objects.filter(history_id__in=members_by_history).select_related(
            field
        )
        for link in links:
            field_id: int = getattr(link, f"{field}_id")
            member: RoleHistoryMember = {"id": field_id}
            member[name] = getattr(getattr(link, field), name, str(field_id))
            members_by_history[link.history_id][key].append(member)

    # Include all snapshots of permissions ever assigned to the role. Filtering
    # snapshots by membership alone would lose removal and clear events.
    permission_memberships = HistoricalPermission.history.model.roles.model
    assigned_history_ids = permission_memberships.objects.filter(role_id=role.pk).values(
        "history_id"
    )
    permission_ids = HistoricalPermission.history.filter(
        history_id__in=assigned_history_ids
    ).values("permission_ptr_id")
    permission_records: list[_PermissionRecord] = list(
        HistoricalPermission.history.filter(permission_ptr_id__in=permission_ids).select_related(
            "history_user"
        )
    )
    belonged_history_ids = set(
        permission_memberships.objects.filter(
            role_id=role.pk, history_id__in=[record.history_id for record in permission_records]
        ).values_list("history_id", flat=True)
    )
    records: list[_DatedRecord] = [(record.history_date, "role", record) for record in role_records]
    records.extend((record.history_date, "permission", record) for record in permission_records)
    records.sort(key=lambda item: (item[0], item[1] == "permission", item[2].history_id))
    target_ids = {
        int(record.codename.split(".")[0])
        for record in permission_records
        if record.codename.split(".")[0].isdecimal()
    }
    targets = ACLBase.objects.in_bulk(target_ids)
    target_names: dict[tuple[int, datetime], str | None] = {}
    permissions: dict[int, _PermissionRecord] = {}
    role_record: _RoleRecord | None = None
    members: dict[RoleRelation, list[RoleHistoryMember]] = {}
    events: list[RoleHistoryEvent] = []

    for item in records:
        date, source, record = item
        if item[1] == "role":
            role_record = item[2]
            members = members_by_history[record.history_id]
        else:
            permission_record = item[2]
            permission_id = permission_record.permission_ptr_id
            belonged = permission_id in permissions
            belongs = record.history_type != "-" and record.history_id in belonged_history_ids
            if belongs:
                permissions[permission_id] = permission_record
            else:
                permissions.pop(permission_id, None)
            if belonged == belongs:
                continue
        # Permission history may predate role tracking. Keep it for reconstructing
        # permissions, and start the combined timeline when role tracking begins.
        if role_record is None:
            continue
        permission_values: list[RoleHistoryPermission] = []
        for permission_id, permission in sorted(permissions.items()):
            target_id = int(permission.codename.split(".")[0])
            cache_key = (target_id, date)
            if cache_key not in target_names:
                target = targets.get(target_id)
                target_name: str | None = target.name if target else None
                if target:
                    target_history = getattr(target.get_subclass_object(), "history", None)
                    if target_history is not None:
                        historical_target = target_history.filter(history_date__lte=date).first()
                        if historical_target is not None:
                            target_name = historical_target.name
                target_names[cache_key] = target_name
            permission_values.append(
                {
                    "id": permission_id,
                    "codename": permission.codename,
                    "name": target_names[cache_key],
                }
            )
        events.append(
            {
                "history_id": record.history_id,
                "history_source": source,
                "history_date": date,
                "history_user": record.history_user,
                "history_type": record.history_type if source == "role" else "~",
                "history_change_reason": record.history_change_reason,
                "name": role_record.name,
                "description": role_record.description,
                "is_active": role_record.is_active,
                "relations": {
                    "users": members["users"],
                    "groups": members["groups"],
                    "admin_users": members["admin_users"],
                    "admin_groups": members["admin_groups"],
                    "permissions": permission_values,
                },
            }
        )
    return list(reversed(events))


def get_role_history_event(role: Role, history_id: int, history_source: str) -> RoleHistoryEvent:
    for event in role_history_events(role):
        if event["history_source"] == history_source and event["history_id"] == history_id:
            if event["is_active"]:
                return event
            break
    raise ValidationError("The specified role history does not exist or is inactive")
