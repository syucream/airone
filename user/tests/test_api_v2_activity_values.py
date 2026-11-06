"""Activity serialization tests for supported attribute types."""

import json

from rest_framework import status

from airone.lib.test import AironeViewTest
from airone.lib.types import AttrType
from group.models import Group
from role.models import Role
from user.models import User


class ActivityAttributeValuesAPITest(AironeViewTest):
    def _setup_attr_update_activity(
        self, user: User, attr_name: str, attr_type: AttrType, values: list
    ):
        """Create model/item and update attr via API. values=[initial, updated].
        Returns (model, item). The most recent PUT sets values[-1]; prev is values[-2]."""
        model = self.create_entity(
            user, "TestModel", attrs=[{"name": attr_name, "type": attr_type}]
        )
        item = self.add_entry(user, "TestItem", model, values={attr_name: values[0]})
        item.attrs.get(schema__name=attr_name).add_value(user, values[1])

        target_attr = model.attrs.get(name=attr_name)
        for value in values:
            params = {
                "name": item.name,
                "attrs": [{"id": target_attr.id, "value": value}],
            }
            resp = self.client.put(
                "/entry/api/v2/%s/" % item.id,
                json.dumps(params),
                "application/json",
            )
            self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)

        return model, item

    def _assert_latest_update_activity(
        self,
        resp,
        item,
        model,
        attr_name: str,
        attr_type: AttrType,
        curr_value,
        prev_value,
    ):
        """Assert that resp.json()[0] is a correctly structured update activity."""
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["action_type"], "update")
        self.assertEqual(resp.json()[0]["target_type"], "item")
        self.assertEqual(resp.json()[0]["target"]["item_id"], item.id)
        self.assertEqual(resp.json()[0]["target"]["attr"]["attribute_name"], attr_name)
        self.assertEqual(resp.json()[0]["target"]["attr"]["type"], attr_type)
        self.assertEqual(resp.json()[0]["target"]["attr"]["curr_value"]["value"], curr_value)
        self.assertEqual(resp.json()[0]["target"]["attr"]["prev_value"]["value"], prev_value)
        self.assertEqual(resp.json()[0]["target"]["model"]["model_id"], model.id)

    def test_get_activity_has_text_typed_record(self):
        user = self.guest_login()

        # prepare to create Model and Item for testing user activity API
        model, item = self._setup_attr_update_activity(
            user, "text_attr", AttrType.TEXT, ["test", "updated text"]
        )

        # call API to get recent activity of target user
        resp = self.client.get("/user/api/v2/%s/activity" % user.id)

        # check that the latest activity has expected data
        self._assert_latest_update_activity(
            resp, item, model, "text_attr", AttrType.TEXT, "updated text", "test"
        )

    def test_get_activity_has_boolean_typed_record(self):
        user = self.guest_login()

        # prepare to create Model and Item for testing user activity API
        model, item = self._setup_attr_update_activity(
            user, "bool_attr", AttrType.BOOLEAN, [False, True]
        )

        # call API to get recent activity of target user
        resp = self.client.get("/user/api/v2/%s/activity" % user.id)

        # check that the latest activity has expected data
        self._assert_latest_update_activity(
            resp, item, model, "bool_attr", AttrType.BOOLEAN, True, False
        )

    def test_get_activity_has_array_string_typed_record(self):
        user = self.guest_login()

        # prepare to create Model and Item for testing user activity API
        model, item = self._setup_attr_update_activity(
            user,
            "arr_str_attr",
            AttrType.ARRAY_STRING,
            [["foo", "bar"], ["baz", "qux"]],
        )

        # call API to get recent activity of target user
        resp = self.client.get("/user/api/v2/%s/activity" % user.id)

        # check that the latest activity has expected data
        self._assert_latest_update_activity(
            resp,
            item,
            model,
            "arr_str_attr",
            AttrType.ARRAY_STRING,
            ["baz", "qux"],
            ["foo", "bar"],
        )

    def test_get_activity_has_named_object_typed_record(self):
        user = self.guest_login()

        # prepare referral model and item
        ref_model = self.create_entity(user, "RefModel")
        ref_item = self.add_entry(user, "RefItem", ref_model)

        # prepare to create Model and Item for testing user activity API
        model, item = self._setup_attr_update_activity(
            user,
            "named_obj_attr",
            AttrType.NAMED_OBJECT,
            [
                {"name": "label1", "id": ref_item.id},
                {"name": "label2", "id": ref_item.id},
            ],
        )

        # call API to get recent activity of target user
        resp = self.client.get("/user/api/v2/%s/activity" % user.id)

        # check that the latest activity has expected data
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["action_type"], "update")
        self.assertEqual(resp.json()[0]["target"]["attr"]["attribute_name"], "named_obj_attr")
        self.assertEqual(resp.json()[0]["target"]["attr"]["type"], AttrType.NAMED_OBJECT)
        self.assertEqual(resp.json()[0]["target"]["model"]["model_id"], model.id)

        curr = resp.json()[0]["target"]["attr"]["curr_value"]["value"]
        self.assertEqual(curr["name"], "label2")
        self.assertEqual(curr["object"]["id"], ref_item.id)
        self.assertEqual(curr["object"]["name"], ref_item.name)
        self.assertEqual(curr["object"]["model"]["id"], ref_model.id)

        prev = resp.json()[0]["target"]["attr"]["prev_value"]["value"]
        self.assertEqual(prev["name"], "label1")
        self.assertEqual(prev["object"]["id"], ref_item.id)
        self.assertEqual(prev["object"]["name"], ref_item.name)
        self.assertEqual(prev["object"]["model"]["id"], ref_model.id)

    def test_get_activity_has_number_typed_record(self):
        user = self.guest_login()
        model, item = self._setup_attr_update_activity(
            user, "num_attr", AttrType.NUMBER, [1.5, 2.5]
        )

        resp = self.client.get("/user/api/v2/%s/activity" % user.id)

        self._assert_latest_update_activity(
            resp, item, model, "num_attr", AttrType.NUMBER, 2.5, 1.5
        )

    def test_get_activity_has_date_typed_record(self):
        user = self.guest_login()
        model, item = self._setup_attr_update_activity(
            user, "date_attr", AttrType.DATE, ["2024-01-01", "2024-06-15"]
        )

        resp = self.client.get("/user/api/v2/%s/activity" % user.id)

        self._assert_latest_update_activity(
            resp, item, model, "date_attr", AttrType.DATE, "2024-06-15", "2024-01-01"
        )

    def test_get_activity_has_datetime_typed_record(self):
        user = self.guest_login()
        model, item = self._setup_attr_update_activity(
            user,
            "dt_attr",
            AttrType.DATETIME,
            ["2024-01-01T00:00:00+00:00", "2024-06-15T12:30:00+00:00"],
        )

        resp = self.client.get("/user/api/v2/%s/activity" % user.id)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["target"]["attr"]["type"], AttrType.DATETIME)
        curr = resp.json()[0]["target"]["attr"]["curr_value"]["value"]
        prev = resp.json()[0]["target"]["attr"]["prev_value"]["value"]
        self.assertTrue(curr.startswith("2024-06-15"))
        self.assertTrue(prev.startswith("2024-01-01"))

    def test_get_activity_has_group_typed_record(self):
        user = self.guest_login()
        group1 = Group.objects.create(name="Group1")
        group2 = Group.objects.create(name="Group2")
        model, item = self._setup_attr_update_activity(
            user, "group_attr", AttrType.GROUP, [group1.id, group2.id]
        )

        resp = self.client.get("/user/api/v2/%s/activity" % user.id)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["target"]["attr"]["type"], AttrType.GROUP)
        curr = resp.json()[0]["target"]["attr"]["curr_value"]["value"]
        prev = resp.json()[0]["target"]["attr"]["prev_value"]["value"]
        self.assertEqual(curr["id"], group2.id)
        self.assertEqual(curr["name"], group2.name)
        self.assertEqual(prev["id"], group1.id)
        self.assertEqual(prev["name"], group1.name)

    def test_get_activity_has_role_typed_record(self):
        user = self.guest_login()
        role1 = Role.objects.create(name="Role1")
        role2 = Role.objects.create(name="Role2")
        model, item = self._setup_attr_update_activity(
            user, "role_attr", AttrType.ROLE, [role1.id, role2.id]
        )

        resp = self.client.get("/user/api/v2/%s/activity" % user.id)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["target"]["attr"]["type"], AttrType.ROLE)
        curr = resp.json()[0]["target"]["attr"]["curr_value"]["value"]
        prev = resp.json()[0]["target"]["attr"]["prev_value"]["value"]
        self.assertEqual(curr["id"], role2.id)
        self.assertEqual(curr["name"], role2.name)
        self.assertEqual(prev["id"], role1.id)
        self.assertEqual(prev["name"], role1.name)

    def test_get_activity_has_array_number_typed_record(self):
        user = self.guest_login()
        model, item = self._setup_attr_update_activity(
            user, "arr_num_attr", AttrType.ARRAY_NUMBER, [[1.5, 2.5], [3.5, 4.5]]
        )

        resp = self.client.get("/user/api/v2/%s/activity" % user.id)

        self._assert_latest_update_activity(
            resp, item, model, "arr_num_attr", AttrType.ARRAY_NUMBER, [3.5, 4.5], [1.5, 2.5]
        )

    def test_get_activity_has_array_object_typed_record(self):
        user = self.guest_login()
        ref_model = self.create_entity(user, "RefModel")
        ref_item1 = self.add_entry(user, "RefItem1", ref_model)
        ref_item2 = self.add_entry(user, "RefItem2", ref_model)
        model, item = self._setup_attr_update_activity(
            user,
            "arr_obj_attr",
            AttrType.ARRAY_OBJECT,
            [[ref_item1.id], [ref_item2.id]],
        )

        resp = self.client.get("/user/api/v2/%s/activity" % user.id)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["target"]["attr"]["type"], AttrType.ARRAY_OBJECT)
        curr = resp.json()[0]["target"]["attr"]["curr_value"]["value"]
        prev = resp.json()[0]["target"]["attr"]["prev_value"]["value"]
        self.assertEqual(len(curr), 1)
        self.assertEqual(curr[0]["id"], ref_item2.id)
        self.assertEqual(curr[0]["name"], ref_item2.name)
        self.assertEqual(curr[0]["model"]["id"], ref_model.id)
        self.assertEqual(len(prev), 1)
        self.assertEqual(prev[0]["id"], ref_item1.id)

    def test_get_activity_has_array_named_object_typed_record(self):
        user = self.guest_login()
        ref_model = self.create_entity(user, "RefModel")
        ref_item = self.add_entry(user, "RefItem", ref_model)
        model, item = self._setup_attr_update_activity(
            user,
            "arr_named_attr",
            AttrType.ARRAY_NAMED_OBJECT,
            [
                [{"name": "label1", "id": ref_item.id}],
                [{"name": "label2", "id": ref_item.id}],
            ],
        )

        resp = self.client.get("/user/api/v2/%s/activity" % user.id)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["target"]["attr"]["type"], AttrType.ARRAY_NAMED_OBJECT)
        curr = resp.json()[0]["target"]["attr"]["curr_value"]["value"]
        prev = resp.json()[0]["target"]["attr"]["prev_value"]["value"]
        self.assertEqual(len(curr), 1)
        self.assertEqual(curr[0]["name"], "label2")
        self.assertEqual(curr[0]["object"]["id"], ref_item.id)
        self.assertEqual(curr[0]["object"]["model"]["id"], ref_model.id)
        self.assertEqual(len(prev), 1)
        self.assertEqual(prev[0]["name"], "label1")
        self.assertEqual(prev[0]["object"]["id"], ref_item.id)

    def test_get_activity_has_array_group_typed_record(self):
        user = self.guest_login()
        group1 = Group.objects.create(name="ArrGroup1")
        group2 = Group.objects.create(name="ArrGroup2")
        model, item = self._setup_attr_update_activity(
            user, "arr_group_attr", AttrType.ARRAY_GROUP, [[group1.id], [group2.id]]
        )

        resp = self.client.get("/user/api/v2/%s/activity" % user.id)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["target"]["attr"]["type"], AttrType.ARRAY_GROUP)
        curr = resp.json()[0]["target"]["attr"]["curr_value"]["value"]
        prev = resp.json()[0]["target"]["attr"]["prev_value"]["value"]
        self.assertEqual(len(curr), 1)
        self.assertEqual(curr[0]["id"], group2.id)
        self.assertEqual(curr[0]["name"], group2.name)
        self.assertEqual(len(prev), 1)
        self.assertEqual(prev[0]["id"], group1.id)

    def test_get_activity_has_array_role_typed_record(self):
        user = self.guest_login()
        role1 = Role.objects.create(name="ArrRole1")
        role2 = Role.objects.create(name="ArrRole2")
        model, item = self._setup_attr_update_activity(
            user, "arr_role_attr", AttrType.ARRAY_ROLE, [[role1.id], [role2.id]]
        )

        resp = self.client.get("/user/api/v2/%s/activity" % user.id)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["target"]["attr"]["type"], AttrType.ARRAY_ROLE)
        curr = resp.json()[0]["target"]["attr"]["curr_value"]["value"]
        prev = resp.json()[0]["target"]["attr"]["prev_value"]["value"]
        self.assertEqual(len(curr), 1)
        self.assertEqual(curr[0]["id"], role2.id)
        self.assertEqual(curr[0]["name"], role2.name)
        self.assertEqual(len(prev), 1)
        self.assertEqual(prev[0]["id"], role1.id)
