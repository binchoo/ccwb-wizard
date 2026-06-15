# ABOUTME: Lambda that aggregates Bedrock token usage by user/team/dept and sends SNS alerts
# ABOUTME: Reads single-dimension CloudWatch metrics (ClaudeCodeBedrock), rolls up into DynamoDB

import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr, Key

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
QUOTA_TABLE = os.environ.get("QUOTA_TABLE", "UserQuotaMetrics")
POLICIES_TABLE = os.environ.get("POLICIES_TABLE")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")
ENABLE_FINEGRAINED_QUOTAS = os.environ.get("ENABLE_FINEGRAINED_QUOTAS", "false").lower() == "true"
METRICS_REGION = os.environ.get("METRICS_REGION", os.environ.get("AWS_REGION", "us-east-1"))
METRIC_NAMESPACE = os.environ.get("METRIC_NAMESPACE", "ClaudeCodeBedrock")

# Default (environment) limits — applied to the USER scope when fine-grained is off.
MONTHLY_TOKEN_LIMIT = int(os.environ.get("MONTHLY_TOKEN_LIMIT", "300000000"))
WARNING_THRESHOLD_80 = int(os.environ.get("WARNING_THRESHOLD_80", "240000000"))
WARNING_THRESHOLD_90 = int(os.environ.get("WARNING_THRESHOLD_90", "270000000"))

AGGREGATION_WINDOW = 900  # 15 min, matches the EventBridge schedule

# Scope → (DynamoDB pk prefix, CloudWatch dimension name, metric suffix)
SCOPES = {
    "user": ("USER", "User", "ByUser"),
    "team": ("TEAM", "Team", "ByTeam"),
    "dept": ("DEPT", "Dept", "ByDept"),
}

dynamodb = boto3.resource("dynamodb")
sns_client = boto3.client("sns")
cloudwatch_client = boto3.client("cloudwatch", region_name=METRICS_REGION)

quota_table = dynamodb.Table(QUOTA_TABLE)
policies_table = dynamodb.Table(POLICIES_TABLE) if POLICIES_TABLE else None


def _chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


# ---------------------------------------------------------------------------
# Discovery + fetch (per axis)
# ---------------------------------------------------------------------------
def _discover_dim_values(metric_name: str, dim_name: str) -> set[str]:
    """Enumerate dimension values already observed for a metric via ListMetrics.

    Self-bootstrapping: an identity shows up as soon as it produces its first
    attributed Bedrock invocation, so GetMetricData (which needs explicit
    dimension values) works on a fresh deployment with no manual seeding.
    """
    seen: set[str] = set()
    try:
        paginator = cloudwatch_client.get_paginator("list_metrics")
        for page in paginator.paginate(Namespace=METRIC_NAMESPACE, MetricName=metric_name):
            for metric in page.get("Metrics", []):
                for dim in metric.get("Dimensions", []):
                    if dim.get("Name") == dim_name and dim.get("Value"):
                        seen.add(dim["Value"])
    except Exception as e:
        print(f"[WARN] ListMetrics failed for {metric_name}/{dim_name}: {e}")
    return seen


def _known_ids_from_table(pk_prefix: str) -> set[str]:
    """Scope identifiers that have history in DynamoDB but no traffic this window."""
    ids: set[str] = set()
    try:
        kwargs = {
            "FilterExpression": Attr("pk").begins_with(f"{pk_prefix}#") & Attr("sk").begins_with("MONTH#"),
            "ProjectionExpression": "scope_id, email",
        }
        while True:
            resp = quota_table.scan(**kwargs)
            for item in resp.get("Items", []):
                ident = item.get("scope_id") or item.get("email")
                if ident:
                    ids.add(ident)
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    except Exception as e:
        print(f"[WARN] scan for {pk_prefix} ids failed: {e}")
    return ids


