"""materialize() quota stack — verifies attribution + fine-grained params flow to CFN."""

import json

from ccwb_domain.config import Config
from ccwb_domain.materialize import materialize


def _config(**quota):
    return Config(
        profile_name="qt",
        aws_region="us-east-1",
        stack_base_name="cc-test",
        provider={"type": "okta", "domain": "test.okta.com", "client_id": "cid123"},
        attribution={"mapping": {"user": "email", "team": "custom:team", "dept": "custom:dept"}, "passthrough": []},
        quota=quota or None,
    )


def _quota_stack(cfg):
    arts = materialize(cfg)
    return next(s for s in arts.stacks if s.stack_name.endswith("-quota"))


def test_quota_stack_carries_attribution_json():
    cfg = _config(monthly_token_limit=100, enable_finegrained_quotas=True)
    stack = _quota_stack(cfg)
    attribution = json.loads(stack.parameters["AttributionJson"])
    assert attribution["mapping"]["team"] == "custom:team"
    assert attribution["mapping"]["dept"] == "custom:dept"


def test_quota_stack_finegrained_flag_lowercased():
    cfg = _config(monthly_token_limit=100, enable_finegrained_quotas=True)
    stack = _quota_stack(cfg)
    assert stack.parameters["EnableFinegrainedQuotas"] == "true"


def test_quota_stack_defaults_when_finegrained_absent():
    cfg = _config(monthly_token_limit=100)
    stack = _quota_stack(cfg)
    assert stack.parameters["EnableFinegrainedQuotas"] == "false"
    assert stack.parameters["AttributionJson"]  # always present


def test_no_quota_stack_when_quota_disabled():
    cfg = _config()  # quota=None
    arts = materialize(cfg)
    assert not any(s.stack_name.endswith("-quota") for s in arts.stacks)
