import tempfile
import unittest
from pathlib import Path

from tools.check_job_params import check_repository, find_violations


class CheckJobParamsTest(unittest.TestCase):
    def test_detects_json_and_pydantic_parsers(self) -> None:
        source = """
import json

def task(job):
    first = json.loads(job.params)
    second = Params.model_validate_json(job.params)
    third = Params.parse_raw(data=job.params)
    return first, second, third
"""

        violations = find_violations(source, Path("job/tasks.py"))

        self.assertEqual(len(violations), 3)
        self.assertEqual([violation.line for violation in violations], [5, 6, 7])
        self.assertEqual([violation.expression for violation in violations], ["job.params"] * 3)

    def test_detects_imported_json_loads_alias(self) -> None:
        source = """
import json as jsonlib
from json import loads as decode_json

def task(job):
    return decode_json(payload=jsonlib.loads(job.params))
"""

        self.assertEqual(len(find_violations(source, Path("job/tasks.py"))), 1)

    def test_detects_job_alias_intermediate_value_and_alternative_json_module(self) -> None:
        source = """
import json
import orjson

def task(task_job):
    raw = task_job.params
    first = json.loads(raw)
    queued = task_job
    second = orjson.loads(queued.params)
    return first, second
"""

        violations = find_violations(source, Path("plugin/tasks.py"))

        self.assertEqual(len(violations), 2)
        self.assertEqual([violation.line for violation in violations], [6, 9])

    def test_task_modules_reserve_params_for_any_variable_name(self) -> None:
        source = """
def task(current, job_config):
    return current.params, job_config.params
"""

        violations = find_violations(source, Path("plugin/tasks.py"))

        self.assertEqual(len(violations), 2)

    def test_non_task_context_params_is_not_a_job_violation(self) -> None:
        source = """
def dispatch(context):
    return context.params
"""

        self.assertEqual(find_violations(source, Path("plugin/handlers.py")), [])

    def test_allows_validated_dto_and_non_production_fixtures(self) -> None:
        source = """
def task(job):
    params = job.get_typed_params(Params)
    return params.model_dump()
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "job").mkdir()
            (root / "job" / "tasks.py").write_text(source, encoding="utf-8")
            (root / "job" / "tests").mkdir()
            (root / "job" / "tests" / "test_fixture.py").write_text(
                "import json\njson.loads(job.params)\n", encoding="utf-8"
            )

            self.assertEqual(check_repository(root), [])

    def test_repository_reports_current_production_violations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "job").mkdir()
            (root / "job" / "tasks.py").write_text(
                "import json\n\ndef task(job):\n    return json.loads(job.params)\n",
                encoding="utf-8",
            )
            (root / "job" / "tests").mkdir()
            (root / "job" / "tests" / "test_fixture.py").write_text(
                "import json\njson.loads(job.params)\n", encoding="utf-8"
            )

            violations = check_repository(root)

            self.assertEqual(len(violations), 1)
            self.assertEqual(violations[0].path, root / "job" / "tasks.py")


if __name__ == "__main__":
    unittest.main()