def _fetch_axis_usage(dim_name: str, suffix: str, identifiers: list[str]) -> dict[str, dict]:
    """GetMetricData for Input/Output{suffix} over the aggregation window.

    Each metric is single-dimension, so querying {dim_name: value} returns the
    value summed across every other (absent) dimension — true per-axis totals.
    """
    if not identifiers:
        return {}
    end = datetime.now(timezone.utc)
    start = end - timedelta(seconds=AGGREGATION_WINDOW)
    out: dict[str, dict] = {}

    # 2 queries per identifier (in + out); GetMetricData caps at 500 queries.
    for batch in _chunked(identifiers, 250):
        queries = []
        for i, ident in enumerate(batch):
            for direction, metric in (("in", f"InputTokens{suffix}"), ("out", f"OutputTokens{suffix}")):
                queries.append({
                    "Id": f"{direction}_{i}",
                    "Label": ident,
                    "MetricStat": {
                        "Metric": {
                            "Namespace": METRIC_NAMESPACE,
                            "MetricName": metric,
                            "Dimensions": [{"Name": dim_name, "Value": ident}],
                        },
                        "Period": AGGREGATION_WINDOW,
                        "Stat": "Sum",
                    },
                    "ReturnData": True,
                })
        try:
            resp = cloudwatch_client.get_metric_data(
                MetricDataQueries=queries, StartTime=start, EndTime=end
            )
        except Exception as e:
            print(f"[ERROR] GetMetricData failed ({dim_name}, batch={len(batch)}): {e}")
            continue
        for r in resp.get("MetricDataResults", []):
            ident = r.get("Label", "")
            total = sum(float(v) for v in r.get("Values", []))
            if total <= 0 or not ident:
                continue
            entry = out.setdefault(ident, {"input_tokens": 0.0, "output_tokens": 0.0})
            if r["Id"].startswith("in_"):
                entry["input_tokens"] += total
            else:
                entry["output_tokens"] += total
            entry["total_tokens"] = entry["input_tokens"] + entry["output_tokens"]
    return out


# ---------------------------------------------------------------------------
# Rollup writes (per scope)
# ---------------------------------------------------------------------------
def update_scope_metrics(scope_type: str, pk_prefix: str, usage_data: dict[str, dict]):
    """Atomically increment the DynamoDB rollup for one scope with the delta."""
    now = datetime.now(timezone.utc)
    current_month = now.strftime("%Y-%m")
    current_date = now.strftime("%Y-%m-%d")
    ttl = int((now.replace(day=28) + timedelta(days=32)).replace(day=1).timestamp())

    for ident, usage in usage_data.items():
        delta = usage.get("total_tokens", 0)
        if delta <= 0:
            continue
        try:
            resp = quota_table.get_item(Key={"pk": f"{pk_prefix}#{ident}", "sk": f"MONTH#{current_month}"})
            existing = resp.get("Item", {})
            daily_reset = existing.get("daily_date") != current_date

            update_expr = "ADD total_tokens :delta, input_tokens :inp, output_tokens :out"
            set_parts = ["last_updated = :ts", "#ttl = :ttl", "scope_type = :st", "scope_id = :sid"]
            if scope_type == "user":
                set_parts.append("email = :sid")  # back-compat: quota_check reads `email`
            if daily_reset:
                set_parts.append("daily_tokens = :delta")
                set_parts.append("daily_date = :date")
            else:
                update_expr += ", daily_tokens :delta"
            update_expr += " SET " + ", ".join(set_parts)

            values = {
                ":delta": Decimal(str(int(delta))),
                ":inp": Decimal(str(int(usage.get("input_tokens", 0)))),
                ":out": Decimal(str(int(usage.get("output_tokens", 0)))),
                ":ts": now.isoformat().replace("+00:00", "Z"),
                ":ttl": ttl,
                ":st": scope_type,
                ":sid": ident,
            }
            if daily_reset:
                values[":date"] = current_date

            quota_table.update_item(
                Key={"pk": f"{pk_prefix}#{ident}", "sk": f"MONTH#{current_month}"},
                UpdateExpression=update_expr,
                ExpressionAttributeNames={"#ttl": "ttl"},
                ExpressionAttributeValues=values,
            )
        except Exception as e:
            print(f"Error updating {scope_type} rollup for {ident}: {e}")
    print(f"Updated {len(usage_data)} {scope_type} rollups")


