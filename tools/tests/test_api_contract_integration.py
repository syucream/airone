"""Opt-in real Pagoda schema/engine journey in a disposable Git repository."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.api_contract_support.snapshot import prepare_snapshots

ROOT = Path(__file__).resolve().parents[2]
PROBE = """from rest_framework import generics, serializers
from rest_framework.response import Response


class ProbeSerializer(serializers.Serializer):
    label = serializers.CharField(required=False)


class ProbeView(generics.GenericAPIView):
    serializer_class = ProbeSerializer

    def post(self, request):
        return Response(request.data)
"""


@unittest.skipUnless(
    os.environ.get("PAGODA_CONTRACT_INTEGRATION") == "1",
    "Set PAGODA_CONTRACT_INTEGRATION=1 after installing the pinned engine",
)
class ContractIntegrationTest(unittest.TestCase):
    def test_real_schema_working_tree_and_failure_journey(self) -> None:
        binary = ROOT / ".cache/api-contract/bin/oasdiff"
        self.assertTrue(binary.is_file(), "Run tools/api_contract.py install first")
        with tempfile.TemporaryDirectory(prefix="pagoda-contract-integration-") as temporary:
            scratch = Path(temporary)
            prepare_snapshots(ROOT, "HEAD", scratch / "input")
            repo = scratch / "input/head"
            # Reconstruct the tracked sample layout before snapshotting this test repository.
            (repo / "custom_view").rename(repo / "custom_view_sample")
            (repo / ".gitignore").write_text(".cache/\n__pycache__/\n*.pyc\n")
            urls = repo / "entity/api_v2/urls.py"
            probe = repo / "entity/api_v2/contract_probe.py"
            probe.write_text(PROBE)
            original = (
                urls.read_text()
                .replace(
                    "from . import views",
                    "from . import views\nfrom .contract_probe import ProbeView",
                )
                .replace(
                    "urlpatterns = [",
                    'urlpatterns = [\n    path("contract-probe", ProbeView.as_view()),',
                )
            )
            urls.write_text(original)
            git_prefix = ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false"]
            for arguments in (
                ["init", "-q"],
                ["config", "user.name", "Contract Test"],
                ["config", "user.email", "contract@example.invalid"],
                ["add", "."],
                ["commit", "-qm", "Isolated real-schema fixture"],
            ):
                subprocess.run(git_prefix + arguments, cwd=repo, check=True, capture_output=True)

            evidence = []

            def run(label: str, expected: str, base: str = "HEAD") -> dict:
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "tools/api_contract.py"),
                        "check",
                        "--base-ref",
                        base,
                        "--oasdiff",
                        str(binary),
                        "--format",
                        "json",
                    ],
                    cwd=repo,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                report = json.loads(completed.stdout)
                evidence.append({"case": label, "report": report})
                self.assertEqual(report["status"], expected, report.get("error"))
                self.assertEqual(
                    completed.returncode, {"compatible": 0, "breaking": 1, "error": 2}[expected]
                )
                return report

            try:
                self.assertFalse(run("unchanged", "compatible")["has_changes"])
                urls.write_text(original.replace('"export",', '"export-renamed",'))
                self.assertGreater(run("rename endpoint", "breaking")["summary"]["breaking"], 0)
                urls.write_text(original)
                probe.write_text(PROBE.replace("required=False", "required=True"))
                run("new required input", "breaking")
                probe.write_text(PROBE.replace("serializers.CharField", "serializers.IntegerField"))
                run("property type change", "breaking")
                probe.write_text(
                    PROBE.replace("required=False", 'required=False, help_text="Note"')
                )
                report = run("description only", "compatible")
                self.assertTrue(report["has_changes"])
                self.assertEqual(report["findings"], [])
                probe.write_text(PROBE)
                extra = repo / "entity/api_v2/new_contract_probe.py"
                extra.write_text(PROBE)
                urls.write_text(
                    original.replace(
                        "from . import views",
                        "from . import views\n"
                        "from .new_contract_probe import ProbeView as NewProbeView",
                    ).replace(
                        "urlpatterns = [",
                        'urlpatterns = [\n    path("new-probe", NewProbeView.as_view()),',
                    )
                )
                report = run("untracked endpoint", "compatible")
                self.assertIn(
                    str(extra.relative_to(repo)), report["comparison"]["included_untracked"]
                )
                self.assertGreater(report["summary"]["non_breaking"], 0)
                urls.write_text(original + "\ninvalid Python !\n")
                self.assertIsNone(run("generation failure", "error")["summary"]["breaking"])
                urls.write_text(original)
                self.assertIsNone(run("missing base", "error", "missing-base")["has_changes"])
            finally:
                output = ROOT / ".cache/api-contract/integration-results.json"
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(evidence, indent=2) + "\n")
                # Persist exact schemas/logs for investigation after the temp checkout is gone.
                for case in evidence:
                    run_id = case["report"]["run_id"]
                    source = repo / ".cache/api-contract" / run_id
                    shutil.copytree(source, output.parent / run_id)


if __name__ == "__main__":
    unittest.main()
