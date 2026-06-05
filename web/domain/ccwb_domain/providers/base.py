"""IdentityProvider ABC and FormField metadata."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar


@dataclass
class FormField:
    """Metadata for one wizard input field. Frontend renders these dynamically."""

    name: str
    label: str
    type: str = "text"  # text | password | number | select | checkbox | textarea
    required: bool = False
    placeholder: str = ""
    default: Any = None
    options: list[dict[str, str]] | None = None  # for type="select"
    validator: str | None = None
    help_text: str = ""
    sensitive: bool = False  # password / keyring target


class IdentityProvider(ABC):
    """Abstract base for an OIDC identity provider strategy."""

    provider_type: ClassVar[str]  # registry key, e.g. "okta"

    @abstractmethod
    def cfn_template_path(self) -> Path:
        """Return path to the CFN template for this provider."""

    @abstractmethod
    def cfn_parameters(self, config: Any) -> dict[str, str]:
        """Return CFN ParameterKey → ParameterValue dict."""

    @abstractmethod
    def settings_env(self, config: Any) -> dict[str, str]:
        """Return settings.json env block key-value pairs."""

    @abstractmethod
    def aws_config_section(self, config: Any) -> str:
        """Return the ~/.aws/config [profile ClaudeCode] section body."""

    @classmethod
    @abstractmethod
    def wizard_inputs(cls) -> list[FormField]:
        """Return FormField metadata for the wizard dynamic form."""

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> "IdentityProvider":
        """Construct an instance from a provider dict (Config.provider)."""

    def oidc_issuer_url(self, config: Any) -> str:
        """Return the OIDC issuer URL for this provider. Used by quota Lambda for JWT validation."""
        return ""
