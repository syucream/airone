"""Recent activity visibility, limits, and time-window tests."""

import json
from datetime import timedelta
from unittest import mock

from django.utils import timezone
from rest_framework import status

from airone.lib.acl import ACLType
from airone.lib.test import AironeViewTest
from airone.lib.types import AttrType
from entry import tasks as entry_tasks
from entry.models import Entry
from user.api_v2.views import UserActivityAPI
from user.tests.helpers import UserFixtureMixin


class RecentActivityAPITest(UserFixtureMixin, AironeViewTest):
    @mock.patch(
        "entry.tasks.create_entry_v2.delay", mock.Mock(side_effect=entry_tasks.create_entry_v2)
    )
    @mock.patch("entry.tasks.edit_entry_v2.delay", mock.Mock(side_effect=entry_tasks.edit_entry_v2))
    @mock.patch(
        "entry.tasks.delete_entry_v2.delay", mock.Mock(side_effect=entry_tasks.delete_entry_v2)
    )
    def test_get_recent_activity(self):
        user_guest = self.guest_login()

        # prepare test Users, Models, and Items
        DAIMYO_NAMES = ["MatsunagaHisahide", "OdaNobunaga", "ToyotomiHideyoshi"]
        daimyos = {x: self._create_user(x) for x in DAIMYO_NAMES}
        model_prefecture = self.create_entity(
            user_guest,
            "Prefecture",
            attrs=[
                {"name": "ruler", "type": AttrType.STRING},
            ],
        )
        model_castle = self.create_entity(
            user_guest,
            "Castle",
            attrs=[
                {"name": "location", "type": AttrType.OBJECT, "ref": model_prefecture.id},
                {"name": "designer", "type": AttrType.STRING},
            ],
        )
        item_prefectures = {
            x: self.add_entry(user_guest, x, model_prefecture)
            for x in [
                "Osaka",
                "Kyoto",
                "Nara",
                "Shiga",
                "Fukui",
                "Okayama",
            ]
        }
        item_castles = {
            castle_name: self.add_entry(
                user_guest,
                castle_name,
                model_castle,
                values={
                    "location": item_prefectures[location_name].id,
                },
            )
            for (castle_name, location_name) in [
                ("TsutuiCastle", "Nara"),
                ("IchijodaniCastle", "Fukui"),
                ("BichuTakamatsuCastle", "Okayama"),
            ]
        }

        # change ruler of Kyoto prefecture over the course of history
        attr_ruler_of_kyoto = model_prefecture.attrs.get(name="ruler")
        for daimyo_name in DAIMYO_NAMES:
            # create each castles by specified daimyos
            self.client.login(username=daimyo_name, password=daimyo_name)
            params = {
                "name": item_prefectures["Kyoto"].name,
                "attrs": [
                    {"id": attr_ruler_of_kyoto.id, "value": daimyo_name},
                ],
            }
            resp = self.client.put(
                "/entry/api/v2/%s/" % item_prefectures["Kyoto"].id,
                json.dumps(params),
                "application/json",
            )
            self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)

        # record each castle by each daimyos
        attr_location_of_castle = model_castle.attrs.get(name="location")
        attr_designer_of_castle = model_castle.attrs.get(name="designer")
        for daimyo_name, castle_name, location_name, designer_name in [
            ("MatsunagaHisahide", "TamonzanCastle", "Nara", ""),
            ("OdaNobunaga", "AzuchiCastle", "Shiga", "NiwaNagahide"),
            ("ToyotomiHideyoshi", "OsakaCastle", "Osaka", "KurodaKanbei"),
        ]:
            # create each castles by specified daimyos
            self.client.login(username=daimyo_name, password=daimyo_name)

            # send API request to create castle item
            params = {
                "name": castle_name,
                "attrs": [
                    {"id": attr_location_of_castle.id, "value": item_prefectures[location_name].id},
                    {"id": attr_designer_of_castle.id, "value": designer_name},
                ],
            }
            resp = self.client.post(
                "/entity/api/v2/%s/entries/" % model_castle.id,
                json.dumps(params),
                "application/json",
            )
            self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)

        # destroy castles by each daimyos
        for daimyo_name, castle_name, location_name in [
            ("MatsunagaHisahide", "TsutuiCastle", "Nara"),
            ("OdaNobunaga", "IchijodaniCastle", "Fukui"),
            ("ToyotomiHideyoshi", "BichuTakamatsuCastle", "Okayama"),
        ]:
            # create each castles by specified daimyos
            self.client.login(username=daimyo_name, password=daimyo_name)

            # send API request to delete castle item
            item_castle = Entry.objects.filter(name=castle_name, schema=model_castle).first()
            resp = self.client.delete(
                "/entry/api/v2/%s/" % item_castle.id, None, "application/json"
            )
            self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

        # Here is the main processing of this test case
        TGT_USERNAME = "OdaNobunaga"
        self.client.login(username=TGT_USERNAME, password=TGT_USERNAME)

        # call API to get recent activity of target user
        resp = self.client.get("/user/api/v2/%s/activity" % daimyos[TGT_USERNAME].id)
        self.assertEqual(resp.status_code, 200)

        # response data expect following data structure for each activity
        # create/delete:
        """
        {
            "action_type": "create" | "delete",
            "target_type": "item",
            "target": {
                "item_id": 100,
                "name": "entry name",
                "model": {"id": 10, "name": "model name"},
            },
            "timestamp": "2024-01-01T00:00:00Z",
        }
        """
        # update:
        """
        {
            "action_type": "update",
            "target_type": "item",
            "target": {
                "item_id": 100,
                "item_name": "entry name",
                "attr": {
                    "attribute_id": 200,
                    "attribute_name": "attr name",
                    "type": AttrType.STRING | AttrType.OBJECT | ...,
                    "curr_value": {
                        "attribute_value_id": 300,
                        "value": "current value",
                        "user": {
                            "user_id": 500,
                            "username": "updated user name",
                        },
                    },
                    "prev_value": {
                        "attribute_value_id": 400,
                        "value": "previous value",
                        "user": {
                            "user_id": 600,
                            "username": "previous updated user name",
                        },
                    },
                },
                "model": {"model_id": 10, "model_name": "model name"},
            },
            "timestamp": "2024-01-01T00:00:00Z",
        }
        """
        item_azuchi = Entry.objects.get(name="AzuchiCastle", schema=model_castle)

        # last activity is deleting castle by OdaNobunaga, so check it first
        self.assertEqual(resp.json()[0]["action_type"], "delete")
        self.assertEqual(resp.json()[0]["target_type"], "item")
        self.assertEqual(resp.json()[0]["target"]["item_id"], item_castles["IchijodaniCastle"].id)
        self.assertEqual(resp.json()[0]["target"]["model"]["id"], model_castle.id)

        # before that target user update attribute of created Item (designer is newer than location)
        self.assertEqual(resp.json()[1]["action_type"], "update")
        self.assertEqual(resp.json()[1]["target_type"], "item")
        self.assertEqual(resp.json()[1]["target"]["item_id"], item_azuchi.id)
        self.assertEqual(resp.json()[1]["target"]["attr"]["attribute_name"], "designer")
        self.assertEqual(resp.json()[1]["target"]["attr"]["type"], AttrType.STRING)
        self.assertEqual(resp.json()[1]["target"]["attr"]["curr_value"]["value"], "NiwaNagahide")
        self.assertEqual(resp.json()[1]["target"]["model"]["model_id"], model_castle.id)

        # before that target user update another attribute of created Item
        self.assertEqual(resp.json()[2]["action_type"], "update")
        self.assertEqual(resp.json()[2]["target_type"], "item")
        self.assertEqual(resp.json()[2]["target"]["item_id"], item_azuchi.id)
        self.assertEqual(resp.json()[2]["target"]["attr"]["attribute_name"], "location")
        self.assertEqual(resp.json()[2]["target"]["attr"]["type"], AttrType.OBJECT)
        self.assertEqual(
            resp.json()[2]["target"]["attr"]["curr_value"]["value"]["id"],
            item_prefectures["Shiga"].id,
        )
        self.assertEqual(resp.json()[2]["target"]["attr"]["curr_value"]["value"]["name"], "Shiga")
        self.assertEqual(
            resp.json()[2]["target"]["attr"]["curr_value"]["value"]["model"]["id"],
            model_prefecture.id,
        )
        self.assertEqual(resp.json()[2]["target"]["model"]["model_id"], model_castle.id)

        # before that target user create castle item
        self.assertEqual(resp.json()[3]["action_type"], "create")
        self.assertEqual(resp.json()[3]["target_type"], "item")
        self.assertEqual(resp.json()[3]["target"]["item_id"], item_azuchi.id)
        self.assertEqual(resp.json()[3]["target"]["model"]["id"], model_castle.id)

        # before that target user update attribute of prefecture item
        self.assertEqual(resp.json()[4]["action_type"], "update")
        self.assertEqual(resp.json()[4]["target_type"], "item")
        self.assertEqual(resp.json()[4]["target"]["item_id"], item_prefectures["Kyoto"].id)
        self.assertEqual(resp.json()[4]["target"]["attr"]["attribute_name"], "ruler")
        self.assertEqual(resp.json()[4]["target"]["attr"]["curr_value"]["value"], "OdaNobunaga")
        self.assertEqual(
            resp.json()[4]["target"]["attr"]["prev_value"]["value"], "MatsunagaHisahide"
        )
        self.assertEqual(
            resp.json()[4]["target"]["attr"]["prev_value"]["user"]["user_id"],
            daimyos["MatsunagaHisahide"].id,
        )
        self.assertEqual(resp.json()[4]["target"]["model"]["model_id"], model_prefecture.id)

    def test_prevent_getting_whole_records(self):
        """
        This test case is for checking the prevention of getting whole records of
        recent activity. When a user has many activities, it is not appropriate
        to return all records of them at once.
        """
        user = self.guest_login()
        limit = UserActivityAPI.LIMIT_RECORDS

        entity = self.create_entity(
            user, "TestModel", attrs=[{"name": "val", "type": AttrType.STRING}]
        )

        # Create limit+1 entries to exceed the create activity limit
        entries = [self.add_entry(user, "item-%d" % i, entity) for i in range(limit + 1)]

        # Delete limit+1 entries to exceed the delete activity limit
        for entry in entries:
            entry.delete(deleted_user=user)

        # Create limit+1 attribute updates to exceed the update activity limit
        live = self.add_entry(user, "live", entity)
        attr = live.attrs.get(schema__name="val")
        for i in range(limit + 1):
            attr.add_value(user, "v%d" % i)

        resp = self.client.get("/user/api/v2/%s/activity" % user.id)
        self.assertEqual(resp.status_code, 200)

        activities = resp.json()
        self.assertLessEqual(sum(1 for a in activities if a["action_type"] == "create"), limit)
        self.assertLessEqual(sum(1 for a in activities if a["action_type"] == "update"), limit)
        self.assertLessEqual(sum(1 for a in activities if a["action_type"] == "delete"), limit)

    def test_get_activity_within_minutes(self):
        """
        When within_minutes is specified, all activities within that window are returned
        regardless of LIMIT_RECORDS.
        """
        user = self.guest_login()
        limit = UserActivityAPI.LIMIT_RECORDS

        entity = self.create_entity(
            user, "TestModel", attrs=[{"name": "val", "type": AttrType.STRING}]
        )

        # Create limit+1 entries so the count exceeds LIMIT_RECORDS
        entries = [self.add_entry(user, "item-%d" % i, entity) for i in range(limit + 1)]

        # Backdate one entry to be outside the within_minutes window
        old_entry = entries[0]
        Entry.objects.filter(pk=old_entry.id).update(
            created_time=timezone.now() - timedelta(minutes=60)
        )

        resp = self.client.get("/user/api/v2/%s/activity?within_minutes=30" % user.id)
        self.assertEqual(resp.status_code, 200)

        create_activities = [a for a in resp.json() if a["action_type"] == "create"]
        # Should return limit entries (limit+1 created, 1 backdated outside window)
        self.assertEqual(len(create_activities), limit)

    def test_get_activity_with_since_timestamp(self):
        user = self.guest_login()

        # create items sparsely over time
        model = self.create_entity(
            user, "TestModel", attrs=[{"name": "val", "type": AttrType.STRING}]
        )
        item = self.add_entry(user, "item", model)
        attr = item.attrs.get(schema__name="val")

        for i in range(3):
            changed_attrv = attr.add_value(user, "changed-%d" % i)

            # backdate its created_time for each 20 minutes
            changed_attrv.created_time = timezone.now() - timedelta(minutes=(20 * i))
            changed_attrv.save(update_fields=["created_time"])

        # Remove the initial empty AttributeValue auto-created during entry registration
        # (register_es calls get_latest_value which creates one; prev_value FK is SET_NULL)
        attr.values.filter(value="").delete()

        # Without since: all 3 update records are returned
        resp = self.client.get("/user/api/v2/%s/activity" % user.id)
        self.assertEqual(resp.status_code, 200)
        update_records = [a for a in resp.json() if a["action_type"] == "update"]
        self.assertEqual(len(update_records), 3)

        # since=10 min ago: only i=2 (40 min ago, is_latest=True) passes the lte+is_latest filter,
        # giving 1 record
        since_iso = (timezone.now() - timedelta(minutes=10)).isoformat()
        resp = self.client.get("/user/api/v2/%s/activity?since=%s" % (user.id, since_iso))
        self.assertEqual(resp.status_code, 200)
        update_records = [a for a in resp.json() if a["action_type"] == "update"]
        self.assertEqual(len(update_records), 1)
        self.assertEqual(update_records[0]["target"]["attr"]["curr_value"]["value"], "changed-2")

    def test_get_activity_since_invalid(self):
        user = self.guest_login()

        resp = self.client.get("/user/api/v2/%s/activity?since=not-a-datetime" % user.id)
        self.assertEqual(resp.status_code, 400)

    def test_get_activity_within_minutes_invalid(self):
        user = self.guest_login()

        resp = self.client.get("/user/api/v2/%s/activity?within_minutes=abc" % user.id)
        self.assertEqual(resp.status_code, 400)

        resp = self.client.get("/user/api/v2/%s/activity?within_minutes=0" % user.id)
        self.assertEqual(resp.status_code, 400)

        resp = self.client.get("/user/api/v2/%s/activity?within_minutes=-5" % user.id)
        self.assertEqual(resp.status_code, 400)

    def test_get_activity_filters_by_permission(self):
        """
        Activities for models/items/attributes the requesting user lacks permission to
        should be excluded from the response.
        """
        admin = self._create_user("admin", is_superuser=True)
        activity_user = self._create_user("activity_user")
        self._create_user("viewing_user")

        public_entity = self.create_entity(
            admin, "PublicModel", attrs=[{"name": "val", "type": AttrType.STRING}]
        )
        private_entity = self.create_entity(
            admin, "PrivateModel", attrs=[{"name": "val", "type": AttrType.STRING}]
        )

        # create entries while both entities are still public so complement_attrs succeeds
        public_entry = self.add_entry(
            activity_user, "pub-item", public_entity, values={"val": "v0"}
        )
        private_entry = self.add_entry(
            activity_user, "priv-item", private_entity, values={"val": "v0"}
        )

        # update attribute values
        public_entry.attrs.get(schema__name="val").add_value(activity_user, "v1")
        private_entry.attrs.get(schema__name="val").add_value(activity_user, "v1")

        # delete entries
        public_entry.delete(deleted_user=activity_user)
        private_entry.delete(deleted_user=activity_user)

        # now restrict private_entity so viewing_user has no permission
        private_entity.is_public = False
        private_entity.default_permission = ACLType.Nothing.id
        private_entity.save()

        # viewing_user requests activity of activity_user
        self.client.login(username="viewing_user", password="viewing_user")
        resp = self.client.get("/user/api/v2/%s/activity" % activity_user.id)
        self.assertEqual(resp.status_code, 200)

        activities = resp.json()
        target_models = {
            a["target"]["model"].get("model_id") or a["target"]["model"].get("id")
            for a in activities
        }
        self.assertIn(public_entity.id, target_models)
        self.assertNotIn(private_entity.id, target_models)

        # --- additional case: Attribute-instance permission filters update activity ---
        # Entity and entry remain public; only the Attribute instance itself is restricted.
        target_model = self.create_entity(
            admin,
            "ModelForAttrPermTest",
            attrs=[
                {"name": "secret1", "type": AttrType.STRING},
                {"name": "secret2", "type": AttrType.STRING},
            ],
        )
        target_item = self.add_entry(
            activity_user,
            "item-for-attr-perm",
            target_model,
            values={"secret1": "init", "secret2": "init"},
        )

        # update activity for secret_attr should be visible to viewing_user
        # at this point since the Attribute instance is still public.
        for attr in target_item.attrs.all():
            attr.add_value(activity_user, "change " + attr.schema.name)

        # with the attribute still public, viewing_user sees the update activities
        # (add_entry itself also records an AttributeValue, so there are at least two)
        resp = self.client.get("/user/api/v2/%s/activity" % activity_user.id)
        self.assertEqual(resp.status_code, 200)

        update_activities = [
            a
            for a in resp.json()
            if a["action_type"] == "update" and a["target"]["model"]["model_id"] == target_model.id
        ]
        self.assertGreater(len(update_activities), 0)

        # set permissoins to prevent viewing_user from seeing the AttributeValue
        # that was updated in the previous step
        model_attr_secret1 = target_model.attrs.get(name="secret1")
        item_attr_secret2 = target_item.attrs.get(schema__name="secret2")
        for attr in [model_attr_secret1, item_attr_secret2]:
            attr.is_public = False
            attr.default_permission = ACLType.Nothing.id
            attr.save()

        resp = self.client.get("/user/api/v2/%s/activity" % activity_user.id)
        self.assertEqual(resp.status_code, 200)

        update_activities = [
            a
            for a in resp.json()
            if a["action_type"] == "update" and a["target"]["model"]["model_id"] == target_model.id
        ]
        self.assertEqual(len(update_activities), 0)

    def test_get_activity_with_to_parameter(self):
        """
        When 'to' is specified together with 'since', all activities in the range
        [to, since] are returned regardless of LIMIT_RECORDS.
        """
        user = self.guest_login()
        limit = UserActivityAPI.LIMIT_RECORDS

        entity = self.create_entity(
            user, "TestModel", attrs=[{"name": "val", "type": AttrType.STRING}]
        )

        # Create limit+1 entries within the range
        in_range_entries = [self.add_entry(user, "in-%d" % i, entity) for i in range(limit + 1)]

        # Backdate one entry to be outside the range (before 'to')
        out_of_range = in_range_entries[0]
        Entry.objects.filter(pk=out_of_range.id).update(
            created_time=timezone.now() - timedelta(days=10)
        )

        since_dt = timezone.now()
        to_dt = since_dt - timedelta(days=5)

        since_iso = since_dt.isoformat()
        to_iso = to_dt.isoformat()

        resp = self.client.get(
            "/user/api/v2/%s/activity?since=%s&to=%s" % (user.id, since_iso, to_iso)
        )
        self.assertEqual(resp.status_code, 200)

        create_activities = [a for a in resp.json() if a["action_type"] == "create"]
        # limit+1 created, 1 backdated outside range → limit in range
        self.assertEqual(len(create_activities), limit)

    def test_get_activity_to_without_since(self):
        """When 'to' is specified without 'since', 'since' defaults to now."""
        user = self.guest_login()
        entity = self.create_entity(
            user, "TestModel", attrs=[{"name": "val", "type": AttrType.STRING}]
        )
        entry = self.add_entry(user, "item", entity)

        # Backdate entry to be within [to, now]
        Entry.objects.filter(pk=entry.id).update(created_time=timezone.now() - timedelta(days=3))

        to_dt = timezone.now() - timedelta(days=5)
        to_iso = to_dt.isoformat()

        resp = self.client.get("/user/api/v2/%s/activity?to=%s" % (user.id, to_iso))
        self.assertEqual(resp.status_code, 200)

        create_activities = [a for a in resp.json() if a["action_type"] == "create"]
        self.assertEqual(len(create_activities), 1)

    def test_get_activity_to_after_since_is_invalid(self):
        """'to' must not be after 'since'."""
        user = self.guest_login()

        since_iso = (timezone.now() - timedelta(days=5)).isoformat()
        to_iso = timezone.now().isoformat()  # to is after since → invalid

        resp = self.client.get(
            "/user/api/v2/%s/activity?since=%s&to=%s" % (user.id, since_iso, to_iso)
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("to", resp.json())

    def test_get_activity_to_since_range_over_one_month_is_invalid(self):
        """The interval between 'since' and 'to' must be less than one month."""
        user = self.guest_login()

        # >LIMIT_DAYS + 1 days apart
        since_iso = timezone.now().isoformat()
        to_iso = (timezone.now() - timedelta(days=UserActivityAPI.LIMIT_DAYS + 1)).isoformat()

        resp = self.client.get(
            "/user/api/v2/%s/activity?since=%s&to=%s" % (user.id, since_iso, to_iso)
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("to", resp.json())

    def test_get_activity_to_invalid_format(self):
        """'to' must be a valid ISO 8601 datetime string."""
        user = self.guest_login()

        resp = self.client.get("/user/api/v2/%s/activity?to=not-a-datetime" % user.id)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("to", resp.json())
