import json
import os
import subprocess
import sys
from unittest.mock import patch

from django.test import SimpleTestCase

from airone.lib.regex import MAX_MATCH_LENGTH, MAX_PATTERN_LENGTH, RegexValidationError
from airone.lib.test import AironeViewTest
from airone.lib.types import AttrType
from entity.models import Entity
from entry.models import Entry


class RegexAPIViewTest(AironeViewTest):
    def setUp(self):
        super().setUp()
        self.user = self.guest_login()
        self.entity = self.create_entity(
            self.user,
            "regex-model",
            attrs=[
                {"name": "text", "type": AttrType.STRING},
                {"name": "array", "type": AttrType.ARRAY_STRING},
            ],
        )
        self.entry = self.add_entry(
            self.user,
            "host-01",
            self.entity,
            values={"text": "prefix host-host", "array": ["first", "suffix-12"]},
        )

    def _search(self, patterns, cond_link="or"):
        return self.client.post(
            f"/entry/api/v1/search_entries/{self.entity.id}",
            json.dumps(
                {
                    "cond_link": cond_link,
                    "cond_params": [{"type": "text", "value": pattern} for pattern in patterns],
                }
            ),
            content_type="application/json",
        )

    def test_search_preserves_regex_and_array_conditions(self):
        for patterns, link, expected in [
            ([r"(?P<word>host)-(?P=word)$"], "or", [self.entry.id]),
            ([r"suffix-\d{2}$"], "or", [self.entry.id]),
            ([r"(?<=prefix )host", "suffix-12"], "and", [self.entry.id]),
            (["host", "missing"], "and", []),
            (["host", "missing"], "or", [self.entry.id]),
            (["^host"], "or", []),
            ([""], "or", []),
        ]:
            with self.subTest(patterns=patterns, link=link):
                response = self._search(patterns, link)
                self.assertEqual(response.status_code, 200)
                self.assertEqual([item["id"] for item in response.json()["results"]], expected)

    def test_search_invalid_patterns_return_400_even_without_values(self):
        self.entry.attrs.update(is_active=False)
        for pattern in ("[", "a" * (MAX_PATTERN_LENGTH + 1), "a{1000000000}", 123):
            with self.subTest(pattern=pattern):
                self.assertEqual(self._search([pattern]).status_code, 400)

    def test_search_does_not_silently_truncate_large_values(self):
        self.entry.attrs.get(schema__name="text").add_value(self.user, "a" * (MAX_MATCH_LENGTH + 1))
        response = self._search(["a"])
        self.assertEqual(response.status_code, 400)
        self.assertIn("input exceeds", response.content.decode())

    def test_search_timeout_is_400_for_scalar_and_array(self):
        for attribute in ("text", "array"):
            with self.subTest(attribute=attribute):
                self.entry.attrs.update(is_active=False)
                self.entry.attrs.filter(schema__name=attribute).update(is_active=True)
                with patch(
                    "entry.api_v1.views.RegexBudget.match",
                    side_effect=RegexValidationError("Regular expression evaluation timed out."),
                ):
                    response = self._search(["host"])
                self.assertEqual(response.status_code, 400)
                self.assertIn("timed out", response.content.decode())

    def test_invalid_stored_pattern_rejects_create_and_update(self):
        # Imports and old data can contain a pattern that bypassed entity validation.
        Entity.objects.filter(pk=self.entity.pk).update(item_name_pattern="[")
        response = self.client.post(
            f"/entity/api/v2/{self.entity.id}/entries/",
            json.dumps({"schema": self.entity.id, "name": "new-name", "attrs": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Configured name pattern", str(response.json()["name"]))
        response = self.client.put(
            f"/entry/api/v2/{self.entry.id}/",
            json.dumps({"name": "new-name"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.name, "host-01")
        self.assertFalse(Entry.objects.filter(name="new-name").exists())

    def test_entity_pattern_validation_rejects_invalid_and_compile_expansion(self):
        for pattern in ("[", "a{1000000000}", "(a{1000}){1000}"):
            with self.subTest(pattern=pattern):
                response = self.client.put(
                    f"/entity/api/v2/{self.entity.id}/",
                    json.dumps({"item_name_pattern": pattern}),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("item_name_pattern", response.json())
                self.entity.refresh_from_db()
                self.assertEqual(self.entity.item_name_pattern, "")


class CatastrophicRegexTest(SimpleTestCase):
    def test_real_catastrophic_patterns_are_bounded_at_both_sinks(self):
        # Run the actual sinks with mocked database reads in a disposable process.
        # Reintroducing stdlib re or dropping the timeout cannot hang the test runner.
        script = r"""
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from configurations import setup
setup()

from django.test import RequestFactory
from airone.lib.drf import InvalidValueError
from airone.lib.types import AttrType
from entity.models import Entity
from entry.api_v1.views import search_entries
from entry.api_v2.serializers import EntryUpdateSerializer
from entry.models import Entry

bad_value = "a" * 100 + "!"
entity = Entity(name="model", item_name_pattern="(a|aa)+$")
entry = Entry(name="original", schema=entity)
serializer = EntryUpdateSerializer(instance=entry)
with patch.object(Entry.objects, "filter") as entries:
    entries.return_value.exists.return_value = False
    try:
        serializer.validate_name(bad_value)
    except InvalidValueError as exc:
        assert "timed out" in str(exc), str(exc)
    else:
        raise AssertionError("Name validation accepted a catastrophic pattern")

    # This classic exponential stdlib pattern is optimized by regex and fails fast.
    entity.item_name_pattern = "(a+)+$"
    try:
        serializer.validate_name(bad_value)
    except InvalidValueError as exc:
        assert "doesn't match" in str(exc.detail[0]), str(exc)
    else:
        raise AssertionError("Invalid name accepted")

for kind in (AttrType.STRING, AttrType.ARRAY_STRING):
    attr = Mock(schema=SimpleNamespace(type=kind))
    if kind == AttrType.STRING:
        attr.get_latest_value.return_value = SimpleNamespace(value=bad_value)
    else:
        attr.get_latest_value.return_value.data_array.all.return_value = [
            SimpleNamespace(value=bad_value)
        ]
    fake_entry = Mock()
    fake_entry.attrs.filter.return_value = [attr]
    request = RequestFactory().post(
        "/entry/api/v1/search_entries/1",
        json.dumps({"cond_params": [{"type": "text", "value": "(a|aa)+$"}]}),
        content_type="application/json",
    )
    request.user = SimpleNamespace(is_authenticated=True)
    with patch.object(Entity.objects, "filter") as entities:
        entities.return_value.exists.return_value = True
        with patch.object(Entry.objects, "order_by") as entries:
            entries.return_value.filter.return_value.all.return_value = [fake_entry]
            response = search_entries(request, "1")
    assert response.status_code == 400, response.content
    assert b"timed out" in response.content, response.content
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
            env={
                **os.environ,
                "PAGODA_LITE": "1",
                "DJANGO_SETTINGS_MODULE": "airone.settings",
                "DJANGO_CONFIGURATION": "Dev",
            },
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
