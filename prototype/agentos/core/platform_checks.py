from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .default_paths import default_mcp_output_dir, default_mcp_state_dir
from .text_safety import safe_json_dumps
from .version_info import runtime_identity

DEFAULT_AGENTOS_IMAGE = "agentos-base:0.1"
DEFAULT_DOCKER_TIMEOUT_SECONDS = 30

_EMBEDDED_AGENTOS_DOCKERFILE = """\
FROM busybox:1.36
RUN mkdir -p /agentos/input /agentos/work /agentos/artifacts /agentos/logs /agentos/report \\
    && printf '%s\\n' \\
      '{' \\
      '  "schema_version": "0.2",' \\
      '  "image": "agentos-base:0.1",' \\
      '  "capabilities": [' \\
      '    {' \\
      '      "name": "base",' \\
      '      "kind": "runtime",' \\
      '      "description": "AgentOS workspace, artifact, policy, review, approval, and sync contract.",' \\
      '      "provides": ["/agentos/work", "/agentos/artifacts", "task.json", "review_package.json", "approval-gated sync"]' \\
      '    }' \\
      '  ],' \\
      '  "notes": [' \\
      '    "Image capabilities describe the sandbox environment contract.",' \\
      '    "Worker binaries such as Codex remain host-side adapters unless a separate worker image is declared."' \\
      '  ]' \\
      '}' > /agentos/capabilities.json
WORKDIR /agentos/work
"""


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
        }


@dataclass(frozen=True)
class DoctorResult:
    status: str
    checks: tuple[DoctorCheck, ...]

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checks": [check.to_dict() for check in self.checks],
        }

    def to_json(self) -> str:
        return safe_json_dumps(self.to_dict(), indent=2)


@dataclass(frozen=True)
class PrepareResult:
    status: str
    image: str
    action: str
    docker_available: bool
    image_available: bool
    message: str
    command: tuple[str, ...] = ()
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "image": self.image,
            "action": self.action,
            "docker_available": self.docker_available,
            "image_available": self.image_available,
            "message": self.message,
            "command": list(self.command),
            "exit_code": self.exit_code,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
        }


def run_doctor(
    workspace_path: Path | None = None,
    *,
    docker_bin: str = "docker",
    docker_sudo: bool = False,
    image: str = DEFAULT_AGENTOS_IMAGE,
) -> DoctorResult:
    if workspace_path is None:
        workspace_path = Path.cwd()
    docker_cli = _check_docker_binary(docker_bin=docker_bin, use_sudo=docker_sudo)
    docker_daemon = _check_docker_daemon(docker_bin=docker_bin, use_sudo=docker_sudo, docker_cli=docker_cli)
    docker_image = _check_docker_image(
        docker_bin=docker_bin,
        use_sudo=docker_sudo,
        image=image,
        docker_daemon=docker_daemon,
    )
    checks = (
        _check_platform(),
        _check_python(),
        _check_runtime_identity(),
        _check_mcp_storage_paths(),
        _check_agentos_cli(),
        docker_cli,
        docker_daemon,
        docker_image,
        _check_workspace_path(workspace_path),
    )
    status = "passed"
    if any(check.status == "failed" for check in checks):
        status = "failed"
    elif any(check.status == "warning" for check in checks):
        status = "warning"
    return DoctorResult(status=status, checks=checks)


