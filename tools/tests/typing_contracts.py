# mypy: ignore-errors=False
"""Static regression checks for contracts whose runtime results survive type erasure."""

from typing import assert_type

from common.lib.import_detector import ImportType, wrap_envelope
from job.models import Job
from job.params import SearchExportParams


def check_job_params(job: Job) -> None:
    assert_type(job.get_typed_params(SearchExportParams), SearchExportParams)
    assert_type(job.get_typed_params(), object)


def check_envelope(records: list[dict[str, str]]) -> None:
    assert_type(wrap_envelope(ImportType.USER, records)["data"], list[dict[str, str]])
