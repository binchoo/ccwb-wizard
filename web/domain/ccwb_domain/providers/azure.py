"""Azure AD / Entra ID identity provider strategy (3 auth modes)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from . import register
from .base import FormField, IdentityProvider
from .okta import DEPLOYMENT, _allowed_regions, _common_aws_config, _common_settings_env


@register
@dataclass
class AzureProvider(IdentityProvider):
    provider_type: ClassVar[str] = "azure"

    tenant_id: str = ""
    client_id: str = ""
    auth_mode: str = "public"  # public | secret | certificate
    # For certificate mode — paths stored in config
    cert_path: str | None = None
    key_path: str | None = None
    # For secret mode — keyring ref stored in config (never raw secret)
    _keyring_ref: str | None = None

    def cfn_template_path(self) -> Path:
        return DEPLOYMENT / "bedrock-auth-azure.yaml"

    def cfn_parameters(self, config: Any) -> dict[str, str]:
        return {
            "AzureTenantId": self.tenant_id,
            "AzureClientId": self.client_id,
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
            FormField(name="tenant_id", label="Azure Tenant ID", required=True, validator="uuid"),
            FormField(name="client_id", label="Azure Client ID", required=True, validator="min_length:10"),
            FormField(
                name="auth_mode", label="Authentication Mode", type="select", required=True,
                options=[
                    {"value": "public", "label": "Public client (no secret needed)"},
                    {"value": "secret", "label": "Confidential — client secret (stored in OS keyring)"},
                    {"value": "certificate", "label": "Confidential — certificate + private key"},
                ],
                default="public",
            ),
            FormField(name="cert_path", label="Certificate PEM path", help_text="Only for certificate mode"),
            FormField(name="key_path", label="Private Key PEM path", help_text="Only for certificate mode"),
        ]

    @classmethod
    def from_dict(cls, data: dict) -> "AzureProvider":
        return cls(
            tenant_id=data.get("tenant_id", ""),
            client_id=data.get("client_id", ""),
            auth_mode=data.get("auth_mode", "public"),
            cert_path=data.get("cert_path"),
            key_path=data.get("key_path"),
            _keyring_ref=data.get("_keyring_ref"),
        )
