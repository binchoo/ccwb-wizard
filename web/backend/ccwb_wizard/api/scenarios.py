"""Scenarios API — expose domain catalogs to the frontend."""

from __future__ import annotations

from fastapi import APIRouter

from ccwb_domain.providers import PROVIDERS
from ccwb_domain.providers.base import FormField
from ccwb_domain.bedrock_models import (
    CLAUDE_MODELS,
    get_available_profiles_for_model,
    get_tier_options_for_region,
    get_invocable_source_regions,
)

router = APIRouter(tags=["scenarios"])


@router.get("/scenarios")
async def get_scenarios() -> dict:
    """Return full scenario catalog for the frontend wizard."""
    return {
        "providers": _serialize_providers(),
        "distribution_types": ["presigned-s3", "landing-page"],
        "models": _serialize_models(),
    }


@router.get("/scenarios/providers")
async def get_providers() -> list[dict]:
    """Provider list with wizard_inputs metadata."""
    return _serialize_providers()


@router.get("/scenarios/models")
async def get_models() -> dict:
    """Model matrix for cascade selector."""
    return _serialize_models()


@router.get("/scenarios/source-regions")
async def get_source_regions() -> list[str]:
    """All AWS regions invocable as a Bedrock source region for any Claude model.

    Used by the Bedrock page to populate the source region dropdown when the
    user wants to override the Environment page region for model invocation.
    """
    return get_invocable_source_regions()


@router.get("/scenarios/tier-options")
async def get_tier_options(region: str) -> dict:
    """Tier-bucketed CRIS profile options invocable from ``region``.

    Returns ``{tier: [{model_id, display_name, profile_key, base_model_name}, ...]}``
    where tier ∈ {haiku, sonnet, opus}. The frontend renders one dropdown per
    tier with these options and persists the chosen ``model_id`` directly.
    """
    buckets = get_tier_options_for_region(region)
    return {tier: [opt.to_dict() for opt in opts] for tier, opts in buckets.items()}


def _serialize_providers() -> list[dict]:
    result = []
    for ptype, cls in PROVIDERS.items():
        inputs = cls.wizard_inputs()
        result.append({
            "type": ptype,
            "wizard_inputs": [_field_to_dict(f) for f in inputs],
        })
    return result


def _serialize_models() -> dict:
    out = {}
    for key, model in CLAUDE_MODELS.items():
        out[key] = {
            "name": model.name,
            "profiles": list(model.profiles.keys()),
            "source_regions": {
                pk: list(pv.source_regions) for pk, pv in model.profiles.items()
            },
        }
    return out


def _field_to_dict(f: FormField) -> dict:
    d: dict = {"name": f.name, "label": f.label, "type": f.type, "required": f.required}
    if f.placeholder:
        d["placeholder"] = f.placeholder
    if f.default is not None:
        d["default"] = f.default
    if f.options:
        d["options"] = f.options
    if f.help_text:
        d["help_text"] = f.help_text
    if f.sensitive:
        d["sensitive"] = True
    if f.validator:
        d["validator"] = f.validator
    return d
