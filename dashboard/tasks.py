import csv
import io
from collections.abc import Iterator
from itertools import product
from typing import Any, NotRequired, TypedDict

import yaml
from django.conf import settings
from natsort import natsorted

from airone.celery import app
from airone.lib.elasticsearch import AdvancedSearchResultRecord, AttrHint
from airone.lib.job import may_schedule_until_job_is_ready, register_job_task
from airone.lib.types import AttrType
from entry.services import AdvancedSearchService
from job.models import Job, JobOperation
from job.params import SearchExportParams


def iter_csv_records(
    values: list[AdvancedSearchResultRecord], attr_names: list[str]
) -> Iterator[AdvancedSearchResultRecord]:
    """Emit one element per array cell, repeating other values on each row.

    Independent arrays produce all combinations. Joined source arrays have
    already been narrowed to the reference belonging to each joined row.
    """
    for record in values:
        arrays = {
            name: record.attrs[name]["value"] or [None]
            for name in dict.fromkeys(attr_names)
            if name in record.attrs
            and record.attrs[name].get("type", 0) & AttrType._ARRAY
            and isinstance(record.attrs[name].get("value"), list)
        }
        if not arrays:
            yield record
            continue
        for items in product(*arrays.values()):
            row = record.model_copy(deep=True)
            for name, item in zip(arrays, items):
                row.attrs[name]["value"] = [] if item is None else [item]
            yield row


def _csv_export(
    job: Job,
    values: list[AdvancedSearchResultRecord],
    attr_names: list[str],
    has_referral: bool,
    *,
    split_array_values: bool = True,
) -> io.StringIO | None:
    output = io.StringIO(newline="")
    # Keep LF row terminators consistent with multiline text values.
    writer = csv.writer(output, lineterminator="\n")

    # write first line of CSV
    if has_referral is not False:
        writer.writerow(["Name", "Entity", *attr_names, "Referral"])
    else:
        writer.writerow(["Name", "Entity", *attr_names])

    records = iter_csv_records(values, attr_names) if split_array_values else iter(values)
    for index, entry_info in enumerate(records):
        line_data = [entry_info.entry["name"]]

        # Abort processing when job is canceled
        if index % Job.STATUS_CHECK_FREQUENCY == 0 and job.is_canceled():
            return None

        # Append the data which specifies Entity name to which target Entry belongs
        line_data.append(entry_info.entity["name"])

        for attr_name in attr_names:
            # This condition eliminates the possibility that an attribute
            # which target entry doens't have is specified in attrinfo variable.
            if attr_name not in entry_info.attrs:
                line_data.append("")
                continue

            value = entry_info.attrs[attr_name]

            vtype = None
            if "type" in value:
                vtype = value["type"]

            vval: Any = None
            if "value" in value:
                vval = value["value"]

            if not value or "value" not in value or value["value"] is None:
                line_data.append("")
                continue

            match vtype:
                case (
                    AttrType.STRING
                    | AttrType.TEXT
                    | AttrType.BOOLEAN
                    | AttrType.DATE
                    | AttrType.DATETIME
                    | AttrType.NUMBER
                ):
                    line_data.append(str(vval))

                case AttrType.OBJECT | AttrType.GROUP | AttrType.ROLE:
                    line_data.append(str(vval["name"]))

                case AttrType.NAMED_OBJECT | AttrType.NAMED_OBJECT_BOOLEAN:
                    [(k, v)] = vval.items()
                    line_data.append(
                        "%s: %s" % (k, v["name"]) if isinstance(v, dict) else "%s: " % k
                    )

                case AttrType.SELECT:
                    line_data.append(str(vval.get("label", "")) if isinstance(vval, dict) else "")

                case AttrType.MULTI_SELECT:
                    line_data.append("\n".join(str(item.get("label", "")) for item in vval))

                case AttrType.ARRAY_STRING:
                    line_data.append("\n".join(natsorted(vval)))

                case AttrType.ARRAY_NUMBER:
                    line_data.append(
                        "\n".join(natsorted([str(x) if x is not None else "" for x in vval]))
                    )

                case AttrType.ARRAY_OBJECT | AttrType.ARRAY_GROUP | AttrType.ARRAY_ROLE:
                    line_data.append("\n".join(natsorted([x["name"] for x in vval])))

                case AttrType.ARRAY_NAMED_OBJECT | AttrType.ARRAY_NAMED_OBJECT_BOOLEAN:
                    items = []
                    for vset in vval:
                        [(k, v)] = vset.items()
                        items.append(
                            "%s: %s" % (k, v["name"]) if isinstance(v, dict) else "%s: " % k
                        )

                    line_data.append("\n".join(natsorted(items)))

                case _:
                    # Types without a dedicated formatter (e.g. SELECT / MULTI_SELECT)
                    # still need a cell, otherwise the following columns get shifted.
                    line_data.append("")

        if has_referral is not False:
            line_data.append(
                str(
                    [
                        "%s / %s" % (x["name"], x["schema"]["name"])
                        for x in entry_info.referrals or []
                    ]
                )
            )

        writer.writerow(line_data)

    return output


