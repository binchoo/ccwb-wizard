"""CloudFormation custom resource: Bedrock model invocation logging configuration.

CloudFormation has no native AWS::Bedrock::ModelInvocationLoggingConfiguration resource
(as of 2026-05). This Lambda fills the gap by calling
``bedrock:PutModelInvocationLoggingConfiguration`` on Create/Update and
``bedrock:DeleteModelInvocationLoggingConfiguration`` on Delete.

A model invocation logging configuration is **account+region scoped** (one config per
region). If multiple ccwb deployments share an account+region they will fight for control
of this single config — by design we let the most-recent stack win, and emit a warning
log on each Update describing what changed.

The CFN template (bedrock-logging.yaml) wraps this Lambda in a Custom resource.
ResourceProperties consumed:

- ``Destination``       — "cloudwatch" | "s3" | "both"
- ``RoleArn``           — IAM role Bedrock service assumes to write logs
- ``LogGroupName``      — present when Destination ∈ {"cloudwatch", "both"}
- ``S3BucketName``      — present when Destination ∈ {"s3", "both"}
- ``EmbedTextToggles``  — dict of {ImageDataDeliveryEnabled, TextDataDeliveryEnabled,
                          EmbeddingDataDeliveryEnabled, VideoDataDeliveryEnabled}
"""
from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)



def _build_logging_config(props: dict) -> dict:
    """Translate ResourceProperties to the Bedrock API ``loggingConfig`` shape."""
    destination = props.get("Destination", "cloudwatch")
    role_arn = props.get("RoleArn")
    if not role_arn:
        raise ValueError("RoleArn is required")

    toggles = props.get("EmbedTextToggles", {}) or {}
    cfg: dict[str, Any] = {
        # These four flags control whether the request/response body is captured
        # alongside metadata. Defaults err on the side of *capturing text* (so usage
        # patterns are visible in dashboards) but *not capturing image/video bytes*
        # (which would inflate log volume and storage cost without much benefit).
        "imageDataDeliveryEnabled": _to_bool(toggles.get("ImageDataDeliveryEnabled", False)),
        "textDataDeliveryEnabled": _to_bool(toggles.get("TextDataDeliveryEnabled", True)),
        "embeddingDataDeliveryEnabled": _to_bool(toggles.get("EmbeddingDataDeliveryEnabled", False)),
        "videoDataDeliveryEnabled": _to_bool(toggles.get("VideoDataDeliveryEnabled", False)),
    }

    if destination in ("cloudwatch", "both"):
        log_group = props.get("LogGroupName")
        if not log_group:
            raise ValueError("LogGroupName required when Destination includes cloudwatch")
        cfg["cloudWatchConfig"] = {
            "logGroupName": log_group,
            "roleArn": role_arn,
        }

    if destination in ("s3", "both"):
        bucket = props.get("S3BucketName")
        if not bucket:
            raise ValueError("S3BucketName required when Destination includes s3")
        cfg["s3Config"] = {
            "bucketName": bucket,
            "keyPrefix": "AWSLogs/BedrockModelInvocationLogs/",
        }

    return cfg


def _to_bool(v) -> bool:
    """CFN passes booleans as strings ('true'/'false') sometimes — normalize."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "on")
    return bool(v)



def _send_response(event: dict, status: str, reason: str = "", physical_id: str | None = None,
                   data: dict | None = None) -> None:
    """Reply to CloudFormation custom-resource lifecycle event.

    boto3's CloudFormation client doesn't have a "send response" operation — this is a
    direct PUT to the pre-signed URL CloudFormation includes in the event payload.
    """
    response_body = json.dumps({
        "Status": status,
        "Reason": reason or f"See CloudWatch Logs: {event.get('RequestId', '')}",
        "PhysicalResourceId": physical_id or event.get("PhysicalResourceId") or event["LogicalResourceId"],
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": data or {},
        "NoEcho": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        url=event["ResponseURL"],
        data=response_body,
        headers={"Content-Type": "", "Content-Length": str(len(response_body))},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            logger.info("CloudFormation response status %s", resp.status)
    except Exception as e:
        # Last-resort logging.  If we can't talk to CFN the stack will time out, but at
        # least the failure cause is in CloudWatch Logs.
        logger.error("Failed to send CFN response: %s", e)


def handler(event: dict, context) -> None:
    """CFN custom-resource entry point."""
    logger.info("Event: %s", json.dumps({k: v for k, v in event.items() if k != "ResponseURL"}))

    request_type = event.get("RequestType")
    props = event.get("ResourceProperties", {}) or {}
    physical_id = f"bedrock-logging-config-{event.get('StackId', 'unknown').split('/')[-1]}"

    bedrock = boto3.client("bedrock")

    try:
        if request_type in ("Create", "Update"):
            cfg = _build_logging_config(props)
            logger.info("Putting Bedrock logging config: %s", json.dumps(cfg))
            bedrock.put_model_invocation_logging_configuration(loggingConfig=cfg)
            _send_response(event, "SUCCESS", physical_id=physical_id, data={"Configured": "true"})

        elif request_type == "Delete":
            try:
                bedrock.delete_model_invocation_logging_configuration()
                logger.info("Deleted Bedrock logging configuration")
            except bedrock.exceptions.ClientError as e:
                # Already absent — not a failure.  Without this the delete-then-recreate
                # cycle (e.g. CFN rollback) would leave the stack stuck.
                if "ResourceNotFoundException" in str(e):
                    logger.info("Logging config already absent; treating Delete as no-op")
                else:
                    raise
            _send_response(event, "SUCCESS", physical_id=physical_id)

        else:
            _send_response(event, "FAILED", reason=f"Unknown RequestType: {request_type}",
                           physical_id=physical_id)

    except Exception as e:
        logger.exception("Custom resource failed")
        _send_response(event, "FAILED", reason=str(e)[:1000], physical_id=physical_id)
