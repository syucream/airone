"""Authorization regression gate.

Every case in this module pins the authorization decision for an endpoint that
was reported by the 2026-10-22 security review (see
``docs/security/authorization-hardening.md``). The goal is not to exercise
features but to make it impossible to silently re-open any of these holes:

* a regular user must not be able to widen their own privileges (superuser flag,
  group membership, role membership, authentication type), and
* a regular user must not be able to reach, mutate or destroy an object that
  they only know the id of.

The last two tests are structural: they fail when a new permission class is added
without a ``has_permission`` implementation, or when a known privileged view stops
being gated, so the pattern behind the findings cannot come back unnoticed.
"""

import json
from collections.abc import Iterator
from typing import Any

from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.viewsets import ViewSetMixin

from airone.lib.acl import ACLObjType, ACLType
from airone.lib.test import AironeViewTest
from entity.models import Entity
from entry.api_v2.serializers import EntryCreateSerializer
from entry.models import Entry
from group.models import Group
from isolation.models import IsolationParent
from job.models import Job, JobOperation, JobStatus
from user.models import User


class AuthorizationTestBase(AironeViewTest):
    def post_json(self, path: str, payload: dict[str, Any]) -> Any:
        return self.client.post(path, json.dumps(payload), "application/json")

    def put_json(self, path: str, payload: dict[str, Any]) -> Any:
        return self.client.put(path, json.dumps(payload), "application/json")

    def delete_json(self, path: str, payload: dict[str, Any]) -> Any:
        return self.client.delete(path, json.dumps(payload), "application/json")

    def post_yaml(self, path: str, body: str) -> Any:
        return self.client.post(path, body, "application/yaml")

    def create_user(self, username: str, **kwargs: Any) -> User:
        user: User = User.objects.create(username=username, **kwargs)
        user.set_password(username)
        user.save()

        return user


class PrivilegeEscalationTest(AuthorizationTestBase):
    """A user must not be able to promote themselves into a more privileged role."""

    def test_group_create_requires_superuser(self) -> None:
        guest = self.guest_login()
        privileged = Group.objects.create(name="privileged")

        # A child group inherits the roles of its ancestors through
        # User.belonging_groups(), so creating one is a privilege escalation.
        resp = self.post_json(
            "/group/api/v2/groups",
            {"name": "attacker-group", "parent_group": privileged.id, "members": [guest.id]},
        )

        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Group.objects.filter(name="attacker-group").exists())
        self.assertNotIn(privileged, guest.belonging_groups())

    def test_group_create_is_allowed_for_superuser(self) -> None:
        self.admin_login()

        resp = self.post_json("/group/api/v2/groups", {"name": "admin-group", "members": []})

        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Group.objects.filter(name="admin-group").exists())

    def test_group_reads_stay_available_for_regular_users(self) -> None:
        # The UI needs the group list/tree to render selects, so the create/update
        # gate must not be widened into a read restriction.
        self.guest_login()

        self.assertEqual(self.client.get("/group/api/v2/groups").status_code, 200)
        self.assertEqual(self.client.get("/group/api/v2/groups/tree").status_code, 200)

    def test_group_update_requires_superuser(self) -> None:
        guest = self.guest_login()
        group = Group.objects.create(name="privileged")

        resp = self.put_json(
            "/group/api/v2/groups/%s" % group.id,
            {"name": "renamed", "parent_group": None, "members": [guest.id]},
        )

        self.assertEqual(resp.status_code, 403)
        group.refresh_from_db()
        self.assertEqual(group.name, "privileged")

    def test_group_import_requires_superuser(self) -> None:
        self.guest_login()
        group = Group.objects.create(name="privileged")

        resp = self.post_yaml(
            "/group/api/v2/groups/import", "- id: %s\n  name: renamed\n" % group.id
        )

        self.assertEqual(resp.status_code, 403)
        group.refresh_from_db()
        self.assertEqual(group.name, "privileged")

    def test_user_import_requires_superuser(self) -> None:
        guest = self.guest_login()
        Group.objects.create(name="privileged")

        # Adding oneself to a privileged group is enough to inherit its roles.
        resp = self.post_yaml(
            "/user/api/v2/import/",
            "- username: %s\n  groups: privileged\n  email: guest@example.com\n" % guest.username,
        )

        self.assertEqual(resp.status_code, 403)
        self.assertFalse(guest.groups.filter(name="privileged").exists())

    def test_role_import_requires_superuser(self) -> None:
        guest = self.guest_login()

        resp = self.post_yaml(
            "/role/api/v2/import",
            "- name: pwn\n  users: [%s]\n  groups: []\n  admin_users: [%s]\n"
            "  admin_groups: []\n" % (guest.username, guest.username),
        )

        self.assertEqual(resp.status_code, 403)
        self.assertFalse(guest.role.filter(name="pwn").exists())

    def test_user_cannot_grant_self_superuser(self) -> None:
        guest = self.guest_login()

        resp = self.put_json(
            "/user/api/v2/%s/" % guest.id,
            {
                "username": guest.username,
                "email": "guest@example.com",
                "is_superuser": True,
                "token_lifetime": 3600,
            },
        )

        self.assertEqual(resp.status_code, 403)
        guest.refresh_from_db()
        self.assertFalse(guest.is_superuser)

    def test_superuser_may_grant_superuser(self) -> None:
        self.admin_login()
        target = self.create_user("promoted")

        resp = self.put_json(
            "/user/api/v2/%s/" % target.id,
            {
                "username": target.username,
                "email": "promoted@example.com",
                "is_superuser": True,
                "token_lifetime": 3600,
            },
        )

        self.assertEqual(resp.status_code, 200)
        target.refresh_from_db()
        self.assertTrue(target.is_superuser)

    def test_legacy_do_edit_only_changes_own_token_lifetime(self) -> None:
        self.guest_login()
        victim = self.create_user("victim")
        original_lifetime = victim.token_lifetime

        resp = self.post_json(
            "/user/do_edit/%s" % victim.id,
            {"name": victim.username, "email": "victim@example.com", "token_lifetime": "0"},
        )

        self.assertEqual(resp.status_code, 400)
        victim.refresh_from_db()
        self.assertEqual(victim.token_lifetime, original_lifetime)

    def test_legacy_do_edit_allows_own_token_lifetime(self) -> None:
        guest = self.guest_login()

        resp = self.post_json(
            "/user/do_edit/%s" % guest.id,
            {"name": guest.username, "email": "guest@example.com", "token_lifetime": "0"},
        )

        self.assertEqual(resp.status_code, 200)
        guest.refresh_from_db()
        self.assertEqual(guest.token_lifetime, 0)

    def test_authentication_type_of_another_user_cannot_be_changed(self) -> None:
        self.guest_login()
        victim = self.create_user("victim")

        resp = self.client.patch(
            "/user/api/v2/%s/auth" % victim.id,
            json.dumps({"ldap_password": "anything"}),
            "application/json",
        )

        self.assertEqual(resp.status_code, 403)
        victim.refresh_from_db()
        self.assertNotEqual(victim.authenticate_type, User.AuthenticateType.AUTH_TYPE_LDAP)


