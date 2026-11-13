import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.check_api_compatibility import (
    SCHEMA_BOOTSTRAP,
    CompatibilityError,
    compare_schemas,
    generate_schema,
    snapshot_sources,
)


def schema() -> dict:
    return {
        "openapi": "3.0.3",
        "info": {"title": "Compatibility fixture", "version": "1"},
        "paths": {
            "/items": {
                "post": {
                    "operationId": "createItem",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"name": {"type": "string"}},
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"id": {"type": "string"}},
                                    }
                                }
                            },
                        }
                    },
                },
            },
        },
    }


@unittest.skipUnless(
    shutil.which("oasdiff"), "Install pinned oasdiff to run compatibility fixtures"
)
class RealOasdiffTest(unittest.TestCase):
    def compare(self, changed: dict) -> int:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.json"
            current = Path(directory) / "current.json"
            base.write_text(json.dumps(schema()))
            current.write_text(json.dumps(changed))
            return compare_schemas(base, current)

    def test_deleted_endpoint(self) -> None:
        changed = schema()
        changed["paths"] = {}
        self.assertEqual(self.compare(changed), 1)

    def test_added_required_query_parameter(self) -> None:
        changed = schema()
        changed["paths"]["/items"]["post"]["parameters"] = [
            {
                "name": "scope",
                "in": "query",
                "required": True,
                "schema": {"type": "string"},
            }
        ]
        self.assertEqual(self.compare(changed), 1)

    def test_added_required_request_property(self) -> None:
        changed = schema()
        body = changed["paths"]["/items"]["post"]["requestBody"]
        request = body["content"]["application/json"]["schema"]
        request["properties"]["scope"] = {"type": "string"}
        request["required"] = ["scope"]
        self.assertEqual(self.compare(changed), 1)

    def test_optional_query_becomes_required(self) -> None:
        original = schema()
        parameter = {
            "name": "scope",
            "in": "query",
            "required": False,
            "schema": {"type": "string"},
        }
        original["paths"]["/items"]["post"]["parameters"] = [parameter]
        changed = copy.deepcopy(original)
        changed["paths"]["/items"]["post"]["parameters"][0]["required"] = True
        with patch(__name__ + ".schema", return_value=original):
            self.assertEqual(self.compare(changed), 1)

    def test_required_response_property_removed(self) -> None:
        original = schema()
        response = original["paths"]["/items"]["post"]["responses"]["200"]
        response["content"]["application/json"]["schema"]["required"] = ["id"]
        changed = copy.deepcopy(original)
        response = changed["paths"]["/items"]["post"]["responses"]["200"]
        response["content"]["application/json"]["schema"]["properties"] = {}
        response["content"]["application/json"]["schema"]["required"] = []
        with patch(__name__ + ".schema", return_value=original):
            self.assertEqual(self.compare(changed), 1)

    def test_response_property_type_change(self) -> None:
        changed = schema()
        response = changed["paths"]["/items"]["post"]["responses"]["200"]
        response["content"]["application/json"]["schema"]["properties"]["id"] = {
            "type": "integer",
        }
        self.assertEqual(self.compare(changed), 1)

    def test_optional_request_property_is_compatible(self) -> None:
        changed = copy.deepcopy(schema())
        body = changed["paths"]["/items"]["post"]["requestBody"]
        body["content"]["application/json"]["schema"]["properties"]["scope"] = {
            "type": "string",
        }
        self.assertEqual(self.compare(changed), 0)


class SchemaGenerationTest(unittest.TestCase):
    def test_generation_rejects_nonzero_and_per_view_errors(self) -> None:
        for status, stderr in [
            (1, "ImportError: missing dependency"),
            (0, "entry/views.py:3: Error [EntryView]: invalid field"),
            (0, "Error: invalid schema"),
        ]:
            with self.subTest(stderr=stderr), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with patch("tools.check_api_compatibility.subprocess.run") as run:
                    run.return_value = subprocess.CompletedProcess([], status, stderr=stderr)
                    with self.assertRaisesRegex(CompatibilityError, "generation failed"):
                        generate_schema(root, root / "schema.yaml")

    def test_empty_schema_paths_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def generate(*args, **kwargs):
                kwargs["stdout"].write("openapi: 3.0.3\npaths: {}")
                return subprocess.CompletedProcess([], 0, stderr="")

            with patch("tools.check_api_compatibility.subprocess.run", side_effect=generate):
                with self.assertRaisesRegex(CompatibilityError, "no API paths"):
                    generate_schema(root, root / "schema.yaml")

    def test_generation_forces_source_and_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def generate(*args, **kwargs):
                kwargs["stdout"].write("openapi: 3.0.3\npaths: { /items: {} }")
                return subprocess.CompletedProcess([], 0, stderr="ImportError: warning text")

            with patch("tools.check_api_compatibility.subprocess.run", side_effect=generate) as run:
                generate_schema(root, root / "schema.yaml")
            environment = run.call_args.kwargs["env"]
            self.assertEqual(environment["DJANGO_CONFIGURATION"], "DRFSpectacularExcludeCustomView")
            self.assertEqual(environment["PAGODA_LITE"], "1")
            self.assertEqual(environment["PYTHONPATH"], f"{root}:{root}/plugin/sdk")

    def test_bootstrap_resolves_base_packages_and_blocks_current_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = root / "snapshot"
            current = root / "current"
            for package in ("airone", "entry", "plugin/sdk/pagoda_plugin_sdk"):
                path = snapshot / package
                path.mkdir(parents=True)
                (path / "__init__.py").write_text("")
            current.mkdir()
            (current / "current_only.py").write_text("")
            (snapshot / "manage.py").write_text(
                "import importlib.util, json\n"
                "print(json.dumps({name: importlib.util.find_spec(name).origin "
                "for name in ('airone', 'entry', 'pagoda_plugin_sdk')}))\n"
                "assert importlib.util.find_spec('current_only') is None\n"
            )
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join(
                map(str, (snapshot, snapshot / "plugin/sdk", current))
            )
            result = subprocess.run(
                [sys.executable, "-c", SCHEMA_BOOTSTRAP, str(current)],
                cwd=snapshot,
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            origins = json.loads(result.stdout)
            for origin in origins.values():
                self.assertTrue(Path(origin).resolve().is_relative_to(snapshot.resolve()))

    def test_snapshot_contains_only_committed_python_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repository"
            root.mkdir()
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            (root / "manage.py").write_text("# committed source\n")
            (root / "README.md").write_text("documentation")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "-c",
                    "commit.gpgsign=false",
                    "commit",
                    "--quiet",
                    "-m",
                    "fixture",
                ],
                cwd=root,
                check=True,
            )
            (root / "manage.py").write_text("# uncommitted source\n")
            (root / "local.py").write_text("# untracked source\n")
            destination = Path(temporary) / "snapshot"
            destination.mkdir()
            commit = snapshot_sources(root, "HEAD", destination)
            self.assertRegex(commit, r"^[0-9a-f]{40,64}$")
            self.assertEqual((destination / "manage.py").read_text(), "# committed source\n")
            self.assertEqual([path.name for path in destination.iterdir()], ["manage.py"])

    def test_invalid_base_reference_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            with self.assertRaises(subprocess.CalledProcessError):
                snapshot_sources(root, "does-not-exist", root / "snapshot")


if __name__ == "__main__":
    unittest.main()
