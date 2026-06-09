# ABOUTME: Lambda function that monitors user token quotas and sends SNS alerts
# ABOUTME: Queries CloudWatch PromQL API for usage data, writes to DynamoDB, checks thresholds

import json
import boto3
import os
from datetime import datetime, timezone
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr

# Initialize clients
dynamodb = boto3.resource("dynamodb")
sns_client = boto3.client("sns")

# Configuration from environment
QUOTA_TABLE = os.environ.get("QUOTA_TABLE", "UserQuotaMetrics")
POLICIES_TABLE = os.environ.get("POLICIES_TABLE")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")
ENABLE_FINEGRAINED_QUOTAS = os.environ.get("ENABLE_FINEGRAINED_QUOTAS", "false").lower() == "true"
METRICS_REGION = os.environ.get("METRICS_REGION", os.environ.get("AWS_REGION", "us-east-1"))

# Default limits
MONTHLY_TOKEN_LIMIT = int(os.environ.get("MONTHLY_TOKEN_LIMIT", "300000000"))
WARNING_THRESHOLD_80 = int(os.environ.get("WARNING_THRESHOLD_80", "240000000"))
WARNING_THRESHOLD_90 = int(os.environ.get("WARNING_THRESHOLD_90", "270000000"))

# DynamoDB tables
quota_table = dynamodb.Table(QUOTA_TABLE)
policies_table = dynamodb.Table(POLICIES_TABLE) if POLICIES_TABLE else None


AGGREGATION_WINDOW = 900  # 15 minutes in seconds (matches EventBridge schedule)

# CloudWatch metric namespace populated by bedrock-logging stack metric filters.
# (Replaces the OTEL-based PromQL data source as of v3.0.)
METRIC_NAMESPACE = os.environ.get("METRIC_NAMESPACE", "ClaudeCodeBedrock")

cloudwatch_client = boto3.client("cloudwatch", region_name=METRICS_REGION)


def _discover_users_from_metrics() -> set[str]:
    """Discover users from the CloudWatch metric dimensions themselves.

    The bedrock-logging metric filters emit ``InputTokensByUser`` in the
    ``ClaudeCodeBedrock`` namespace with a ``User`` dimension equal to
    ``$.requestMetadata.user`` (the ccwb identity contract). ListMetrics returns
    every metric+dimension combination already observed, so we can enumerate the
    set of ``User`` values WITHOUT knowing them in advance — this is what breaks
    the empty-table bootstrap deadlock (GetMetricData needs explicit dimensions).
    """
    seen: set[str] = set()
    try:
        paginator = cloudwatch_client.get_paginator("list_metrics")
        for page in paginator.paginate(
            Namespace=METRIC_NAMESPACE,
            MetricName="InputTokensByUser",
        ):
            for metric in page.get("Metrics", []):
                for dim in metric.get("Dimensions", []):
                    if dim.get("Name") == "User" and dim.get("Value"):
                        seen.add(dim["Value"])
    except Exception as e:
        print(f"[WARN] Failed to discover users from CloudWatch metrics: {e}")
    return seen


def _list_known_users() -> list[str]:
    """Discover users to query for usage aggregation.

    Union of two sources:
      1. CloudWatch metric dimensions (``ClaudeCodeBedrock/InputTokensByUser`` →
         ``User``) — the authoritative, self-bootstrapping source based on the
         identity contract carried in Bedrock invocation logs.
      2. The UserQuotaMetrics table — retains users who have history but produced
         no traffic in the current ListMetrics window.

    GetMetricData requires dimension values up front, so source (1) is what makes
    a fresh/empty deployment work: users appear as soon as they generate their
    first attributed Bedrock invocation, with no manual seeding.
    """
    seen: set[str] = _discover_users_from_metrics()
    try:
        # Scan rather than Query because we want unique users across all months.
        # Cardinality is bounded by user count (PoC scale), and projection trims payload.
        kwargs = {"ProjectionExpression": "email"}
        while True:
            resp = quota_table.scan(**kwargs)
            for item in resp.get("Items", []):
                email = item.get("email")
                if email:
                    seen.add(email)
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    except Exception as e:
        print(f"[WARN] Failed to enumerate users from DynamoDB: {e}")
    return sorted(seen)