def _read_scope_totals(pk_prefix: str, current_month: str) -> dict[str, dict]:
    """Read cumulative monthly totals for every identifier in a scope."""
    totals: dict[str, dict] = {}
    kwargs = {
        "FilterExpression": Attr("sk").eq(f"MONTH#{current_month}") & Attr("pk").begins_with(f"{pk_prefix}#"),
        "ProjectionExpression": "scope_id, email, total_tokens, daily_tokens",
    }
    while True:
        resp = quota_table.scan(**kwargs)
        for item in resp.get("Items", []):
            ident = item.get("scope_id") or item.get("email")
            if ident:
                totals[ident] = {
                    "total_tokens": float(item.get("total_tokens", 0)),
                    "daily_tokens": float(item.get("daily_tokens", 0)),
                }
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return totals


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------
def load_all_policies() -> dict[str, dict]:
    """Load every CURRENT policy into a {policy_type:identifier → policy} cache."""
    policies: dict[str, dict] = {}
    if not policies_table:
        return policies
    kwargs = {"FilterExpression": Attr("sk").eq("CURRENT")}
    try:
        while True:
            resp = policies_table.scan(**kwargs)
            for item in resp.get("Items", []):
                pt, ident = item.get("policy_type"), item.get("identifier")
                if not (pt and ident):
                    continue
                policies[f"{pt}:{ident}"] = {
                    "policy_type": pt,
                    "identifier": ident,
                    "monthly_token_limit": int(item.get("monthly_token_limit", 0)),
                    "daily_token_limit": int(item.get("daily_token_limit", 0)) if item.get("daily_token_limit") else None,
                    "warning_threshold_80": int(item.get("warning_threshold_80", 0)),
                    "warning_threshold_90": int(item.get("warning_threshold_90", 0)),
                    "enforcement_mode": item.get("enforcement_mode", "alert"),
                    "enabled": item.get("enabled", True),
                }
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    except Exception as e:
        print(f"Error loading policies: {e}")
    return policies


def resolve_scope_policy(scope_type: str, identifier: str, policies_cache: dict) -> dict | None:
    """Resolve the effective policy for one scope identifier.

    user scope falls back to the env default (or the 'default' policy when
    fine-grained is on). team/dept resolve to their own policy only — no default,
    so an unconfigured team/dept is simply not enforced.
    """
    if not ENABLE_FINEGRAINED_QUOTAS:
        if scope_type == "user":
            return {
                "policy_type": "default", "identifier": "environment",
                "monthly_token_limit": MONTHLY_TOKEN_LIMIT, "daily_token_limit": None,
                "warning_threshold_80": WARNING_THRESHOLD_80, "warning_threshold_90": WARNING_THRESHOLD_90,
                "enforcement_mode": "alert", "enabled": True,
            }
        return None

    key = f"{scope_type}:{identifier}"
    if key in policies_cache and policies_cache[key].get("enabled"):
        return policies_cache[key]
    if scope_type == "user":
        default = policies_cache.get("default:default")
        if default and default.get("enabled"):
            return default
    return None


