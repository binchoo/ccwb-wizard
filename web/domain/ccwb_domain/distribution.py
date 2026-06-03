"""Distribution strategies — PresignedS3 / LandingPage."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEPLOYMENT = Path("deployment/infrastructure")


@dataclass
class PresignedS3:
    """Simplest distribution — presigned S3 URLs for installer zip."""

    type: str = "presigned-s3"

    def cfn_template_path(self) -> Path:
        return DEPLOYMENT / "presigned-s3-distribution.yaml"

    def cfn_parameters(self, config: Any) -> dict[str, str]:
        return {"StackBaseName": config.stack_base_name}


@dataclass
class LandingPage:
    """Self-service landing page — ALB + Lambda + OIDC web auth."""

    type: str = "landing-page"
    vpc_id: str = ""
    public_subnets: list[str] = field(default_factory=list)
    private_subnets: list[str] = field(default_factory=list)
    idp_provider: str = ""  # okta | azure | auth0 | cognito
    idp_config: dict[str, str] = field(default_factory=dict)
    custom_domain: str = ""
    hosted_zone_id: str | None = None

    def cfn_template_path(self) -> Path:
        return DEPLOYMENT / "landing-page-distribution.yaml"

    def cfn_parameters(self, config: Any) -> dict[str, str]:
        params: dict[str, str] = {
            "VpcId": self.vpc_id,
            "PublicSubnetIds": ",".join(self.public_subnets),
            "PrivateSubnetIds": ",".join(self.private_subnets),
            "IdPProvider": self.idp_provider,
            "CustomDomainName": self.custom_domain,
        }
        if self.hosted_zone_id:
            params["HostedZoneId"] = self.hosted_zone_id
        # IdP-specific params
        for k, v in self.idp_config.items():
            params[k] = v
        return params


Distribution = PresignedS3 | LandingPage | None


def distribution_strategy(data: dict | None) -> PresignedS3 | LandingPage | None:
    """Dispatch a distribution dict to the correct strategy."""
    if data is None:
        return None
    dtype = data.get("type", "")
    if dtype == "presigned-s3":
        return PresignedS3()
    if dtype == "landing-page":
        return LandingPage(
            vpc_id=data.get("vpc_id", ""),
            public_subnets=data.get("public_subnets", []),
            private_subnets=data.get("private_subnets", []),
            idp_provider=data.get("idp_provider", ""),
            idp_config=data.get("idp_config", {}),
            custom_domain=data.get("custom_domain", ""),
            hosted_zone_id=data.get("hosted_zone_id"),
        )
    raise ValueError(f"Unknown distribution type: '{dtype}'. Expected 'presigned-s3' or 'landing-page'.")
