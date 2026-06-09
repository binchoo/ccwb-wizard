"""Unit tests for provider strategies."""

import pytest

from ccwb_domain.config import Config
from ccwb_domain.providers import PROVIDERS, provider_strategy
from ccwb_domain.providers.base import FormField, IdentityProvider


class TestProviderRegistry:
    """Registry integrity and dispatch."""

    def test_five_providers_registered(self):
        assert len(PROVIDERS) == 5
        assert set(PROVIDERS.keys()) == {"okta", "azure", "cognito", "auth0", "generic"}

    def test_all_providers_are_identity_provider_subclass(self):
        for name, cls in PROVIDERS.items():
            assert issubclass(cls, IdentityProvider), f"{name} is not IdentityProvider"

    def test_dispatch_okta(self):
        p = provider_strategy({"type": "okta", "domain": "x.okta.com", "client_id": "abc"})
        assert p.provider_type == "okta"

    def test_dispatch_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown provider type"):
            provider_strategy({"type": "nonexistent"})


class TestOktaProvider:
    def test_cfn_parameters(self):
        from ccwb_domain.providers.okta import OktaProvider

        p = OktaProvider(domain="test.okta.com", client_id="id123")
        config = Config(profile_name="t", stack_base_name="test-stack", source_region="us-east-1", models={"sonnet": "us.anthropic.claude-sonnet-4-6", "haiku": "", "opus": ""}, cross_region_profile="us")
        params = p.cfn_parameters(config)
        assert params["OktaDomain"] == "test.okta.com"
        assert params["OktaClientId"] == "id123"
        assert params["FederationType"] == "direct"

    def test_settings_env(self):
        from ccwb_domain.providers.okta import OktaProvider

        p = OktaProvider(domain="x", client_id="y")
        config = Config(profile_name="t", source_region="us-east-1", models={"sonnet": "us.anthropic.claude-sonnet-4-6", "haiku": "us.anthropic.claude-haiku-4-5", "opus": ""})
        env = p.settings_env(config)
        assert env["AWS_PROFILE"] == "t"
        assert env["CLAUDE_CODE_USE_MANTLE"] == "0"
        assert env["AWS_REGION"] == "us-east-1"
        assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "us.anthropic.claude-sonnet-4-6"
        assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "us.anthropic.claude-haiku-4-5"
        assert "ANTHROPIC_DEFAULT_OPUS_MODEL" not in env  # empty = not included
        assert "ANTHROPIC_MODEL" not in env  # removed: duplicated sonnet, redundant

    def test_wizard_inputs(self):
        from ccwb_domain.providers.okta import OktaProvider

        inputs = OktaProvider.wizard_inputs()
        assert len(inputs) >= 2
        assert all(isinstance(f, FormField) for f in inputs)
        names = [f.name for f in inputs]
        assert "domain" in names
        assert "client_id" in names


class TestAzureProvider:
    def test_auth_modes(self):
        from ccwb_domain.providers.azure import AzureProvider

        for mode in ("public", "secret", "certificate"):
            p = AzureProvider.from_dict({"type": "azure", "tenant_id": "t", "client_id": "c", "auth_mode": mode})
            assert p.auth_mode == mode


class TestMaterialize:
    """Basic materialize() smoke test."""

    def test_materialize_produces_stacks(self):
        from ccwb_domain.materialize import materialize

        config = Config(
            profile_name="test",
            aws_region="us-east-1",
            stack_base_name="my-stack",
            provider={"type": "okta", "domain": "test.okta.com", "client_id": "abc123"},
            models={"sonnet": "us.anthropic.claude-sonnet-4-6", "haiku": "", "opus": ""},
            cross_region_profile="us",
            source_region="us-east-1",
        )
        result = materialize(config)
        stack_names = [s.stack_name for s in result.stacks]
        assert "my-stack-auth" in stack_names
        assert "my-stack-bedrock-logging" in stack_names
        assert "my-stack-dashboard" in stack_names
        assert "my-stack-s3" in stack_names

    def test_materialize_deterministic(self):
        from ccwb_domain.materialize import materialize

        config = Config(
            profile_name="det",
            stack_base_name="det-stack",
            provider={"type": "auth0", "domain": "x.auth0.com", "client_id": "id"},
            models={"sonnet": "us.anthropic.claude-sonnet-4-6", "haiku": "", "opus": ""},
            cross_region_profile="us",
            source_region="us-east-1",
        )
        r1 = materialize(config)
        r2 = materialize(config)
        assert r1.to_review_dict() == r2.to_review_dict()

    def test_materialize_with_quota(self):
        from ccwb_domain.materialize import materialize

        config = Config(
            profile_name="q",
            stack_base_name="q-stack",
            provider={"type": "okta", "domain": "o.okta.com", "client_id": "c"},
            models={"sonnet": "us.anthropic.claude-sonnet-4-6", "haiku": "", "opus": ""},
            cross_region_profile="us",
            source_region="us-east-1",
            quota={"monthly_token_limit": 100000000, "daily_token_limit": 5000000, "daily_enforcement": "alert", "monthly_enforcement": "block"},
        )
        result = materialize(config)
        stack_names = [s.stack_name for s in result.stacks]
        assert "q-stack-quota" in stack_names

    def test_to_review_dict_masks_secrets(self):
        from ccwb_domain.materialize import DeploymentArtifacts, KeyringWrite, StackPlan

        artifacts = DeploymentArtifacts(
            stacks=[],
            settings_json_template={},
            aws_config_template="",
            keyring_writes=[KeyringWrite(service="svc", account="acct", value="TOP_SECRET")],
        )
        review = artifacts.to_review_dict()
        assert review["keyring_writes"][0]["value"] == "***"
