import argparse
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.api_contract import (
    check,
    classify,
    comparison_summary,
    main,
    normalize_findings,
    render_markdown,
)
from tools.api_contract_support.common import ContractError, run_command


class ApiContractReportTest(unittest.TestCase):
    def test_report_summary_keeps_changes_and_digest_without_repeating_manifest(self) -> None:
        full = {
            "base_source_digest": "base",
            "head_source_digest": "head",
            "base_files": {"same.py": "1", "changed.py": "1", "deleted.py": "1"},
            "head_files": {"same.py": "1", "changed.py": "2", "new.py": "1"},
            "excluded": ["example.txt"],
            "included_untracked": ["new.py"],
        }
        summary = comparison_summary(full)
        self.assertNotIn("base_files", summary)
        self.assertNotIn("excluded", summary)
        self.assertEqual(summary["changed_source_files"], ["changed.py", "deleted.py", "new.py"])
        self.assertEqual(summary["head_source_digest"], "head")
        self.assertEqual(summary["included_untracked"], ["new.py"])
        self.assertEqual(summary["manifest"], "comparison.json")

    def finding(self, level: int = 3, source: str = "/first/base.json") -> dict:
        return {
            "id": "api-path-removed-without-deprecation",
            "level": level,
            "operation": "GET",
            "path": "/items/",
            "text": "api path removed without deprecation",
            "baseSource": {"file": source, "line": 10},
        }

    def test_finding_identity_does_not_depend_on_temporary_artifact_path(self) -> None:
        first = normalize_findings([self.finding()])
        second = normalize_findings([self.finding(source="/second/base.json")])
        self.assertEqual(first, second)
        self.assertEqual(first[0]["path"], "/items/")
        self.assertEqual(first[0]["method"], "GET")

    def test_classification_preserves_warning_without_falsely_reporting_breakage(self) -> None:
        for level, expected, code in (
            (1, "compatible", 0),
            (2, "review_required", 0),
            (3, "breaking", 1),
        ):
            with self.subTest(level=level):
                status, summary, exit_code = classify(normalize_findings([self.finding(level)]))
                self.assertEqual(status, expected)
                self.assertEqual(exit_code, code)
                self.assertEqual(sum(summary.values()), 1)
        self.assertEqual(
            classify([]),
            ("compatible", {"breaking": 0, "review_required": 0, "non_breaking": 0}, 0),
        )

    def test_unknown_engine_level_fails_closed(self) -> None:
        with self.assertRaises(ContractError):
            normalize_findings([self.finding(4)])
        with self.assertRaises(ContractError):
            normalize_findings([self.finding(True)])
        with self.assertRaises(ContractError):
            normalize_findings([{**self.finding(), "path": None}])

    def args(self, output: Path) -> argparse.Namespace:
        return argparse.Namespace(
            base_ref="origin/master", output_dir=str(output), oasdiff=None, timeout=1
        )

    def test_generation_failure_produces_unknown_counts_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch(
                    "tools.api_contract.run_command",
                    return_value=subprocess.CompletedProcess([], 0, str(root), ""),
                ),
                patch("tools.api_contract.environment_info", return_value={}),
                patch("tools.api_contract.resolve_engine", return_value=root / "oasdiff"),
                patch("tools.api_contract.prepare_snapshots", return_value={"base_sha": "abc"}),
                patch(
                    "tools.api_contract.generate_schema", side_effect=ContractError("bad schema")
                ),
                patch("tools.api_contract.run_engine") as engine,
            ):
                report, output = check(self.args(root / "report"))
            engine.assert_not_called()
            self.assertEqual(report["status"], "error")
            self.assertEqual(report["exit_code"], 2)
            self.assertIsNone(report["summary"]["breaking"])
            self.assertIsNone(report["has_changes"])
            self.assertEqual(report["error"]["stage"], "generate_base")
            self.assertEqual(json.loads((output / "report.json").read_text()), report)
            self.assertIn("bad schema", (output / "report.md").read_text())

    def test_existing_output_is_not_overwritten_and_json_setup_error_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            previous = output / "report.json"
            previous.write_text("previous successful evidence")
            with (
                patch(
                    "tools.api_contract.run_command",
                    return_value=subprocess.CompletedProcess([], 0, temporary, ""),
                ),
                patch("sys.stdout", new_callable=io.StringIO) as stdout,
                patch("sys.stderr", new_callable=io.StringIO),
            ):
                code = main(
                    ["check", "--base-ref", "HEAD", "--output-dir", temporary, "--format", "json"]
                )
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "error")
            self.assertEqual(previous.read_text(), "previous successful evidence")

    def test_description_only_diff_is_visible_without_consumer_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch(
                    "tools.api_contract.run_command",
                    return_value=subprocess.CompletedProcess([], 0, temporary, ""),
                ),
                patch("tools.api_contract.environment_info", return_value={}),
                patch("tools.api_contract.resolve_engine", return_value=root / "oasdiff"),
                patch("tools.api_contract.prepare_snapshots", return_value={}),
                patch("tools.api_contract.generate_schema", return_value={}),
                patch(
                    "tools.api_contract.run_engine",
                    return_value={
                        "version": "1.33.0",
                        "binary_sha256": "test",
                        "config_sha256": "test-config",
                        "flags": ["--format", "json"],
                        "diff": {"info": {"description": {"from": "a", "to": "b"}}},
                        "findings": [],
                    },
                ),
            ):
                report, _ = check(self.args(root / "report"))
            self.assertEqual(report["status"], "compatible")
            self.assertTrue(report["has_changes"])
            self.assertIn("diff.json", render_markdown(report))

    def test_timeout_is_a_comparison_error(self) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("oasdiff", 1)):
            with self.assertRaisesRegex(ContractError, "timed out"):
                run_command(["oasdiff"], timeout=1)


if __name__ == "__main__":
    unittest.main()