def prepare_docker_environment(
    *,
    image: str = DEFAULT_AGENTOS_IMAGE,
    docker_bin: str = "docker",
    use_sudo: bool = False,
    build_default: bool = True,
    pull_missing: bool = False,
    timeout_seconds: int = 120,
) -> PrepareResult:
    docker_cli = _check_docker_binary(docker_bin=docker_bin, use_sudo=use_sudo)
    if docker_cli.status != "passed":
        return PrepareResult(
            status="failed",
            image=image,
            action="check_docker_cli",
            docker_available=False,
            image_available=False,
            message=docker_cli.message,
        )

    docker_daemon = _check_docker_daemon(docker_bin=docker_bin, use_sudo=use_sudo, docker_cli=docker_cli)
    if docker_daemon.status != "passed":
        return PrepareResult(
            status="failed",
            image=image,
            action="check_docker_daemon",
            docker_available=False,
            image_available=False,
            message=docker_daemon.message,
        )

    if _docker_image_exists(image=image, docker_bin=docker_bin, use_sudo=use_sudo):
        return PrepareResult(
            status="passed",
            image=image,
            action="none",
            docker_available=True,
            image_available=True,
            message=f"Docker image already available: {image}.",
        )

    if image == DEFAULT_AGENTOS_IMAGE and build_default:
        return _build_default_agentos_image(
            image=image,
            docker_bin=docker_bin,
            use_sudo=use_sudo,
            timeout_seconds=timeout_seconds,
        )

    if pull_missing:
        return _pull_docker_image(
            image=image,
            docker_bin=docker_bin,
            use_sudo=use_sudo,
            timeout_seconds=timeout_seconds,
        )

    return PrepareResult(
        status="failed",
        image=image,
        action="none",
        docker_available=True,
        image_available=False,
        message=(
            f"Docker image is missing: {image}. Run agentos prepare --image {image} "
            "or pass a locally available image."
        ),
    )


def ensure_docker_environment(
    *,
    image: str = DEFAULT_AGENTOS_IMAGE,
    docker_bin: str = "docker",
    use_sudo: bool = False,
) -> PrepareResult:
    result = prepare_docker_environment(image=image, docker_bin=docker_bin, use_sudo=use_sudo)
    if not result.passed:
        if result.action == "check_docker_cli":
            raise FileNotFoundError(result.message)
        raise RuntimeError(result.message)
    return result


def render_doctor(result: DoctorResult) -> str:
    lines = [f"status: {result.status}"]
    lines.extend(f"{check.status}: {check.name} - {check.message}" for check in result.checks)
    lines.extend(["", "Next steps:"])
    lines.extend(_doctor_next_steps(result))
    return "\n".join(lines)


def _doctor_next_steps(result: DoctorResult) -> list[str]:
    checks_by_name = {check.name: check for check in result.checks}
    steps: list[str] = []

    docker_cli = checks_by_name.get("docker_cli")
    docker_daemon = checks_by_name.get("docker_daemon")
    docker_image = checks_by_name.get("docker_image")
    workspace_path = checks_by_name.get("workspace_path")

    if docker_cli and docker_cli.status != "passed":
        steps.append("- Install Docker, then run `agentos doctor --workspace \"$PWD\"` again.")
    elif docker_daemon and docker_daemon.status != "passed":
        steps.append("- Start Docker, then run `agentos doctor --workspace \"$PWD\"` again.")
    elif docker_image and docker_image.status != "passed":
        steps.append("- Run `agentos prepare`, then run `agentos doctor --workspace \"$PWD\"` again.")

    if workspace_path and workspace_path.status != "passed":
        steps.append("- Move or fix the workspace path shown above before using sync.")

    if result.status == "passed":
        steps.append("- Run `agentos demo` to see the review-before-sync flow.")
        steps.append("- Then try `agentos run --input <project> --task \"Update the README\" --execute`.")
    elif not steps:
        steps.append("- Fix the warning above, or continue with non-Docker commands if it does not apply.")

    return steps


def is_wsl() -> bool:
    version_path = Path("/proc/version")
    if not version_path.exists():
        return False
    version = version_path.read_text(encoding="utf-8", errors="ignore").lower()
    return "microsoft" in version or "wsl" in version


def _check_platform() -> DoctorCheck:
    system = platform.system()
    if system == "Linux":
        if is_wsl():
            return DoctorCheck("platform", "passed", "Windows via WSL2/Linux-compatible environment detected.")
        return DoctorCheck("platform", "passed", "Linux environment detected.")
    if system == "Windows":
        return DoctorCheck(
            "platform",
            "passed",
            "Native Windows environment detected. WSL2 is still recommended for Docker-heavy workflows.",
        )
    return DoctorCheck("platform", "warning", f"{system} is not an officially tested platform.")


