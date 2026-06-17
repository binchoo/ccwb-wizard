# ABOUTME: Real-time quota check before credential issuance — blocks when any scope is over
# ABOUTME: Enforces user + team + dept aggregate limits using the JWT-derived attribution scopes

import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3

# Vendored from credential-process so user/team/dept are derived identically to the
# magic header (same mapping + b64 sanitize), keeping scope ids aligned with the
# CloudWatch metric dimensions and DynamoDB rollups written by quota_monitor.
from bedrock_metadata import build_metadata_from_jwt

dynamodb = boto3.resource("dynamodb")

QUOTA_TABLE = os.environ.get("QUOTA_TABLE", "UserQuotaMetrics")
POLICIES_TABLE = os.environ.get("POLICIES_TABLE", "QuotaPolicies")
MISSING_EMAIL_ENFORCEMENT = os.environ.get("MISSING_EMAIL_ENFORCEMENT", "block")
ERROR_HANDLING_MODE = os.environ.get("ERROR_HANDLING_MODE", "fail_closed")

ENABLE_FINEGRAINED_QUOTAS = os.environ.get("ENABLE_FINEGRAINED_QUOTAS", "false").lower() == "true"
MONTHLY_TOKEN_LIMIT = int(os.environ.get("MONTHLY_TOKEN_LIMIT", "0"))
DAILY_TOKEN_LIMIT = int(os.environ.get("DAILY_TOKEN_LIMIT", "0"))
MONTHLY_ENFORCEMENT_MODE = os.environ.get("MONTHLY_ENFORCEMENT_MODE", "block")
WARNING_THRESHOLD_80 = int(os.environ.get("WARNING_THRESHOLD_80", "240000000"))
WARNING_THRESHOLD_90 = int(os.environ.get("WARNING_THRESHOLD_90", "270000000"))

# Attribution mapping (user/team/dept ← IdP claim) passed from the wizard config so the
# check derives the same scope identifiers that landed in the logs/metrics.
try:
    _ATTRIBUTION = json.loads(os.environ.get("ATTRIBUTION_JSON", "") or "{}")
except Exception:
    _ATTRIBUTION = {}

# scope → DynamoDB pk prefix
SCOPE_PREFIX = {"user": "USER", "team": "TEAM", "dept": "DEPT"}

quota_table = dynamodb.Table(QUOTA_TABLE)
policies_table = dynamodb.Table(POLICIES_TABLE)


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def build_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }


def derive_scopes(jwt_claims: dict) -> dict:
    """Derive {user, team, dept} ids from JWT claims via the attribution mapping.

    Uses the same build_metadata_from_jwt as the credential helper, so values match
    the magic-header / metric-dimension / rollup keys exactly (including b64: for
    non-ASCII). Falls back to the raw ``email`` claim for user when no mapping is set.
    """
    scopes = {}
    metadata = build_metadata_from_jwt(jwt_claims, attribution=_ATTRIBUTION or None)
    for scope_type in ("user", "team", "dept"):
        val = metadata.get(scope_type)
        if val:
            scopes[scope_type] = val
    if "user" not in scopes:
        email = jwt_claims.get("email")
        if email:
            scopes["user"] = email
    return scopes


def get_policy(policy_type: str, identifier: str) -> dict | None:
    pk = f"POLICY#{policy_type}#{identifier}"
    try:
        item = policies_table.get_item(Key={"pk": pk, "sk": "CURRENT"}).get("Item")
        if not item:
            return None
        return {
            "policy_type": item.get("policy_type"),
            "identifier": item.get("identifier"),
            "monthly_token_limit": int(item.get("monthly_token_limit", 0)),
            "daily_token_limit": int(item.get("daily_token_limit", 0)) if item.get("daily_token_limit") else None,
            "enforcement_mode": item.get("enforcement_mode", "alert"),
            "enabled": item.get("enabled", True),
        }
    except Exception as e:
        print(f"Error getting policy {policy_type}:{identifier}: {e}")
        return None


def resolve_scope_policy(scope_type: str, identifier: str) -> dict | None:
    """Effective policy for a scope. user falls back to env default / default policy."""
    if not ENABLE_FINEGRAINED_QUOTAS:
        if scope_type == "user" and MONTHLY_TOKEN_LIMIT > 0:
            return {
                "policy_type": "default", "identifier": "environment",
                "monthly_token_limit": MONTHLY_TOKEN_LIMIT,
                "daily_token_limit": DAILY_TOKEN_LIMIT if DAILY_TOKEN_LIMIT > 0 else None,
                "enforcement_mode": MONTHLY_ENFORCEMENT_MODE, "enabled": True,
            }
        return None
    policy = get_policy(scope_type, identifier)
    if policy and policy.get("enabled", True):
        return policy
    if scope_type == "user":
        default = get_policy("default", "default")
        if default and default.get("enabled", True):
            return default
    return None


