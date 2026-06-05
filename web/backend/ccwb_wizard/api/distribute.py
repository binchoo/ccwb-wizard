"""Distribute API — upload package to S3 + generate presigned URL.

POST /api/profile/{name}/distribute
  → Uploads zip to distribution S3 bucket.
  → Returns presigned URL (default 48h expiry).
"""

from __future__ import annotations

from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import APIRouter, HTTPException

from ccwb_domain.config import Config
from ..settings import PROFILES_DIR

router = APIRouter(tags=["distribute"])

DIST_BASE = Path(__file__).resolve().parents[4] / "dist"


def _get_distribution_bucket(region: str, stack_base_name: str) -> str:
    """Get distribution bucket name from CFN stack output."""
    cfn = boto3.client("cloudformation", region_name=region)
    stack_name = f"{stack_base_name}-distribution"
    try:
        resp = cfn.describe_stacks(StackName=stack_name)
        outputs = {o["OutputKey"]: o["OutputValue"]
                   for o in resp["Stacks"][0].get("Outputs", [])}
        bucket = outputs.get("DistributionBucket", "")
        if not bucket:
            raise ValueError(f"No DistributionBucket output in {stack_name}")
        return bucket
    except ClientError as e:
        raise ValueError(f"Distribution stack not found: {e}")


def _detect_platform() -> str:
    """Detect current platform for zip naming."""
    import platform
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        return f"macos-{'arm64' if machine == 'arm64' else 'intel'}"
    elif system == "linux":
        return "linux"
    elif system == "windows":
        return "windows"
    return f"{system}-{machine}"


@router.post("/profile/{name}/distribute")
async def distribute_package(name: str, expiry_hours: int = 48) -> dict:
    """Upload package zip to S3 and return presigned download URL."""
    # Load profile
    path = PROFILES_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")

    config = Config.load(path)
    platform_name = _detect_platform()
    zip_path = DIST_BASE / f"{name}-{platform_name}.zip"

    if not zip_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Package not built yet. Run Package first. Expected: {zip_path}"
        )

    # Get distribution bucket
    try:
        bucket = _get_distribution_bucket(config.aws_region, config.stack_base_name)
    except (ValueError, NoCredentialsError) as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Upload to S3
    s3_key = f"packages/{name}/{zip_path.name}"
    try:
        s3 = boto3.client("s3", region_name=config.aws_region)
        s3.upload_file(str(zip_path), bucket, s3_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {e}")

    # Generate presigned URL
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": s3_key},
            ExpiresIn=expiry_hours * 3600,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Presigned URL generation failed: {e}")

    return {
        "status": "distributed",
        "profile_name": name,
        "platform": platform_name,
        "bucket": bucket,
        "s3_key": s3_key,
        "presigned_url": url,
        "expiry_hours": expiry_hours,
        "zip_size_mb": round(zip_path.stat().st_size / 1024 / 1024, 2),
    }
