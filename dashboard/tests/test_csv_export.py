import csv
import io
import json
from unittest.mock import Mock, patch

from django.core.files.storage import default_storage
from django.test import SimpleTestCase
from django.urls import reverse

from airone.lib.elasticsearch import AdvancedSearchResultRecord, AdvancedSearchResults
from airone.lib.test import AironeViewTest
from airone.lib.types import AttrType
from dashboard.tasks import _csv_export, export_search_result, iter_csv_records
from entity.models import Entity
from entry.tasks import _csv_export_v2, export_search_result_v2
from job.models import Job, JobStatus


class CsvExportTest(SimpleTestCase):
    def test_every_array_element_gets_a_row_with_repeated_item_name(self):
        cases = [
            (
                AttrType.ARRAY_STRING,
                ['first,"value"', "second\nline"],
                ['first,"value"', "second\nline"],
            ),
            (AttrType.ARRAY_NUMBER, [2, 0, -1], ["2", "0", "-1"]),
            (
                AttrType.ARRAY_OBJECT,
                [{"id": 1, "name": "ip1"}, {"id": 2, "name": "ip2"}],
                ["ip1", "ip2"],
            ),
            (AttrType.ARRAY_GROUP, [{"name": "group1"}, {"name": "group2"}], ["group1", "group2"]),
            (AttrType.ARRAY_ROLE, [{"name": "role1"}, {"name": "role2"}], ["role1", "role2"]),
            (
                AttrType.ARRAY_NAMED_OBJECT,
                [{"nic1": {"name": "ip1"}}, {"nic2": None}],
                ["nic1: ip1", "nic2: "],
            ),
            (
                AttrType.ARRAY_NAMED_OBJECT_BOOLEAN,
                [{"nic1": {"name": "ip1", "boolean": False}}, {"nic2": {"name": "ip2"}}],
                ["nic1: ip1", "nic2: ip2"],
            ),
            (
                AttrType.MULTI_SELECT,
                [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}],
                ["A", "B"],
            ),
            (AttrType.ARRAY_STRING, [], [""]),
        ]
        for exporter in [_csv_export, _csv_export_v2]:
            for attr_type, values, expected in cases:
                with self.subTest(exporter=exporter.__name__, attr_type=attr_type, values=values):
                    record = AdvancedSearchResultRecord(
                        entity={"id": 1, "name": "VM"},
                        entry={"id": 2, "name": "vm7264"},
                        attrs={
                            "array": {"type": attr_type, "value": values},
                            "scalar": {"type": AttrType.STRING, "value": "same"},
                        },
                        is_readable=True,
                    )
                    original = record.model_dump()
                    output = exporter(
                        Mock(is_canceled=Mock(return_value=False)),
                        [record],
                        {"attrinfo": [{"name": "array"}, {"name": "scalar"}]},
                        False,
                    )
                    prefix = ["vm7264", "VM"] if exporter is _csv_export else ["vm7264"]
                    self.assertEqual(
                        list(csv.reader(io.StringIO(output.getvalue())))[1:],
                        [prefix + [item, "same"] for item in expected],
                    )
                    self.assertEqual(record.model_dump(), original)

    def test_multiple_arrays_repeat_other_values_for_all_combinations(self):
        record = AdvancedSearchResultRecord(
            entity={"id": 1, "name": "VM"},
            entry={"id": 2, "name": "vm7264"},
            attrs={
                "ips": {"type": AttrType.ARRAY_STRING, "value": ["ip1", "ip2"]},
                "tags": {"type": AttrType.ARRAY_STRING, "value": ["tag1", "tag2", "tag3"]},
                "scalar": {"type": AttrType.STRING, "value": "same"},
            },
            is_readable=True,
        )
        for exporter in [_csv_export, _csv_export_v2]:
            with self.subTest(exporter=exporter.__name__):
                output = exporter(
                    Mock(is_canceled=Mock(return_value=False)),
                    [record],
                    {"attrinfo": [{"name": name} for name in ["ips", "tags", "scalar"]]},
                    False,
                )
                prefix = ["vm7264", "VM"] if exporter is _csv_export else ["vm7264"]
                self.assertEqual(
                    list(csv.reader(io.StringIO(output.getvalue())))[1:],
                    [
                        prefix + [ip, tag, "same"]
                        for ip in ["ip1", "ip2"]
                        for tag in ["tag1", "tag2", "tag3"]
                    ],
                )

    def make_record(self, **arrays):
        return AdvancedSearchResultRecord(
            entity={"id": 1, "name": "VM"},
            entry={"id": 2, "name": "vm7264"},
            attrs={
                name: {"type": AttrType.ARRAY_STRING, "value": values}
                for name, values in arrays.items()
            },
            is_readable=True,
        )

    def test_row_budget_boundary_and_one_over(self):
        record = self.make_record(a=["a", "b"], b=["1", "2", "3"])
        for exporter in [_csv_export, _csv_export_v2]:
            with self.subTest(exporter=exporter.__name__), self.settings(CSV_EXPORT_MAX_ROWS=6):
                output = exporter(
                    Mock(is_canceled=Mock(return_value=False)),
                    [record],
                    {"attrinfo": [{"name": "a"}, {"name": "b"}]},
                    False,
                )
                self.assertEqual(len(list(csv.reader(io.StringIO(output.getvalue())))), 7)
            with self.subTest(exporter=exporter.__name__), self.settings(CSV_EXPORT_MAX_ROWS=5):
                with self.assertRaisesRegex(ValueError, "maximum of 5 data rows"):
                    exporter(Mock(), [record], {"attrinfo": [{"name": "a"}, {"name": "b"}]}, False)

    def test_budget_is_cumulative_and_checked_before_any_expansion(self):
        records = [self.make_record(a=["a", "b"]), self.make_record(a=["c", "d"])]
        with self.settings(CSV_EXPORT_MAX_ROWS=3), patch("dashboard.tasks.product") as product:
            with self.assertRaisesRegex(ValueError, "maximum of 3 data rows"):
                list(iter_csv_records(records, ["a"]))
            product.assert_not_called()

    def test_joined_columns_count_toward_budget(self):
        record = self.make_record(a=["a", "b"], **{"ref.tags": ["1", "2", "3"]})
        params = {
            "attrinfo": [{"name": "a"}],
            "join_attrs": [{"name": "ref", "attrinfo": [{"name": "tags"}]}],
        }
        with self.settings(CSV_EXPORT_MAX_ROWS=6):
            output = _csv_export_v2(
                Mock(is_canceled=Mock(return_value=False)), [record], params, False
            )
            self.assertEqual(len(list(csv.reader(io.StringIO(output.getvalue())))), 7)
        with self.settings(CSV_EXPORT_MAX_ROWS=5):
            with self.assertRaisesRegex(ValueError, "maximum of 5 data rows"):
                _csv_export_v2(Mock(), [record], params, False)

    def test_nonpositive_budget_is_rejected(self):
        for limit in (0, -1):
            with self.subTest(limit=limit), self.settings(CSV_EXPORT_MAX_ROWS=limit):
                with self.assertRaisesRegex(ValueError, "must be a positive integer"):
                    list(iter_csv_records([self.make_record(a=["a"])], ["a"]))

    def test_huge_product_is_rejected_before_expansion(self):
        record = self.make_record(**{f"a{i}": ["x"] * 200 for i in range(4)})
        with (
            self.settings(CSV_EXPORT_MAX_ROWS=100_000),
            patch("dashboard.tasks.product") as product,
        ):
            with self.assertRaisesRegex(ValueError, "maximum of 100000 data rows"):
                list(iter_csv_records([record], list(record.attrs)))
            product.assert_not_called()

    def test_empty_arrays_and_duplicate_columns_count_once(self):
        record = self.make_record(a=["a", "b"], empty=[])
        with self.settings(CSV_EXPORT_MAX_ROWS=2):
            rows = list(iter_csv_records([record], ["a", "a", "empty"]))
        self.assertEqual(len(rows), 2)
        self.assertEqual([row.attrs["empty"]["value"] for row in rows], [[], []])
        self.assertEqual(record.attrs["a"]["value"], ["a", "b"])

    def test_scalar_records_also_count_toward_budget(self):
        with self.settings(CSV_EXPORT_MAX_ROWS=1):
            with self.assertRaisesRegex(ValueError, "maximum of 1 data rows"):
                list(iter_csv_records([self.make_record(), self.make_record()], []))

    def test_canceled_export_does_not_return_partial_output(self):
        for exporter in [_csv_export, _csv_export_v2]:
            with self.subTest(exporter=exporter.__name__):
                self.assertIsNone(
                    exporter(
                        Mock(is_canceled=Mock(return_value=True)),
                        [self.make_record(a=["a", "b"])],
                        {"attrinfo": [{"name": "a"}]},
                        False,
                    )
                )