def _chunked(seq, size):
    """Yield successive chunks of ``size`` from ``seq``."""
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def fetch_usage_from_cloudwatch():
    """Fetch per-user token usage from CloudWatch Custom Metrics.

    Replaces the v2.x PromQL data path. The bedrock-logging stack defines metric
    filters on Bedrock model invocation logs that emit ``InputTokensByUser`` and
    ``OutputTokensByUser`` to the ``ClaudeCodeBedrock`` namespace, with a ``User``
    dimension matching ``$.requestMetadata.user``.

    Returns a dict shaped exactly like the old PromQL function so callers don't change:

        {
          "alice@example.com": {
            "total_tokens": 1234,
            "input_tokens": 1000,
            "output_tokens": 234,
          },
          ...
        }
    """
    users_list = _list_known_users()
    if not users_list:
        print("No users discovered yet; skipping CloudWatch fetch.")
        return {}

    end = datetime.now(timezone.utc)
    start = end - __import__("datetime").timedelta(seconds=AGGREGATION_WINDOW)

    # GetMetricData allows max 500 queries per call, but each user contributes 2
    # (input + output), so chunk to 250 users per batch.
    users: dict[str, dict] = {}

    for batch in _chunked(users_list, 250):
        queries = []
        for i, email in enumerate(batch):
            queries.append({
                "Id": f"in_{i}",
                "Label": email,
                "MetricStat": {
                    "Metric": {
                        "Namespace": METRIC_NAMESPACE,
                        "MetricName": "InputTokensByUser",
                        "Dimensions": [{"Name": "User", "Value": email}],
                    },
                    "Period": AGGREGATION_WINDOW,
                    "Stat": "Sum",
                },
                "ReturnData": True,
            })
            queries.append({
                "Id": f"out_{i}",
                "Label": email,
                "MetricStat": {
                    "Metric": {
                        "Namespace": METRIC_NAMESPACE,
                        "MetricName": "OutputTokensByUser",
                        "Dimensions": [{"Name": "User", "Value": email}],
                    },
                    "Period": AGGREGATION_WINDOW,
                    "Stat": "Sum",
                },
                "ReturnData": True,
            })

        try:
            resp = cloudwatch_client.get_metric_data(
                MetricDataQueries=queries, StartTime=start, EndTime=end,
            )
        except Exception as e:
            print(f"[ERROR] GetMetricData failed for batch of {len(batch)}: {e}")
            continue

        # Map results back to users.  Each query Id encodes its index and direction.
        for r in resp.get("MetricDataResults", []):
            qid = r["Id"]
            email = r.get("Label", "")
            values = r.get("Values", [])
            total = sum(float(v) for v in values)
            if total <= 0 or not email:
                continue
            entry = users.setdefault(email, {"total_tokens": 0.0})
            if qid.startswith("in_"):
                entry["input_tokens"] = entry.get("input_tokens", 0.0) + total
            elif qid.startswith("out_"):
                entry["output_tokens"] = entry.get("output_tokens", 0.0) + total
            entry["total_tokens"] = entry.get("input_tokens", 0.0) + entry.get("output_tokens", 0.0)

    print(f"Fetched delta usage for {len(users)} users from CloudWatch ({AGGREGATION_WINDOW}s window)")
    return users


# Back-compat alias: the rest of this module still calls fetch_usage_from_promql.
# Pointing the alias at the new function lets us swap data sources without
# touching the lambda_handler / update_quota_metrics call sites.
fetch_usage_from_promql = fetch_usage_from_cloudwatch


def update_quota_metrics(usage_data):
    """Atomically increment UserQuotaMetrics with delta from PromQL (like old MetricsAggregator)."""
    now = datetime.now(timezone.utc)
    current_month = now.strftime("%Y-%m")
    current_date = now.strftime("%Y-%m-%d")
    ttl = int((now.replace(day=28) + __import__("datetime").timedelta(days=32)).replace(day=1).timestamp())

    for email, usage in usage_data.items():
        delta = usage.get("total_tokens", 0)
        if delta <= 0:
            continue
        try:
            # Check if daily_date changed (new day = reset daily counter)
            response = quota_table.get_item(Key={"pk": f"USER#{email}", "sk": f"MONTH#{current_month}"})
            existing = response.get("Item", {})
            daily_reset = existing.get("daily_date") != current_date

            update_expr = "ADD total_tokens :delta, input_tokens :inp, output_tokens :out, cache_tokens :cache"
            if daily_reset:
                update_expr += " SET daily_tokens = :delta, daily_date = :date, last_updated = :ts, #ttl = :ttl, email = :email"
            else:
                update_expr += ", daily_tokens :delta SET last_updated = :ts, #ttl = :ttl, email = :email"

            quota_table.update_item(
                Key={"pk": f"USER#{email}", "sk": f"MONTH#{current_month}"},
                UpdateExpression=update_expr,
                ExpressionAttributeNames={"#ttl": "ttl"},
                ExpressionAttributeValues={
                    ":delta": Decimal(str(int(delta))),
                    ":inp": Decimal(str(int(usage.get("input_tokens", 0)))),
                    ":out": Decimal(str(int(usage.get("output_tokens", 0)))),
                    ":cache": Decimal(str(int(usage.get("cache_tokens", 0)))),
                    ":date": current_date,
                    ":ts": now.isoformat().replace("+00:00", "Z"),
                    ":ttl": ttl,
                    ":email": email,
                },
            )
        except Exception as e:
            print(f"Error updating quota for {email}: {e}")

    print(f"Updated UserQuotaMetrics for {len(usage_data)} users")