def _check_python() -> DoctorCheck:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 11):
        return DoctorCheck("python", "passed", f"Python {version} at {sys.executable}.")
    return DoctorCheck("python", "failed", f"Python {version} is too old; use Python 3.11+.")


def _check_runtime_identity() -> DoctorCheck:
    identity = runtime_identity(Path(__file__))
    manifest = identity.get("manifest_version") or "unknown"
    server = identity.get("server_version") or "unknown"
    plugin_root = identity.get("plugin_root") or "unknown"
    launcher = identity.get("node_launcher") or identity.get("python_launcher") or "unknown"
    status = "passed" if manifest == server else "warning"
    prefix = ""
    if status == "warning":
        prefix = (
            "Running MCP server does not match the installed plugin manifest. "
            "This usually means the current Codex conversation is still attached to an older MCP process; "
            "restart Codex or open a new conversation after updating AgentOS. "
        )
    return DoctorCheck(
        "runtime_identity",
        status,
        f"{prefix}running server {server}, manifest {manifest}, plugin_root={plugin_root}, launcher={launcher}",
    )


def _check_mcp_storage_paths() -> DoctorCheck:
    state_dir = default_mcp_state_dir()
    output_dir = default_mcp_output_dir()
    return DoctorCheck(
        "mcp_storage",
        "passed",
        f"state_dir={state_dir}; output_dir={output_dir}",
    )


def _check_agentos_cli() -> DoctorCheck:
    executable = shutil.which("agentos")
    if executable is None:
        return DoctorCheck(
            "agentos_cli",
            "passed",
            (
                "agentos executable is not on PATH. Bundled plugin MCP tools can still run; "
                "install the CLI only for terminal fallback commands."
            ),
        )
    return DoctorCheck("agentos_cli", "passed", f"agentos executable found at {executable}.")


def _check_docker_binary(*, docker_bin: str, use_sudo: bool) -> DoctorCheck:
    if use_sudo and shutil.which("sudo") is None:
        return DoctorCheck("docker_cli", "warning", "sudo not found; cannot run Docker through sudo.")
    docker = shutil.which(docker_bin)
    if docker is None:
        return DoctorCheck("docker_cli", "warning", f"Docker CLI not found: {docker_bin}.")
    return DoctorCheck("docker_cli", "passed", f"Docker CLI found at {docker}.")


def _check_docker_daemon(*, docker_bin: str, use_sudo: bool, docker_cli: DoctorCheck) -> DoctorCheck:
    if docker_cli.status != "passed":
        return DoctorCheck("docker_daemon", "warning", "Skipped because Docker CLI is unavailable.")
    completed = _run_docker(
        [*docker_prefix(docker_bin=docker_bin, use_sudo=use_sudo), "info"],
        timeout_seconds=DEFAULT_DOCKER_TIMEOUT_SECONDS,
    )
    if isinstance(completed, Exception):
        return DoctorCheck("docker_daemon", "warning", f"Docker daemon is unavailable: {completed}.")
    if completed.returncode != 0:
        detail = _command_error_tail(completed)
        return DoctorCheck(
            "docker_daemon",
            "warning",
            f"Docker daemon is not responding. Start Docker, then run agentos doctor again. {detail}".strip(),
        )
    return DoctorCheck("docker_daemon", "passed", "Docker daemon is responding.")


def _check_docker_image(*, docker_bin: str, use_sudo: bool, image: str, docker_daemon: DoctorCheck) -> DoctorCheck:
    if docker_daemon.status != "passed":
        return DoctorCheck("docker_image", "warning", "Skipped because Docker daemon is unavailable.")
    if _docker_image_exists(image=image, docker_bin=docker_bin, use_sudo=use_sudo):
        return DoctorCheck("docker_image", "passed", f"Docker image available: {image}.")
    return DoctorCheck(
        "docker_image",
        "warning",
        f"Docker image missing: {image}. Run agentos prepare --image {image} before Docker sandbox steps.",
    )


