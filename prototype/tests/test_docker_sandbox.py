from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agentos.sandbox.docker_sandbox import DEFAULT_IMAGE, build_docker_run_command, run_docker_task
from agentos.sandbox.sandbox_policy import (
    MountPolicy,
    SandboxPolicy,
    build_default_policy,
    validate_sandbox_policy,
)
from fake_tools import write_python_tool


class DockerSandboxTests(unittest.TestCase):
    def test_build_docker_run_command_uses_safe_defaults(self) -> None:
        workspace_dir = _host_path("work")
        artifact_dir = _host_path("artifacts")
        command = build_docker_run_command(
            workspace_dir=workspace_dir,
            artifact_dir=artifact_dir,
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
        self.assertIn(f"{workspace_dir.resolve()}:/agentos/work", command)
        self.assertIn(f"{artifact_dir.resolve()}:/agentos/artifacts", command)
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

    def test_build_docker_run_command_omits_user_when_uid_is_unavailable(self) -> None:
        with (
            patch("agentos.sandbox.docker_sandbox.os.getuid", None, create=True),
            patch("agentos.sandbox.docker_sandbox.os.getgid", None, create=True),
        ):
            command = build_docker_run_command(
                workspace_dir=Path("/tmp/work"),
                artifact_dir=Path("/tmp/artifacts"),
                command=["true"],
            )

        self.assertNotIn("--user", command)

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
            workspace_dir=_host_path("work"),
            artifact_dir=_host_path("artifacts"),
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
            fake_docker = write_python_tool(
                root / "fake-docker",
                "from pathlib import Path\n"
                "import sys\n"
                "artifacts = None\n"
                "args = sys.argv[1:]\n"
                "for index, value in enumerate(args[:-1]):\n"
                "    if value == '-v' and args[index + 1].endswith(':/agentos/artifacts'):\n"
                "        artifacts = args[index + 1][:-len(':/agentos/artifacts')]\n"
                "if artifacts:\n"
                "    Path(artifacts, 'result.txt').write_text('ok\\n', encoding='utf-8')\n"
                "raise SystemExit(0)\n",
            )

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
            capability_artifact = json.loads(result.capability_artifact.read_text())
            command_artifact = json.loads(result.command_artifact.read_text())
            provenance_artifact = json.loads(result.provenance_artifact.read_text())
            review_package = json.loads(result.review_package_artifact.read_text())

            self.assertEqual(policy_artifact["validation"]["status"], "passed")
            self.assertEqual(provenance_artifact["status"], "unavailable")
            self.assertEqual(capability_artifact["capabilities"][0]["name"], "base")
            self.assertEqual(command_artifact["policy_status"], "passed")
            self.assertEqual(command_artifact["policy_ref"], f"artifact://{result.session_id}/sandbox-policy.json")
            self.assertEqual(command_artifact["capabilities_ref"], f"artifact://{result.session_id}/image-capabilities.json")
            self.assertEqual(command_artifact["image_provenance_ref"], f"artifact://{result.session_id}/image-provenance.json")
            self.assertEqual(review_package["validation"]["checks"][0]["name"], "sandbox policy")
            self.assertEqual(review_package["validation"]["checks"][0]["status"], "passed")
            self.assertEqual(review_package["validation"]["checks"][1]["name"], "image provenance")
            self.assertEqual(review_package["task"]["capabilities"], ["base"])
            self.assertEqual(review_package["artifacts"][0]["digest"]["algorithm"], "sha256")
            self.assertEqual(review_package["approval"]["scopes"], [])

    def test_run_docker_task_requires_directory_input(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_file = root / "README.md"
            input_file.write_text("hello\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "must be a directory"):
                run_docker_task(
                    state_dir=root / "state",
                    output_dir=root / "output",
                    input_path=input_file,
                    command=["true"],
                )


def _host_path(name: str) -> Path:
    return (Path.cwd() / ".agentos-test-paths" / name).resolve()


if __name__ == "__main__":
    unittest.main()
