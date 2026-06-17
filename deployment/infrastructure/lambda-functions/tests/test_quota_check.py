# ABOUTME: Unit tests for quota_check lambda — multi-scope (user/team/dept) aggregate enforcement
# ABOUTME: Loads the standalone index.py via importlib and injects fake DynamoDB tables

import importlib.util
import json
import os
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
CHECK_DIR = HERE.parent / "quota_check"


def _load_quota_check(monkeypatch, **env):
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    # bedrock_metadata is a sibling module imported by index.py
    monkeypatch.syspath_prepend(str(CHECK_DIR))
    spec = importlib.util.spec_from_file_location("quota_check_index", CHECK_DIR / "index.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeTable:
    def __init__(self, items=None):
        self.items = items or {}  # (pk, sk) -> item

    def get_item(self, Key):
        item = self.items.get((Key["pk"], Key["sk"]))
        return {"Item": item} if item else {}


def _event(claims):
    return {"requestContext": {"authorizer": {"jwt": {"claims": claims}}}}


ATTR = json.dumps({"mapping": {"user": "email", "team": "custom:team", "dept": "custom:dept"}})


def test_derive_scopes_maps_team_and_dept(monkeypatch):
    mod = _load_quota_check(monkeypatch, ENABLE_FINEGRAINED_QUOTAS="true", ATTRIBUTION_JSON=ATTR)
    scopes = mod.derive_scopes({"email": "a@x.com", "custom:team": "blue", "custom:dept": "eng"})
    assert scopes == {"user": "a@x.com", "team": "blue", "dept": "eng"}


def test_team_aggregate_block(monkeypatch):
    """Team usage over a block-mode team policy denies access (true aggregation)."""
    mod = _load_quota_check(monkeypatch, ENABLE_FINEGRAINED_QUOTAS="true", ATTRIBUTION_JSON=ATTR)
    mod.policies_table = FakeTable({
        ("POLICY#team#blue", "CURRENT"): {
            "policy_type": "team", "identifier": "blue",
            "monthly_token_limit": 1000, "enforcement_mode": "block", "enabled": True,
        },
    })
    mod.quota_table = FakeTable({
        # team rollup already over the limit (sum of all members)
        ("TEAM#blue", "MONTH#" + mod.datetime.now(mod.timezone.utc).strftime("%Y-%m")):
            {"total_tokens": 1500, "daily_tokens": 0},
    })
    resp = json.loads(mod.lambda_handler(_event(
        {"email": "a@x.com", "custom:team": "blue", "custom:dept": "eng"}), None)["body"])
    assert resp["allowed"] is False
    assert resp["blocked_scope"] == "team"
    assert resp["reason"] == "monthly_exceeded"


def test_team_under_limit_allows(monkeypatch):
    mod = _load_quota_check(monkeypatch, ENABLE_FINEGRAINED_QUOTAS="true", ATTRIBUTION_JSON=ATTR)
    mod.policies_table = FakeTable({
        ("POLICY#team#blue", "CURRENT"): {
            "policy_type": "team", "identifier": "blue",
            "monthly_token_limit": 1000, "enforcement_mode": "block", "enabled": True,
        },
    })
    mod.quota_table = FakeTable({
        ("TEAM#blue", "MONTH#" + mod.datetime.now(mod.timezone.utc).strftime("%Y-%m")):
            {"total_tokens": 500, "daily_tokens": 0},
    })
    resp = json.loads(mod.lambda_handler(_event(
        {"email": "a@x.com", "custom:team": "blue"}), None)["body"])
    assert resp["allowed"] is True


def test_alert_only_team_does_not_block(monkeypatch):
    mod = _load_quota_check(monkeypatch, ENABLE_FINEGRAINED_QUOTAS="true", ATTRIBUTION_JSON=ATTR)
    mod.policies_table = FakeTable({
        ("POLICY#team#blue", "CURRENT"): {
            "policy_type": "team", "identifier": "blue",
            "monthly_token_limit": 1000, "enforcement_mode": "alert", "enabled": True,
        },
    })
    mod.quota_table = FakeTable({
        ("TEAM#blue", "MONTH#" + mod.datetime.now(mod.timezone.utc).strftime("%Y-%m")):
            {"total_tokens": 9999, "daily_tokens": 0},
    })
    resp = json.loads(mod.lambda_handler(_event(
        {"email": "a@x.com", "custom:team": "blue"}), None)["body"])
    assert resp["allowed"] is True


def test_missing_identity_fail_closed(monkeypatch):
    mod = _load_quota_check(monkeypatch, ENABLE_FINEGRAINED_QUOTAS="true",
                            ATTRIBUTION_JSON=ATTR, MISSING_EMAIL_ENFORCEMENT="block")
    mod.policies_table = FakeTable()
    mod.quota_table = FakeTable()
    resp = json.loads(mod.lambda_handler(_event({"sub": "no-email"}), None)["body"])
    assert resp["allowed"] is False
    assert resp["reason"] == "missing_identity"