class JobIdorTest(AuthorizationTestBase):
    """Jobs run with the permissions of the user who owns them."""

    def _create_job(self, user: User, entity: Entity) -> Job:
        job: Job = Job.objects.create(
            user=user,
            target=entity,
            operation=JobOperation.CREATE_ENTRY,
            status=JobStatus.PREPARING,
            text="preparing",
            params="{}",
        )

        return job

    def test_cannot_cancel_another_users_job(self) -> None:
        victim = self.create_user("victim")
        entity = self.create_entity(victim, "victim-entity")
        job = self._create_job(victim, entity)

        self.guest_login()
        resp = self.delete_json("/api/v1/job/", {"job_id": job.id})

        self.assertEqual(resp.status_code, 403)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.PREPARING)

    def test_can_cancel_own_job(self) -> None:
        guest = self.guest_login()
        entity = self.create_entity(guest, "own-entity")
        job = self._create_job(guest, entity)

        resp = self.delete_json("/api/v1/job/", {"job_id": job.id})

        self.assertEqual(resp.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELED)


class ACLAuthorizationTest(AuthorizationTestBase):
    """ACLs must be authorized against the concrete object, not its base row."""

    def _private_entity_with_public_entry(self) -> tuple[Entity, Entry]:
        admin = self.admin_login()
        entity = self.create_entity(admin, "private-entity", is_public=False)
        entry = self.add_entry(admin, "private-entry", entity)
        self.assertTrue(entry.is_public)

        return entity, entry

    def test_acl_of_child_under_private_parent_is_hidden(self) -> None:
        _entity, entry = self._private_entity_with_public_entry()
        self.guest_login()

        resp = self.client.get("/acl/api/v2/acls/%s" % entry.id)

        self.assertEqual(resp.status_code, 403)

    def test_acl_of_child_under_private_parent_cannot_be_rewritten(self) -> None:
        _entity, entry = self._private_entity_with_public_entry()
        self.guest_login()

        resp = self.put_json(
            "/acl/api/v2/acls/%s" % entry.id,
            {"is_public": False, "default_permission": ACLType.Writable.id, "acl_settings": []},
        )

        self.assertEqual(resp.status_code, 403)
        entry.refresh_from_db()
        self.assertTrue(entry.is_public)

    def test_acl_is_visible_for_regular_user_when_entity_is_public(self) -> None:
        admin = self.admin_login()
        entity = self.create_entity(admin, "public-entity")
        entry = self.add_entry(admin, "public-entry", entity)

        self.guest_login()
        resp = self.client.get("/acl/api/v2/acls/%s" % entry.id)

        self.assertEqual(resp.status_code, 200)

    def test_acl_is_visible_for_superuser(self) -> None:
        _entity, entry = self._private_entity_with_public_entry()

        resp = self.client.get("/acl/api/v2/acls/%s" % entry.id)

        self.assertEqual(resp.status_code, 200)

    def test_acl_history_of_child_under_private_parent_is_hidden(self) -> None:
        _entity, entry = self._private_entity_with_public_entry()
        self.guest_login()

        resp = self.client.get("/acl/api/v2/acls/%s/history" % entry.id)

        self.assertEqual(resp.status_code, 403)

    def test_legacy_acl_set_ignores_client_object_type(self) -> None:
        _entity, entry = self._private_entity_with_public_entry()
        self.guest_login()

        # object_type "0" used to resolve to the bare ACLBase row, which skipped
        # the parent Entity permission check.
        resp = self.post_json(
            "/acl/set",
            {
                "object_id": str(entry.id),
                "object_type": "0",
                "acl": [],
                "default_permission": str(ACLType.Writable.id),
            },
        )

        self.assertEqual(resp.status_code, 400)
        entry.refresh_from_db()
        self.assertTrue(entry.is_public)

    def test_legacy_acl_set_with_mismatched_object_type_is_not_a_server_error(self) -> None:
        _entity, entry = self._private_entity_with_public_entry()
        self.guest_login()

        # A client used to be able to pick a model through object_type, which meant
        # either the wrong row was loaded or the lookup raised DoesNotExist (500).
        # The stored row is authoritative now, so this is a plain permission denial.
        resp = self.post_json(
            "/acl/set",
            {
                "object_id": str(entry.id),
                "object_type": str(int(ACLObjType.Entity)),
                "acl": [],
                "default_permission": str(ACLType.Writable.id),
            },
        )

        self.assertEqual(resp.status_code, 400)
        entry.refresh_from_db()
        self.assertTrue(entry.is_public)


