"""Tests for source isolation and schema validation without Django setup."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.api_contract_support.common import ContractError
from tools.api_contract_support.snapshot import _validate_schema, generate_schema, prepare_snapshots


class SnapshotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Snapshot Test")
        self.git("config", "commit.gpgsign", "false")
        self.write("airone/settings.py", "raise RuntimeError('must not be loaded')\n")
        self.write("example.py", "value = 1\n")
        self.write("custom_view_sample/api_v2/urls.py", "urlpatterns = []\n")
        self.write(".gitignore", "custom_view/\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")

    def git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def write(self, name: str, text: str) -> None:
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_staged_unstaged_and_untracked_are_included(self) -> None:
        self.write("example.py", "value = 2\n")
        self.git("add", "example.py")
        self.write("example.py", "value = 3\n")
        self.write("new.py", "value = 4\n")
        self.write(".env", "do not copy\n")
        self.write("secrets.py", "do not copy\n")
        self.write("custom_view/api_v2/urls.py", "raise RuntimeError('deployment')\n")
        destination = self.root / "snapshots"
        metadata = prepare_snapshots(self.repo, "HEAD", destination)
        self.assertEqual((destination / "base/example.py").read_text(), "value = 1\n")
        self.assertEqual((destination / "head/example.py").read_text(), "value = 3\n")
        self.assertEqual(metadata["included_untracked"], ["new.py"])
        self.assertTrue(metadata["working_tree_dirty"])
        self.assertNotEqual(metadata["base_source_digest"], metadata["head_source_digest"])
        self.assertFalse((destination / "head/.env").exists())
        self.assertFalse((destination / "head/secrets.py").exists())
        self.assertEqual(
            (destination / "head/custom_view/api_v2/urls.py").read_text(), "urlpatterns = []\n"
        )
        self.assertIn("Common", (destination / "head/airone/settings.py").read_text())

    def test_relevant_symlink_fails_closed(self) -> None:
        (self.repo / "link.py").symlink_to(self.repo / "example.py")
        with self.assertRaises(ContractError):
            prepare_snapshots(self.repo, "HEAD", self.root / "snapshots")

    def test_deleted_source_is_absent(self) -> None:
        (self.repo / "example.py").unlink()
        destination = self.root / "snapshots"
        prepare_snapshots(self.repo, "HEAD", destination)
        self.assertTrue((destination / "base/example.py").exists())
        self.assertFalse((destination / "head/example.py").exists())

    def test_schema_validation(self) -> None:
        valid = {"openapi": "3.0.3", "paths": {"/entries": {}}, "$ref": "#/components/x"}
        _validate_schema(valid)
        for value in ({}, {"openapi": "3.0.3", "paths": {}}, {**valid, "$ref": "file:x"}):
            with self.subTest(value=value), self.assertRaises(ContractError):
                _validate_schema(value)

    def test_generator_failures_and_zero_error_summary(self) -> None:
        schema = self.root / "schema.json"
        log = self.root / "generation.log"
        cases = [
            (1, "", {"openapi": "3.0.3", "paths": {"/x": {}}}, False),
            (0, "Error [View]: missing serializer", {}, False),
            (0, "Errors:   2 (1 unique)", {"openapi": "3.0.3", "paths": {"/x": {}}}, False),
            (0, "Errors: 0 (0 unique)", {"openapi": "3.0.3", "paths": {"/x": {}}}, True),
            (0, "", {"openapi": "3.0.3", "paths": {}}, False),
            (0, "", None, False),
        ]
        for status, diagnostic, value, succeeds in cases:
            with self.subTest(diagnostic=diagnostic, value=value):
                schema.write_text(json.dumps(value) if value is not None else "invalid json")
                result = subprocess.CompletedProcess([], status, "", diagnostic)
                with patch("tools.api_contract_support.snapshot.run_command", return_value=result):
                    if succeeds:
                        self.assertEqual(
                            generate_schema(self.repo, schema, log)["warning_count"], 0
                        )
                    else:
                        with self.assertRaises(ContractError):
                            generate_schema(self.repo, schema, log)
                self.assertEqual(log.read_text(), diagnostic)

    def test_missing_base_ref_fails(self) -> None:
        with self.assertRaises(ContractError):
            prepare_snapshots(self.repo, "does-not-exist", self.root / "snapshots")

    def test_binary_safe_base_source(self) -> None:
        self.write("example.py", "value = 5\r\n")
        self.git("add", "example.py")
        self.git("commit", "-qm", "crlf")
        destination = self.root / "snapshots"
        metadata = prepare_snapshots(self.repo, "HEAD", destination)
        self.assertEqual((destination / "base/example.py").read_bytes(), b"value = 5\r\n")
        self.assertEqual(metadata["base_source_digest"], metadata["head_source_digest"])

    def test_option_like_base_ref_is_rejected(self) -> None:
        with self.assertRaises(ContractError):
            prepare_snapshots(self.repo, "--all", self.root / "snapshots")

    def test_pth_and_pythonpath_cannot_rescue_deleted_module(self) -> None:
        stale = self.root / "stale"
        stale.mkdir()
        (stale / "deleted_contract_module.py").write_text("raise RuntimeError('stale loaded')\n")
        libraries = self.root / "site-packages"
        libraries.mkdir()
        (libraries / "editable.pth").write_text(str(stale) + "\n")
        self.write("manage.py", "import deleted_contract_module\n")
        log = self.root / "generation.log"
        with (
            patch.dict(os.environ, {"PYTHONPATH": str(stale)}),
            patch(
                "tools.api_contract_support.snapshot.sysconfig.get_path",
                return_value=str(libraries),
            ),
            self.assertRaises(ContractError),
        ):
            generate_schema(self.repo, self.root / "schema.json", log)
        self.assertIn("No module named 'deleted_contract_module'", log.read_text())
        self.assertNotIn("stale loaded", log.read_text())

    def test_bracketed_warning_is_counted(self) -> None:
        schema = self.root / "schema.json"
        schema.write_text(json.dumps({"openapi": "3.0.3", "paths": {"/x": {}}}))
        result = subprocess.CompletedProcess([], 0, "", "Warning [Serializer]: fallback\n")
        with patch("tools.api_contract_support.snapshot.run_command", return_value=result):
            metadata = generate_schema(self.repo, schema, self.root / "generation.log")
        self.assertEqual(metadata["warning_count"], 1)


if __name__ == "__main__":
    unittest.main()
