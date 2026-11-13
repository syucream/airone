import json
from html.parser import HTMLParser
from typing import Any, TypedDict, cast

from django.urls import reverse

from airone.lib.test import AironeViewTest, with_airone_settings
from airone.lib.types import AttrType
from entity.models import Entity, EntityAttr


class ScriptElement(TypedDict):
    attrs: dict[str, str | None]
    text: str


class SearchResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[ScriptElement] = []
        self.elements: list[tuple[str, dict[str, str | None]]] = []
        self.current_script: ScriptElement | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self.elements.append((tag, attributes))
        if tag == "script":
            self.current_script = {"attrs": attributes, "text": ""}
            self.scripts.append(self.current_script)

    def handle_data(self, data: str) -> None:
        if self.current_script is not None:
            self.current_script["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.current_script = None


class AdvancedSearchXSSTest(AironeViewTest):
    def setUp(self) -> None:
        super().setUp()
        owner = self.admin_login()
        self.entity = Entity.objects.create(name="search-entity", created_user=owner)
        for name in ["first attribute", "second attribute"]:
            EntityAttr.objects.create(
                name=name,
                type=AttrType.STRING,
                parent_entity=self.entity,
                created_user=owner,
            )
        self.reader = self.guest_login("readonly")
        self.reader.is_readonly = True
        self.reader.save(update_fields=["is_readonly"])

    def parse_result(
        self, params: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], SearchResultParser]:
        response = self.client.get(
            reverse("dashboard:advanced_search_result"),
            {"entity[]": [self.entity.id], **params},
        )
        self.assertEqual(response.status_code, 200)
        parser = SearchResultParser()
        parser.feed(response.content.decode())
        scripts = [
            script
            for script in parser.scripts
            if script["attrs"].get("id") == "advanced-search-hint-attrs"
        ]
        self.assertEqual(len(scripts), 1)
        self.assertEqual(scripts[0]["attrs"].get("type"), "application/json")
        payload = cast(list[dict[str, Any]], json.loads(scripts[0]["text"]))
        self.assertIsInstance(payload, list)
        self.assertEqual(payload, response.context["hint_attrs"])
        return payload, parser

    def test_untrusted_attribute_names_are_json_data(self) -> None:
        names = [
            "xss-trailing-backslash\\",
            '</script><script id="xss-injected">alert(1)</script>',
            '"><img id="xss-injected" src=x onerror=alert(1)>',
            "xss-quotes-'\"-[]#.:&",
            "xss-日本語-\u2028-\u2029-\n-end",
        ]
        for parameter in ["attr[]", "attrinfo"]:
            for name in names:
                with self.subTest(parameter=parameter, name=name):
                    params = (
                        {"attr[]": [name]}
                        if parameter == "attr[]"
                        else {"attrinfo": json.dumps([{"name": name}])}
                    )
                    payload, parser = self.parse_result(params)
                    self.assertEqual([hint["name"] for hint in payload], [name])
                    executable_scripts = "\n".join(
                        script["text"]
                        for script in parser.scripts
                        if script["attrs"].get("type") != "application/json"
                    )
                    self.assertNotIn(name, executable_scripts)
                    self.assertFalse(
                        any(attrs.get("id") == "xss-injected" for _, attrs in parser.elements)
                    )

    def test_multiple_attributes_preserve_order_and_filters(self) -> None:
        hints = [
            {"name": "second attribute", "keyword": "needle '<&", "exact_match": True},
            {"name": "first attribute", "keyword": "other", "exact_match": False},
        ]
        payload, _ = self.parse_result({"attrinfo": json.dumps(hints)})
        self.assertEqual([hint["name"] for hint in payload], [hint["name"] for hint in hints])
        for actual, expected in zip(payload, hints):
            self.assertEqual(actual["keyword"], expected["keyword"])
            self.assertEqual(actual["exact_match"], expected["exact_match"])
        payload, _ = self.parse_result({"attr[]": [hint["name"] for hint in hints]})
        self.assertEqual([hint["name"] for hint in payload], [hint["name"] for hint in hints])

    @with_airone_settings({"LEGACY_UI_DISABLED": True})
    def test_disabled_legacy_ui_returns_404(self) -> None:
        response = self.client.get(
            reverse("dashboard:advanced_search_result"),
            {"entity[]": [self.entity.id], "attr[]": ["first attribute"]},
        )
        self.assertEqual(response.status_code, 404)