class EntityEditIdorTest(AuthorizationTestBase):
    """Editing an Entity must never touch attributes or rules of another Entity."""

    def test_do_edit_rejects_foreign_attr_id(self) -> None:
        admin = self.admin_login()
        victim_entity = self.create_entity(admin, "victim-entity", attrs=[{"name": "victim-attr"}])
        victim_attr = victim_entity.attrs.first()

        guest = self.guest_login()
        own_entity = self.create_entity(guest, "own-entity")

        resp = self.post_json(
            "/entity/do_edit/%s" % own_entity.id,
            {
                "name": own_entity.name,
                "note": "",
                "is_toplevel": False,
                "attrs": [
                    {
                        "id": victim_attr.id,
                        "name": victim_attr.name,
                        "type": str(int(victim_attr.type)),
                        "is_mandatory": False,
                        "is_delete_in_chain": False,
                        "row_index": "0",
                        "deleted": True,
                    }
                ],
            },
        )

        self.assertEqual(resp.status_code, 400)
        victim_attr.refresh_from_db()
        self.assertTrue(victim_attr.is_active)

        own_entity.refresh_from_db()
        self.assertEqual(own_entity.get_status(Entity.STATUS_EDITING), 0)

    def test_edit_entity_job_rejects_foreign_attr_id(self) -> None:
        admin = self.admin_login()
        victim_entity = self.create_entity(admin, "victim-entity", attrs=[{"name": "victim-attr"}])
        victim_attr = victim_entity.attrs.first()

        guest = self.guest_login()
        own_entity = self.create_entity(guest, "own-entity")

        # Simulate the state entity.views.do_edit leaves behind before queueing.
        own_entity.set_status(Entity.STATUS_EDITING)

        job = Job.new_edit_entity(
            guest,
            own_entity,
            params={
                "name": own_entity.name,
                "note": "",
                "is_toplevel": False,
                "attrs": [
                    {
                        "id": victim_attr.id,
                        "name": victim_attr.name,
                        "type": int(victim_attr.type),
                        "is_mandatory": False,
                        "is_delete_in_chain": False,
                        "row_index": "0",
                        "deleted": True,
                    }
                ],
            },
        )
        job.run(will_delay=False)

        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.ERROR)

        victim_attr.refresh_from_db()
        self.assertTrue(victim_attr.is_active)

        # The EDITING flag must be cleared on rejection, otherwise the Entity is
        # locked out of further edits forever.
        own_entity.refresh_from_db()
        self.assertEqual(own_entity.get_status(Entity.STATUS_EDITING), 0)

    def test_v2_entity_update_rejects_foreign_isolation_rule(self) -> None:
        admin = self.admin_login()
        victim_entity = self.create_entity(admin, "victim-entity", is_public=False)
        rule = IsolationParent.objects.create(entity=victim_entity)

        guest = self.guest_login()
        own_entity = self.create_entity(guest, "own-entity")

        resp = self.put_json(
            "/entity/api/v2/%s/" % own_entity.id,
            {
                "isolation_rules": [
                    {"id": rule.id, "conditions": [], "action": {"is_prevent_all": False}}
                ]
            },
        )

        self.assertEqual(resp.status_code, 400)
        self.assertTrue(IsolationParent.objects.filter(id=rule.id, entity=victim_entity).exists())


