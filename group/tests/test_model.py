from unittest import mock

from airone.lib.elasticsearch import AttrHint
from airone.lib.test import AironeTestCase
from airone.lib.types import AttrType
from entry.models import Entry
from entry.services import AdvancedSearchService
from group import tasks
from group.models import Group
from user.models import User


class GroupDeletionTest(AironeTestCase):
    def test_delete_edge_group(self):
        parent = Group.objects.create(name="parent")
        group = Group.objects.create(name="group1", parent_group=parent)

        group.delete()

        group.refresh_from_db()
        parent.refresh_from_db()
        self.assertFalse(group.is_active)
        self.assertTrue(group.name.startswith("group1_deleted_"))
        self.assertEqual(group.parent_group, parent)
        self.assertTrue(parent.is_active)

    def test_delete_parent_group(self):
        """Deleting a parent reparents its active children to their grandparent."""
        root = Group.objects.create(name="root")
        parent = Group.objects.create(name="parent", parent_group=root)
        child = Group.objects.create(name="child", parent_group=parent)

        parent.delete()
        child.refresh_from_db()
        self.assertEqual(child.parent_group, root)

    def test_delete_parent_lonely_group(self):
        """A parent can be deleted after all of its children have been deleted."""
        parent = Group.objects.create(name="parent")
        child = Group.objects.create(name="child", parent_group=parent)
        child.delete()
        child.refresh_from_db()
        self.assertFalse(child.is_active)
        self.assertTrue(child.name.startswith("child_deleted_"))

        parent.delete()

        parent.refresh_from_db()
        self.assertFalse(parent.is_active)
        self.assertTrue(parent.name.startswith("parent_deleted_"))


class GroupReferralsTest(AironeTestCase):
    def test_get_referred_entries_through_group_attr(self):
        user = User.objects.create(username="user1")
        unreferenced_group = Group.objects.create(name="unreferenced")
        group = Group.objects.create(name="referenced", parent_group=unreferenced_group)

        for index in range(3):
            entity = self.create_entity(
                user=user,
                name=f"Entity{index}",
                attrs=[{"name": "group", "type": AttrType.GROUP}],
            )
            self.add_entry(
                user,
                "e-%d" % index,
                entity,
                values={
                    "group": group,
                },
            )

        # check Group.get_referred_entries()
        self.assertFalse(unreferenced_group.get_referred_entries().exists())
        self.assertEqual([e.name for e in group.get_referred_entries()], ["e-0", "e-1", "e-2"])

        # check Group.get_referred_entries() with entity-name
        self.assertEqual(
            [e.name for e in group.get_referred_entries(entity_name="Entity1")], ["e-1"]
        )

        # check Group.get_referred_entries() after deleting Entry
        entry = Entry.objects.get(schema__name="Entity1", is_active=True)
        entry.delete()
        self.assertFalse(group.get_referred_entries(entity_name="Entity1").exists())

    def test_get_referred_entries_through_array_group_attr(self):
        user = User.objects.create(username="user1")
        first_group = Group.objects.create(name="first")
        second_group = Group.objects.create(name="second")

        for index in range(3):
            entity = self.create_entity(
                user=user,
                name=f"Entity{index}",
                attrs=[{"name": "groups", "type": AttrType.ARRAY_GROUP}],
            )
            self.add_entry(
                user,
                "e-%d" % index,
                entity,
                values={
                    "groups": [first_group, second_group],
                },
            )

        for group in [first_group, second_group]:
            # check Group.get_referred_entries()
            self.assertEqual([e.name for e in group.get_referred_entries()], ["e-0", "e-1", "e-2"])

            # check Group.get_referred_entries() with entity-name
            self.assertEqual(
                [e.name for e in group.get_referred_entries(entity_name="Entity1")], ["e-1"]
            )

    @mock.patch(
        "group.tasks.edit_group_referrals.delay", mock.Mock(side_effect=tasks.edit_group_referrals)
    )
    def test_delete_group(self):
        user = User.objects.create(username="user1")
        group = Group.objects.create(name="group")
        entity = self.create_entity(
            user=user,
            name="Entity1",
            attrs=[{"name": "group", "type": AttrType.GROUP}],
        )

        self.add_entry(
            user,
            "e-1",
            entity,
            values={"group": group},
        )
        group.delete()

        results = AdvancedSearchService.search_entries(user, [entity.id], [AttrHint(name="group")])
        self.assertEqual(results.ret_values[0].attrs["group"]["value"]["name"], "")


class GroupLimitTest(AironeTestCase):
    def test_max_groups(self):
        limit = Group.objects.count() + 2
        with self.settings(MAX_GROUPS=limit):
            Group.objects.create(name="below-limit")
            Group.objects.create(name="at-limit")
            self.assertEqual(Group.objects.count(), limit)

            with self.assertRaises(RuntimeError):
                Group.objects.create(name="over-limit")
            self.assertFalse(Group.objects.filter(name="over-limit").exists())
            self.assertEqual(Group.objects.count(), limit)

    def test_max_groups_unlimited(self):
        with self.settings(MAX_GROUPS=None):
            group = Group.objects.create(name="unlimited")

        self.assertTrue(Group.objects.filter(pk=group.pk).exists())