def _check_workspace_path(workspace_path: Path) -> DoctorCheck:
    resolved = workspace_path.resolve()
    path_text = str(resolved)
    normalized_path_text = path_text.replace("\\", "/")
    if "$PWD" in path_text:
        return DoctorCheck(
            "workspace_path",
            "warning",
            "Workspace path contains literal $PWD; use . in Windows CMD or a shell that expands $PWD.",
        )
    if normalized_path_text.startswith("/mnt/c/") or normalized_path_text.startswith("/mnt/d/"):
        return DoctorCheck(
            "workspace_path",
            "warning",
            "Workspace is under a Windows-mounted drive; WSL ext4 paths are faster and safer.",
        )
    return DoctorCheck("workspace_path", "passed", f"Workspace path looks suitable: {resolved}.")


def docker_prefix(docker_bin: str = "docker", use_sudo: bool = False) -> list[str]:
    return ["sudo", docker_bin] if use_sudo else [docker_bin]


def _docker_image_exists(*, image: str, docker_bin: str, use_sudo: bool) -> bool:
    completed = _run_docker(
        [*docker_prefix(docker_bin=docker_bin, use_sudo=use_sudo), "image", "inspect", image],
        timeout_seconds=DEFAULT_DOCKER_TIMEOUT_SECONDS,
    )
    return not isinstance(completed, Exception) and completed.returncode == 0


def _build_default_agentos_image(
    *,
    image: str,
    docker_bin: str,
    use_sudo: bool,
    timeout_seconds: int,
) -> PrepareResult:
    command = [*docker_prefix(docker_bin=docker_bin, use_sudo=use_sudo), "build", "-t", image, "-"]
    completed = _run_docker(command, input_text=_EMBEDDED_AGENTOS_DOCKERFILE, timeout_seconds=timeout_seconds)
    return _prepare_result_from_completed(
        image=image,
        action="build_default_image",
        command=command,
        completed=completed,
        success_message=f"Built AgentOS Docker image: {image}.",
        failure_message=f"Failed to build AgentOS Docker image: {image}.",
    )


def _pull_docker_image(*, image: str, docker_bin: str, use_sudo: bool, timeout_seconds: int) -> PrepareResult:
    command = [*docker_prefix(docker_bin=docker_bin, use_sudo=use_sudo), "pull", image]
    completed = _run_docker(command, timeout_seconds=timeout_seconds)
    return _prepare_result_from_completed(
        image=image,
        action="pull_image",
        command=command,
        completed=completed,
        success_message=f"Pulled Docker image: {image}.",
        failure_message=f"Failed to pull Docker image: {image}.",
    )


def _prepare_result_from_completed(
    *,
    image: str,
    action: str,
    command: list[str],
    completed: subprocess.CompletedProcess[str] | Exception,
    success_message: str,
    failure_message: str,
) -> PrepareResult:
    if isinstance(completed, Exception):
        return PrepareResult(
            status="failed",
            image=image,
            action=action,
            docker_available=False,
            image_available=False,
            message=f"{failure_message} {completed}",
            command=tuple(command),
        )
    stdout_tail = _tail(completed.stdout)
    stderr_tail = _tail(completed.stderr)
    if completed.returncode == 0:
        return PrepareResult(
            status="passed",
            image=image,
            action=action,
            docker_available=True,
            image_available=True,
            message=success_message,
            command=tuple(command),
            exit_code=completed.returncode,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
        )
    return PrepareResult(
        status="failed",
        image=image,
        action=action,
        docker_available=True,
        image_available=False,
        message=f"{failure_message} {_command_error_tail(completed)}".strip(),
        command=tuple(command),
        exit_code=completed.returncode,
        stdout_tail=stdout_tail,
        stderr_tail=stderr_tail,
    )


def _run_docker(
    command: list[str],
    *,
    input_text: str | None = None,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str] | Exception:
    try:
        return subprocess.run(
            command,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired) as exc:
        return exc


def _command_error_tail(completed: subprocess.CompletedProcess[str]) -> str:
    return _tail(completed.stderr or completed.stdout)


def _tail(value: str | None, limit: int = 1200) -> str:
    if not value:
        return ""
    return value[-limit:]