class _ExportReferral(TypedDict):
    entity: str
    entry: str


class _ExportEntry(TypedDict):
    name: str
    attrs: dict[str, object]
    referrals: NotRequired[list[_ExportReferral]]


def _yaml_export(
    job: Job,
    values: list[AdvancedSearchResultRecord],
    attr_names: list[str],
    has_referral: bool,
) -> io.StringIO | None:
    output = io.StringIO()

    def _get_attr_value(atype: int, value: Any) -> object:
        match atype:
            case _ if atype & AttrType._ARRAY:
                return [_get_attr_value(atype ^ AttrType._ARRAY, x) for x in value]

            case AttrType.NAMED_OBJECT:
                [(key, val)] = value.items()
                return {key: val["name"]}

            case AttrType.OBJECT | AttrType.GROUP | AttrType.ROLE:
                return value["name"]

            case _:
                return value

    resp_data: dict[str, list[_ExportEntry]] = {}
    for index, entry_info in enumerate(values):
        data: _ExportEntry = {
            "name": entry_info.entry["name"],
            "attrs": {},
        }

        # Abort processing when job is canceled
        if index % Job.STATUS_CHECK_FREQUENCY == 0 and job.is_canceled():
            return None

        for attr_name in attr_names:
            if attr_name in entry_info.attrs:
                _adata = entry_info.attrs[attr_name]
                if "value" not in _adata:
                    continue

                data["attrs"][attr_name] = _get_attr_value(_adata["type"], _adata["value"])

        if has_referral is not False:
            data["referrals"] = [
                {
                    "entity": x["schema"]["name"],
                    "entry": x["name"],
                }
                for x in entry_info.referrals or []
            ]

        if entry_info.entity["name"] in resp_data:
            resp_data[entry_info.entity["name"]].append(data)
        else:
            resp_data[entry_info.entity["name"]] = [data]

    output.write(yaml.dump(resp_data, default_flow_style=False, allow_unicode=True))

    return output


@register_job_task(JobOperation.EXPORT_SEARCH_RESULT)
@app.task(bind=True)
@may_schedule_until_job_is_ready
def export_search_result(self: object, job: Job) -> None:
    user = job.user
    params = job.get_typed_params(SearchExportParams)
    has_referral = params.has_referral
    referral_name = params.referral_name
    hint_attrs = [
        AttrHint.model_validate(attr.model_dump(mode="json", by_alias=True, exclude_unset=True))
        for attr in params.attrinfo
    ]
    attr_names = [hint.name for hint in hint_attrs]
    if has_referral and referral_name is None:
        referral_name = ""

    resp = AdvancedSearchService.search_entries(
        user,
        params.entities,
        hint_attrs,
        settings.ES_CONFIG["MAXIMUM_RESULTS_NUM"],
        params.entry_name,
        referral_name,
    )

    io_stream: io.StringIO | None = None
    match params.export_style:
        case "yaml":
            io_stream = _yaml_export(job, resp.ret_values, attr_names, has_referral)
        case "csv":
            io_stream = _csv_export(job, resp.ret_values, attr_names, has_referral)

    if io_stream:
        job.set_cache(io_stream.getvalue())
