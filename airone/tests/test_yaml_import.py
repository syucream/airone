from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from airone.lib.test import AironeViewTest
from airone.tests.test_yaml import alias_tree
from common.tests.compat import post_import
from entity.models import Entity
from entry.models import Entry
from job.models import Job
from role import tasks as role_tasks
from role.models import Role


class YAMLImportSecurityTest(AironeViewTest):
    def test_every_v2_import_parser_rejects_cycles_before_serialization(self):
        self.admin_login()
        urls = (
            "/common/api/v2/import",
            "/common/api/v2/import/preview",
            "/entry/api/v2/import/",
            "/entry/api/v2/import/preview/",
            "/entity/api/v2/import",
            "/entity/api/v2/import/preview",
            "/role/api/v2/import",
            "/user/api/v2/import/",
            "/group/api/v2/groups/import",
        )
        with (
            patch("job.models.serialize_job_params") as serialize,
            patch("rest_framework.serializers.BaseSerializer.is_valid") as validate,
        ):
            for url in urls:
                with self.subTest(url=url):
                    response = self.client.post(url, "&a [*a]", content_type="application/yaml")
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json()["code"], "AE-140000")
            serialize.assert_not_called()
            validate.assert_not_called()
        self.assertFalse(Job.objects.exists())

    def test_entry_alias_bomb_is_rejected_before_job_creation_for_regular_user(self):
        user = self.guest_login()
        entity = Entity.objects.create(name="import-target", created_user=user)
        source = (
            f"- entity: {entity.name}\n"
            "  entries:\n"
            "    - name: imported-entry\n"
            "      attrs:\n"
            "        - name: attribute\n"
            "          value:\n            " + alias_tree().replace("\n", "\n            ")
        )
        self._assert_bomb_rejected(
            source,
            (
                "/entry/api/v2/import/",
                "/entry/api/v2/import/preview/",
                "/common/api/v2/import",
                "/common/api/v2/import/preview",
            ),
        )
        self.assertFalse(Entry.objects.exists())

    def test_role_permission_alias_bomb_is_rejected_before_validation_and_job_creation(self):
        user = self.admin_login()
        entity = Entity.objects.create(name="permission-target", created_user=user)
        source = (
            "- name: imported-role\n"
            "  users: []\n"
            "  groups: []\n"
            "  admin_users: []\n"
            "  admin_groups: []\n"
            "  permissions:\n"
            f"    - obj_id: {entity.id}\n"
            "      permission: readable\n"
            "      extra:\n        " + alias_tree().replace("\n", "\n        ")
        )
        self._assert_bomb_rejected(source, ("/role/api/v2/import", "/common/api/v2/import"))
        self.assertFalse(Role.objects.exists())

    def test_common_entity_unknown_field_is_checked_before_serializer_discards_it(self):
        self.guest_login()
        source = "Entity: []\nEntityAttr: []\nignored:\n  " + alias_tree().replace("\n", "\n  ")
        self._assert_bomb_rejected(
            source, ("/common/api/v2/import", "/common/api/v2/import/preview")
        )
        self.assertFalse(Entity.objects.exists())

    def _assert_bomb_rejected(self, source, urls):
        with (
            patch("job.models.serialize_job_params") as serialize,
            patch("rest_framework.serializers.BaseSerializer.is_valid") as validate,
        ):
            for url in urls:
                with self.subTest(url=url):
                    response = self.client.post(url, source, content_type="application/yaml")
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json()["code"], "AE-140000")
                    self.assertIn("expanded node limit", response.json()["message"])
            validate.assert_not_called()
            serialize.assert_not_called()
        self.assertFalse(Job.objects.exists())

    def test_oversized_request_is_a_parse_error_without_job_creation(self):
        self.guest_login()
        with (
            patch("airone.lib.yaml.MAX_YAML_BYTES", 100),
            patch("job.models.serialize_job_params") as serialize,
        ):
            response = self.client.post(
                "/common/api/v2/import", "#" + "a" * 100, content_type="application/yaml"
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["code"], "AE-140000")
            self.assertIn("input size", response.json()["message"])
            serialize.assert_not_called()
        self.assertFalse(Job.objects.exists())

    @patch("role.tasks.import_role_v2.delay", Mock(side_effect=role_tasks.import_role_v2))
    def test_normal_role_aliases_survive_validation_and_job_serialization(self):
        self.admin_login()
        source = (
            "- name: imported-role\n"
            "  users: &empty []\n"
            "  groups: *empty\n"
            "  admin_users: *empty\n"
            "  admin_groups: *empty\n"
            "  permissions: *empty\n"
        )
        response = post_import(self, "/role/api/v2/import", source)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Role.objects.filter(name="imported-role").exists())
        self.assertEqual(Job.objects.count(), 1)

    def test_legacy_imports_reject_aliases_before_jobs_or_resource_imports(self):
        user = self.admin_login()
        entity = Entity.objects.create(name="legacy-target", created_user=user)
        urls = (
            reverse("entry:do_import", args=[entity.id]),
            reverse("dashboard:do_import"),
            reverse("group:do_import_user_and_group"),
        )
        with (
            patch("job.models.serialize_job_params") as serialize,
            patch("dashboard.views.EntityResource.import_data_from_request") as import_resource,
        ):
            for source in ("&a [*a]", alias_tree(), alias_tree(merge=True)):
                for url in urls:
                    with self.subTest(url=url, source=source[:30]):
                        upload = SimpleUploadedFile("import.yaml", source.encode())
                        response = self.client.post(url, {"file": upload})
                        self.assertEqual(response.status_code, 400)
            serialize.assert_not_called()
            import_resource.assert_not_called()
        self.assertFalse(Job.objects.exists())
        self.assertFalse(Entry.objects.exists())
        self.assertEqual(Entity.objects.count(), 1)

    def test_legacy_imports_reject_invalid_scalars_as_client_errors(self):
        user = self.admin_login()
        entity = Entity.objects.create(name="legacy-target", created_user=user)
        for url in (
            reverse("entry:do_import", args=[entity.id]),
            reverse("dashboard:do_import"),
            reverse("group:do_import_user_and_group"),
        ):
            for source in ("date: 2026-99-99", "number: " + "1" * 4400):
                with self.subTest(url=url, source=source[:30]):
                    upload = SimpleUploadedFile("import.yaml", source.encode())
                    response = self.client.post(url, {"file": upload})
                    self.assertEqual(response.status_code, 400)
        self.assertFalse(Job.objects.exists())
