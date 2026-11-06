"""User management, permissions, and import/export API tests."""

import json
from unittest.mock import patch

import yaml
from rest_framework import status

from airone.lib.test import AironeViewTest, load_export_payload
from common.lib.import_detector import ImportType
from common.tests.compat import post_import
from group.models import Group
from job.models import Job, JobStatus
from role.models import Role
from user.models import User
from user.tests.helpers import UserFixtureMixin


class UserManagementAPITest(UserFixtureMixin, AironeViewTest):
    def test_get_user(self):
        login_user = self.guest_login()

        resp = self.client.get("/user/api/v2/%s/" % login_user.id)
        self.assertEqual(resp.status_code, 200)

        body = resp.json()
        self.assertEqual(body["id"], login_user.id)
        self.assertEqual(body["username"], login_user.username)
        self.assertEqual(body["email"], login_user.email)
        self.assertEqual(body["is_superuser"], login_user.is_superuser)
        self.assertEqual(body["date_joined"], login_user.date_joined.isoformat())
        self.assertEqual(body["token"], None)

        other = self._create_user("test1", "test1@example.com")
        resp = self.client.get("/user/api/v2/%s/" % other.id)
        self.assertEqual(resp.status_code, 403)

        # parent user can retrieve their co-user
        co_user = self._create_user("co_user", "co@example.com", parent_user=login_user)
        resp = self.client.get("/user/api/v2/%s/" % co_user.id)
        self.assertEqual(resp.status_code, 200)

    def test_update_other_user_by_guest_is_forbidden(self):
        self.guest_login()
        other_user = self._create_user("other")

        resp = self.client.put(
            "/user/api/v2/%d/" % other_user.id,
            json.dumps(
                {
                    "username": other_user.username,
                    "email": other_user.email,
                    "is_superuser": other_user.is_superuser,
                    "token_lifetime": 3600,
                }
            ),
            "application/json",
        )

        self.assertEqual(resp.status_code, 403)

    def test_get_user_includes_created_readonly_users(self):
        parent_user = self.guest_login()
        co_user = self._create_user("co_user", parent_user=parent_user)

        resp = self.client.get("/user/api/v2/%d/" % parent_user.id)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json()["co_users"],
            [{"id": co_user.id, "username": co_user.username}],
        )

    def test_get_user_groups_and_roles(self):
        login_user = self.guest_login()

        parent_group = self._create_group("parent_group")
        child_group = Group.objects.create(name="child_group", parent_group=parent_group)
        login_user.groups.add(child_group)

        direct_role = Role.objects.create(name="direct_role")
        direct_role.users.add(login_user)
        group_role = Role.objects.create(name="group_role")
        group_role.groups.add(child_group)
        admin_role = Role.objects.create(name="admin_role")
        admin_role.admin_groups.add(parent_group)

        resp = self.client.get("/user/api/v2/%s/" % login_user.id)
        self.assertEqual(resp.status_code, 200)

        body = resp.json()
        self.assertEqual(
            body["groups"],
            [
                {
                    "id": child_group.id,
                    "name": "child_group",
                    "display_name": "",
                    "is_direct": True,
                },
                {
                    "id": parent_group.id,
                    "name": "parent_group",
                    "display_name": "",
                    "is_direct": False,
                },
            ],
        )
        self.assertEqual(
            body["roles"],
            [
                {
                    "id": admin_role.id,
                    "name": "admin_role",
                    "is_direct": False,
                    "is_admin": True,
                    "via_groups": [
                        {"id": parent_group.id, "name": "parent_group", "display_name": ""}
                    ],
                },
                {
                    "id": direct_role.id,
                    "name": "direct_role",
                    "is_direct": True,
                    "is_admin": False,
                    "via_groups": [],
                },
                {
                    "id": group_role.id,
                    "name": "group_role",
                    "is_direct": False,
                    "is_admin": False,
                    "via_groups": [
                        {"id": child_group.id, "name": "child_group", "display_name": ""}
                    ],
                },
            ],
        )

    def test_get_user_groups_and_roles_when_user_belongs_to_nothing(self):
        login_user = self.guest_login()

        resp = self.client.get("/user/api/v2/%s/" % login_user.id)
        self.assertEqual(resp.status_code, 200)

        body = resp.json()
        self.assertEqual(body["groups"], [])
        self.assertEqual(body["roles"], [])

    def test_get_user_excludes_deleted_groups_and_roles(self):
        login_user = self.guest_login()

        active_group = self._create_group("active_group")
        deleted_group = self._create_group("deleted_group")
        login_user.groups.add(active_group, deleted_group)
        deleted_group.is_active = False
        deleted_group.save(update_fields=["is_active"])

        active_role = Role.objects.create(name="active_role")
        active_role.users.add(login_user)
        deleted_role = Role.objects.create(name="deleted_role", is_active=False)
        deleted_role.users.add(login_user)

        resp = self.client.get("/user/api/v2/%s/" % login_user.id)
        self.assertEqual(resp.status_code, 200)

        body = resp.json()
        self.assertEqual([g["name"] for g in body["groups"]], ["active_group"])
        self.assertEqual([r["name"] for r in body["roles"]], ["active_role"])

    def test_get_me(self):
        login_user = self.guest_login()
        co_user1 = self._create_user("guest-co1", "co1@example.com", parent_user=login_user)
        co_user2 = self._create_user("guest-co2", "co2@example.com", parent_user=login_user)

        resp = self.client.get("/user/api/v2/me")
        self.assertEqual(resp.status_code, 200)

        body = resp.json()
        self.assertEqual(body["user_id"], login_user.id)
        self.assertEqual(body["username"], login_user.username)
        self.assertEqual(body["email"], login_user.email)

        co_user_ids = {u["user_id"] for u in body["co_users"]}
        self.assertIn(co_user1.id, co_user_ids)
        self.assertIn(co_user2.id, co_user_ids)

        # unauthenticated access is rejected
        self.client.logout()
        resp = self.client.get("/user/api/v2/me")
        self.assertEqual(resp.status_code, 403)

    def test_list_user(self):
        login_user = self.guest_login()
        admin_user = self._create_user("admin", "admin@example.com", True)

        resp = self.client.get("/user/api/v2/")
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(
            resp.json(),
            {
                "count": 2,
                "next": None,
                "previous": None,
                "results": [
                    {
                        "id": admin_user.id,
                        "username": "admin",
                        "email": "admin@example.com",
                        "is_superuser": True,
                        "is_readonly": False,
                        "date_joined": admin_user.date_joined.isoformat(),
                        "parent_user": None,
                    },
                    {
                        "id": login_user.id,
                        "username": "guest",
                        "email": "",
                        "is_superuser": False,
                        "is_readonly": False,
                        "date_joined": login_user.date_joined.isoformat(),
                        "parent_user": None,
                    },
                ],
            },
        )

    def test_create_user_by_admin(self):
        self.admin_login()

        params = {
            "username": "superuser",
            "email": "superuser@example.com",
            "password": "secret-pass",
            "is_superuser": True,
        }
        resp = self.client.post(
            "/user/api/v2/",
            json.dumps(params),
            "application/json",
        )
        self.assertEqual(resp.status_code, 201)

        created_user = User.objects.filter(username="superuser").first()
        self.assertIsNotNone(created_user)
        self.assertEqual(created_user.email, "superuser@example.com")
        self.assertTrue(created_user.is_superuser)
        self.assertTrue(created_user.check_password("secret-pass"))
        self.assertFalse(created_user.is_readonly)
        self.assertIsNone(created_user.parent_user)

        # check to prevent creating duplicated username user
        resp = self.client.post(
            "/user/api/v2/",
            json.dumps(params),
            "application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()[0]["message"], "User with this username already exists")

    def test_create_superuser_by_guest(self):
        self.guest_login()

        params = {
            "username": "superuser",
            "email": "superuser@example.com",
            "password": "secret-pass",
            "is_superuser": True,
        }
        resp = self.client.post(
            "/user/api/v2/",
            json.dumps(params),
            "application/json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["message"], "You don't have permission to create superuser")

        # check superuser wasn't created, actually.
        self.assertFalse(User.objects.filter(username="superuser").exists())

    def test_create_readonly_by_guest(self):
        guest_user = self.guest_login()

        # for checking wrong duplication error
        # (creating user will be "guest-new-user", so "newuser" won't be duplicated)
        self._create_user("newuser")

        params = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "secret-pass",
            "is_superuser": False,
        }
        resp = self.client.post(
            "/user/api/v2/",
            json.dumps(params),
            "application/json",
        )
        self.assertEqual(resp.status_code, 201)

        # check readonly user was created.
        created_user = User.objects.filter(username=guest_user.username + "-newuser").first()
        self.assertIsNotNone(created_user)
        self.assertEqual(created_user.email, guest_user.email)
        self.assertFalse(created_user.is_superuser)
        self.assertTrue(created_user.check_password("secret-pass"))
        self.assertTrue(created_user.is_readonly)
        self.assertEqual(created_user.parent_user, guest_user)

        # check to prevent creating duplicated username user
        resp = self.client.post(
            "/user/api/v2/",
            json.dumps(params),
            "application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json()["username"][0]["message"], "A user with that username already exists."
        )

    def test_update_user_cannot_grant_superuser_to_themselves(self):
        """A non-superuser must not be able to escalate through a self-update."""
        login_user = self.guest_login()

        resp = self.client.put(
            "/user/api/v2/%d/" % login_user.id,
            json.dumps(
                {
                    "username": login_user.username,
                    "email": "guest@example.com",
                    "is_superuser": True,
                }
            ),
            "application/json",
        )
        self.assertEqual(resp.status_code, 403)

        login_user.refresh_from_db()
        self.assertFalse(login_user.is_superuser)

    def test_update_user_cannot_change_own_username(self):
        """Renaming users is reserved for administrators."""
        login_user = self.guest_login()

        resp = self.client.put(
            "/user/api/v2/%d/" % login_user.id,
            json.dumps(
                {
                    "username": "renamed-by-myself",
                    "email": "guest@example.com",
                    "is_superuser": False,
                }
            ),
            "application/json",
        )
        self.assertEqual(resp.status_code, 403)

        login_user.refresh_from_db()
        self.assertEqual(login_user.username, "guest")

    def test_update_user_with_unchanged_is_superuser(self):
        """A normal self-update (is_superuser is false) has to keep working."""
        login_user = self.guest_login()

        resp = self.client.put(
            "/user/api/v2/%d/" % login_user.id,
            json.dumps(
                {
                    "username": login_user.username,
                    "email": "guest@example.com",
                    "is_superuser": False,
                    "token_lifetime": 3600,
                }
            ),
            "application/json",
        )
        self.assertEqual(resp.status_code, 200)

        login_user.refresh_from_db()
        self.assertEqual(login_user.email, "guest@example.com")
        self.assertEqual(login_user.token_lifetime, 3600)
        self.assertFalse(login_user.is_superuser)

    def test_update_user_is_superuser_by_superuser(self):
        """A superuser is still allowed to grant the privilege to others."""
        self.admin_login()
        user = self._create_user("user")

        resp = self.client.put(
            "/user/api/v2/%d/" % user.id,
            json.dumps(
                {
                    "username": user.username,
                    "email": "user@example.com",
                    "is_superuser": True,
                }
            ),
            "application/json",
        )
        self.assertEqual(resp.status_code, 200)

        user.refresh_from_db()
        self.assertTrue(user.is_superuser)

    def test_delete_user(self):
        self.admin_login()

        user: User = User.objects.create(username="user")
        resp = self.client.delete("/user/api/v2/%d/" % user.id)
        self.assertEqual(resp.status_code, 204)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

        # already deleted case
        resp = self.client.delete("/user/api/v2/%d/" % user.id)
        self.assertEqual(resp.status_code, 404)

    def test_delete_user_without_permission(self):
        self.guest_login()

        user: User = User.objects.create(username="user")
        resp = self.client.delete("/user/api/v2/%d/" % user.id)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(
            resp.json(),
            {
                "code": "AE-210000",
                "message": "You do not have permission to perform this action.",
            },
        )

    def test_delete_own_co_user(self):
        user_guest = self.guest_login()

        # create co-user for guest user
        co_user = self._create_user("co_user", email="co_user@example.com", parent_user=user_guest)

        # delete co-user by parent user
        resp = self.client.delete("/user/api/v2/%d/" % co_user.id)
        self.assertEqual(resp.status_code, 204)

        # check co-user was deleted actually.
        co_user.refresh_from_db()
        self.assertFalse(co_user.is_active)

    def test_import(self):
        self.admin_login()

        self._create_group("Group1")
        self._create_group("Group2")

        fp = self.open_fixture_file("import_user.yaml")
        resp = post_import(self, "/user/api/v2/import/", fp.read(), content_type="application/yaml")

        self.assertEqual(resp.status_code, 200)

        user1 = User.objects.filter(username="User1").first()

        self.assertEqual(user1.email, "user1@example.com")
        self.assertEqual(user1.groups.count(), 2)

    def test_import_by_non_superuser_is_forbidden(self):
        admin = User.objects.create(username="admin", email="admin@example.com", is_superuser=True)
        group = self._create_group("Group1")
        self.guest_login()

        body = yaml.dump(
            [
                {
                    "id": admin.id,
                    "username": "admin",
                    "email": "attacker@example.com",
                    "groups": "",
                },
                {"username": "guest", "email": "guest@example.com", "groups": "Group1"},
            ]
        )
        resp = post_import(self, "/user/api/v2/import/", body, content_type="application/yaml")

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        admin.refresh_from_db()
        self.assertEqual(admin.email, "admin@example.com")
        self.assertFalse(group.user_set.exists())

    def test_export(self):
        self.admin_login()

        group1 = self._create_group("Group1")
        group2 = self._create_group("Group2")

        user1 = self._create_user("user1")
        user1.groups.add(group1)
        user1.groups.add(group2)

        user2 = self._create_user("user2")
        user2.groups.add(group1)

        with patch.object(Job, "run") as enqueue:
            resp = self.client.post("/user/api/v2/export")
        enqueue.assert_called_once_with()
        self.assertEqual(resp.status_code, 202)
        self.assertNotIn("Content-Disposition", resp)
        job = Job.objects.get(id=resp.json()["id"])
        job.run(will_delay=False)
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.DONE)
        resp = self.client.get(f"/job/api/v2/{job.id}/download")
        self.assertEqual(resp.status_code, 200)
        self.assertRegex(
            resp["Content-Disposition"],
            r'^attachment; filename="user_\d{4}_\d{2}_\d{2}_\d{2}_\d{2}\.yaml"$',
        )

        obj = load_export_payload(resp.content, ImportType.USER)
        self.assertTrue(isinstance(obj, list))
        self.assertEqual(len(obj), 3)
