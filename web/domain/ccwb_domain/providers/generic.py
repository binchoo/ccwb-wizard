"""Generic OIDC identity provider strategy (Keycloak, PingFederate, etc.)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from . import register
from .base import FormField, IdentityProvider
from .okta import DEPLOYMENT, _allowed_regions, _common_aws_config, _common_settings_env


@register
@dataclass
class GenericProvider(IdentityProvider):
    provider_type: ClassVar[str] = "generic"

    issuer_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    thumbprint: str = ""
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    jwks_uri: str = ""

    def cfn_template_path(self) -> Path:
        return DEPLOYMENT / "bedrock-auth-generic.yaml"

    def cfn_parameters(self, config: Any) -> dict[str, str]:
        return {
            "OidcIssuerUrl": self.issuer_url.rstrip("/"),
            "OidcClientId": self.client_id,
            "OidcThumbprintList": self.thumbprint,
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
            FormField(name="issuer_url", label="Issuer URL", placeholder="https://auth.example.com", required=True, validator="url"),
            FormField(name="client_id", label="Client ID", required=True, validator="min_length:10"),
            FormField(name="client_secret", label="Client Secret", type="password", sensitive=True, help_text="Confidential client(예: Google Web application)는 필수. Keycloak public client 등 secret 미사용 시 비워두세요."),
            FormField(name="thumbprint", label="TLS Thumbprint (auto-calculated)", help_text="SHA-1 thumbprint of JWKS host TLS cert"),
            FormField(name="authorization_endpoint", label="Authorization Endpoint", help_text="Auto-discovered from well-known"),
            FormField(name="token_endpoint", label="Token Endpoint", help_text="Auto-discovered from well-known"),
            FormField(name="jwks_uri", label="JWKS URI", help_text="Auto-discovered from well-known"),
        ]

    @classmethod
    def from_dict(cls, data: dict) -> "GenericProvider":
        return cls(
            issuer_url=data.get("issuer_url", ""),
            client_id=data.get("client_id", ""),
            client_secret=data.get("client_secret", ""),
            thumbprint=data.get("thumbprint", ""),
            authorization_endpoint=data.get("authorization_endpoint", ""),
            token_endpoint=data.get("token_endpoint", ""),
            jwks_uri=data.get("jwks_uri", ""),
        )

    def oidc_issuer_url(self, config: Any) -> str:
        return self.issuer_url.rstrip("/")
