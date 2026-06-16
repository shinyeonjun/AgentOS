from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CAPABILITY_SCHEMA_VERSION = "0.2"


@dataclass(frozen=True)
class Capability:
    name: str
    kind: str
    description: str
    provides: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "provides": list(self.provides),
        }


CAPABILITY_CATALOG: dict[str, Capability] = {
    "base": Capability(
        name="base",
        kind="runtime",
        description="AgentOS workspace, artifact, policy, review, approval, and sync contract.",
        provides=(
            "/agentos/work",
            "/agentos/artifacts",
            "task.json",
            "review_package.json",
            "approval-gated sync",
        ),
    ),
    "code": Capability(
        name="code",
        kind="workflow",
        description="Code change workflows with diff artifacts and validation command records.",
        provides=(
            "changed file detection",
            "text diff artifacts",
            "test command validation",
            "selected-file approval scopes",
        ),
    ),
    "document": Capability(
        name="document",
        kind="workflow",
        description="Markdown/document editing workflows with structured review and selected sync.",
        provides=(
            "document diff artifacts",
            "document structure validation",
            "selected-file approval scopes",
        ),
    ),
}


def capability_manifest(capability_names: list[str] | tuple[str, ...]) -> dict[str, Any]:
    unknown = [name for name in capability_names if name not in CAPABILITY_CATALOG]
    if unknown:
        raise ValueError(f"unknown AgentOS capability: {', '.join(unknown)}")
    return {
        "schema_version": CAPABILITY_SCHEMA_VERSION,
        "capabilities": [CAPABILITY_CATALOG[name].to_dict() for name in capability_names],
    }


def image_capability_manifest(
    *,
    image: str,
    capability_names: list[str] | tuple[str, ...] = ("base",),
) -> dict[str, Any]:
    manifest = capability_manifest(capability_names)
    return {
        "schema_version": CAPABILITY_SCHEMA_VERSION,
        "image": image,
        "capabilities": manifest["capabilities"],
        "notes": [
            "Image capabilities describe the sandbox environment contract.",
            "Worker binaries such as Codex remain host-side adapters unless a separate worker image is declared.",
        ],
    }
