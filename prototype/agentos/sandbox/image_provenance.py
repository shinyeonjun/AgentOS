from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ImageProvenance:
    requested_image: str
    status: str
    image_id: str | None
    repo_digests: tuple[str, ...]
    pinned_reference: str | None
    error: str | None = None

    @property
    def resolved(self) -> bool:
        return self.status == "resolved"

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_image": self.requested_image,
            "status": self.status,
            "image_id": self.image_id,
            "repo_digests": list(self.repo_digests),
            "pinned_reference": self.pinned_reference,
            "error": self.error,
        }


def inspect_image_provenance(
    *,
    image: str,
    docker_prefix: list[str],
    timeout_seconds: int = 20,
) -> ImageProvenance:
    command = [*docker_prefix, "image", "inspect", image]
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired) as exc:
        return _unavailable(image, str(exc))

    if completed.returncode != 0:
        return _unavailable(image, (completed.stderr or completed.stdout).strip())

    try:
        image_data = json.loads(completed.stdout)[0]
    except (IndexError, json.JSONDecodeError, TypeError) as exc:
        return _unavailable(image, f"could not parse docker image inspect output: {exc}")

    image_id = image_data.get("Id")
    repo_digests = tuple(item for item in image_data.get("RepoDigests", []) if isinstance(item, str))
    pinned_reference = repo_digests[0] if repo_digests else image_id
    if not pinned_reference:
        return _unavailable(image, "docker image inspect returned no image id or repo digest")

    return ImageProvenance(
        requested_image=image,
        status="resolved",
        image_id=image_id,
        repo_digests=repo_digests,
        pinned_reference=pinned_reference,
    )


def _unavailable(image: str, error: str) -> ImageProvenance:
    return ImageProvenance(
        requested_image=image,
        status="unavailable",
        image_id=None,
        repo_digests=(),
        pinned_reference=None,
        error=error,
    )
