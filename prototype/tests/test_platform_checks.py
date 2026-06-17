from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from agentos.core.platform_checks import render_doctor, run_doctor


class PlatformChecksTests(unittest.TestCase):
    def test_doctor_warns_for_missing_docker(self) -> None:
        with (
            patch("agentos.core.platform_checks.platform.system", return_value="Linux"),
            patch("agentos.core.platform_checks.is_wsl", return_value=False),
            patch("agentos.core.platform_checks.shutil.which", return_value=None),
        ):
            result = run_doctor(workspace_path=Path("/home/user/project"))

        self.assertEqual(result.status, "warning")
        statuses = {check.name: check.status for check in result.checks}
        self.assertEqual(statuses["platform"], "passed")
        self.assertEqual(statuses["docker"], "warning")
        self.assertNotIn("patch", statuses)

    def test_doctor_warns_on_native_windows(self) -> None:
        with (
            patch("agentos.core.platform_checks.platform.system", return_value="Windows"),
            patch("agentos.core.platform_checks.shutil.which", return_value="/usr/bin/tool"),
        ):
            result = run_doctor(workspace_path=Path("C:/project"))

        self.assertEqual(result.status, "warning")
        self.assertEqual(result.checks[0].name, "platform")
        self.assertEqual(result.checks[0].status, "warning")
        self.assertIn("experimental", result.checks[0].message)

    def test_doctor_warns_when_shell_does_not_expand_pwd(self) -> None:
        with (
            patch("agentos.core.platform_checks.platform.system", return_value="Windows"),
            patch("agentos.core.platform_checks.shutil.which", return_value="/usr/bin/tool"),
            patch("pathlib.Path.resolve", return_value=Path("D:/AgentOS/$PWD")),
        ):
            result = run_doctor(workspace_path=Path("$PWD"))

        self.assertEqual(result.status, "warning")
        workspace_check = result.checks[-1]
        self.assertEqual(workspace_check.name, "workspace_path")
        self.assertEqual(workspace_check.status, "warning")
        self.assertIn("$PWD", workspace_check.message)

    def test_doctor_warns_for_windows_mounted_wsl_workspace(self) -> None:
        with (
            patch("agentos.core.platform_checks.platform.system", return_value="Linux"),
            patch("agentos.core.platform_checks.is_wsl", return_value=True),
            patch("agentos.core.platform_checks.shutil.which", return_value="/usr/bin/tool"),
            patch("pathlib.Path.resolve", return_value=Path("/mnt/c/projects/agentos")),
        ):
            result = run_doctor(workspace_path=Path("/mnt/c/projects/agentos"))

        self.assertEqual(result.status, "warning")
        workspace_check = result.checks[-1]
        self.assertEqual(workspace_check.name, "workspace_path")
        self.assertEqual(workspace_check.status, "warning")

    def test_render_doctor_is_human_readable(self) -> None:
        with (
            patch("agentos.core.platform_checks.platform.system", return_value="Linux"),
            patch("agentos.core.platform_checks.is_wsl", return_value=False),
            patch("agentos.core.platform_checks.shutil.which", return_value="/usr/bin/tool"),
        ):
            result = run_doctor(workspace_path=Path("/home/user/project"))

        rendered = render_doctor(result)
        self.assertIn("status: passed", rendered)
        self.assertIn("platform", rendered)


if __name__ == "__main__":
    unittest.main()
