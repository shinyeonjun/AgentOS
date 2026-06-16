from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from agentos.platform_checks import render_doctor, run_doctor


class PlatformChecksTests(unittest.TestCase):
    def test_doctor_warns_for_missing_optional_tools(self) -> None:
        with (
            patch("agentos.platform_checks.platform.system", return_value="Linux"),
            patch("agentos.platform_checks.is_wsl", return_value=False),
            patch("agentos.platform_checks.shutil.which", return_value=None),
        ):
            result = run_doctor(workspace_path=Path("/home/user/project"))

        self.assertEqual(result.status, "warning")
        statuses = {check.name: check.status for check in result.checks}
        self.assertEqual(statuses["platform"], "passed")
        self.assertEqual(statuses["docker"], "warning")
        self.assertEqual(statuses["patch"], "warning")

    def test_doctor_fails_on_native_windows(self) -> None:
        with (
            patch("agentos.platform_checks.platform.system", return_value="Windows"),
            patch("agentos.platform_checks.shutil.which", return_value="/usr/bin/tool"),
        ):
            result = run_doctor(workspace_path=Path("C:/project"))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.checks[0].name, "platform")
        self.assertEqual(result.checks[0].status, "failed")
        self.assertIn("WSL2", result.checks[0].message)

    def test_doctor_warns_for_windows_mounted_wsl_workspace(self) -> None:
        with (
            patch("agentos.platform_checks.platform.system", return_value="Linux"),
            patch("agentos.platform_checks.is_wsl", return_value=True),
            patch("agentos.platform_checks.shutil.which", return_value="/usr/bin/tool"),
            patch("pathlib.Path.resolve", return_value=Path("/mnt/c/projects/agentos")),
        ):
            result = run_doctor(workspace_path=Path("/mnt/c/projects/agentos"))

        self.assertEqual(result.status, "warning")
        workspace_check = result.checks[-1]
        self.assertEqual(workspace_check.name, "workspace_path")
        self.assertEqual(workspace_check.status, "warning")

    def test_render_doctor_is_human_readable(self) -> None:
        with (
            patch("agentos.platform_checks.platform.system", return_value="Linux"),
            patch("agentos.platform_checks.is_wsl", return_value=False),
            patch("agentos.platform_checks.shutil.which", return_value="/usr/bin/tool"),
        ):
            result = run_doctor(workspace_path=Path("/home/user/project"))

        rendered = render_doctor(result)
        self.assertIn("status: passed", rendered)
        self.assertIn("platform", rendered)


if __name__ == "__main__":
    unittest.main()
