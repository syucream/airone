import subprocess
from unittest import TestCase, mock

from airone.lib.version import get_version


class VersionTest(TestCase):
    @mock.patch("airone.lib.version.subprocess.run")
    def test_returns_first_application_tag_without_a_shell(self, run: mock.Mock) -> None:
        run.return_value = subprocess.CompletedProcess([], 0, stdout="v1.2.3\nv1.2.4\n")

        self.assertEqual(get_version("/checkout with spaces"), "v1.2.3")

        run.assert_called_once_with(
            ["git", "tag", "--points-at"],
            cwd="/checkout with spaces",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1,
            check=True,
        )

    @mock.patch("airone.lib.version.subprocess.run")
    def test_excludes_tags_containing_core_package_marker(self, run: mock.Mock) -> None:
        run.return_value = subprocess.CompletedProcess(
            [], 0, stdout="pagoda-core-1.0\npreview-pagoda-core-2.0\nv3.0\nv4.0\n"
        )

        self.assertEqual(get_version("/checkout"), "v3.0")

    @mock.patch("airone.lib.version.subprocess.run")
    def test_missing_application_tags_warn_and_return_unknown(self, run: mock.Mock) -> None:
        for tags in ("", "\n", "pagoda-core-1.0\n"):
            with self.subTest(tags=tags):
                run.return_value = subprocess.CompletedProcess([], 0, stdout=tags)
                with self.assertLogs("airone.lib.version", level="WARNING"):
                    self.assertEqual(get_version("/checkout"), "unknown")

    @mock.patch("airone.lib.version.subprocess.run")
    def test_unavailable_git_metadata_warns_without_failing_startup(self, run: mock.Mock) -> None:
        failures = (
            subprocess.TimeoutExpired(["git", "tag", "--points-at"], timeout=1),
            FileNotFoundError("git is unavailable"),
            subprocess.CalledProcessError(128, ["git", "tag", "--points-at"]),
            PermissionError("git cannot be executed"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                run.side_effect = failure
                with self.assertLogs("airone.lib.version", level="WARNING"):
                    self.assertEqual(get_version("/checkout"), "unknown")
