"""Config dataclass — the single source of truth for a ccwb deployment profile.

A Config is a JSON file at ``~/.ccwb/profiles/<name>.json`` (schema 3.0).
UI, CLI, and AI agents all read/write the same file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "3.0"


@dataclass
class Config:
    """Top-level configuration for one ccwb deployment."""

    profile_name: str
    schema_version: str = SCHEMA_VERSION

    # Page 3 — AWS Infrastructure
    aws_region: str = ""
    stack_base_name: str = ""

    # Page 2 — Identity Provider (polymorphic dict, dispatched by "type" key)
    provider: dict[str, Any] = field(default_factory=dict)

    # Page 4 — Bedrock
    model_id: str = ""
    cross_region_profile: str = ""
    source_region: str = ""
    inference_profiles: dict[str, str | None] = field(
        default_factory=lambda: {"opus": None, "sonnet": None, "haiku": None}
    )

    # Page 5 — Bedrock Logging + Quota
    bedrock_logging: dict[str, Any] = field(
        default_factory=lambda: {"destination": "cloudwatch", "retention_days": 90}
    )
    quota: dict[str, Any] | None = None

    # Page 6 — Distribution
    distribution: dict[str, Any] | None = None

    # Page 7 — Additional Features
    enable_codebuild_windows: bool = False
    enable_cowork_3p: bool = True
    enable_cc_telemetry: bool = False

    # Page 8 — Tags
    tags: dict[str, str] = field(default_factory=dict)

    # --- IO ---

    @classmethod
    def load(cls, path: Path) -> "Config":
        """Load a Config from a JSON file. Raises on unknown schema_version."""
        data = json.loads(path.read_text(encoding="utf-8"))
        version = data.get("schema_version", "unknown")
        if version != SCHEMA_VERSION:
            raise UnsupportedSchemaError(
                f"schema_version '{version}' is not supported. "
                f"Only '{SCHEMA_VERSION}' is recognized. "
                f"Please recreate this profile using the ccwb wizard."
            )
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self, path: Path) -> None:
        """Save Config to a JSON file. Creates parent dirs if needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: getattr(self, k) for k in self.__dataclass_fields__}
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (for API responses, etc.)."""
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


class UnsupportedSchemaError(Exception):
    """Raised when a Config file has an unrecognized schema_version."""
