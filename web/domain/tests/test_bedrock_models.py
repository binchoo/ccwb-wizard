"""Unit tests for bedrock_models.py (Cleanup unit test debt + Domain baseline)."""

import pytest

from ccwb_domain.bedrock_models import (
    CLAUDE_MODELS,
    ClaudeModel,
    InferenceProfile,
    get_all_model_display_names,
    get_available_profiles_for_model,
    get_default_region_for_profile,
    get_destination_regions_for_model_profile,
    get_model_id_for_profile,
    get_profile_description,
    get_source_regions_for_model_profile,
)


class TestModelMatrix:
    """Matrix data integrity."""

    def test_claude_models_not_empty(self):
        assert len(CLAUDE_MODELS) >= 1

    def test_every_model_has_at_least_one_profile(self):
        for key, model in CLAUDE_MODELS.items():
            assert len(model.profiles) >= 1, f"{key} has no profiles"

    def test_every_model_is_claude_model_instance(self):
        for key, model in CLAUDE_MODELS.items():
            assert isinstance(model, ClaudeModel), f"{key} is not ClaudeModel"

    def test_every_profile_is_inference_profile_instance(self):
        for model_key, model in CLAUDE_MODELS.items():
            for prof_key, prof in model.profiles.items():
                assert isinstance(prof, InferenceProfile), f"{model_key}/{prof_key}"

    def test_every_profile_has_model_id(self):
        for model_key, model in CLAUDE_MODELS.items():
            for prof_key, prof in model.profiles.items():
                assert prof.model_id, f"{model_key}/{prof_key} has empty model_id"

    def test_every_profile_has_source_regions(self):
        for model_key, model in CLAUDE_MODELS.items():
            for prof_key, prof in model.profiles.items():
                assert len(prof.source_regions) >= 1, f"{model_key}/{prof_key}"

    def test_known_model_exists(self):
        assert "sonnet-4-6" in CLAUDE_MODELS


class TestHelperFunctions:
    """Helper function correctness."""

    def test_get_available_profiles_for_known_model(self):
        profiles = get_available_profiles_for_model("sonnet-4-6")
        assert "us" in profiles
        assert isinstance(profiles, list)

    def test_get_available_profiles_for_unknown_model(self):
        assert get_available_profiles_for_model("nonexistent-99") == []

    def test_get_model_id_for_profile(self):
        model_id = get_model_id_for_profile("sonnet-4-6", "us")
        assert "anthropic" in model_id
        assert "sonnet" in model_id

    def test_get_model_id_unknown_model_raises(self):
        with pytest.raises(ValueError, match="Unknown model"):
            get_model_id_for_profile("nonexistent", "us")

    def test_get_model_id_unknown_profile_raises(self):
        with pytest.raises(ValueError, match="not available"):
            get_model_id_for_profile("sonnet-4-6", "nonexistent-profile")

    def test_get_default_region_for_us(self):
        assert get_default_region_for_profile("us") == "us-east-1"

    def test_get_default_region_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown profile"):
            get_default_region_for_profile("antarctica")

    def test_get_source_regions(self):
        regions = get_source_regions_for_model_profile("sonnet-4-6", "us")
        assert "us-east-1" in regions
        assert isinstance(regions, (list, tuple))

    def test_get_destination_regions(self):
        regions = get_destination_regions_for_model_profile("sonnet-4-6", "us")
        assert len(regions) >= 1

    def test_get_all_model_display_names_not_empty(self):
        names = get_all_model_display_names()
        assert len(names) >= 1
        # Every value is a non-empty string
        for model_id, display in names.items():
            assert display, f"Empty display name for {model_id}"

    def test_get_profile_description(self):
        desc = get_profile_description("sonnet-4-6", "us")
        assert isinstance(desc, str)
        assert len(desc) > 0


class TestDictLikeInterface:
    """Backward-compatible dict-like access."""

    def test_model_getitem(self):
        model = CLAUDE_MODELS["sonnet-4-6"]
        assert model["name"] == model.name
        assert "us" in model["profiles"]

    def test_model_contains(self):
        model = CLAUDE_MODELS["sonnet-4-6"]
        assert "profiles" in model
        assert "name" in model

    def test_profile_getitem(self):
        prof = CLAUDE_MODELS["sonnet-4-6"].profiles["us"]
        assert prof["model_id"] == prof.model_id

    def test_profile_keys(self):
        prof = CLAUDE_MODELS["sonnet-4-6"].profiles["us"]
        keys = prof.keys()
        assert "model_id" in keys
        assert "source_regions" in keys