def check_limits_and_generate_alerts(scope_type, identifier, total_tokens, daily_tokens,
                                     policy, month_name, current_date, days_remaining,
                                     days_in_month, sent_alerts):
    """Emit alert dicts for a scope identifier that crossed monthly/daily thresholds."""
    alerts = []
    policy_info = f"{policy['policy_type']}:{policy['identifier']}"
    enforcement_mode = policy.get("enforcement_mode", "alert")
    monthly_limit = policy["monthly_token_limit"]
    monthly_pct = (total_tokens / monthly_limit) * 100 if monthly_limit > 0 else 0
    day_of_month = max(1, int(current_date.split("-")[2]))
    daily_average = total_tokens / day_of_month
    projected_total = daily_average * days_in_month

    level = None
    if monthly_limit > 0 and total_tokens > monthly_limit:
        level = "exceeded"
    elif total_tokens > policy["warning_threshold_90"] > 0:
        level = "critical"
    elif total_tokens > policy["warning_threshold_80"] > 0:
        level = "warning"
    if level and f"{scope_type}#{identifier}#monthly#{level}" not in sent_alerts:
        alerts.append({
            "scope_type": scope_type, "identifier": identifier,
            "alert_type": "monthly", "alert_level": level,
            "current_usage": int(total_tokens), "limit": monthly_limit,
            "percentage": round(monthly_pct, 1), "month": month_name,
            "days_remaining": days_remaining, "daily_average": int(daily_average),
            "projected_total": int(projected_total), "policy_info": policy_info,
            "enforcement_mode": enforcement_mode,
        })

    daily_limit = policy.get("daily_token_limit")
    if daily_limit:
        daily_pct = (daily_tokens / daily_limit) * 100 if daily_limit > 0 else 0
        dlevel = None
        if daily_tokens > daily_limit:
            dlevel = "exceeded"
        elif daily_tokens > daily_limit * 0.9:
            dlevel = "critical"
        elif daily_tokens > daily_limit * 0.8:
            dlevel = "warning"
        if dlevel and f"{scope_type}#{identifier}#daily#{current_date}#{dlevel}" not in sent_alerts:
            alerts.append({
                "scope_type": scope_type, "identifier": identifier,
                "alert_type": "daily", "alert_level": dlevel,
                "current_usage": int(daily_tokens), "limit": daily_limit,
                "percentage": round(daily_pct, 1), "date": current_date,
                "policy_info": policy_info, "enforcement_mode": enforcement_mode,
            })
    return alerts


# ---------------------------------------------------------------------------
# Alert dedup + delivery
# ---------------------------------------------------------------------------
def get_sent_alerts(month_prefix: str) -> set[str]:
    """Alerts already sent this month (so we notify once per threshold crossing)."""
    sent: set[str] = set()
    kwargs = {
        "KeyConditionExpression": Key("pk").eq("ALERTS") & Key("sk").begins_with(f"{month_prefix}#ALERT#")
    }
    try:
        while True:
            resp = quota_table.query(**kwargs)
            for item in resp.get("Items", []):
                parts = item["sk"].split("#")
                # ym ALERT scope_type identifier alert_type alert_level [date]
                if len(parts) >= 6:
                    scope_type, ident, atype, alevel = parts[2], parts[3], parts[4], parts[5]
                    if atype == "daily" and len(parts) >= 7:
                        sent.add(f"{scope_type}#{ident}#daily#{parts[6]}#{alevel}")
                    else:
                        sent.add(f"{scope_type}#{ident}#{atype}#{alevel}")
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    except Exception as e:
        print(f"Error reading sent alerts: {e}")
    return sent


def record_sent_alert(month_prefix: str, alert: dict):
    """Persist an alert marker so duplicates are suppressed for the period."""
    try:
        st, ident, atype, alevel = alert["scope_type"], alert["identifier"], alert["alert_type"], alert["alert_level"]
        if atype == "daily":
            date = alert.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
            sk = f"{month_prefix}#ALERT#{st}#{ident}#{atype}#{alevel}#{date}"
        else:
            sk = f"{month_prefix}#ALERT#{st}#{ident}#{atype}#{alevel}"
        quota_table.put_item(Item={
            "pk": "ALERTS", "sk": sk,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "scope_type": st, "identifier": ident,
            "alert_type": atype, "alert_level": alevel,
            "usage_at_alert": Decimal(str(alert.get("current_usage", 0))),
            "ttl": int(datetime.now(timezone.utc).timestamp()) + (60 * 86400),
        })
    except Exception as e:
        print(f"Error recording alert: {e}")


