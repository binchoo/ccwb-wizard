"""Google identity provider strategy (confidential desktop client: PKCE + client secret).

Distinct from the generic OIDC strategy (public client + PKCE only). Google's
"Desktop app" OAuth client issues a client_secret that must be sent on the token
exchange *in addition to* PKCE. That secret is NOT collected in the wizard and is
NOT shipped in the package — it is injected per-machine into the OS keyring via
`credential-process --set-client-secret` (or the CCWB_CLIENT_SECRET env var).

Google's authorize and token endpoints live on different hosts, so the endpoints
are emitted as absolute URLs (the credential-process generic/absolute path), not
derived from a single provider_domain.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from . import register
from .base import FormField, IdentityProvider
from .okta import DEPLOYMENT, _allowed_regions, _common_aws_config, _common_settings_env

# Fixed Google OIDC endpoints (issuer is constant; no discovery needed).
GOOGLE_ISSUER = "https://accounts.google.com"
GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


@register
@dataclass
class GoogleProvider(IdentityProvider):
    provider_type: ClassVar[str] = "google"

    client_id: str = ""
    # Google desktop clients are confidential at the token endpoint: the secret is
    # required but is treated by Google as non-confidential (PKCE is the real defense).
    # Stored in the OS keyring per-machine, never in config/profile JSON.
    auth_mode: str = "secret"

    def cfn_template_path(self) -> Path:
        return DEPLOYMENT / "bedrock-auth-google.yaml"

    def cfn_parameters(self, config: Any) -> dict[str, str]:
        return {
            "GoogleClientId": self.client_id,
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
            FormField(
                name="client_id",
                label="Google Client ID",
                placeholder="xxxx.apps.googleusercontent.com",
                required=True,
                validator="min_length:10",
                help_text="'Desktop app' 타입 OAuth 클라이언트 ID",
            ),
            FormField(
                name="client_secret",
                label="Google Client Secret",
                placeholder="GOCSPX-...",
                required=True,
                sensitive=True,
                help_text="위저드가 이 머신의 OS keychain에 저장합니다. config.json에는 포함되지 않습니다.",
            ),
        ]

    @classmethod
    def from_dict(cls, data: dict) -> "GoogleProvider":
        return cls(
            client_id=data.get("client_id", ""),
            auth_mode=data.get("auth_mode", "secret"),
        )

    def oidc_issuer_url(self, config: Any) -> str:
        return GOOGLE_ISSUER
