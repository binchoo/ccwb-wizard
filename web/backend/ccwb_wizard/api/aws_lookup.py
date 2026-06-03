"""AWS Lookup API — region, VPC, subnet, hosted zone, Cognito stack discovery.

All endpoints handle NoCredentialsError gracefully (HTTP 503).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["aws_lookup"])


def _get_boto3_client(service: str, region: str | None = None):
    """Get a boto3 client. Raises HTTPException 503 on credential failure."""
    try:
        import boto3
        kwargs = {}
        if region:
            kwargs["region_name"] = region
        return boto3.client(service, **kwargs)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AWS credentials not available: {e}. Check AWS_PROFILE or ~/.aws/credentials.",
        )


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