def send_alerts(alerts: list[dict]):
    """Publish alerts to SNS (email subscribers are managed at deploy time)."""
    if not SNS_TOPIC_ARN:
        print("SNS_TOPIC_ARN not configured")
        return
    scope_label = {"user": "User", "team": "Team", "dept": "Dept"}
    for alert in alerts:
        try:
            level_prefix = {"warning": "WARNING", "critical": "CRITICAL", "exceeded": "EXCEEDED"}.get(
                alert["alert_level"], "ALERT")
            type_label = {"monthly": "Monthly Token Quota", "daily": "Daily Token Quota"}.get(
                alert["alert_type"], "Quota")
            scope = scope_label.get(alert["scope_type"], alert["scope_type"])
            subject = f"Claude Code {level_prefix} - {scope} {type_label} - {alert['percentage']:.0f}%"
            message = (
                f"SCOPE: {scope} = {alert['identifier']}\n"
                f"ALERT: {type_label} - {alert['alert_level'].upper()}\n"
                f"Usage: {alert['current_usage']:,} / {alert['limit']:,} ({alert['percentage']:.1f}%)\n"
                f"Policy: {alert.get('policy_info', 'default')}\n"
                f"Enforcement: {alert.get('enforcement_mode', 'alert')}"
            )
            sns_client.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject[:100], Message=message)
        except Exception as e:
            print(f"Error sending alert for {alert.get('identifier')}: {e}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def lambda_handler(event, context):
    """Aggregate user/team/dept usage from CloudWatch, roll up to DynamoDB, alert."""
    now = datetime.now(timezone.utc)
    print(f"Starting quota monitoring at {now.isoformat()}")
    current_month = now.strftime("%Y-%m")
    month_name = now.strftime("%B %Y")
    current_date = now.strftime("%Y-%m-%d")
    days_in_month = (now.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    days_in_month = days_in_month.day
    days_remaining = days_in_month - now.day

    try:
        # Step 1: per-axis delta aggregation → DynamoDB rollups
        for scope_type, (pk_prefix, dim_name, suffix) in SCOPES.items():
            ids = _discover_dim_values(f"InputTokens{suffix}", dim_name)
            ids |= _known_ids_from_table(pk_prefix)
            delta = _fetch_axis_usage(dim_name, suffix, sorted(ids))
            if delta:
                update_scope_metrics(scope_type, pk_prefix, delta)

        # Step 2: load policies + dedup state
        policies_cache = load_all_policies() if (ENABLE_FINEGRAINED_QUOTAS and policies_table) else {}
        sent_alerts = get_sent_alerts(current_month)

        # Step 3: evaluate cumulative totals per scope
        alerts_to_send = []
        stats = {"user": 0, "team": 0, "dept": 0, "exceeded": 0}
        for scope_type, (pk_prefix, _dim, _suffix) in SCOPES.items():
            totals = _read_scope_totals(pk_prefix, current_month)
            for ident, usage in totals.items():
                stats[scope_type] += 1
                policy = resolve_scope_policy(scope_type, ident, policies_cache)
                if policy is None:
                    continue
                total_tokens = usage.get("total_tokens", 0)
                daily_tokens = usage.get("daily_tokens", 0)
                alerts = check_limits_and_generate_alerts(
                    scope_type, ident, total_tokens, daily_tokens, policy,
                    month_name, current_date, days_remaining, days_in_month, sent_alerts,
                )
                limit = policy["monthly_token_limit"]
                if limit > 0 and total_tokens > limit:
                    stats["exceeded"] += 1
                for alert in alerts:
                    alerts_to_send.append(alert)
                    record_sent_alert(current_month, alert)

        if alerts_to_send:
            send_alerts(alerts_to_send)
            print(f"Sent {len(alerts_to_send)} alerts")

        print(f"Summary - users:{stats['user']} teams:{stats['team']} depts:{stats['dept']} exceeded:{stats['exceeded']}")
        return {"statusCode": 200, "body": json.dumps(stats)}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"statusCode": 500, "body": json.dumps(f"Error: {e}")}