def get_scope_usage(scope_type: str, identifier: str) -> dict:
    """Current-month usage for a scope identifier (daily reset on date change)."""
    now = datetime.now(timezone.utc)
    month_prefix = now.strftime("%Y-%m")
    current_date = now.strftime("%Y-%m-%d")
    pk = f"{SCOPE_PREFIX[scope_type]}#{identifier}"
    try:
        item = quota_table.get_item(Key={"pk": pk, "sk": f"MONTH#{month_prefix}"}).get("Item")
        if not item:
            return {"total_tokens": 0, "daily_tokens": 0}
        daily_tokens = float(item.get("daily_tokens", 0))
        if item.get("daily_date") != current_date:
            daily_tokens = 0
        return {"total_tokens": float(item.get("total_tokens", 0)), "daily_tokens": daily_tokens}
    except Exception as e:
        print(f"Error getting usage for {pk}: {e}")
        return {"total_tokens": 0, "daily_tokens": 0}


def get_unblock_status(user_id: str) -> dict:
    """Active admin unblock override (keyed on the user scope)."""
    try:
        item = quota_table.get_item(Key={"pk": f"USER#{user_id}", "sk": "UNBLOCK#CURRENT"}).get("Item")
        if not item:
            return {"is_unblocked": False}
        expires_at = item.get("expires_at")
        if expires_at:
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > expires_dt:
                return {"is_unblocked": False, "expired": True}
        return {
            "is_unblocked": True, "expires_at": expires_at,
            "unblocked_by": item.get("unblocked_by"), "reason": item.get("reason"),
        }
    except Exception as e:
        print(f"Error checking unblock for {user_id}: {e}")
        return {"is_unblocked": False, "error": str(e)}


def evaluate_scope(scope_type: str, identifier: str) -> dict:
    """Evaluate one scope. Returns a verdict dict with allowed/blocked + detail."""
    policy = resolve_scope_policy(scope_type, identifier)
    if policy is None:
        return {"scope": scope_type, "identifier": identifier, "blocked": False, "reason": "no_policy"}

    usage = get_scope_usage(scope_type, identifier)
    monthly = usage.get("total_tokens", 0)
    daily = usage.get("daily_tokens", 0)
    monthly_limit = policy.get("monthly_token_limit", 0)
    daily_limit = policy.get("daily_token_limit")
    enforcement = policy.get("enforcement_mode", "alert")

    detail = {
        "scope": scope_type, "identifier": identifier,
        "enforcement_mode": enforcement,
        "policy": {"type": policy.get("policy_type"), "identifier": policy.get("identifier")},
        "usage": {
            "monthly_tokens": int(monthly), "monthly_limit": monthly_limit,
            "monthly_percent": round(monthly / monthly_limit * 100, 1) if monthly_limit > 0 else 0,
            "daily_tokens": int(daily),
            **({"daily_limit": daily_limit, "daily_percent": round(daily / daily_limit * 100, 1) if daily_limit else 0} if daily_limit else {}),
        },
        "blocked": False,
        "reason": "within_quota",
    }

    if enforcement != "block":
        detail["reason"] = "alert_only"
        return detail
    if monthly_limit > 0 and monthly >= monthly_limit:
        detail["blocked"] = True
        detail["reason"] = "monthly_exceeded"
    elif daily_limit and daily_limit > 0 and daily >= daily_limit:
        detail["blocked"] = True
        detail["reason"] = "daily_exceeded"
    return detail


def lambda_handler(event, context):
    """JWT-authenticated quota check. Blocks if ANY scope (user/team/dept) is over."""
    try:
        authorizer = event.get("requestContext", {}).get("authorizer", {})
        jwt_claims = authorizer.get("jwt", {}).get("claims", {})

        scopes = derive_scopes(jwt_claims)
        if "user" not in scopes:
            allow = MISSING_EMAIL_ENFORCEMENT != "block"
            return build_response(200, {
                "allowed": allow, "reason": "missing_identity",
                "message": "JWT has no user identity" + ("" if allow else " - access denied"),
            })

        user_id = scopes["user"]

        # Admin override (user scope) short-circuits everything.
        unblock = get_unblock_status(user_id)
        if unblock.get("is_unblocked"):
            return build_response(200, {
                "allowed": True, "reason": "unblocked",
                "unblock_status": unblock, "scopes": scopes,
                "message": f"Temporarily unblocked until {unblock.get('expires_at')}",
            })

        details = [evaluate_scope(st, ident) for st, ident in scopes.items()]
        blocking = [d for d in details if d["blocked"]]

        if blocking:
            first = blocking[0]
            u = first["usage"]
            return build_response(200, {
                "allowed": False, "reason": first["reason"],
                "blocked_scope": first["scope"], "scopes": scopes,
                "details": details,
                "message": (
                    f"{first['scope'].capitalize()} quota exceeded for '{first['identifier']}': "
                    f"{u['monthly_tokens']:,} / {u['monthly_limit']:,} tokens. "
                    "Contact your administrator."
                ),
            })

        if not any(d["reason"] != "no_policy" for d in details):
            return build_response(200, {
                "allowed": True, "reason": "no_policy", "scopes": scopes,
                "details": details, "message": "No quota policy configured - unlimited access",
            })

        return build_response(200, {
            "allowed": True, "reason": "within_quota", "scopes": scopes,
            "details": details, "message": "Access granted - within quota limits",
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        allow = ERROR_HANDLING_MODE != "fail_closed"
        return build_response(200, {
            "allowed": allow, "reason": "check_failed",
            "message": f"Quota check failed ({ERROR_HANDLING_MODE}): {e}",
        })
