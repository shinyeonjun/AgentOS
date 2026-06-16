from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agentos.docker_sandbox import DEFAULT_IMAGE, build_docker_run_command, run_docker_task
from agentos.sandbox_policy import (
    MountPolicy,
    SandboxPolicy,
    build_default_policy,
    validate_sandbox_policy,
)


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
        self.assertIn("--cap-drop", command)
        self.assertIn("ALL", command)
        self.assertIn("--security-opt", command)
        self.assertIn("no-new-privileges", command)
        self.assertIn("--read-only", command)
        self.assertIn("--tmpfs", command)
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

    def test_build_docker_run_command_rejects_unsafe_network(self) -> None:
        with self.assertRaises(ValueError):
            build_docker_run_command(
                workspace_dir=Path("/tmp/work"),
                artifact_dir=Path("/tmp/artifacts"),
                command=["true"],
                network="host",
            )

    def test_default_sandbox_policy_passes(self) -> None:
        policy = build_default_policy(
            image=DEFAULT_IMAGE,
            network="none",
            workspace_dir=Path("/tmp/work"),
            artifact_dir=Path("/tmp/artifacts"),
        )
        validation = validate_sandbox_policy(policy)

        self.assertEqual(validation.status, "passed")
        self.assertTrue(validation.passed)

    def test_sandbox_policy_rejects_extra_writable_mount(self) -> None:
        policy = SandboxPolicy(
            image=DEFAULT_IMAGE,
            network="none",
            workdir="/agentos/work",
            mounts=(
                MountPolicy(host_path=Path("/tmp/work"), container_path="/agentos/work"),
                MountPolicy(host_path=Path("/tmp/artifacts"), container_path="/agentos/artifacts"),
                MountPolicy(host_path=Path("/tmp/host"), container_path="/agentos/host"),
            ),
        )
        validation = validate_sandbox_policy(policy)

        self.assertEqual(validation.status, "failed")
        failed_checks = {check.name for check in validation.checks if check.status == "failed"}
        self.assertIn("writable_mounts", failed_checks)

    def test_run_docker_task_writes_policy_artifact(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_project = root / "input-project"
            input_project.mkdir()
            (input_project / "README.md").write_text("hello policy\n", encoding="utf-8")
            fake_docker = root / "fake-docker"
            fake_docker.write_text(
                "#!/bin/sh\n"
                "artifacts=''\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = '-v' ]; then\n"
                "    shift\n"
                "    case \"$1\" in\n"
                "      *:/agentos/artifacts) artifacts=${1%:/agentos/artifacts} ;;\n"
                "    esac\n"
                "  fi\n"
                "  shift\n"
                "done\n"
                "printf 'ok\\n' > \"$artifacts/result.txt\"\n"
                "exit 0\n",
                encoding="utf-8",
            )
            fake_docker.chmod(0o755)

            result = run_docker_task(
                state_dir=root / "state",
                output_dir=root / "output",
                input_path=input_project,
                command=["sh", "-c", "printf ok"],
                docker_bin=str(fake_docker),
            )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.policy_status, "passed")
            policy_artifact = json.loads(result.policy_artifact.read_text())
            command_artifact = json.loads(result.command_artifact.read_text())
            review_package = json.loads(result.review_package_artifact.read_text())

            self.assertEqual(policy_artifact["validation"]["status"], "passed")
            self.assertEqual(command_artifact["policy_status"], "passed")
            self.assertEqual(command_artifact["policy_ref"], f"artifact://{result.session_id}/sandbox-policy.json")
            self.assertEqual(review_package["validation"]["checks"][0]["name"], "sandbox policy")
            self.assertEqual(review_package["validation"]["checks"][0]["status"], "passed")
            self.assertEqual(review_package["approval"]["scopes"], [])


if __name__ == "__main__":
    unittest.main()
