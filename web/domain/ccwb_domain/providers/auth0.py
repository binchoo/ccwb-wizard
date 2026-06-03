"""Auth0 identity provider strategy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from . import register
from .base import FormField, IdentityProvider
from .okta import DEPLOYMENT, _allowed_regions, _common_aws_config, _common_settings_env


@register
@dataclass
class Auth0Provider(IdentityProvider):
    provider_type: ClassVar[str] = "auth0"

    domain: str = ""
    client_id: str = ""

    def cfn_template_path(self) -> Path:
        return DEPLOYMENT / "bedrock-auth-auth0.yaml"

    def cfn_parameters(self, config: Any) -> dict[str, str]:
        return {
            "Auth0Domain": self.domain,
            "Auth0ClientId": self.client_id,
            "IdentityPoolName": config.stack_base_name,
            "AllowedBedrockRegions": ",".join(_allowed_regions(config)),
            "EnableMonitoring": "true",
            "FederationType": "direct",
        }

    def settings_env(self, config: Any) -> dict[str, str]:
        return _common_settings_env(config)

    def aws_config_section(self, config: Any) -> str:
        return _common_aws_config(config)

    @classmethod
    def wizard_inputs(cls) -> list[FormField]:
        return [
            FormField(name="domain", label="Auth0 Domain", placeholder="company.auth0.com", required=True),
            FormField(name="client_id", label="Client ID", required=True, validator="min_length:10"),
        ]

    @classmethod
    def from_dict(cls, data: dict) -> "Auth0Provider":
        return cls(domain=data.get("domain", ""), client_id=data.get("client_id", ""))
