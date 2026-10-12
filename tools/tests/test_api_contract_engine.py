"""Engine failures must never be confused with a successful comparison."""

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.api_contract_support.common import ContractError
from tools.api_contract_support.engine import PINNED_VERSION, install_engine, run_engine

INSTALLED_ENGINE = Path(__file__).resolve().parents[2] / ".cache/api-contract/bin/oasdiff"


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.binary = self.root / "oasdiff"
        self.binary.write_bytes(b"binary")
        self.base = self.root / "base.json"
        self.head = self.root / "head.json"
        for spec in (self.base, self.head):
            spec.write_text('{"openapi":"3.0.3","paths":{}}')

    def results(self, diff="{}", findings="[]", code=0):
        return [
            subprocess.CompletedProcess([], 0, f"oasdiff version {PINNED_VERSION}\n", ""),
            subprocess.CompletedProcess([], code, diff, "failure"),
            subprocess.CompletedProcess([], 0, findings, ""),
        ]

    def run_comparison(self):
        return run_engine(self.binary, self.base, self.head, self.root / "output")

    @patch("tools.api_contract_support.engine.run_command")
    def test_success_preserves_findings_and_artifacts(self, command):
        findings = [{"id": "removed", "level": 3, "text": "removed", "path": "/x"}]
        command.side_effect = self.results(findings=json.dumps(findings))
        result = self.run_comparison()
        self.assertEqual(result["findings"], findings)
        self.assertEqual(json.loads((self.root / "output/findings.json").read_text()), findings)
        self.assertEqual(len(result["binary_sha256"]), 64)

    @patch("tools.api_contract_support.engine.run_command")
    def test_nonzero_is_error_even_with_valid_json(self, command):
        command.side_effect = self.results(code=1)
        with self.assertRaises(ContractError):
            self.run_comparison()

    @patch("tools.api_contract_support.engine.run_command")
    def test_malformed_and_unknown_records_fail(self, command):
        for diff, findings in (
            ("oops", "[]"),
            ("[]", "[]"),
            ("{}", "{}"),
            ("{}", '[{"id":"x","text":"x","level":4}]'),
        ):
            with self.subTest(diff=diff, findings=findings):
                command.side_effect = self.results(diff, findings)
                with self.assertRaises(ContractError):
                    self.run_comparison()

    @patch("tools.api_contract_support.engine.run_command")
    def test_wrong_version_fails(self, command):
        command.return_value = subprocess.CompletedProcess([], 0, "oasdiff version 0.1", "")
        with self.assertRaises(ContractError):
            self.run_comparison()
        self.assertEqual(command.call_count, 1)

    @patch("tools.api_contract_support.engine.run_command")
    def test_external_reference_rejected_before_execution(self, command):
        self.base.write_text('{"schema":{"$ref":"https://example.com/spec"}}')
        with self.assertRaises(ContractError):
            self.run_comparison()
        command.assert_not_called()

    def test_installer_rejects_checksum_and_unsafe_archive(self):
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w:gz") as target:
            member = tarfile.TarInfo("../oasdiff")
            member.size = 1
            target.addfile(member, io.BytesIO(b"x"))
        payload = archive.getvalue()
        for digest in ("invalid", hashlib.sha256(payload).hexdigest()):
            with (
                self.subTest(digest=digest),
                patch("tools.api_contract_support.engine.platform.system", return_value="Linux"),
                patch("tools.api_contract_support.engine.platform.machine", return_value="x86_64"),
                patch(
                    "tools.api_contract_support.engine.ASSET_SHA256", {("linux", "amd64"): digest}
                ),
                patch(
                    "tools.api_contract_support.engine.urllib.request.urlopen",
                    return_value=io.BytesIO(payload),
                ),
            ):
                with self.assertRaises(ContractError):
                    install_engine(self.root / "installed")
                self.assertFalse((self.root / "installed").exists())

    def executable(self, version=PINNED_VERSION, diff="{}", findings="[]", code=0):
        self.binary.write_text(
            f"#!{sys.executable}\n"
            "import sys\n"
            f"if '--version' in sys.argv: print('oasdiff version {version}')\n"
            f"elif sys.argv[1] == 'diff': print({diff!r}); sys.exit({code})\n"
            f"else: print({findings!r})\n"
        )
        self.binary.chmod(0o755)

    def test_real_process_output_failures(self):
        for options, message in (
            ({"version": "0.1"}, "Expected oasdiff"),
            ({"diff": "malformed"}, "malformed JSON"),
            ({"code": 2}, "diff failed"),
            ({"findings": '[{"id":"x","text":"x","level":99}]'}, "malformed finding"),
        ):
            with self.subTest(options=options):
                self.executable(**options)
                with self.assertRaisesRegex(ContractError, message):
                    self.run_comparison()

    def test_installer_valid_archive_and_wrong_version(self):
        for version in (PINNED_VERSION, "0.1"):
            self.executable(version=version)
            archive = io.BytesIO()
            with tarfile.open(fileobj=archive, mode="w:gz") as target:
                target.add(self.binary, arcname="oasdiff")
            payload = archive.getvalue()
            with (
                self.subTest(version=version),
                patch("tools.api_contract_support.engine.platform.system", return_value="Linux"),
                patch("tools.api_contract_support.engine.platform.machine", return_value="x86_64"),
                patch(
                    "tools.api_contract_support.engine.ASSET_SHA256",
                    {("linux", "amd64"): hashlib.sha256(payload).hexdigest()},
                ),
                patch(
                    "tools.api_contract_support.engine.urllib.request.urlopen",
                    return_value=io.BytesIO(payload),
                ),
            ):
                destination = self.root / f"installed-{version}"
                if version == PINNED_VERSION:
                    self.assertEqual(install_engine(destination), destination.resolve())
                    self.assertEqual(destination.read_bytes(), self.binary.read_bytes())
                    self.assertTrue(destination.stat().st_mode & 0o111)
                else:
                    with self.assertRaisesRegex(ContractError, "Expected oasdiff"):
                        install_engine(destination)
                    self.assertFalse(destination.exists())

    @patch("tools.api_contract_support.engine.urllib.request.urlopen")
    @patch("tools.api_contract_support.engine.platform.machine", return_value="s390x")
    def test_unsupported_architecture_never_downloads(self, machine, urlopen):
        with self.assertRaisesRegex(ContractError, "Unsupported"):
            install_engine(self.root / "installed")
        urlopen.assert_not_called()

    @patch("tools.api_contract_support.engine.run_command")
    def test_subprocess_configuration_is_isolated(self, command):
        command.side_effect = self.results()
        with patch.dict(os.environ, {"OASDIFF_CONFIG": "/malicious", "HOME": "/unsafe"}):
            result = self.run_comparison()
        self.assertEqual(result["config_sha256"], hashlib.sha256(b"{}\n").hexdigest())
        self.assertIn("--allow-external-refs=false", result["flags"])
        for call in command.call_args_list:
            self.assertNotIn("HOME", call.kwargs["env"])
            self.assertFalse(any(key.startswith("OASDIFF_") for key in call.kwargs["env"]))
            self.assertIn("--config", call.args[0])
            self.assertNotEqual(call.kwargs["cwd"], Path.cwd())

    @unittest.skipUnless(
        INSTALLED_ENGINE.exists(),
        "Run tools/api_contract.py install for the real-engine regression",
    )
    def test_real_pinned_binary_ignores_local_and_environment_config(self):
        spec = {
            "openapi": "3.0.3",
            "info": {"title": "test", "version": "1"},
            "paths": {"/deleted": {"get": {"responses": {"200": {"description": "OK"}}}}},
        }
        self.base.write_text(json.dumps(spec))
        spec["paths"] = {}
        self.head.write_text(json.dumps(spec))
        malicious = self.root / ".oasdiff.yaml"
        malicious.write_text("unmatch-path: .*\n")
        original = Path.cwd()
        try:
            os.chdir(self.root)
            with patch.dict(os.environ, {"OASDIFF_CONFIG": str(malicious), "HOME": str(self.root)}):
                result = run_engine(
                    INSTALLED_ENGINE,
                    self.base,
                    self.head,
                    self.root / "output",
                )
            self.assertTrue(any(finding["level"] == 3 for finding in result["findings"]))
        finally:
            os.chdir(original)


if __name__ == "__main__":
    unittest.main()
