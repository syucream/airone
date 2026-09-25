"""Seed the deterministic dataset used by the live-service browser suite."""

import json
import os
import sys

import configurations

if os.environ.get("PAGODA_LIVE_SERVICE_E2E") != "1":
    raise RuntimeError(
        "Set PAGODA_LIVE_SERVICE_E2E=1 only after selecting dedicated database and search indexes."
    )

# Allow this script to be run directly from the repository root.
sys.path.append("./")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "airone.settings")
os.environ.setdefault("DJANGO_CONFIGURATION", "Dev")
configurations.setup()

from airone.lib.acl import ACLType  # noqa: E402
from airone.lib.types import AttrType  # noqa: E402
from entity.models import Entity, EntityAttr  # noqa: E402
from entry.models import Entry  # noqa: E402
from role.models import HistoricalPermission, Role  # noqa: E402
from user.models import User  # noqa: E402

PASSWORD = "e2e-password"
TARGET_ENTITY = "E2E Asset Catalog"
REFERENCE_ENTITY = "E2E Asset References"
REGION_ENTITY = "E2E Deployment Regions"
PROTECTED_ENTRY = "e2e-protected-entry"
DECOY_ENTRY = "e2e-decoy-entry"
HIDDEN_ENTRY = "e2e-hidden-entry"
RESTRICTED_PATH_ENTRY = "e2e-asset-with-restricted-reference"
REFERENCE_ENTRY = "e2e-reference-alpha"
REFERENCE_ENTRY_OTHER = "e2e-reference-beta"
RESTRICTED_REFERENCE_ENTRY = "e2e-reference-restricted"
REGION_ENTRY = "e2e-region-tokyo"
REGION_ENTRY_OTHER = "e2e-region-osaka"


def ensure_user(username: str, *, is_superuser: bool = False) -> User:
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={
            "email": f"{username}@example.test",
            "is_staff": is_superuser,
            "is_superuser": is_superuser,
        },
    )
    user.email = f"{username}@example.test"
    user.is_active = True
    user.is_staff = is_superuser
    user.is_superuser = is_superuser
    user.is_readonly = False
    user.set_password("admin" if is_superuser else PASSWORD)
    user.save()
    return user


def ensure_entity(name: str, admin: User) -> Entity:
    entity, _ = Entity.objects.get_or_create(
        name=name,
        defaults={"created_user": admin, "is_public": False},
    )
    entity.created_user = admin
    entity.is_active = True
    entity.is_public = False
    entity.default_permission = ACLType.Nothing
    entity.save()
    return entity


def ensure_attr(entity: Entity, name: str, attr_type: AttrType, admin: User) -> EntityAttr:
    attr, _ = EntityAttr.objects.get_or_create(
        parent_entity=entity,
        name=name,
        defaults={
            "type": attr_type,
            "created_user": admin,
            "is_active": True,
            "is_public": True,
        },
    )
    attr.type = attr_type
    attr.is_active = True
    attr.is_public = True
    attr.save()
    return attr


def ensure_entry(entity: Entity, name: str, admin: User) -> Entry:
    entry = Entry.objects.filter(schema=entity, name=name).first()
    if entry is None:
        entry = Entry.objects.create(schema=entity, name=name, created_user=admin)
    elif not entry.is_active:
        entry.restore()
    return entry


def set_entry_visibility(entry: Entry, *, is_public: bool) -> None:
    entry.is_public = is_public
    entry.default_permission = ACLType.Nothing
    entry.save(update_fields=["is_public", "default_permission"])


def set_value(entry: Entry, schema: EntityAttr, value: object, admin: User) -> None:
    attr = entry.add_attribute_from_base(schema, admin)
    current = attr.get_latest_value()
    if isinstance(value, Entry):
        is_current = current is not None and current.referral_id == value.id
    else:
        is_current = current is not None and current.get_value(with_metainfo=False) == value
    if not is_current:
        attr.add_value(admin, value)


def set_role_permissions(role: Role, permissions: list[HistoricalPermission]) -> None:
    """Set reverse HistoricalPermission links without reverse-side history signals."""
    through = Role.permissions.through
    through.objects.filter(role_id=role.id).delete()
    through.objects.bulk_create(
        [
            through(role_id=role.id, historicalpermission_id=permission.id)
            for permission in permissions
        ]
    )


