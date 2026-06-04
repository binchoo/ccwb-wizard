"""AWS Lookup API — region, VPC, subnet, hosted zone, Cognito stack discovery.

All endpoints handle NoCredentialsError gracefully (HTTP 503).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["aws_lookup"])

# In-memory store for selected AWS profile (per wizard session)
_selected_aws_profile: str | None = None


def _get_boto3_client(service: str, region: str | None = None):
    """Get a boto3 client. Raises HTTPException 503 on credential failure."""
    try:
        import boto3
        kwargs = {}
        if region:
            kwargs["region_name"] = region
        if _selected_aws_profile:
            session = boto3.Session(profile_name=_selected_aws_profile)
            return session.client(service, **kwargs)
        return boto3.client(service, **kwargs)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AWS credentials not available: {e}. Check AWS_PROFILE or ~/.aws/credentials.",
        )


@router.get("/aws/profiles")
async def list_aws_profiles() -> list[dict]:
    """List named profiles from ~/.aws/config + ~/.aws/credentials."""
    import configparser
    from pathlib import Path

    profiles = []
    for config_file in [Path.home() / ".aws" / "config", Path.home() / ".aws" / "credentials"]:
        if not config_file.exists():
            continue
        parser = configparser.ConfigParser()
        parser.read(str(config_file))
        for section in parser.sections():
            # ~/.aws/config uses [profile xxx], credentials uses [xxx]
            name = section.replace("profile ", "") if section.startswith("profile ") else section
            if name not in [p["name"] for p in profiles]:
                profiles.append({"name": name, "source": config_file.name})

    return profiles


@router.post("/aws/profiles/select")
async def select_aws_profile(body: dict) -> dict:
    """Select an AWS profile for subsequent API calls. Validates with STS."""
    global _selected_aws_profile
    profile_name = body.get("profile_name", "")

    try:
        import boto3
        session = boto3.Session(profile_name=profile_name if profile_name else None)
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        _selected_aws_profile = profile_name or None
        return {
            "status": "ok",
            "profile": profile_name or "(default)",
            "account": identity.get("Account", ""),
            "arn": identity.get("Arn", ""),
        }
    except Exception as e:
        error_msg = str(e)
        if "expired" in error_msg.lower() or "token" in error_msg.lower():
            return {
                "status": "expired",
                "profile": profile_name,
                "detail": f"Profile '{profile_name}' credentials expired. Run: aws sso login --profile {profile_name}",
            }
        raise HTTPException(status_code=503, detail=f"Cannot use profile '{profile_name}': {error_msg}")


@router.get("/aws/regions")
async def list_regions() -> list[str]:
    """List AWS regions where Bedrock is available."""
    # Hardcoded known Bedrock regions (faster than EC2 describe-regions + filtering)
    return [
        "us-east-1", "us-east-2", "us-west-1", "us-west-2",
        "ca-central-1", "ca-west-1",
        "eu-central-1", "eu-central-2", "eu-north-1",
        "eu-south-1", "eu-south-2", "eu-west-1", "eu-west-2", "eu-west-3",
        "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
        "ap-south-1", "ap-south-2",
        "ap-southeast-1", "ap-southeast-2", "ap-southeast-3", "ap-southeast-4",
        "ap-east-2",
        "me-south-1", "me-central-1",
        "af-south-1", "il-central-1",
        "sa-east-1",
    ]


@router.get("/aws/vpcs")
async def list_vpcs(region: str) -> list[dict]:
    """List VPCs in a region."""
    ec2 = _get_boto3_client("ec2", region)
    try:
        resp = ec2.describe_vpcs()
        return [
            {"vpc_id": v["VpcId"], "cidr": v.get("CidrBlock", ""), "is_default": v.get("IsDefault", False),
             "name": next((t["Value"] for t in v.get("Tags", []) if t["Key"] == "Name"), "")}
            for v in resp.get("Vpcs", [])
        ]
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/aws/subnets")
async def list_subnets(vpc_id: str, region: str) -> list[dict]:
    """List subnets in a VPC."""
    ec2 = _get_boto3_client("ec2", region)
    try:
        resp = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
        return [
            {"subnet_id": s["SubnetId"], "az": s["AvailabilityZone"], "cidr": s.get("CidrBlock", ""),
             "name": next((t["Value"] for t in s.get("Tags", []) if t["Key"] == "Name"), ""),
             "map_public_ip": s.get("MapPublicIpOnLaunch", False)}
            for s in resp.get("Subnets", [])
        ]
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/aws/hosted-zones")
async def list_hosted_zones() -> list[dict]:
    """List Route53 hosted zones."""
    r53 = _get_boto3_client("route53")
    try:
        resp = r53.list_hosted_zones()
        return [
            {"id": z["Id"].split("/")[-1], "name": z["Name"], "private": z["Config"].get("PrivateZone", False)}
            for z in resp.get("HostedZones", [])
        ]
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/aws/bedrock-logging-status")
async def get_bedrock_logging_status(region: str) -> dict:
    """Check if Bedrock model invocation logging is already configured in this account/region."""
    bedrock = _get_boto3_client("bedrock", region)
    try:
        resp = bedrock.get_model_invocation_logging_configuration()
        config = resp.get("loggingConfig", {})
        if not config:
            return {"exists": False}

        # Determine current destination
        has_cw = bool(config.get("cloudWatchConfig", {}).get("logGroupName"))
        has_s3 = bool(config.get("s3Config", {}).get("bucketName"))

        if has_cw and has_s3:
            destination = "both"
        elif has_cw:
            destination = "cloudwatch"
        elif has_s3:
            destination = "s3"
        else:
            return {"exists": False}

        return {
            "exists": True,
            "destination": destination,
            "cloudwatch_log_group": config.get("cloudWatchConfig", {}).get("logGroupName", ""),
            "s3_bucket": config.get("s3Config", {}).get("bucketName", ""),
        }
    except Exception as e:
        # If we can't check (permission denied, etc.), don't block — just report unknown
        return {"exists": "unknown", "detail": str(e)}


@router.get("/aws/cognito-pools")
async def list_cognito_pools(region: str) -> list[dict]:
    """List Cognito User Pools in the selected region. Returns pool ID, name, and app clients."""
    cidp = _get_boto3_client("cognito-idp", region)
    try:
        pools = []
        paginator = cidp.get_paginator("list_user_pools")
        for page in paginator.paginate(MaxResults=60):
            for pool in page.get("UserPools", []):
                pool_id = pool["Id"]
                pool_name = pool.get("Name", "")
                # Get app clients for this pool
                clients = []
                try:
                    client_resp = cidp.list_user_pool_clients(UserPoolId=pool_id, MaxResults=20)
                    clients = [
                        {"client_id": c["ClientId"], "client_name": c.get("ClientName", "")}
                        for c in client_resp.get("UserPoolClients", [])
                    ]
                except Exception:
                    pass
                # Get domain
                domain = ""
                try:
                    pool_desc = cidp.describe_user_pool(UserPoolId=pool_id)
                    domain = pool_desc.get("UserPool", {}).get("Domain", "")
                except Exception:
                    pass
                pools.append({
                    "user_pool_id": pool_id,
                    "name": pool_name,
                    "domain": domain,
                    "clients": clients,
                })
        return pools
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Cannot list Cognito User Pools: {e}")


@router.get("/aws/cognito-stack")
async def detect_cognito_stack(region: str) -> dict | None:
    """Auto-detect cognito-user-pool-setup stack outputs."""
    cfn = _get_boto3_client("cloudformation", region)
    try:
        resp = cfn.describe_stacks()
        for stack in resp.get("Stacks", []):
            outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}
            if "UserPoolId" in outputs and "UserPoolDomain" in outputs:
                return {
                    "user_pool_id": outputs["UserPoolId"],
                    "user_pool_domain": outputs.get("UserPoolDomain", ""),
                    "client_id": outputs.get("DistributionWebClientId", ""),
                    "client_secret_arn": outputs.get("DistributionWebClientSecretArn", ""),
                }
    except Exception:
        pass
    return None
