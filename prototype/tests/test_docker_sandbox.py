from __future__ import annotations

import unittest
from pathlib import Path

from agentos.docker_sandbox import DEFAULT_IMAGE, build_docker_run_command


class DockerSandboxTests(unittest.TestCase):
    def test_build_docker_run_command_uses_safe_defaults(self) -> None:
        command = build_docker_run_command(
            workspace_dir=Path("/tmp/work"),
            artifact_dir=Path("/tmp/artifacts"),
            command=["sh", "-c", "cat README.md"],
        )

        self.assertEqual(command[0], "docker")
        self.assertIn("--rm", command)
        self.assertIn("--network", command)
        self.assertIn("none", command)
        self.assertIn("/tmp/work:/agentos/work", command)
        self.assertIn("/tmp/artifacts:/agentos/artifacts", command)
        self.assertIn(DEFAULT_IMAGE, command)
        self.assertEqual(command[-3:], ["sh", "-c", "cat README.md"])

    def test_build_docker_run_command_can_use_sudo(self) -> None:
        command = build_docker_run_command(
            workspace_dir=Path("/tmp/work"),
            artifact_dir=Path("/tmp/artifacts"),
            command=["true"],
            use_sudo=True,
        )

        self.assertEqual(command[:2], ["sudo", "docker"])


if __name__ == "__main__":
    unittest.main()
