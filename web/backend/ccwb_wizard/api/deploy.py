"""Deploy API — create/update CFN stacks from materialized profile.

POST /api/profile/{name}/deploy
  → Deploys all stacks in dependency order.
  → Returns SSE stream with progress events.

GET /api/profile/{name}/deploy/status
  → Returns current stack statuses.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ccwb_domain.config import Config
from ccwb_domain.materialize import materialize
from ..settings import PROFILES_DIR

router = APIRouter(tags=["deploy"])

# CFN template root (relative to ccwb/)
CFN_ROOT = Path(__file__).resolve().parents[4] / "deployment" / "infrastructure"


def _get_cfn_client(region: str):
    """Get CloudFormation client for the given region."""
    return boto3.client("cloudformation", region_name=region)


def _read_template(template_path: Path) -> str:
    """Read CFN template body. Resolves relative paths against CFN_ROOT.
    
    Also injects Lambda code where placeholder stubs exist (ZipFile pattern).
    For templates with relative Code paths (e.g. ./lambda-functions/...),
    use _package_template() instead.
    """
    # template_path from materialize is relative to deployment/infrastructure
    full_path = CFN_ROOT / template_path.name if not template_path.is_absolute() else template_path
    if not full_path.exists():
        # Try the path as-is from materialize
        full_path = Path(__file__).resolve().parents[4] / str(template_path)
    if not full_path.exists():
        raise FileNotFoundError(f"CFN template not found: {template_path} (tried {full_path})")
    
    content = full_path.read_text(encoding="utf-8")
    
    # Inject Lambda code for ZipFile placeholders
    content = _inject_lambda_code(content)
    
    return content


def _package_template(template_path: Path, s3_bucket: str, region: str) -> str:
    """Run `aws cloudformation package` for templates with relative Code paths.
    
    Uploads Lambda code to S3 and returns the packaged template body with S3 URIs.
    """
    import subprocess
    import tempfile
    
    full_path = CFN_ROOT / template_path.name if not template_path.is_absolute() else template_path
    if not full_path.exists():
        raise FileNotFoundError(f"CFN template not found: {template_path}")
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
        tmp_output = tmp.name
    
    cmd = [
        "aws", "cloudformation", "package",
        "--template-file", str(full_path),
        "--s3-bucket", s3_bucket,
        "--s3-prefix", "ccwb-lambda-code",
        "--output-template-file", tmp_output,
        "--region", region,
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(CFN_ROOT))
    if result.returncode != 0:
        raise RuntimeError(f"cloudformation package failed:\n{result.stderr[-1000:]}")
    
    packaged = Path(tmp_output).read_text(encoding="utf-8")
    Path(tmp_output).unlink(missing_ok=True)
    return packaged


def _needs_packaging(template_path: Path) -> bool:
    """Check if a template has relative Code paths that need `cloudformation package`."""
    full_path = CFN_ROOT / template_path.name if not template_path.is_absolute() else template_path
    if not full_path.exists():
        return False
    content = full_path.read_text(encoding="utf-8")
    # Relative Code paths like "Code: ./lambda-functions/..."
    return bool(re.search(r'^\s+Code:\s+\./', content, re.M))


# Lambda functions directory
LAMBDA_DIR = CFN_ROOT / "lambda-functions"

# Map: placeholder comment substring → lambda source file path (relative to LAMBDA_DIR)
_LAMBDA_PLACEHOLDER_MAP = {
    "bedrock_logging_config/index.py": LAMBDA_DIR / "bedrock_logging_config" / "index.py",
}


def _inject_lambda_code(template_content: str) -> str:
    """Replace ZipFile placeholder stubs with actual Lambda code.
    
    Detects the placeholder pattern by looking for the lambda source path
    in a comment, then replaces the entire ZipFile content block.
    """
    for marker_path, source_file in _LAMBDA_PLACEHOLDER_MAP.items():
        if marker_path not in template_content:
            continue
        if not source_file.exists():
            continue
        
        # Find the line containing the marker and work backwards to find "ZipFile: |"
        lines = template_content.splitlines()
        marker_line_idx = None
        for i, line in enumerate(lines):
            if marker_path in line and "placeholder" in line:
                marker_line_idx = i
                break
        
        if marker_line_idx is None:
            continue
        
        # Find "ZipFile: |" line above the marker
        zipfile_line_idx = None
        for i in range(marker_line_idx - 1, -1, -1):
            if "ZipFile:" in lines[i]:
                zipfile_line_idx = i
                break
        
        if zipfile_line_idx is None:
            continue
        
        # Find the end of the placeholder block (next line with same or less indentation as ZipFile)
        zipfile_indent = len(lines[zipfile_line_idx]) - len(lines[zipfile_line_idx].lstrip())
        end_idx = marker_line_idx + 1
        while end_idx < len(lines):
            line = lines[end_idx]
            if line.strip() == "":
                end_idx += 1
                continue
            line_indent = len(line) - len(line.lstrip())
            if line_indent <= zipfile_indent:
                break
            end_idx += 1
        
        # Build replacement: ZipFile line + indented lambda code
        content_indent = " " * (zipfile_indent + 4)  # ZipFile content is indented +4
        lambda_code = source_file.read_text(encoding="utf-8")
        indented_lines = []
        for code_line in lambda_code.splitlines():
            if code_line.strip():
                indented_lines.append(f"{content_indent}{code_line}")
            else:
                indented_lines.append("")
        
        new_lines = lines[:zipfile_line_idx]
        new_lines.append(lines[zipfile_line_idx])  # Keep "ZipFile: |"
        new_lines.extend(indented_lines)
        new_lines.extend(lines[end_idx:])
        
        template_content = "\n".join(new_lines)
    
    return template_content


def _stack_exists(cfn, stack_name: str) -> bool:
    """Check if a stack exists (any state except DELETE_COMPLETE)."""
    try:
        resp = cfn.describe_stacks(StackName=stack_name)
        status = resp["Stacks"][0]["StackStatus"]
        return status != "DELETE_COMPLETE"
    except ClientError as e:
        if "does not exist" in str(e):
            return False
        raise


def _deploy_stack(cfn, stack_name: str, template_body: str,
                  parameters: dict[str, str], capabilities: list[str],
                  tags: dict[str, str]) -> str:
    """Create or update a single CFN stack. Returns the operation type."""
    cfn_params = [{"ParameterKey": k, "ParameterValue": v} for k, v in parameters.items()]
    cfn_tags = [{"Key": k, "Value": v} for k, v in tags.items()]

    if _stack_exists(cfn, stack_name):
        try:
            cfn.update_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=cfn_params,
                Capabilities=capabilities,
                Tags=cfn_tags,
            )
            return "UPDATE"
        except ClientError as e:
            if "No updates are to be performed" in str(e):
                return "NO_CHANGE"
            raise
    else:
        cfn.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=cfn_params,
            Capabilities=capabilities,
            Tags=cfn_tags,
            OnFailure="ROLLBACK",
        )
        return "CREATE"


def _wait_for_stack(cfn, stack_name: str, timeout: int = 600) -> dict:
    """Poll stack until terminal state. Returns final status dict."""
    start = time.time()
    while time.time() - start < timeout:
        resp = cfn.describe_stacks(StackName=stack_name)
        stack = resp["Stacks"][0]
        status = stack["StackStatus"]
        if status.endswith("_COMPLETE") or status.endswith("_FAILED"):
            return {"stack_name": stack_name, "status": status,
                    "reason": stack.get("StackStatusReason", "")}
        time.sleep(5)
    return {"stack_name": stack_name, "status": "TIMEOUT",
            "reason": f"Exceeded {timeout}s"}


@router.post("/profile/{name}/deploy")
async def deploy_profile(name: str):
    """Deploy all CFN stacks for a profile. Returns SSE stream."""
    path = PROFILES_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")

    config = Config.load(path)
    artifacts = materialize(config)

    async def event_stream():
        try:
            cfn = _get_cfn_client(config.aws_region)
        except NoCredentialsError:
            yield _sse({"type": "error", "message": "AWS credentials not configured"})
            return

        # Pre-check: if Bedrock logging is already configured, reuse its log group
        # instead of skipping the whole stack. The logging stack still deploys —
        # it creates the metric filters (for the dashboard) on the EXISTING log
        # group, and skips re-configuring the logging destination.
        existing_log_group = ""
        if config.bedrock_logging.get("skip_if_exists"):
            try:
                bedrock = boto3.client("bedrock", region_name=config.aws_region)
                resp = bedrock.get_model_invocation_logging_configuration()
                cw = (resp.get("loggingConfig") or {}).get("cloudWatchConfig") or {}
                existing_log_group = cw.get("logGroupName", "")
            except Exception:
                pass  # If check fails, proceed with normal deploy (creates new log group)

        # Track S3 artifacts bucket name (from first stack output)
        s3_bucket = ""

        # Track the effective Bedrock log group name. Seeded from the existing-config
        # check above; refined from the bedrock-logging stack output after it deploys.
        # Injected into the dashboard stack so its Logs Insights widgets query the
        # log group that actually receives invocation logs.
        effective_log_group = existing_log_group

        # Pre-fetch S3 bucket from existing stack (if already deployed)
        try:
            s3_stack_name = f"{config.stack_base_name}-s3"
            resp = cfn.describe_stacks(StackName=s3_stack_name)
            outputs = {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0].get("Outputs", [])}
            s3_bucket = outputs.get("CfnArtifactsBucket", "")
        except Exception:
            pass

        total = len(artifacts.stacks)
        for i, stack_plan in enumerate(artifacts.stacks, 1):
            # For bedrock-logging: if an existing log group was found, inject it as
            # ExistingLogGroupName so the stack reuses it (metric filters attach to
            # the log group that actually receives logs).
            if "bedrock-logging" in stack_plan.stack_name and existing_log_group:
                stack_plan.parameters["ExistingLogGroupName"] = existing_log_group
                yield _sse({"type": "progress", "stack": stack_plan.stack_name,
                            "step": i, "total": total,
                            "status": f"REUSING log group {existing_log_group}"})

            # For the dashboard: point its Logs Insights widgets at the effective
            # log group captured from the bedrock-logging stack (or existing config).
            if "dashboard" in stack_plan.stack_name and effective_log_group:
                stack_plan.parameters["LogGroupName"] = effective_log_group
                yield _sse({"type": "progress", "stack": stack_plan.stack_name,
                            "step": i, "total": total,
                            "status": f"QUERYING log group {effective_log_group}"})

            yield _sse({"type": "progress", "stack": stack_plan.stack_name,
                        "step": i, "total": total, "status": "DEPLOYING"})
            try:
                # Determine if template needs `cloudformation package` (relative Code paths)
                if _needs_packaging(stack_plan.template_path):
                    if not s3_bucket:
                        raise RuntimeError(
                            f"{stack_plan.stack_name} requires S3 bucket for Lambda packaging, "
                            "but S3 artifacts stack has not been deployed yet."
                        )
                    template_body = _package_template(stack_plan.template_path, s3_bucket, config.aws_region)
                else:
                    template_body = _read_template(stack_plan.template_path)
                
                op = _deploy_stack(cfn, stack_plan.stack_name, template_body,
                                   stack_plan.parameters, stack_plan.capabilities,
                                   stack_plan.tags)
                if op == "NO_CHANGE":
                    yield _sse({"type": "progress", "stack": stack_plan.stack_name,
                                "step": i, "total": total, "status": "NO_CHANGE"})
                    continue

                result = _wait_for_stack(cfn, stack_plan.stack_name)
                yield _sse({"type": "progress", "stack": stack_plan.stack_name,
                            "step": i, "total": total, **result})

                if "FAILED" in result["status"] or result["status"] == "TIMEOUT":
                    yield _sse({"type": "error",
                                "message": f"{stack_plan.stack_name}: {result['status']} — {result['reason']}"})
                    return

                # Sync CFN outputs to profile (e.g. FederatedRoleArn from auth stack)
                synced = _sync_outputs_to_profile(cfn, stack_plan.stack_name, path)
                if synced:
                    yield _sse({"type": "sync", "stack": stack_plan.stack_name, "synced": synced})

                # Capture S3 artifacts bucket for subsequent `cloudformation package` calls
                if "-s3" in stack_plan.stack_name and not s3_bucket:
                    try:
                        resp = cfn.describe_stacks(StackName=stack_plan.stack_name)
                        outputs = {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0].get("Outputs", [])}
                        s3_bucket = outputs.get("CfnArtifactsBucket", "")
                    except Exception:
                        pass

                # Capture the effective Bedrock log group from the logging stack output
                # so the dashboard (deployed later) queries the right log group.
                if "bedrock-logging" in stack_plan.stack_name:
                    try:
                        resp = cfn.describe_stacks(StackName=stack_plan.stack_name)
                        outputs = {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0].get("Outputs", [])}
                        lg = outputs.get("LogGroupName", "")
                        if lg:
                            effective_log_group = lg
                    except Exception:
                        pass

            except Exception as e:
                yield _sse({"type": "error", "message": f"{stack_plan.stack_name}: {e}"})
                return

        yield _sse({"type": "complete", "message": f"All {total} stacks deployed successfully"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(data: dict) -> str:
    """Format a Server-Sent Event."""
    return f"data: {json.dumps(data)}\n\n"


# Output keys to sync back to profile after deploy
_OUTPUT_TO_PROFILE_MAP = {
    "FederatedRoleArn": ("provider", "federated_role_arn"),
    "DirectSTSRoleArn": ("provider", "federated_role_arn"),  # fallback alias
}


def _sync_outputs_to_profile(cfn, stack_name: str, profile_path: Path) -> list[str]:
    """Read CFN stack outputs and write relevant values back to the profile.

    Returns list of synced field names (for SSE reporting).
    """
    try:
        resp = cfn.describe_stacks(StackName=stack_name)
        outputs = {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0].get("Outputs", [])}
    except Exception:
        return []

    if not outputs:
        return []

    # Load current profile
    profile_data = json.loads(profile_path.read_text(encoding="utf-8"))
    synced = []

    for output_key, (section, field) in _OUTPUT_TO_PROFILE_MAP.items():
        if output_key not in outputs:
            continue
        value = outputs[output_key]
        if not value:
            continue

        # Write into the correct nested location
        if section == "provider":
            if "provider" not in profile_data:
                profile_data["provider"] = {}
            if profile_data["provider"].get(field) != value:
                profile_data["provider"][field] = value
                synced.append(f"provider.{field}")
        else:
            if profile_data.get(field) != value:
                profile_data[field] = value
                synced.append(field)

    # Quota check API endpoint → profile.quota.api_endpoint (consumed by credential-process).
    # Only applied when the profile has quota enabled (quota dict present); the credential
    # provider activates quota enforcement only when quota_api_endpoint is set in config.
    quota_endpoint = outputs.get("QuotaCheckApiEndpoint")
    if quota_endpoint and isinstance(profile_data.get("quota"), dict):
        if profile_data["quota"].get("api_endpoint") != quota_endpoint:
            profile_data["quota"]["api_endpoint"] = quota_endpoint
            synced.append("quota.api_endpoint")

    if synced:
        profile_path.write_text(
            json.dumps(profile_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    return synced

@router.get("/profile/{name}/deploy/status")
async def deploy_status(name: str) -> list[dict]:
    """Get current status of all stacks for a profile."""
    path = PROFILES_DIR / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")

    config = Config.load(path)
    artifacts = materialize(config)

    try:
        cfn = _get_cfn_client(config.aws_region)
    except NoCredentialsError:
        raise HTTPException(status_code=503, detail="AWS credentials not configured")

    results = []
    for stack_plan in artifacts.stacks:
        try:
            resp = cfn.describe_stacks(StackName=stack_plan.stack_name)
            stack = resp["Stacks"][0]
            results.append({
                "stack_name": stack_plan.stack_name,
                "status": stack["StackStatus"],
                "outputs": {o["OutputKey"]: o["OutputValue"]
                            for o in stack.get("Outputs", [])},
            })
        except ClientError:
            results.append({
                "stack_name": stack_plan.stack_name,
                "status": "NOT_DEPLOYED",
                "outputs": {},
            })
    return results