def lambda_handler(event, context):
    """Fetch usage from PromQL, update DynamoDB, check quotas, send alerts."""
    print(f"Starting quota monitoring at {datetime.now(timezone.utc).isoformat()}")

    now = datetime.now(timezone.utc)
    month_name = now.strftime("%B %Y")
    current_date = now.strftime("%Y-%m-%d")
    days_in_month = (31 if now.month in [1, 3, 5, 7, 8, 10, 12]
                     else (30 if now.month != 2 else (29 if now.year % 4 == 0 else 28)))
    days_remaining = days_in_month - now.day

    try:
        # Step 1: Fetch delta usage from PromQL and increment DynamoDB
        delta_data = fetch_usage_from_promql()
        if delta_data:
            update_quota_metrics(delta_data)

        # Step 2: Read cumulative totals from DynamoDB for threshold checking
        current_month = now.strftime("%Y-%m")
        usage_data = {}
        response = quota_table.scan(
            FilterExpression=Attr("sk").eq(f"MONTH#{current_month}") & Attr("pk").begins_with("USER#"),
            ProjectionExpression="email, total_tokens, daily_tokens",
        )
        for item in response.get("Items", []):
            email = item.get("email")
            if email:
                usage_data[email] = {
                    "total_tokens": float(item.get("total_tokens", 0)),
                    "daily_tokens": float(item.get("daily_tokens", 0)),
                }
        while "LastEvaluatedKey" in response:
            response = quota_table.scan(
                FilterExpression=Attr("sk").eq(f"MONTH#{current_month}") & Attr("pk").begins_with("USER#"),
                ProjectionExpression="email, total_tokens, daily_tokens",
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            for item in response.get("Items", []):
                email = item.get("email")
                if email:
                    usage_data[email] = {
                        "total_tokens": float(item.get("total_tokens", 0)),
                        "daily_tokens": float(item.get("daily_tokens", 0)),
                    }

        if not usage_data:
            print("No usage data in DynamoDB")
            return {"statusCode": 200, "body": "No usage data"}

        # Step 3: Load policies
        policies_cache = {}
        if ENABLE_FINEGRAINED_QUOTAS and policies_table:
            policies_cache = load_all_policies()

        # Step 3: Check sent alerts
        sent_alerts = get_sent_alerts(month_name)

        # Step 4: Check each user against quotas
        alerts_to_send = []
        stats = {"total_users": 0, "over_80": 0, "over_90": 0, "exceeded": 0, "daily_exceeded": 0}

        for email, usage in usage_data.items():
            stats["total_users"] += 1
            policy = resolve_user_quota(email, [], policies_cache)
            if policy is None:
                continue

            total_tokens = usage.get("total_tokens", 0)
            daily_tokens = usage.get("daily_tokens", 0)

            alerts = check_limits_and_generate_alerts(
                email=email, total_tokens=total_tokens, daily_tokens=daily_tokens,
                policy=policy, month_name=month_name, current_date=current_date,
                days_remaining=days_remaining, days_in_month=days_in_month, sent_alerts=sent_alerts,
            )

            monthly_pct = (total_tokens / policy["monthly_token_limit"]) * 100 if policy["monthly_token_limit"] > 0 else 0
            if monthly_pct > 100:
                stats["exceeded"] += 1
            elif monthly_pct > 90:
                stats["over_90"] += 1
            elif monthly_pct > 80:
                stats["over_80"] += 1
            if policy.get("daily_token_limit") and daily_tokens > policy["daily_token_limit"]:
                stats["daily_exceeded"] += 1

            for alert in alerts:
                alert_key = f"{email}#{alert['alert_type']}#{alert['alert_level']}"
                if alert_key not in sent_alerts:
                    alerts_to_send.append(alert)
                    record_sent_alert(month_name, email, alert["alert_type"], alert["alert_level"], alert)

        if alerts_to_send:
            send_alerts(alerts_to_send)
            print(f"Sent {len(alerts_to_send)} alerts")

        print(f"Summary - Total: {stats['total_users']}, Over 80%: {stats['over_80']}, Over 90%: {stats['over_90']}, Exceeded: {stats['exceeded']}")
        return {"statusCode": 200, "body": json.dumps(stats)}

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return {"statusCode": 500, "body": json.dumps(f"Error: {e}")}


def load_all_policies():
    """Load all quota policies from QuotaPolicies table."""
    policies = {}
    if not policies_table:
        return policies
    try:
        response = policies_table.scan(FilterExpression=Attr("sk").eq("CURRENT"))
        for item in response.get("Items", []):
            pt, ident = item.get("policy_type"), item.get("identifier")
            if pt and ident:
                policies[f"{pt}:{ident}"] = {
                    "policy_type": pt, "identifier": ident,
                    "monthly_token_limit": int(item.get("monthly_token_limit", 0)),
                    "daily_token_limit": int(item.get("daily_token_limit", 0)) if item.get("daily_token_limit") else None,
                    "warning_threshold_80": int(item.get("warning_threshold_80", 0)),
                    "warning_threshold_90": int(item.get("warning_threshold_90", 0)),
                    "enforcement_mode": item.get("enforcement_mode", "alert"),
                    "enabled": item.get("enabled", True),
                }
        while "LastEvaluatedKey" in response:
            response = policies_table.scan(FilterExpression=Attr("sk").eq("CURRENT"), ExclusiveStartKey=response["LastEvaluatedKey"])
            for item in response.get("Items", []):
                pt, ident = item.get("policy_type"), item.get("identifier")
                if pt and ident:
                    policies[f"{pt}:{ident}"] = {
                        "policy_type": pt, "identifier": ident,
                        "monthly_token_limit": int(item.get("monthly_token_limit", 0)),
                        "daily_token_limit": int(item.get("daily_token_limit", 0)) if item.get("daily_token_limit") else None,
                        "warning_threshold_80": int(item.get("warning_threshold_80", 0)),
                        "warning_threshold_90": int(item.get("warning_threshold_90", 0)),
                        "enforcement_mode": item.get("enforcement_mode", "alert"),
                        "enabled": item.get("enabled", True),
                    }
    except Exception as e:
        print(f"Error loading policies: {e}")
    return policies


def resolve_user_quota(email, groups, policies_cache):
    """Resolve effective quota policy: user > group > default > env defaults."""
    if not ENABLE_FINEGRAINED_QUOTAS:
        return {
            "policy_type": "default", "identifier": "environment",
            "monthly_token_limit": MONTHLY_TOKEN_LIMIT, "daily_token_limit": None,
            "warning_threshold_80": WARNING_THRESHOLD_80, "warning_threshold_90": WARNING_THRESHOLD_90,
            "enforcement_mode": "alert", "enabled": True,
        }
    user_key = f"user:{email}"
    if user_key in policies_cache and policies_cache[user_key].get("enabled"):
        return policies_cache[user_key]
    group_policies = [policies_cache[f"group:{g}"] for g in (groups or [])
                      if f"group:{g}" in policies_cache and policies_cache[f"group:{g}"].get("enabled")]
    if group_policies:
        return min(group_policies, key=lambda p: p["monthly_token_limit"])
    default_key = "default:default"
    if default_key in policies_cache and policies_cache[default_key].get("enabled"):
        return policies_cache[default_key]
    return None


def check_limits_and_generate_alerts(email, total_tokens, daily_tokens, policy,
                                     month_name, current_date, days_remaining, days_in_month, sent_alerts):
    """Check limits and generate alert dicts."""
    alerts = []
    policy_info = f"{policy['policy_type']}:{policy['identifier']}"
    enforcement_mode = policy.get("enforcement_mode", "alert")
    monthly_limit = policy["monthly_token_limit"]
    monthly_pct = (total_tokens / monthly_limit) * 100 if monthly_limit > 0 else 0
    daily_average = total_tokens / max(1, int(current_date.split("-")[2]))
    projected_total = daily_average * days_in_month

    level = None
    if total_tokens > monthly_limit:
        level = "exceeded"
    elif total_tokens > policy["warning_threshold_90"]:
        level = "critical"
    elif total_tokens > policy["warning_threshold_80"]:
        level = "warning"

    if level and f"{email}#monthly#{level}" not in sent_alerts:
        alerts.append({
            "user": email, "alert_type": "monthly", "alert_level": level,
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
        elif daily_tokens > (daily_limit * 0.9):
            dlevel = "critical"
        elif daily_tokens > (daily_limit * 0.8):
            dlevel = "warning"
        if dlevel and f"{email}#daily#{current_date}#{dlevel}" not in sent_alerts:
            alerts.append({
                "user": email, "alert_type": "daily", "alert_level": dlevel,
                "current_usage": int(daily_tokens), "limit": daily_limit,
                "percentage": round(daily_pct, 1), "date": current_date,
                "policy_info": policy_info, "enforcement_mode": enforcement_mode,
            })
    return alerts


def get_sent_alerts(month_name):
    """Get alerts already sent this month."""
    sent = set()
    try:
        month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
        response = quota_table.query(
            KeyConditionExpression=Key("pk").eq("ALERTS") & Key("sk").begins_with(f"{month_prefix}#ALERT#")
        )
        for item in response.get("Items", []):
            parts = item["sk"].split("#")
            if len(parts) >= 5:
                email, atype, alevel = parts[2], parts[3], parts[4]
                if atype == "daily" and len(parts) >= 6:
                    sent.add(f"{email}#{atype}#{parts[5]}#{alevel}")
                else:
                    sent.add(f"{email}#{atype}#{alevel}")
        while "LastEvaluatedKey" in response:
            response = quota_table.query(
                KeyConditionExpression=Key("pk").eq("ALERTS") & Key("sk").begins_with(f"{month_prefix}#ALERT#"),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            for item in response.get("Items", []):
                parts = item["sk"].split("#")
                if len(parts) >= 5:
                    email, atype, alevel = parts[2], parts[3], parts[4]
                    if atype == "daily" and len(parts) >= 6:
                        sent.add(f"{email}#{atype}#{parts[5]}#{alevel}")
                    else:
                        sent.add(f"{email}#{atype}#{alevel}")
    except Exception as e:
        print(f"Error checking sent alerts: {e}")
    return sent


def record_sent_alert(month_name, email, alert_type, alert_level, alert_data):
    """Record sent alert to prevent duplicates."""
    try:
        month_prefix = datetime.now(timezone.utc).strftime("%Y-%m")
        if alert_type == "daily":
            date = alert_data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
            sk = f"{month_prefix}#ALERT#{email}#{alert_type}#{alert_level}#{date}"
        else:
            sk = f"{month_prefix}#ALERT#{email}#{alert_type}#{alert_level}"
        quota_table.put_item(Item={
            "pk": "ALERTS", "sk": sk,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "email": email, "alert_type": alert_type, "alert_level": alert_level,
            "usage_at_alert": Decimal(str(alert_data.get("current_usage", 0))),
            "ttl": int(datetime.now(timezone.utc).timestamp()) + (60 * 86400),
        })
    except Exception as e:
        print(f"Error recording alert: {e}")


def send_alerts(alerts):
    """Send alerts via SNS."""
    if not SNS_TOPIC_ARN:
        print("SNS_TOPIC_ARN not configured")
        return
    for alert in alerts:
        try:
            level_prefix = {"warning": "WARNING", "critical": "CRITICAL", "exceeded": "EXCEEDED"}.get(alert["alert_level"], "ALERT")
            type_label = {"monthly": "Monthly Token Quota", "daily": "Daily Token Quota"}.get(alert["alert_type"], "Quota")
            subject = f"Claude Code {level_prefix} - {type_label} - {alert['percentage']:.0f}%"
            message = (f"USER: {alert['user']}\nALERT: {type_label} - {alert['alert_level'].upper()}\n"
                       f"Usage: {alert['current_usage']:,} / {alert['limit']:,} ({alert['percentage']:.1f}%)\n"
                       f"Policy: {alert.get('policy_info', 'default')}\n"
                       f"Enforcement: {alert.get('enforcement_mode', 'alert')}")
            sns_client.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject, Message=message)
        except Exception as e:
            print(f"Error sending alert for {alert['user']}: {e}")
