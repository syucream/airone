# mypy: ignore-errors=False
"""Static regression checks for contracts whose runtime results survive type erasure."""

from typing import assert_type

from airone.lib.multidb import db_readonly


def check_decorator() -> None:
    @db_readonly
    def view(entry_id: int) -> str:
        return str(entry_id)

    assert_type(view(1), str)