def seed() -> dict[str, object]:
    admin = ensure_user("admin", is_superuser=True)
    editor = ensure_user("e2e-editor")
    viewer = ensure_user("e2e-viewer")
    denied = ensure_user("e2e-denied")

    region_entity = ensure_entity(REGION_ENTITY, admin)
    region_code = ensure_attr(region_entity, "code", AttrType.STRING, admin)
    region_entry = ensure_entry(region_entity, REGION_ENTRY, admin)
    region_entry_other = ensure_entry(region_entity, REGION_ENTRY_OTHER, admin)
    set_entry_visibility(region_entry, is_public=True)
    set_entry_visibility(region_entry_other, is_public=True)
    set_value(region_entry, region_code, "jp-east-1", admin)
    set_value(region_entry_other, region_code, "jp-west-1", admin)

    reference_entity = ensure_entity(REFERENCE_ENTITY, admin)
    reference_label = ensure_attr(reference_entity, "label", AttrType.STRING, admin)
    reference_region = ensure_attr(reference_entity, "region", AttrType.OBJECT, admin)
    reference_region.referral.set([region_entity])
    reference_entry = ensure_entry(reference_entity, REFERENCE_ENTRY, admin)
    reference_entry_other = ensure_entry(reference_entity, REFERENCE_ENTRY_OTHER, admin)
    restricted_reference_entry = ensure_entry(reference_entity, RESTRICTED_REFERENCE_ENTRY, admin)
    set_entry_visibility(reference_entry, is_public=True)
    set_entry_visibility(reference_entry_other, is_public=True)
    set_entry_visibility(restricted_reference_entry, is_public=False)
    set_value(reference_entry, reference_label, "Reference Alpha", admin)
    set_value(reference_entry, reference_region, region_entry, admin)
    set_value(reference_entry_other, reference_label, "Reference Beta", admin)
    set_value(reference_entry_other, reference_region, region_entry_other, admin)
    set_value(restricted_reference_entry, reference_label, "Restricted Reference", admin)
    set_value(restricted_reference_entry, reference_region, region_entry, admin)

    target_entity = ensure_entity(TARGET_ENTITY, admin)
    description = ensure_attr(target_entity, "description", AttrType.STRING, admin)
    reference = ensure_attr(target_entity, "reference", AttrType.OBJECT, admin)
    reference.referral.set([reference_entity])

    protected_entry = ensure_entry(target_entity, PROTECTED_ENTRY, admin)
    decoy_entry = ensure_entry(target_entity, DECOY_ENTRY, admin)
    hidden_entry = ensure_entry(target_entity, HIDDEN_ENTRY, admin)
    restricted_path_entry = ensure_entry(target_entity, RESTRICTED_PATH_ENTRY, admin)
    set_entry_visibility(protected_entry, is_public=True)
    set_entry_visibility(decoy_entry, is_public=True)
    set_entry_visibility(hidden_entry, is_public=False)
    set_entry_visibility(restricted_path_entry, is_public=True)
    set_value(protected_entry, description, "protected value", admin)
    set_value(protected_entry, reference, reference_entry, admin)
    set_value(decoy_entry, description, "decoy value", admin)
    set_value(decoy_entry, reference, reference_entry_other, admin)
    set_value(hidden_entry, description, "hidden value", admin)
    set_value(hidden_entry, reference, reference_entry, admin)
    set_value(restricted_path_entry, description, "restricted path value", admin)
    set_value(restricted_path_entry, reference, restricted_reference_entry, admin)

    editor_role, _ = Role.objects.get_or_create(name="E2E Asset Catalog Editors")
    viewer_role, _ = Role.objects.get_or_create(name="E2E Asset Catalog Viewers")
    editor_role.is_active = True
    viewer_role.is_active = True
    editor_role.save()
    viewer_role.save()
    editor_role.users.set([editor])
    viewer_role.users.set([viewer])
    editor_role.admin_users.set([admin])
    viewer_role.admin_users.set([admin])
    set_role_permissions(
        editor_role,
        [entity.writable for entity in (region_entity, reference_entity, target_entity)],
    )
    set_role_permissions(
        viewer_role,
        [entity.readable for entity in (region_entity, reference_entity, target_entity)],
    )

    # Direct ORM setup deliberately bypasses the request hooks which normally
    # keep Elasticsearch synchronized. Live-service search assertions need the
    # seeded records to be visible before the browser suite starts.
    for entry in (
        region_entry,
        region_entry_other,
        reference_entry,
        reference_entry_other,
        restricted_reference_entry,
        protected_entry,
        decoy_entry,
        hidden_entry,
        restricted_path_entry,
    ):
        entry.register_es()

    return {
        "password": PASSWORD,
        "users": {
            "admin": admin.username,
            "editor": editor.username,
            "viewer": viewer.username,
            "denied": denied.username,
        },
        "entities": {
            "target": {"id": target_entity.id, "name": target_entity.name},
            "region": {"id": region_entity.id, "name": region_entity.name},
            "reference": {
                "id": reference_entity.id,
                "name": reference_entity.name,
            },
        },
        "entries": {
            "protected": {"id": protected_entry.id, "name": protected_entry.name},
            "decoy": {"id": decoy_entry.id, "name": decoy_entry.name},
            "hidden": {"id": hidden_entry.id, "name": hidden_entry.name},
            "restricted_path": {
                "id": restricted_path_entry.id,
                "name": restricted_path_entry.name,
            },
            "reference": {"id": reference_entry.id, "name": reference_entry.name},
            "region": {"id": region_entry.id, "name": region_entry.name},
        },
        "attrs": {
            "description": description.id,
            "reference": reference.id,
            "reference_region": reference_region.id,
            "region_code": region_code.id,
        },
    }


if __name__ == "__main__":
    print(json.dumps(seed(), sort_keys=True))  # noqa: T201