class CsvExportJobBudgetTest(AironeViewTest):
    def test_readonly_export_requests_fail_job_without_publishing_cache(self):
        user = self.guest_login()
        user.is_readonly = True
        user.save(update_fields=["is_readonly"])
        entity = Entity.objects.create(name="Entity", created_user=user)
        record = AdvancedSearchResultRecord(
            entity={"id": entity.id, "name": entity.name},
            entry={"id": 1, "name": "entry"},
            attrs={"a": {"type": AttrType.ARRAY_STRING, "value": ["a", "b"]}},
            is_readable=True,
        )
        result = AdvancedSearchResults(ret_count=1, ret_values=[record])
        cases = [
            (
                reverse("dashboard:export_search_result"),
                "dashboard.tasks.export_search_result.delay",
                export_search_result,
            ),
            (
                "/entry/api/v2/advanced_search_result_export/",
                "entry.tasks.export_search_result_v2.delay",
                export_search_result_v2,
            ),
        ]
        for url, delay, task in cases:
            with self.subTest(url=url), self.settings(CSV_EXPORT_MAX_ROWS=1):
                with (
                    patch(delay, side_effect=task),
                    patch(
                        "dashboard.tasks.AdvancedSearchService.search_entries", return_value=result
                    ),
                    patch(
                        "entry.tasks.AdvancedSearchService.apply_join_attrs", return_value=result
                    ),
                    patch.object(Job, "set_cache") as set_cache,
                ):
                    response = self.client.post(
                        url,
                        json.dumps(
                            {
                                "entities": [entity.id],
                                "attrinfo": [{"name": "a"}],
                                "export_style": "csv",
                                "is_all_entities": False,
                            }
                        ),
                        "application/json",
                    )
                self.assertEqual(response.status_code, 200)
                job = Job.objects.latest("id")
                self.assertEqual(job.status, JobStatus.ERROR)
                self.assertIn("maximum of 1 data rows", job.text)
                set_cache.assert_not_called()
                self.assertFalse(default_storage.exists(f"job_{job.id}"))
