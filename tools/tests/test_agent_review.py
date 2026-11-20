import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.agent_review import run_checks

IMPLEMENTATION_ROOT = Path(__file__).resolve().parents[2]
INTENT = "Review the update to the operator instructions."
FINDING = {
    "path": "README.md",
    "line": 1,
    "problem": "The documented unit is incorrect.",
    "scenario": "An operator follows the instructions and uses hours instead of minutes.",
}


class AgentReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)
        self.repo = self.workspace / "repo"
        self.repo.mkdir()
        self.marker = self.workspace / "reviewer-called"
        self.report_path = self.repo / ".artifacts" / "agent-review" / "report.json"
        self.git("init", "-q")
        self.git("config", "user.email", "tests@example.invalid")
        self.git("config", "user.name", "Review Tests")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", str(self.workspace / "hooks"))
        self.write(".gitignore", ".artifacts/\n")
        self.write("README.md", "Original instructions\n")
        self.git("add", ".")
        self.git("commit", "-qm", "Base")
        self.git("branch", "base")
        self.write("README.md", "Updated instructions\n")
        self.commit_readme()
        reviewer = self.workspace / "codex"
        reviewer.write_text(
            f"#!{sys.executable}\n"
            + textwrap.dedent(
                r"""
                import os
                import sys
                from pathlib import Path

                Path(os.environ["REVIEW_TEST_MARKER"]).write_text(sys.stdin.read())
                if os.environ["REVIEW_TEST_EDIT"] == "yes":
                    Path(os.environ["REVIEW_TEST_REPO"], "README.md").write_text("Edited\n")
                output = Path(sys.argv[sys.argv.index("-o") + 1])
                output.write_text(os.environ["REVIEW_TEST_RESPONSE"])
                raise SystemExit(int(os.environ["REVIEW_TEST_EXIT"]))
                """
            ).lstrip("\n"),
            encoding="utf-8",
        )
        reviewer.chmod(0o755)

    def write(self, path: str, content: str) -> None:
        (self.repo / path).write_text(content, encoding="utf-8")

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.repo, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    def commit_readme(self) -> None:
        self.git("add", "README.md")
        self.git("commit", "-qm", "Update instructions")

    def review(
        self,
        status: str,
        *,
        response: str | None = None,
        reviewer_exit: int = 0,
        edit: bool = False,
        reviewer_called: bool = True,
        scenario: tuple[str, ...] = (),
        django_scenario: bool = False,
        scenario_on_path: bool = False,
    ) -> dict[str, object]:
        self.marker.unlink(missing_ok=True)
        self.report_path.unlink(missing_ok=True)
        env = {
            **os.environ,
            "PATH": os.pathsep.join((str(self.workspace), os.environ["PATH"])),
            "PYTHONPATH": str(IMPLEMENTATION_ROOT),
            "REVIEW_TEST_MARKER": str(self.marker),
            "REVIEW_TEST_REPO": str(self.repo),
            "REVIEW_TEST_RESPONSE": (
                json.dumps(
                    {"complete": True, "summary": "Reviewed the instructions.", "findings": []}
                )
                if response is None
                else response
            ),
            "REVIEW_TEST_EXIT": str(reviewer_exit),
            "REVIEW_TEST_EDIT": "yes" if edit else "no",
        }
        flag = "--django-scenario" if django_scenario else "--scenario"
        if scenario_on_path:
            env["PATH"] = os.pathsep.join(("tools", env["PATH"]))
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.agent_review",
                "--base",
                "base",
                "--intent",
                INTENT,
                *([flag, *scenario] if scenario else []),
            ],
            cwd=self.repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        diagnostic = result.stdout + result.stderr
        self.assertEqual(result.returncode == 0, status == "passed", diagnostic)
        self.assertEqual(self.marker.exists(), reviewer_called, diagnostic)
        self.assertTrue(self.report_path.is_file(), diagnostic)
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], status, report)
        return report

    def test_clean_committed_candidate_passes(self) -> None:
        report = self.review("passed")
        self.assertEqual(report["head"], self.git("rev-parse", "HEAD"))
        self.assertIn(INTENT, self.marker.read_text(encoding="utf-8"))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_findings_require_changes_and_new_commit_can_pass(self) -> None:
        finding = {"complete": True, "summary": "Fix the documented unit.", "findings": [FINDING]}
        report = self.review("changes_requested", response=json.dumps(finding))
        self.assertEqual(report["review"], finding)
        self.write("README.md", "Wait five minutes.\n")
        self.commit_readme()
        self.review("passed")

    def test_reviewer_errors_block(self) -> None:
        for response, reviewer_exit in [
            ("not JSON", 0),
            ("", 0),
            ('{"complete": true, "summary": "Missing findings."}', 0),
            ('{"complete": true, "summary": "Incomplete finding.", "findings": [{}]}', 0),
            ('{"complete": false, "summary": "Review incomplete.", "findings": []}', 0),
            ('{"summary": "Missing completion status.", "findings": []}', 0),
            (None, 2),
        ]:
            with self.subTest(response=response, reviewer_exit=reviewer_exit):
                self.review("blocked", response=response, reviewer_exit=reviewer_exit)

    def test_dirty_worktree_blocks_before_review(self) -> None:
        self.write("README.md", "Draft instructions\n")
        self.review("blocked", reviewer_called=False)

    def test_untracked_file_blocks_before_review(self) -> None:
        self.write("draft.md", "Draft instructions\n")
        self.review("blocked", reviewer_called=False)

    def test_empty_candidate_diff_blocks_before_review(self) -> None:
        self.write("README.md", "Original instructions\n")
        self.commit_readme()
        self.review("blocked", reviewer_called=False)

    def test_whitespace_error_blocks_before_review(self) -> None:
        self.write("README.md", "Updated instructions with trailing whitespace \n")
        self.commit_readme()
        self.review("blocked", reviewer_called=False)

    def test_concurrent_tracked_edit_blocks_pass(self) -> None:
        self.review("blocked", edit=True)
        self.assertEqual((self.repo / "README.md").read_text(encoding="utf-8"), "Edited\n")

    def test_whitespace_gate_compares_to_merge_base(self) -> None:
        self.git("checkout", "-q", "base")
        self.write("base-only.md", "Existing trailing whitespace \n")
        self.git("add", "base-only.md")
        self.git("commit", "-qm", "Shared history")
        merge_base = self.git("rev-parse", "HEAD")
        self.git("checkout", "-qb", "candidate")
        self.write("README.md", "Candidate instructions\n")
        self.commit_readme()
        self.git("checkout", "-q", "base")
        self.git("rm", "base-only.md")
        self.git("commit", "-qm", "Remove upstream file")
        self.git("checkout", "-q", "candidate")

        report = self.review("passed")
        self.assertEqual(report["base"], merge_base)

    def test_lite_uses_candidate_sample_and_refreshes_schema_before_test(self) -> None:
        (self.repo / "tools").mkdir()
        (self.repo / "custom_view_sample").mkdir()
        self.write("custom_view_sample/marker", "candidate")
        self.write(
            "tools/lite.sh",
            "#!/bin/sh\ntest -f .artifacts/migrations-ready && "
            'test "$(cat custom_view/marker)" = candidate\n',
        )
        (self.repo / "tools/lite.sh").chmod(0o755)
        uv = self.workspace / "uv"
        uv.write_text(
            "#!/bin/sh\n"
            'test "$*" = "run python manage.py makemigrations --noinput" && '
            'test "$PAGODA_LITE" = 1 && test -L custom_view && '
            'test -f "$PAGODA_REVIEW_MIGRATIONS/__init__.py" && touch .artifacts/migrations-ready\n'
        )
        uv.chmod(0o755)
        self.git("add", "tools/lite.sh", "custom_view_sample/marker")
        self.git("commit", "-qm", "Add sample and Lite fixture")
        # The runner also selects airone and entry because the Lite script changed.
        self.review("passed", scenario=("tools/lite.sh", "test", "job"))
        self.assertFalse((self.repo / "custom_view").is_symlink())
        (self.repo / "custom_view").mkdir()
        (self.repo / ".git" / "info" / "exclude").write_text("custom_view/\n")
        self.write("custom_view/marker", "local extension")
        self.review("blocked", reviewer_called=False, scenario=("tools/lite.sh", "test", "job"))
        self.assertEqual((self.repo / "custom_view/marker").read_text(), "local extension")

    def test_docs_only_django_scenarios_are_isolated_regardless_of_path(self) -> None:
        (self.repo / "tools").mkdir()
        (self.repo / "custom_view_sample").mkdir()
        self.write("custom_view_sample/marker", "candidate")
        django_environment = (
            'test -L custom_view && test "$(cat custom_view/marker)" = candidate && '
            'test -f "$PAGODA_REVIEW_MIGRATIONS/__init__.py"'
        )
        scripts = ("tools/lite.sh", "tools/check_generated_client.sh")
        for script in scripts:
            body = django_environment
            if script == "tools/lite.sh":
                body += " && test -f .artifacts/migrations-ready"
            self.write(script, f"#!/bin/sh\n{body}\n")
            (self.repo / script).chmod(0o755)
        uv = self.workspace / "uv"
        uv.write_text(
            "#!/bin/sh\n"
            'test "$*" = "run python manage.py makemigrations --noinput" && '
            f"{django_environment} && touch .artifacts/migrations-ready\n"
        )
        uv.chmod(0o755)
        self.git("add", *scripts, "custom_view_sample/marker")
        self.git("commit", "-qm", "Add existing Django commands")
        self.git("branch", "-f", "base", "HEAD")
        self.write("README.md", "Candidate instructions\n")
        self.commit_readme()

        for script in scripts:
            scenarios = (
                (script,),
                (f"./{script}",),
                (str(self.repo / script),),
                (Path(script).name,),
                ("bash", script),
                ("sh", "-eu", "--", f"./{script}"),
                ("bash", "--noprofile", "-eo", "pipefail", str(self.repo / script)),
            )
            for scenario in scenarios:
                with self.subTest(scenario=scenario):
                    (self.repo / ".artifacts/migrations-ready").unlink(missing_ok=True)
                    report = self.review("passed", scenario=scenario, scenario_on_path=True)
                    self.assertEqual(report["paths"], ["README.md"])
                    self.assertFalse((self.repo / "custom_view").is_symlink())

        wrapper = (
            f"{django_environment} && test -f .artifacts/migrations-ready"
            ' && test "$PAGODA_LITE" = 1'
        )
        (self.repo / ".artifacts/migrations-ready").unlink(missing_ok=True)
        self.review("passed", scenario=("sh", "-c", wrapper), django_scenario=True)
        self.assertFalse((self.repo / "custom_view").exists())

    def test_docs_only_non_django_scenario_does_not_prepare_django(self) -> None:
        self.review(
            "passed",
            scenario=("sh", "-c", 'test -z "$PAGODA_REVIEW_MIGRATIONS" && test ! -e custom_view'),
        )

    def test_gate_timeout_stops_descendant_writes_and_records_receipt(self) -> None:
        ready = self.workspace / "descendant-started"
        unexpected = self.workspace / "unexpected-write"
        parent = """sh -c ': > "$1"; sleep 0.8; : > "$2"' sh "$1" "$2" & wait"""
        report: dict[str, list[dict[str, object]]] = {"checks": []}
        with patch("tools.agent_review.CHECK_TIMEOUT", 0.4):
            with self.assertRaises(subprocess.TimeoutExpired):
                run_checks(
                    [["sh", "-c", parent, "sh", str(ready), str(unexpected)]],
                    self.workspace,
                    report,
                    os.environ.copy(),
                )
        self.assertTrue(ready.exists())
        self.assertTrue(report["checks"][0]["timed_out"])
        self.assertIn("seconds", report["checks"][0])
        time.sleep(0.9)
        self.assertFalse(unexpected.exists())

    def test_supplied_acceptance_failure_prevents_review(self) -> None:
        report = self.review(
            "blocked",
            reviewer_called=False,
            scenario=(sys.executable, "-c", "raise SystemExit(23)"),
        )
        self.assertEqual(report["checks"][-1]["returncode"], 23)

    def test_git_index_flags_cannot_hide_modified_code(self) -> None:
        for flag in ("assume-unchanged", "skip-worktree"):
            with self.subTest(flag=flag):
                self.git("update-index", f"--{flag}", "README.md")
                self.write("README.md", "Local content differs from reviewed commit\n")
                self.assertEqual(self.git("status", "--porcelain"), "")
                self.review("blocked", reviewer_called=False)
                self.git("update-index", f"--no-{flag}", "README.md")
                self.git("restore", "README.md")

    def test_codegen_gate_detects_drift_without_overwriting_committed_client(self) -> None:
        scripts = self.repo / "tools"
        scripts.mkdir()
        gate = scripts / "check_generated_client.sh"
        shutil.copy2(IMPLEMENTATION_ROOT / "tools" / gate.name, gate)
        generator = scripts / "generate_client.sh"
        generator.write_text(
            '#!/bin/sh\nset -eu\ncp README.md "${PAGODA_CLIENT_SPEC_PATH:-spec.yaml}"\n'
            'mkdir -p "$1" && cp README.md "$1/model.ts"\n'
        )
        generator.chmod(0o755)
        spec = self.repo / "spec.yaml"
        spec.write_text("Local draft schema\n")
        client = self.repo / "frontend/src/apiclient/autogenerated"
        client.mkdir(parents=True)
        model = client / "model.ts"
        model.write_text("Updated instructions\n")
        self.assertEqual(subprocess.run([gate], capture_output=True).returncode, 0)
        self.write("README.md", "Changed schema\n")
        self.assertEqual(subprocess.run([gate], capture_output=True).returncode, 1)
        self.assertEqual(model.read_text(), "Updated instructions\n")
        self.assertEqual(spec.read_text(), "Local draft schema\n")
        self.assertEqual(list(self.repo.glob("pagoda-client-check.*")), [])
