import json

from airone.lib.test import AironeViewTest
from airone.lib.types import AttrType
from entity.models import EntityAttr
from entry.tests.test_api_v2 import BaseViewTest
from group.models import Group
from role.models import Role


class AttributeLifecycleApprovalGateTest(AironeViewTest):
    """Exercise every supported attribute type against the real persistence layer."""

    def test_all_18_attribute_types_survive_create_retrieve_and_update(self):
        user = self.admin_login()
        group = Group.objects.create(name="gate-group")
        role = Role.objects.create(name="gate-role")
        ref_entity = self.create_entity(user, "gate-reference")
        ref_entry = self.add_entry(user, "gate-reference-entry", ref_entity)

        attrs = [dict(attr) for attr in self.ALL_TYPED_ATTR_PARAMS_FOR_CREATING_ENTITY]
        for attr in attrs:
            if attr["type"] & AttrType.OBJECT:
                attr["ref"] = ref_entity
        attrs.extend(
            [
                {"name": "select", "type": AttrType.SELECT},
                {"name": "multi_select", "type": AttrType.MULTI_SELECT},
            ]
        )
        entity = self.create_entity(user, "gate-all-types", attrs=attrs)
        choices = [
            {"value": "first", "label": "First"},
            {"value": "second", "label": "Second"},
        ]
        EntityAttr.objects.filter(
            parent_entity=entity, type__in=[AttrType.SELECT, AttrType.MULTI_SELECT]
        ).update(choices=choices)

        initial_values = {
            "val": "alpha",
            "vals": ["alpha", "beta"],
            "ref": ref_entry.id,
            "refs": [ref_entry.id],
            "name": {"name": "named-alpha", "id": ref_entry.id},
            "names": [{"name": "named-alpha", "id": ref_entry.id}],
            "group": group.id,
            "groups": [group.id],
            "bool": True,
            "text": "long alpha",
            "date": "2026-01-02",
            "role": role.id,
            "roles": [role.id],
            "datetime": "2026-01-02T03:04:05+00:00",
            "num": 12.5,
            "nums": [1, 2.5],
            "select": "first",
            "multi_select": ["first", "second"],
        }
        entry = self.add_entry(user, "gate-entry", entity, values=initial_values)

        self.assertEqual(entry.attrs.count(), 18)
        expected_types = {
            attr["type"] for attr in self.ALL_TYPED_ATTR_PARAMS_FOR_CREATING_ENTITY
        } | {AttrType.SELECT, AttrType.MULTI_SELECT}
        self.assertEqual(
            {attr.schema.type for attr in entry.attrs.select_related("schema")}, expected_types
        )
        response = self.client.get(f"/entry/api/v2/{entry.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["attrs"]), 18)

        updated_values = {
            **initial_values,
            "val": "omega",
            "vals": ["omega"],
            "bool": False,
            "text": "long omega",
            "date": "2027-02-03",
            "datetime": "2027-02-03T04:05:06+00:00",
            "num": 99,
            "nums": [99, 100.5],
            "select": "second",
            "multi_select": ["second"],
        }
        for attr_name, value in updated_values.items():
            entry.attrs.get(schema__name=attr_name).add_value(user, value)
        entry.register_es()

        self.assertEqual(
            entry.attrs.get(schema__name="val").get_latest_value().get_value(), "omega"
        )
        self.assertEqual(
            entry.attrs.get(schema__name="nums").get_latest_value().get_value(), [99, 100.5]
        )
        self.assertEqual(
            entry.attrs.get(schema__name="select").get_latest_value().get_value(),
            {"value": "second", "label": "Second"},
        )
        self.assertEqual(
            entry.attrs.get(schema__name="multi_select").get_latest_value().get_value(),
            [{"value": "second", "label": "Second"}],
        )
        response = self.client.get(f"/entry/api/v2/{entry.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["attrs"]), 18)


class AdvancedSearchPagingApprovalGateTest(BaseViewTest):
    def test_advanced_search_limit_and_offset_are_stable(self):
        for name in ["page-alpha", "page-bravo", "page-charlie"]:
            self.add_entry(self.user, name, self.entity, values={"val": name})

        response = self.client.post(
            "/entry/api/v2/advanced_search/",
            json.dumps(
                {
                    "entities": [self.entity.id],
                    "attrinfo": [{"name": "val"}],
                    "entry_limit": 1,
                    "entry_offset": 1,
                    "sort": {"target_attrname": "__entry_name__", "order": "asc"},
                }
            ),
            "application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_count"], 3)
        self.assertEqual(response.json()["count"], 3)
        self.assertEqual(len(response.json()["values"]), 1)
        self.assertEqual(response.json()["values"][0]["entry"]["name"], "page-bravo")