class EntryAuthorizationTest(AuthorizationTestBase):
    """Entry side objects must follow the permission of the Entry / Entity."""

    def test_create_entry_attr_rejects_foreign_schema(self) -> None:
        admin = self.admin_login()
        foreign_entity = self.create_entity(admin, "foreign-entity", attrs=[{"name": "foreign"}])
        foreign_attr = foreign_entity.attrs.first()

        guest = self.guest_login()
        own_entity = self.create_entity(guest, "own-entity")
        own_entry = self.add_entry(guest, "own-entry", own_entity)

        resp = self.post_json(
            "/entry/api/v1/create_entry_attr/%s" % own_entry.id,
            {"entity_attr_id": foreign_attr.id},
        )

        self.assertEqual(resp.status_code, 400)
        self.assertFalse(own_entry.attrs.filter(schema=foreign_attr).exists())

    def test_create_entry_attr_requires_entry_write(self) -> None:
        admin = self.admin_login()
        entity = self.create_entity(
            admin, "private-entity", attrs=[{"name": "attr"}], is_public=False
        )
        entry = self.add_entry(admin, "private-entry", entity)
        attr = entity.attrs.first()

        self.guest_login()
        resp = self.post_json(
            "/entry/api/v1/create_entry_attr/%s" % entry.id, {"entity_attr_id": attr.id}
        )

        self.assertEqual(resp.status_code, 400)

    def test_alias_create_requires_entry_write(self) -> None:
        admin = self.admin_login()
        entity = self.create_entity(admin, "private-entity", is_public=False)
        entry = self.add_entry(admin, "private-entry", entity)

        self.guest_login()
        resp = self.post_json("/entry/api/v2/alias/", {"name": "alias-name", "entry": entry.id})

        self.assertEqual(resp.status_code, 403)
        self.assertFalse(entry.aliases.filter(name="alias-name").exists())

    def test_alias_create_by_readonly_user_is_rejected(self) -> None:
        admin = self.admin_login()
        entity = self.create_entity(admin, "public-entity")
        entry = self.add_entry(admin, "public-entry", entity)

        readonly = self.create_user("readonly", is_readonly=True)
        self.client.login(username=readonly.username, password=readonly.username)

        resp = self.post_json("/entry/api/v2/alias/", {"name": "alias-name", "entry": entry.id})

        self.assertEqual(resp.status_code, 403)

    def test_alias_destroy_requires_entry_write(self) -> None:
        admin = self.admin_login()
        entity = self.create_entity(admin, "private-entity", is_public=False)
        entry = self.add_entry(admin, "private-entry", entity)
        alias = entry.add_alias("existing-alias")

        self.guest_login()
        resp = self.client.delete("/entry/api/v2/alias/%s" % alias.id)

        self.assertEqual(resp.status_code, 403)
        self.assertTrue(entry.aliases.filter(id=alias.id).exists())

    def test_alias_create_is_allowed_for_writable_entry(self) -> None:
        guest = self.guest_login()
        entity = self.create_entity(guest, "own-entity")
        entry = self.add_entry(guest, "own-entry", entity)

        resp = self.post_json("/entry/api/v2/alias/", {"name": "alias-name", "entry": entry.id})

        self.assertEqual(resp.status_code, 201)
        self.assertTrue(entry.aliases.filter(name="alias-name").exists())

    def test_entry_create_on_private_entity_is_forbidden(self) -> None:
        admin = self.admin_login()
        entity = self.create_entity(admin, "private-entity", is_public=False)

        self.guest_login()
        resp = self.post_json(
            "/entity/api/v2/%s/entries/" % entity.id, {"schema": entity.id, "name": "new-entry"}
        )

        self.assertEqual(resp.status_code, 403)

    def test_entry_create_serializer_requires_schema_write(self) -> None:
        admin = self.admin_login()
        entity = self.create_entity(admin, "private-entity", is_public=False)

        guest = self.create_user("guest")

        # The serializer is shared by the API, plugin overrides and async jobs, so
        # it has to enforce the schema permission on its own.
        serializer = EntryCreateSerializer(
            data={"schema": entity.id, "name": "new-entry"}, context={"_user": guest}
        )
        with self.assertRaises(PermissionDenied):
            serializer.is_valid(raise_exception=True)


