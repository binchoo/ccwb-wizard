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
    """Derive AllowedBedrockRegions from config's model selections."""
    from ..bedrock_models import get_destination_regions_for_model_profile

    all_regions: set[str] = set()
    models = getattr(config, "models", {})
    profile = getattr(config, "cross_region_profile", "")

    for tier, model_id in models.items():
        if not model_id:
            continue
        model_key = _resolve_model_key(model_id)
        if model_key and profile:
            try:
                regions = get_destination_regions_for_model_profile(model_key, profile)
                all_regions.update(regions)
            except (ValueError, KeyError):
                pass

    if not all_regions:
        return [config.source_region] if config.source_region else ["us-east-1"]
    return sorted(all_regions)


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
    env: dict[str, str] = {
        "AWS_PROFILE": config.profile_name,
        "AWS_REGION": config.source_region,
        "CLAUDE_CODE_USE_BEDROCK": "1",
        "ANTHROPIC_CUSTOM_HEADERS": "__ANTHROPIC_CUSTOM_HEADERS__",
        "CLAUDE_CODE_USE_MANTLE": "0",
    }
    # Tier-based model mapping
    models = getattr(config, "models", {})
    if models.get("sonnet"):
        env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = models["sonnet"]
        env["ANTHROPIC_MODEL"] = models["sonnet"]  # backward compat — default model = sonnet
    if models.get("haiku"):
        env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = models["haiku"]
    if models.get("opus"):
        env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = models["opus"]

    # Telemetry
    env["CLAUDE_CODE_ENABLE_TELEMETRY"] = "1" if config.enable_cc_telemetry else "0"

    # Application Inference Profile ARNs (optional — skip if null/empty)
    inference_profiles = getattr(config, "inference_profiles", {})
    if inference_profiles.get("opus"):
        env["ANTHROPIC_OPUS_MODEL_ARN"] = inference_profiles["opus"]
    if inference_profiles.get("sonnet"):
        env["ANTHROPIC_SONNET_MODEL_ARN"] = inference_profiles["sonnet"]
    if inference_profiles.get("haiku"):
        env["ANTHROPIC_HAIKU_MODEL_ARN"] = inference_profiles["haiku"]

    return env


def _common_aws_config(config: Any) -> str:
    """Common ~/.aws/config section."""
    return (
        f"[profile ClaudeCode]\n"
        f"region = {config.source_region}\n"
        f'credential_process = "credential-process" --profile {config.profile_name}\n'
    )
