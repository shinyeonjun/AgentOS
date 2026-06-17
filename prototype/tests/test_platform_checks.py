from __future__ import annotations

import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from agentos.core.platform_checks import prepare_docker_environment, render_doctor, run_doctor


def _docker_success(command: list[str], **_: object) -> CompletedProcess[str]:
    return CompletedProcess(command, 0, stdout="ok\n", stderr="")


def _docker_image_missing(command: list[str], **_: object) -> CompletedProcess[str]:
    if command[:3] == ["docker", "image", "inspect"]:
        return CompletedProcess(command, 1, stdout="", stderr="No such image\n")
    return CompletedProcess(command, 0, stdout="ok\n", stderr="")


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
        self.assertEqual(statuses["docker_cli"], "warning")
        self.assertEqual(statuses["docker_daemon"], "warning")
        self.assertEqual(statuses["docker_image"], "warning")
        self.assertNotIn("patch", statuses)

    def test_doctor_warns_on_native_windows(self) -> None:
        with (
            patch("agentos.core.platform_checks.platform.system", return_value="Windows"),
            patch("agentos.core.platform_checks.shutil.which", return_value="/usr/bin/tool"),
            patch("agentos.core.platform_checks.subprocess.run", side_effect=_docker_success),
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
            patch("agentos.core.platform_checks.subprocess.run", side_effect=_docker_success),
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
            patch("agentos.core.platform_checks.subprocess.run", side_effect=_docker_success),
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
            patch("agentos.core.platform_checks.subprocess.run", side_effect=_docker_success),
        ):
            result = run_doctor(workspace_path=Path("/home/user/project"))

        rendered = render_doctor(result)
        self.assertIn("status: passed", rendered)
        self.assertIn("platform", rendered)

    def test_doctor_warns_when_default_image_is_missing(self) -> None:
        with (
            patch("agentos.core.platform_checks.platform.system", return_value="Linux"),
            patch("agentos.core.platform_checks.is_wsl", return_value=False),
            patch("agentos.core.platform_checks.shutil.which", return_value="/usr/bin/tool"),
            patch("agentos.core.platform_checks.subprocess.run", side_effect=_docker_image_missing),
        ):
            result = run_doctor(workspace_path=Path("/home/user/project"))

        statuses = {check.name: check.status for check in result.checks}
        self.assertEqual(result.status, "warning")
        self.assertEqual(statuses["docker_daemon"], "passed")
        self.assertEqual(statuses["docker_image"], "warning")

    def test_prepare_builds_default_image_when_missing(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command: list[str], **_: object) -> CompletedProcess[str]:
            commands.append(command)
            if command[:3] == ["docker", "image", "inspect"]:
                return CompletedProcess(command, 1, stdout="", stderr="No such image\n")
            return CompletedProcess(command, 0, stdout="built\n", stderr="")

        with (
            patch("agentos.core.platform_checks.shutil.which", return_value="/usr/bin/tool"),
            patch("agentos.core.platform_checks.subprocess.run", side_effect=fake_run),
        ):
            result = prepare_docker_environment()

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.action, "build_default_image")
        self.assertIn(["docker", "build", "-t", "agentos-base:0.1", "-"], commands)

    def test_prepare_reports_missing_custom_image_without_pull(self) -> None:
        with (
            patch("agentos.core.platform_checks.shutil.which", return_value="/usr/bin/tool"),
            patch("agentos.core.platform_checks.subprocess.run", side_effect=_docker_image_missing),
        ):
            result = prepare_docker_environment(image="example/custom:1")

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.action, "none")
        self.assertFalse(result.image_available)


if __name__ == "__main__":
    unittest.main()
