"""Cognito User Pool identity provider strategy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from . import register
from .base import FormField, IdentityProvider
from .okta import DEPLOYMENT, _allowed_regions, _common_aws_config, _common_settings_env


@register
@dataclass
class CognitoProvider(IdentityProvider):
    provider_type: ClassVar[str] = "cognito"

    user_pool_id: str = ""
    client_id: str = ""
    user_pool_domain: str = ""

    def cfn_template_path(self) -> Path:
        return DEPLOYMENT / "bedrock-auth-cognito-pool.yaml"

    def cfn_parameters(self, config: Any) -> dict[str, str]:
        return {
            "CognitoUserPoolId": self.user_pool_id,
            "CognitoClientId": self.client_id,
            "UserPoolDomain": self.user_pool_domain,
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
            FormField(name="user_pool_id", label="User Pool ID", placeholder="us-east-1_ABC123", required=True, validator="cognito_pool_id"),
            FormField(name="client_id", label="Client ID", required=True, validator="min_length:10"),
            FormField(name="user_pool_domain", label="User Pool Domain", placeholder="myteam-claude", required=True),
        ]

    @classmethod
    def from_dict(cls, data: dict) -> "CognitoProvider":
        return cls(
            user_pool_id=data.get("user_pool_id", ""),
            client_id=data.get("client_id", ""),
            user_pool_domain=data.get("user_pool_domain", ""),
        )