class PermissionClassGateTest(AironeViewTest):
    """Structural gate around the pattern that produced the findings."""

    # Permission classes that intentionally implement only object level checks.
    # Each one is safe because the action that needs a collection level decision is
    # handled elsewhere; keep this list empty on purpose when adding new classes.
    ALLOWED_OBJECT_ONLY_PERMISSIONS = {
        # UserAPI.create is handled by UserCreateSerializer, which only lets a
        # non-superuser mint read-only co-users.
        "user.api_v2.views.UserPermission",
        # EntryAPI has no create route: entries are created through
        # EntityEntryAPI (EntityPermission.has_permission) and
        # EntryCreateSerializer.validate both require Writable on the schema.
        "entry.api_v2.views.EntryPermission",
        # ACLAPI only exposes retrieve/update.
        "acl.api_v2.views.ACLPermission",
    }

    # Views whose permission wiring is security critical. Removing the gate from any
    # of them would re-open a privilege escalation.
    EXPECTED_GATES = {
        "GroupAPI": {
            "create": "UserPermission",
            "update": "UserPermission",
            "destroy": "UserPermission",
        },
        "GroupImportAPI": {"post": "IsSuperuser"},
        "UserImportAPI": {"post": "IsSuperuser"},
        "RoleImportAPI": {"post": "IsSuperuser"},
    }

    def _iter_view_classes(self) -> Iterator[type[ViewSetMixin]]:
        def walk(
            patterns: list[URLPattern | URLResolver],
        ) -> Iterator[type[ViewSetMixin]]:
            for pattern in patterns:
                if isinstance(pattern, URLResolver):
                    yield from walk(pattern.url_patterns)
                else:
                    view_class = getattr(pattern.callback, "cls", None)
                    # GenericViewSet is not a subclass of ViewSet; both derive
                    # from ViewSetMixin, so that is what we key on.
                    if view_class and issubclass(view_class, ViewSetMixin):
                        yield view_class

        yield from walk(get_resolver().url_patterns)

    def _permission_classes(self, permission: Any) -> Iterator[type[BasePermission]]:
        # `IsAuthenticated & Foo` is an OperandHolder, not a class.
        if hasattr(permission, "op1_class"):
            yield from self._permission_classes(permission.op1_class)
            yield from self._permission_classes(permission.op2_class)
        else:
            yield permission

    def test_no_object_only_permission_class_is_added(self) -> None:
        found: set[str] = set()
        for view_class in set(self._iter_view_classes()):
            for permission in view_class.permission_classes:
                for permission_class in self._permission_classes(permission):
                    # BasePermission.has_permission() always returns True, so a
                    # class that does not define its own has_permission decides
                    # nothing for collection actions such as create.
                    if "has_permission" not in permission_class.__dict__:
                        found.add(
                            "%s.%s" % (permission_class.__module__, permission_class.__name__)
                        )

        self.assertEqual(
            found,
            self.ALLOWED_OBJECT_ONLY_PERMISSIONS,
            "Object-only permission classes reached a ViewSet: %s" % sorted(found),
        )

    def test_privileged_views_keep_their_gates(self) -> None:
        for view_class in set(self._iter_view_classes()):
            expected = self.EXPECTED_GATES.get(view_class.__name__)
            if expected is None:
                continue

            names = {
                permission_class.__name__
                for permission in view_class.permission_classes
                for permission_class in self._permission_classes(permission)
            }
            self.assertTrue(
                set(expected.values()) <= names,
                "%s lost its permission gate (expected %s, got %s)"
                % (view_class.__name__, expected, names),
            )
