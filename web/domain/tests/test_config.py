"""Unit tests for Config dataclass — load/save roundtrip, schema validation."""

import json
import tempfile
from pathlib import Path

import pytest

from ccwb_domain.config import Config, UnsupportedSchemaError


class TestConfigRoundtrip:
    """Config.save() → Config.load() roundtrip."""

    def test_save_and_load(self, tmp_path: Path):
        cfg = Config(
            profile_name="test-profile",
            aws_region="us-east-1",
            stack_base_name="test-stack",
            provider={"type": "okta", "domain": "test.okta.com", "client_id": "abc123"},
            models={"sonnet": "us.anthropic.claude-sonnet-4-6", "haiku": "", "opus": ""},
            cross_region_profile="us",
            source_region="us-east-1",
        )
        path = tmp_path / "profiles" / "test.json"
        cfg.save(path)

        loaded = Config.load(path)
        assert loaded.profile_name == "test-profile"
        assert loaded.provider == {"type": "okta", "domain": "test.okta.com", "client_id": "abc123"}
        assert loaded.models["sonnet"] == "us.anthropic.claude-sonnet-4-6"

    def test_schema_version_preserved(self, tmp_path: Path):
        cfg = Config(profile_name="v-test")
        path = tmp_path / "v.json"
        cfg.save(path)
        loaded = Config.load(path)
        assert loaded.schema_version == "3.0"

    def test_unknown_fields_ignored(self, tmp_path: Path):
        path = tmp_path / "extra.json"
        data = {"profile_name": "extra", "schema_version": "3.0", "unknown_field": "hello"}
        path.write_text(json.dumps(data))
        loaded = Config.load(path)
        assert loaded.profile_name == "extra"
        assert not hasattr(loaded, "unknown_field")

    def test_unsupported_schema_raises(self, tmp_path: Path):
        path = tmp_path / "old.json"
        path.write_text(json.dumps({"profile_name": "old", "schema_version": "2.0"}))
        with pytest.raises(UnsupportedSchemaError, match="2.0"):
            Config.load(path)

    def test_missing_schema_raises(self, tmp_path: Path):
        path = tmp_path / "no-ver.json"
        path.write_text(json.dumps({"profile_name": "x"}))
        with pytest.raises(UnsupportedSchemaError, match="unknown"):
            Config.load(path)

    def test_no_secret_in_saved_json(self, tmp_path: Path):
        """Config.save() must never write raw secrets to disk."""
        cfg = Config(
            profile_name="sec-test",
            provider={"type": "azure", "tenant_id": "t", "client_id": "c", "auth_mode": "secret", "_keyring_ref": "ccwb:sec-test-client-secret"},
        )
        path = tmp_path / "sec.json"
        cfg.save(path)
        content = path.read_text()
        # _keyring_ref is metadata, not a raw secret — this is fine
        assert "_keyring_ref" in content
        # But there should be no "client_secret" key with an actual value
        data = json.loads(content)
        provider = data.get("provider", {})
        assert "client_secret" not in provider

    def test_to_dict(self):
        cfg = Config(profile_name="dict-test", aws_region="eu-west-1")
        d = cfg.to_dict()
        assert d["profile_name"] == "dict-test"
        assert d["aws_region"] == "eu-west-1"
        assert d["schema_version"] == "3.0"
