"""Okta identity provider strategy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from . import register
from .base import FormField, IdentityProvider

DEPLOYMENT = Path("deployment/infrastructure")


@register
@dataclass
class OktaProvider(IdentityProvider):
    provider_type: ClassVar[str] = "okta"

    domain: str = ""
    client_id: str = ""

    def cfn_template_path(self) -> Path:
        return DEPLOYMENT / "bedrock-auth-okta.yaml"

    def cfn_parameters(self, config: Any) -> dict[str, str]:
        return {
            "OktaDomain": self.domain,
            "OktaClientId": self.client_id,
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
            FormField(name="domain", label="Okta Domain", placeholder="company.okta.com", required=True, validator="okta_domain"),
            FormField(name="client_id", label="Client ID", required=True, validator="min_length:10"),
        ]

    @classmethod
    def from_dict(cls, data: dict) -> "OktaProvider":
        return cls(domain=data.get("domain", ""), client_id=data.get("client_id", ""))


def _allowed_regions(config: Any) -> list[str]:
    """Derive AllowedBedrockRegions from config's model profile."""
    from ..bedrock_models import get_destination_regions_for_model_profile

    try:
        model_key = _resolve_model_key(config.model_id)
        return get_destination_regions_for_model_profile(model_key, config.cross_region_profile)
    except (ValueError, KeyError):
        return [config.source_region] if config.source_region else ["us-east-1"]


def _resolve_model_key(model_id: str) -> str:
    """Best-effort reverse lookup from model_id to model_key."""
    from ..bedrock_models import CLAUDE_MODELS

    for key, model in CLAUDE_MODELS.items():
        for profile in model.profiles.values():
            if profile.model_id == model_id:
                return key
    return ""


def _common_settings_env(config: Any) -> dict[str, str]:
    """Common settings.json env block (rule-of-thumb §7)."""
    env = {
        "AWS_PROFILE": "ClaudeCode",
        "AWS_REGION": config.source_region,
        "ANTHROPIC_MODEL": config.model_id,
        "ANTHROPIC_CUSTOM_HEADERS": "__ANTHROPIC_CUSTOM_HEADERS__",
        "CLAUDE_CODE_USE_MANTLE": "0",
    }
    if config.enable_cc_telemetry:
        env["CLAUDE_CODE_ENABLE_TELEMETRY"] = "1"
    else:
        env["CLAUDE_CODE_ENABLE_TELEMETRY"] = "0"
    return env


def _common_aws_config(config: Any) -> str:
    """Common ~/.aws/config section."""
    return (
        f"[profile ClaudeCode]\n"
        f"region = {config.source_region}\n"
        f'credential_process = "credential-process" --profile {config.profile_name}\n'
    )
