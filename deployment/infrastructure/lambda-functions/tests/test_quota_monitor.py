# ABOUTME: Unit tests for quota_monitor lambda — per-axis fetch, scope policy, alert generation
# ABOUTME: Loads standalone index.py via importlib; injects a fake CloudWatch client

import importlib.util
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
MON_DIR = HERE.parent / "quota_monitor"


def _load(monkeypatch, **env):
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location("quota_monitor_index", MON_DIR / "index.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeCW:
    """Minimal CloudWatch stub returning fixed in/out token sums per label."""
    def __init__(self, results):
        self._results = results

    def get_metric_data(self, MetricDataQueries, StartTime, EndTime):
        out = []
        for qid_label in self._results:
            out.append(qid_label)
        return {"MetricDataResults": out}


def test_fetch_axis_usage_sums_in_and_out(monkeypatch):
    mod = _load(monkeypatch)
    # in_0 = input for blue, out_0 = output for blue
    mod.cloudwatch_client = FakeCW([
        {"Id": "in_0", "Label": "blue", "Values": [100.0, 50.0]},
        {"Id": "out_0", "Label": "blue", "Values": [30.0]},
    ])
    usage = mod._fetch_axis_usage("Team", "ByTeam", ["blue"])
    assert usage["blue"]["input_tokens"] == 150.0
    assert usage["blue"]["output_tokens"] == 30.0
    assert usage["blue"]["total_tokens"] == 180.0


def test_resolve_team_policy_no_default_fallback(monkeypatch):
    mod = _load(monkeypatch, ENABLE_FINEGRAINED_QUOTAS="true")
    cache = {
        "team:blue": {"policy_type": "team", "identifier": "blue", "monthly_token_limit": 1000,
                      "warning_threshold_80": 800, "warning_threshold_90": 900,
                      "enforcement_mode": "block", "enabled": True, "daily_token_limit": None},
        "default:default": {"policy_type": "default", "identifier": "default", "monthly_token_limit": 50,
                            "warning_threshold_80": 40, "warning_threshold_90": 45,
                            "enforcement_mode": "block", "enabled": True, "daily_token_limit": None},
    }
    # team resolves to its own policy
    assert mod.resolve_scope_policy("team", "blue", cache)["monthly_token_limit"] == 1000
    # unknown team gets NO default (team has no fallback)
    assert mod.resolve_scope_policy("team", "ghost", cache) is None
    # unknown user falls back to default
    assert mod.resolve_scope_policy("user", "ghost@x.com", cache)["policy_type"] == "default"


def test_resolve_user_env_default_when_finegrained_off(monkeypatch):
    mod = _load(monkeypatch, ENABLE_FINEGRAINED_QUOTAS="false", MONTHLY_TOKEN_LIMIT="777")
    pol = mod.resolve_scope_policy("user", "a@x.com", {})
    assert pol["monthly_token_limit"] == 777
    # team/dept have no env default when fine-grained is off
    assert mod.resolve_scope_policy("team", "blue", {}) is None


def test_check_limits_generates_team_exceeded_alert(monkeypatch):
    mod = _load(monkeypatch, ENABLE_FINEGRAINED_QUOTAS="true")
    policy = {"policy_type": "team", "identifier": "blue", "monthly_token_limit": 1000,
              "warning_threshold_80": 800, "warning_threshold_90": 900,
              "enforcement_mode": "block", "daily_token_limit": None}
    alerts = mod.check_limits_and_generate_alerts(
        "team", "blue", total_tokens=1500, daily_tokens=0, policy=policy,
        month_name="June 2026", current_date="2026-06-15", days_remaining=15,
        days_in_month=30, sent_alerts=set())
    assert len(alerts) == 1
    assert alerts[0]["scope_type"] == "team"
    assert alerts[0]["alert_level"] == "exceeded"
    assert alerts[0]["alert_type"] == "monthly"
