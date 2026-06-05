"""materialize(config) → DeploymentArtifacts.

The single function that maps a Config to everything needed for deploy:
CFN stacks in dependency order, settings.json template, ~/.aws/config
body, and keyring write operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Config
from .distribution import distribution_strategy
from .providers import provider_strategy

DEPLOYMENT = Path("deployment/infrastructure")


@dataclass
class StackPlan:
    """One CFN stack to deploy."""

    stack_name: str
    template_path: Path
    parameters: dict[str, str]
    capabilities: list[str] = field(default_factory=lambda: ["CAPABILITY_NAMED_IAM"])
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class KeyringWrite:
    """One OS keyring entry to write."""

    service: str
    account: str
    value: str  # in-memory only — never serialized to disk


@dataclass
class DeploymentArtifacts:
    """Output of materialize() — consumed by deploy/review."""

    stacks: list[StackPlan]
    settings_json_template: dict[str, Any]
    aws_config_template: str
    keyring_writes: list[KeyringWrite]

    def to_review_dict(self) -> dict[str, Any]:
        """Serialize for the Review page. Secret values masked."""
        return {
            "stacks": [
                {"stack_name": s.stack_name, "template": str(s.template_path), "parameters": s.parameters, "tags": s.tags}
                for s in self.stacks
            ],
            "settings_json_template": self.settings_json_template,
            "aws_config_template": self.aws_config_template,
            "keyring_writes": [
                {"service": kw.service, "account": kw.account, "value": "***"}
                for kw in self.keyring_writes
            ],
        }


def materialize(config: Config) -> DeploymentArtifacts:
    """Config → DeploymentArtifacts. Deterministic — no time/random deps."""
    provider = provider_strategy(config.provider)
    dist = distribution_strategy(config.distribution)

    stacks: list[StackPlan] = []

    # 1. S3 bucket for CFN artifacts (needed by cloudformation package for Lambda code)
    stacks.append(StackPlan(
        stack_name=f"{config.stack_base_name}-s3",
        template_path=DEPLOYMENT / "s3bucket.yaml",
        parameters={},
        tags=config.tags,
    ))

    # 2. Auth stack (always)
    stacks.append(StackPlan(
        stack_name=f"{config.stack_base_name}-auth",
        template_path=provider.cfn_template_path(),
        parameters=provider.cfn_parameters(config),
        capabilities=["CAPABILITY_NAMED_IAM"],
        tags=config.tags,
    ))

    # 3. Bedrock logging (always)
    stacks.append(StackPlan(
        stack_name=f"{config.stack_base_name}-bedrock-logging",
        template_path=DEPLOYMENT / "bedrock-logging.yaml",
        parameters={
            "ProfileName": config.profile_name,
            "BedrockLoggingDestination": config.bedrock_logging.get("destination", "cloudwatch"),
            "DataRetentionDays": str(config.bedrock_logging.get("retention_days", 90)),
        },
        tags=config.tags,
    ))

    # 3. Dashboard (always)
    stacks.append(StackPlan(
        stack_name=f"{config.stack_base_name}-dashboard",
        template_path=DEPLOYMENT / "claude-code-dashboard.yaml",
        parameters={"ProfileName": config.profile_name, "Region": config.aws_region},
        tags=config.tags,
    ))

    # 4. Quota (optional)
    if config.quota:
        # Resolve OIDC issuer URL for JWT validation in quota Lambda
        oidc_issuer = provider.oidc_issuer_url(config) if hasattr(provider, "oidc_issuer_url") else ""
        oidc_client_id = config.provider.get("client_id", "")
        stacks.append(StackPlan(
            stack_name=f"{config.stack_base_name}-quota",
            template_path=DEPLOYMENT / "quota-monitoring.yaml",
            parameters={
                "MonthlyTokenLimit": str(config.quota.get("monthly_token_limit", 225000000)),
                "DailyTokenLimit": str(config.quota.get("daily_token_limit", 0)),
                "DailyEnforcementMode": config.quota.get("daily_enforcement", "alert"),
                "MonthlyEnforcementMode": config.quota.get("monthly_enforcement", "block"),
                "EnableFinegrainedQuotas": str(config.quota.get("enable_finegrained_quotas", False)).lower(),
                "OidcIssuerUrl": oidc_issuer,
                "OidcClientId": oidc_client_id,
            },
            tags=config.tags,
        ))

    # 5. Distribution (optional)
    if dist:
        stacks.append(StackPlan(
            stack_name=f"{config.stack_base_name}-distribution",
            template_path=dist.cfn_template_path(),
            parameters=dist.cfn_parameters(config),
            tags=config.tags,
        ))

    # 6. CodeBuild (optional)
    if config.enable_codebuild_windows:
        stacks.append(StackPlan(
            stack_name=f"{config.stack_base_name}-codebuild",
            template_path=DEPLOYMENT / "codebuild-windows.yaml",
            parameters={"StackBaseName": config.stack_base_name},
            tags=config.tags,
        ))

    # settings.json template
    settings_template = {"env": provider.settings_env(config)}

    # ~/.aws/config template
    aws_config = provider.aws_config_section(config)

    # Keyring writes (currently: azure secret mode only)
    keyring_writes: list[KeyringWrite] = []

    return DeploymentArtifacts(
        stacks=stacks,
        settings_json_template=settings_template,
        aws_config_template=aws_config,
        keyring_writes=keyring_writes,
    )
