"""Bedrock model matrix for ccwb.

Extracted from the legacy ``source/claude_code_with_bedrock/models.py`` for the
new ``ccwb_domain`` package. Single source of truth for Claude model IDs,
cross-region inference profiles, and source/destination regions.

Q1=A scope (Cleanup unit): model matrix and related helpers only. Quota
domain (PolicyType, EnforcementMode, QuotaPolicy, UserQuotaUsage) is
intentionally not extracted — the Domain unit will redesign it for schema 3.0.

Q2=C tidying applied: import cleanup, module docstring, function order
(dataclass → builder → data → getter). Signatures and logic preserved.
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InferenceProfile:
    """A CRIS inference profile for a specific geography."""

    model_id: str
    description: str
    source_regions: tuple[str, ...]
    destination_regions: tuple[str, ...]

    def __getitem__(self, key: str):
        """Dict-like access for backward compatibility."""
        return getattr(self, key)

    def get(self, key: str, default=None):
        """Dict-like .get() for backward compatibility."""
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        """Support 'key in profile' checks."""
        return hasattr(self, key)

    def keys(self):
        """Dict-like .keys() for backward compatibility."""
        return ["model_id", "description", "source_regions", "destination_regions"]


@dataclass(frozen=True)
class ClaudeModel:
    """A Claude model with its available inference profiles."""

    name: str
    base_model_id: str
    profiles: dict[str, InferenceProfile]

    def __getitem__(self, key: str):
        """Dict-like access for backward compatibility."""
        if key == "profiles":
            return self.profiles
        return getattr(self, key)

    def get(self, key: str, default=None):
        """Dict-like .get() for backward compatibility."""
        if key == "profiles":
            return self.profiles
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        """Support 'key in model' checks."""
        if key == "profiles":
            return True
        return hasattr(self, key)

    def keys(self):
        """Dict-like .keys() for backward compatibility."""
        return ["name", "base_model_id", "profiles"]

    @property
    def available_profiles(self) -> list[str]:
        return list(self.profiles.keys())


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _build_profile(data: dict) -> InferenceProfile:
    """Convert a profile dict to an InferenceProfile dataclass."""
    return InferenceProfile(
        model_id=data["model_id"],
        description=data.get("description", ""),
        source_regions=tuple(data.get("source_regions", ())),
        destination_regions=tuple(data.get("destination_regions", ())),
    )


def _build_model(data: dict) -> ClaudeModel:
    """Convert a model dict to a ClaudeModel dataclass."""
    profiles = {k: _build_profile(v) for k, v in data.get("profiles", {}).items()}
    return ClaudeModel(
        name=data["name"],
        base_model_id=data["base_model_id"],
        profiles=profiles,
    )


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


DEFAULT_REGIONS = {
    "us": "us-east-1",
    "eu": "eu-west-1",
    "europe": "eu-west-1",
    "apac": "ap-northeast-1",
    "us-gov": "us-gov-west-1",
}


# ---------------------------------------------------------------------------
# Model matrix (raw literal, then converted to dataclasses)
# ---------------------------------------------------------------------------

_CLAUDE_MODELS_RAW = {
    "sonnet-4-6": {
        "name": "Claude Sonnet 4.6",
        "base_model_id": "anthropic.claude-sonnet-4-6",
        "profiles": {
            "us": {
                "model_id": "us.anthropic.claude-sonnet-4-6",
                "description": "US CRIS - US and Canada regions",
                "source_regions": [
                    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
                    "ca-central-1", "ca-west-1",
                ],
                "destination_regions": [
                    "us-east-1", "us-east-2", "us-west-2",
                    "ca-central-1", "ca-west-1",
                ],
            },
            "global": {
                "model_id": "global.anthropic.claude-sonnet-4-6",
                "description": "Global CRIS - All commercial AWS regions worldwide",
                "source_regions": [
                    "af-south-1", "ap-east-2", "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
                    "ap-south-1", "ap-south-2", "ap-southeast-1", "ap-southeast-2", "ap-southeast-3",
                    "ap-southeast-4", "ap-southeast-5", "ap-southeast-7",
                    "ca-central-1", "ca-west-1",
                    "eu-central-1", "eu-central-2", "eu-north-1", "eu-south-1", "eu-south-2",
                    "eu-west-1", "eu-west-2", "eu-west-3",
                    "il-central-1", "me-central-1", "me-south-1", "mx-central-1", "sa-east-1",
                    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
                ],
                "destination_regions": ["all-commercial"],
            },
            "eu": {
                "model_id": "eu.anthropic.claude-sonnet-4-6",
                "description": "EU CRIS - European regions",
                "source_regions": ["eu-central-1", "eu-north-1", "eu-south-1", "eu-south-2", "eu-west-1", "eu-west-3"],
                "destination_regions": ["eu-central-1", "eu-north-1", "eu-south-1", "eu-south-2", "eu-west-1", "eu-west-3"],
            },
            "au": {
                "model_id": "au.anthropic.claude-sonnet-4-6",
                "description": "AU CRIS - Australia regions",
                "source_regions": ["ap-southeast-2", "ap-southeast-4"],
                "destination_regions": ["ap-southeast-2", "ap-southeast-4"],
            },
            "jp": {
                "model_id": "jp.anthropic.claude-sonnet-4-6",
                "description": "JP CRIS - Japan regions",
                "source_regions": ["ap-northeast-1", "ap-northeast-3"],
                "destination_regions": ["ap-northeast-1", "ap-northeast-3"],
            },
        },
    },
    "opus-4-8": {
        "name": "Claude Opus 4.8",
        "base_model_id": "anthropic.claude-opus-4-8",
        "profiles": {
            "us": {
                "model_id": "us.anthropic.claude-opus-4-8",
                "description": "US CRIS - US and Canada regions",
                "source_regions": [
                    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
                    "ca-central-1", "ca-west-1",
                ],
                "destination_regions": [
                    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
                    "ca-central-1", "ca-west-1",
                ],
            },
            "global": {
                "model_id": "global.anthropic.claude-opus-4-8",
                "description": "Global CRIS - All commercial AWS regions worldwide",
                "source_regions": [
                    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
                    "ca-central-1", "ca-west-1",
                    "eu-central-1", "eu-central-2", "eu-north-1",
                    "eu-south-1", "eu-south-2", "eu-west-1", "eu-west-2", "eu-west-3",
                    "ap-east-2", "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
                    "ap-south-1", "ap-south-2",
                    "ap-southeast-1", "ap-southeast-2", "ap-southeast-3", "ap-southeast-4",
                    "me-south-1", "me-central-1", "af-south-1", "il-central-1",
                    "sa-east-1",
                ],
                "destination_regions": [
                    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
                    "ca-central-1", "ca-west-1",
                    "eu-central-1", "eu-central-2", "eu-north-1",
                    "eu-south-1", "eu-south-2", "eu-west-1", "eu-west-2", "eu-west-3",
                    "ap-east-2", "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
                    "ap-south-1", "ap-south-2",
                    "ap-southeast-1", "ap-southeast-2", "ap-southeast-3", "ap-southeast-4",
                    "me-south-1", "me-central-1", "af-south-1", "il-central-1",
                    "sa-east-1",
                ],
            },
            "eu": {
                "model_id": "eu.anthropic.claude-opus-4-8",
                "description": "EU CRIS - European regions",
                "source_regions": [
                    "eu-central-1", "eu-central-2", "eu-north-1",
                    "eu-south-1", "eu-south-2", "eu-west-1", "eu-west-3",
                ],
                "destination_regions": [
                    "eu-central-1", "eu-central-2", "eu-north-1",
                    "eu-south-1", "eu-south-2", "eu-west-1", "eu-west-3",
                ],
            },
        },
    },
    "opus-4-7": {
        "name": "Claude Opus 4.7",
        "base_model_id": "anthropic.claude-opus-4-7",
        "profiles": {
            "us": {
                "model_id": "us.anthropic.claude-opus-4-7",
                "description": "US CRIS - US and Canada regions",
                "source_regions": [
                    "us-east-1",
                    "us-east-2",
                    "us-west-1",
                    "us-west-2",
                    "ca-central-1",
                    "ca-west-1",
                ],
                "destination_regions": [
                    "us-east-1",
                    "us-east-2",
                    "us-west-1",
                    "us-west-2",
                    "ca-central-1",
                    "ca-west-1",
                ],
            },
            "global": {
                "model_id": "global.anthropic.claude-opus-4-7",
                "description": "Global CRIS - All commercial AWS regions worldwide",
                "source_regions": [
                    # North America
                    "us-east-1",
                    "us-east-2",
                    "us-west-1",
                    "us-west-2",
                    "ca-central-1",
                    "ca-west-1",
                    # Europe
                    "eu-central-1",
                    "eu-central-2",
                    "eu-north-1",
                    "eu-south-1",
                    "eu-south-2",
                    "eu-west-1",
                    "eu-west-2",
                    "eu-west-3",
                    # Asia Pacific
                    "ap-east-2",
                    "ap-northeast-1",
                    "ap-northeast-2",
                    "ap-northeast-3",
                    "ap-south-1",
                    "ap-south-2",
                    "ap-southeast-1",
                    "ap-southeast-2",
                    "ap-southeast-3",
                    "ap-southeast-4",
                    # Middle East & Africa
                    "me-south-1",
                    "me-central-1",
                    "af-south-1",
                    "il-central-1",
                    # South America
                    "sa-east-1",
                ],
                "destination_regions": [
                    # North America
                    "us-east-1",
                    "us-east-2",
                    "us-west-1",
                    "us-west-2",
                    "ca-central-1",
                    "ca-west-1",
                    # Europe
                    "eu-central-1",
                    "eu-central-2",
                    "eu-north-1",
                    "eu-south-1",
                    "eu-south-2",
                    "eu-west-1",
                    "eu-west-2",
                    "eu-west-3",
                    # Asia Pacific
                    "ap-east-2",
                    "ap-northeast-1",
                    "ap-northeast-2",
                    "ap-northeast-3",
                    "ap-south-1",
                    "ap-south-2",
                    "ap-southeast-1",
                    "ap-southeast-2",
                    "ap-southeast-3",
                    "ap-southeast-4",
                    # Middle East & Africa
                    "me-south-1",
                    "me-central-1",
                    "af-south-1",
                    "il-central-1",
                    # South America
                    "sa-east-1",
                ],
            },
        },
    },
    "opus-4-6": {
        "name": "Claude Opus 4.6",
        "base_model_id": "anthropic.claude-opus-4-6-v1",
        "profiles": {
            "us": {
                "model_id": "us.anthropic.claude-opus-4-6-v1",
                "description": "US CRIS - US and Canada regions",
                "source_regions": [
                    "us-east-1",
                    "us-east-2",
                    "us-west-1",
                    "us-west-2",
                    "ca-central-1",
                    "ca-west-1",
                ],
                "destination_regions": [
                    "us-east-1",
                    "us-east-2",
                    "us-west-1",
                    "us-west-2",
                    "ca-central-1",
                    "ca-west-1",
                ],
            },
            "eu": {
                "model_id": "eu.anthropic.claude-opus-4-6-v1",
                "description": "EU CRIS - European regions",
                "source_regions": [
                    "eu-central-1",
                    "eu-central-2",
                    "eu-north-1",
                    "eu-south-1",
                    "eu-south-2",
                    "eu-west-1",
                    "eu-west-3",
                ],
                "destination_regions": [
                    "eu-central-1",
                    "eu-central-2",
                    "eu-north-1",
                    "eu-south-1",
                    "eu-south-2",
                    "eu-west-1",
                    "eu-west-3",
                ],
            },
            "au": {
                "model_id": "au.anthropic.claude-opus-4-6-v1",
                "description": "AU CRIS - Australia regions",
                "source_regions": [
                    "ap-southeast-2",
                    "ap-southeast-4",
                ],
                "destination_regions": [
                    "ap-southeast-2",
                    "ap-southeast-4",
                ],
            },
            "global": {
                "model_id": "global.anthropic.claude-opus-4-6-v1",
                "description": "Global CRIS - All commercial AWS regions worldwide",
                "source_regions": [
                    # North America
                    "us-east-1",
                    "us-east-2",
                    "us-west-1",
                    "us-west-2",
                    "ca-central-1",
                    "ca-west-1",
                    # Europe
                    "eu-central-1",
                    "eu-central-2",
                    "eu-north-1",
                    "eu-south-1",
                    "eu-south-2",
                    "eu-west-1",
                    "eu-west-2",
                    "eu-west-3",
                    # Asia Pacific
                    "ap-east-2",
                    "ap-northeast-1",
                    "ap-northeast-2",
                    "ap-northeast-3",
                    "ap-south-1",
                    "ap-south-2",
                    "ap-southeast-1",
                    "ap-southeast-2",
                    "ap-southeast-3",
                    "ap-southeast-4",
                    # Middle East & Africa
                    "me-south-1",
                    "me-central-1",
                    "af-south-1",
                    "il-central-1",
                    # South America
                    "sa-east-1",
                ],
                "destination_regions": [
                    # North America
                    "us-east-1",
                    "us-east-2",
                    "us-west-1",
                    "us-west-2",
                    "ca-central-1",
                    "ca-west-1",
                    # Europe
                    "eu-central-1",
                    "eu-central-2",
                    "eu-north-1",
                    "eu-south-1",
                    "eu-south-2",
                    "eu-west-1",
                    "eu-west-2",
                    "eu-west-3",
                    # Asia Pacific
                    "ap-east-2",
                    "ap-northeast-1",
                    "ap-northeast-2",
                    "ap-northeast-3",
                    "ap-south-1",
                    "ap-south-2",
                    "ap-southeast-1",
                    "ap-southeast-2",
                    "ap-southeast-3",
                    "ap-southeast-4",
                    # Middle East & Africa
                    "me-south-1",
                    "me-central-1",
                    "af-south-1",
                    "il-central-1",
                    # South America
                    "sa-east-1",
                ],
            },
        },
    },
    "opus-4-5": {
        "name": "Claude Opus 4.5",
        "base_model_id": "anthropic.claude-opus-4-5-20251101-v1:0",
        "profiles": {
            "us": {
                "model_id": "us.anthropic.claude-opus-4-5-20251101-v1:0",
                "description": "US CRIS - US and Canada regions",
                "source_regions": [
                    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
                    "ca-central-1",
                ],
                "destination_regions": [
                    "us-east-1", "us-east-2", "us-west-2",
                    "ca-central-1",
                ],
            },
            "global": {
                "model_id": "global.anthropic.claude-opus-4-5-20251101-v1:0",
                "description": "Global CRIS - All commercial AWS regions worldwide",
                "source_regions": [
                    "af-south-1", "ap-east-2", "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
                    "ap-south-1", "ap-south-2", "ap-southeast-1", "ap-southeast-2", "ap-southeast-3",
                    "ap-southeast-4", "ap-southeast-5", "ap-southeast-7",
                    "ca-central-1", "ca-west-1",
                    "eu-central-1", "eu-central-2", "eu-north-1", "eu-south-1", "eu-south-2",
                    "eu-west-1", "eu-west-2", "eu-west-3",
                    "il-central-1", "me-central-1", "me-south-1", "mx-central-1", "sa-east-1",
                    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
                ],
                "destination_regions": ["all-commercial"],
            },
            "eu": {
                "model_id": "eu.anthropic.claude-opus-4-5-20251101-v1:0",
                "description": "EU CRIS - European regions",
                "source_regions": ["eu-central-1", "eu-north-1", "eu-south-1", "eu-south-2", "eu-west-1", "eu-west-3"],
                "destination_regions": ["eu-central-1", "eu-north-1", "eu-south-1", "eu-south-2", "eu-west-1", "eu-west-3"],
            },
        },
    },
    "opus-4-1": {
        "name": "Claude Opus 4.1",
        "base_model_id": "anthropic.claude-opus-4-1-20250805-v1:0",
        "profiles": {
            "us": {
                "model_id": "us.anthropic.claude-opus-4-1-20250805-v1:0",
                "description": "US regions only",
                "source_regions": ["us-west-2", "us-east-2", "us-east-1"],
                "destination_regions": ["us-east-1", "us-east-2", "us-west-2"],
            }
        },
    },
    "opus-4": {
        "name": "Claude Opus 4",
        "base_model_id": "anthropic.claude-opus-4-20250514-v1:0",
        "profiles": {
            "us": {
                "model_id": "us.anthropic.claude-opus-4-20250514-v1:0",
                "description": "US regions only",
                "source_regions": [
                    "us-west-2",
                    "us-east-2",
                    "us-east-1",
                ],
                "destination_regions": [
                    "us-west-2",
                    "us-east-2",
                    "us-east-1",
                ],
            }
        },
    },
    "sonnet-4": {
        "name": "Claude Sonnet 4",
        "base_model_id": "anthropic.claude-sonnet-4-20250514-v1:0",
        "profiles": {
            "us": {
                "model_id": "us.anthropic.claude-sonnet-4-20250514-v1:0",
                "description": "US regions",
                "source_regions": [
                    "us-west-2",
                    "us-east-2",
                    "us-east-1",
                ],
                "destination_regions": [
                    "us-west-2",
                    "us-east-2",
                    "us-east-1",
                ],
            },
            "eu": {
                "model_id": "eu.anthropic.claude-sonnet-4-20250514-v1:0",
                "description": "European regions",
                "source_regions": [
                    "eu-west-3",
                    "eu-west-1",
                    "eu-south-2",
                    "eu-south-1",
                    "eu-north-1",
                    "eu-central-1",
                ],
                "destination_regions": [
                    "eu-central-1",
                    "eu-north-1",
                    "eu-south-1",
                    "eu-south-2",
                    "eu-west-1",
                    "eu-west-3",
                ],
            },
            "apac": {
                "model_id": "apac.anthropic.claude-sonnet-4-20250514-v1:0",
                "description": "Asia-Pacific regions",
                "source_regions": [
                    "ap-southeast-2",
                    "ap-southeast-1",
                    "ap-south-2",
                    "ap-south-1",
                    "ap-northeast-3",
                    "ap-northeast-2",
                    "ap-northeast-1",
                ],
                "destination_regions": [
                    "ap-northeast-1",
                    "ap-northeast-2",
                    "ap-northeast-3",
                    "ap-south-1",
                    "ap-south-2",
                    "ap-southeast-1",
                    "ap-southeast-2",
                    "ap-southeast-4",
                ],
            },
            "global": {
                "model_id": "global.anthropic.claude-sonnet-4-20250514-v1:0",
                "description": "Global routing across all AWS regions",
                "source_regions": [
                    "us-east-1",
                    "us-east-2",
                    "us-west-1",
                    "us-west-2",
                    "eu-west-1",
                    "eu-west-3",
                    "eu-central-1",
                    "eu-north-1",
                    "eu-south-1",
                    "eu-south-2",
                    "ap-northeast-1",
                    "ap-northeast-2",
                    "ap-northeast-3",
                    "ap-south-1",
                    "ap-south-2",
                    "ap-southeast-1",
                    "ap-southeast-2",
                    "ap-southeast-4",
                ],
                "destination_regions": [
                    "us-east-1",
                    "us-east-2",
                    "us-west-1",
                    "us-west-2",
                    "eu-west-1",
                    "eu-west-3",
                    "eu-central-1",
                    "eu-north-1",
                    "eu-south-1",
                    "eu-south-2",
                    "ap-northeast-1",
                    "ap-northeast-2",
                    "ap-northeast-3",
                    "ap-south-1",
                    "ap-south-2",
                    "ap-southeast-1",
                    "ap-southeast-2",
                    "ap-southeast-4",
                ],
            },
        },
    },
    "sonnet-4-5": {
        "name": "Claude Sonnet 4.5",
        "base_model_id": "anthropic.claude-sonnet-4-5-20250929-v1:0",
        "profiles": {
            "us": {
                "model_id": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "description": "US CRIS - US East (N. Virginia), US East (Ohio), US West (Oregon), US \
                West (N. California)",
                "source_regions": [
                    "us-east-1",  # N. Virginia
                    "us-east-2",  # Ohio
                    "us-west-2",  # Oregon
                    "us-west-1",  # N. California
                ],
                "destination_regions": [
                    "us-east-1",
                    "us-east-2",
                    "us-west-2",
                    "us-west-1",
                ],
            },
            "eu": {
                "model_id": "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "description": "EU CRIS - Europe (Frankfurt, Zurich, Stockholm, Ireland, London, Paris, Milan, Spain)",
                "source_regions": [
                    "eu-central-1",  # Frankfurt
                    "eu-central-2",  # Zurich
                    "eu-north-1",  # Stockholm
                    "eu-west-1",  # Ireland
                    "eu-west-2",  # London
                    "eu-west-3",  # Paris
                    "eu-south-2",  # Milan
                    "eu-south-2",  # Spain
                ],
                "destination_regions": [
                    "eu-central-1",
                    "eu-central-2",
                    "eu-north-1",
                    "eu-west-1",
                    "eu-west-2",
                    "eu-west-3",
                    "eu-south-2",
                    "eu-south-2",
                ],
            },
            "jp": {
                "model_id": "jp.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "description": "Japan CRIS - Asia Pacific (Tokyo), Asia Pacific (Osaka)",
                "source_regions": [
                    "ap-northeast-1",  # Tokyo
                    "ap-northeast-3",  # Osaka
                ],
                "destination_regions": [
                    "ap-northeast-1",
                    "ap-northeast-3",
                ],
            },
            "global": {
                "model_id": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "description": "Global CRIS - All regions worldwide",
                "source_regions": [
                    # North America
                    "us-east-1",  # N. Virginia
                    "us-east-2",  # Ohio
                    "us-west-2",  # Oregon
                    "us-west-1",  # N. California
                    "ca-central-1",  # Canada Central
                    # Europe
                    "eu-central-1",  # Frankfurt
                    "eu-central-2",  # Zurich
                    "eu-north-1",  # Stockholm
                    "eu-west-1",  # Ireland
                    "eu-west-2",  # London
                    "eu-west-3",  # Paris
                    "eu-south-2",  # Milan
                    "eu-south-2",  # Spain
                    # Asia Pacific
                    "ap-southeast-3",  # Jakarta
                    "ap-northeast-1",  # Tokyo
                    "ap-northeast-2",  # Seoul
                    "ap-northeast-3",  # Osaka
                    "ap-south-1",  # Mumbai
                    "ap-south-2",  # Hyderabad
                    "ap-southeast-1",  # Singapore
                    "ap-southeast-4",  # Melbourne
                    "ap-southeast-2",  # Sydney
                    # South America
                    "sa-east-1",  # São Paulo
                ],
                "destination_regions": [
                    # North America
                    "us-east-1",
                    "us-east-2",
                    "us-west-2",
                    "us-west-1",
                    "ca-central-1",
                    # Europe
                    "eu-central-1",
                    "eu-central-2",
                    "eu-north-1",
                    "eu-west-1",
                    "eu-west-2",
                    "eu-west-3",
                    "eu-south-2",
                    "eu-south-2",
                    # Asia Pacific
                    "ap-southeast-3",
                    "ap-northeast-1",
                    "ap-northeast-2",
                    "ap-northeast-3",
                    "ap-south-1",
                    "ap-south-2",
                    "ap-southeast-1",
                    "ap-southeast-4",
                    "ap-southeast-2",
                    # South America
                    "sa-east-1",
                ],
            },
            "au": {
                "model_id": "au.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "description": "AU CRIS - Australia regions",
                "source_regions": ["ap-southeast-2", "ap-southeast-4"],
                "destination_regions": ["ap-southeast-2", "ap-southeast-4"],
            },
        },
    },
    "sonnet-4-5-govcloud": {
        "name": "Claude Sonnet 4.5 (GovCloud)",
        "base_model_id": "anthropic.claude-sonnet-4-5-20250929-v1:0",
        "profiles": {
            "us-gov": {
                "model_id": "us-gov.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "description": "US GovCloud regions",
                "source_regions": ["us-gov-west-1", "us-gov-east-1"],
                "destination_regions": ["us-gov-west-1", "us-gov-east-1"],
            },
        },
    },
    "sonnet-3-7": {
        "name": "Claude 3.7 Sonnet",
        "base_model_id": "anthropic.claude-3-7-sonnet-20250219-v1:0",
        "profiles": {
            "us": {
                "model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                "description": "US regions",
                "source_regions": [
                    "us-west-2",
                    "us-east-2",
                    "us-east-1",
                ],
                "destination_regions": [
                    "us-west-2",
                    "us-east-2",
                    "us-east-1",
                ],
            },
            "eu": {
                "model_id": "eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
                "description": "European regions",
                "source_regions": [
                    "eu-west-3",
                    "eu-west-1",
                    "eu-north-1",
                ],
                "destination_regions": [
                    "eu-central-1",
                    "eu-north-1",
                    "eu-west-1",
                    "eu-west-3",
                ],
            },
            "apac": {
                "model_id": "apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
                "description": "Asia-Pacific regions",
                "source_regions": [
                    "ap-southeast-2",
                    "ap-southeast-1",
                    "ap-south-2",
                    "ap-south-1",
                    "ap-northeast-3",
                    "ap-northeast-2",
                    "ap-northeast-1",
                ],
                "destination_regions": [
                    "ap-northeast-1",
                    "ap-northeast-2",
                    "ap-northeast-3",
                    "ap-south-1",
                    "ap-south-2",
                    "ap-southeast-1",
                    "ap-southeast-2",
                    "ap-southeast-4",
                ],
            },
        },
    },
    "haiku-4-5": {
        "name": "Claude Haiku 4.5",
        "base_model_id": "anthropic.claude-haiku-4-5-20251001-v1:0",
        "profiles": {
            "us": {
                "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
                "description": "US regions",
                "source_regions": ["us-east-1", "us-east-2", "us-west-1", "us-west-2", "ca-central-1"],
                "destination_regions": ["us-east-1", "us-east-2", "us-west-2", "ca-central-1"],
            },
            "global": {
                "model_id": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
                "description": "All commercial regions",
                "source_regions": [
                    "af-south-1", "ap-east-2", "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
                    "ap-south-1", "ap-south-2", "ap-southeast-1", "ap-southeast-2", "ap-southeast-3",
                    "ap-southeast-4", "ap-southeast-5", "ap-southeast-7",
                    "ca-central-1", "ca-west-1",
                    "eu-central-1", "eu-central-2", "eu-north-1", "eu-south-1", "eu-south-2",
                    "eu-west-1", "eu-west-2", "eu-west-3",
                    "il-central-1", "me-central-1", "me-south-1", "mx-central-1", "sa-east-1",
                    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
                ],
                "destination_regions": ["all-commercial"],
            },
            "eu": {
                "model_id": "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
                "description": "EU CRIS - European regions",
                "source_regions": ["eu-central-1", "eu-north-1", "eu-south-1", "eu-south-2", "eu-west-1", "eu-west-3"],
                "destination_regions": ["eu-central-1", "eu-north-1", "eu-south-1", "eu-south-2", "eu-west-1", "eu-west-3"],
            },
            "au": {
                "model_id": "au.anthropic.claude-haiku-4-5-20251001-v1:0",
                "description": "AU CRIS - Australia regions",
                "source_regions": ["ap-southeast-2", "ap-southeast-4"],
                "destination_regions": ["ap-southeast-2", "ap-southeast-4"],
            },
            "jp": {
                "model_id": "jp.anthropic.claude-haiku-4-5-20251001-v1:0",
                "description": "JP CRIS - Japan regions",
                "source_regions": ["ap-northeast-1", "ap-northeast-3"],
                "destination_regions": ["ap-northeast-1", "ap-northeast-3"],
            },
        },
    },
    "sonnet-3-7-govcloud": {
        "name": "Claude 3.7 Sonnet (GovCloud)",
        "base_model_id": "anthropic.claude-3-7-sonnet-20250219-v1:0",
        "profiles": {
            "us-gov": {
                "model_id": "us-gov.anthropic.claude-3-7-sonnet-20250219-v1:0",
                "description": "US GovCloud regions",
                "source_regions": ["us-gov-west-1", "us-gov-east-1"],
                "destination_regions": ["us-gov-west-1", "us-gov-east-1"],
            },
        },
    },
}


# Convert raw dict to typed dataclasses for type safety and IDE support.
# The dict interface is preserved via __getitem__ and .get() on the dataclasses.
CLAUDE_MODELS: dict[str, ClaudeModel] = {k: _build_model(v) for k, v in _CLAUDE_MODELS_RAW.items()}


# ---------------------------------------------------------------------------
# Getter helpers
# ---------------------------------------------------------------------------


def get_available_profiles_for_model(model_key: str) -> list[str]:
    """Get list of available cross-region profiles for a given model."""
    if model_key not in CLAUDE_MODELS:
        return []
    return list(CLAUDE_MODELS[model_key]["profiles"].keys())


def get_model_id_for_profile(model_key: str, profile_key: str) -> str:
    """Get the model ID for a specific model and cross-region profile."""
    if model_key not in CLAUDE_MODELS:
        raise ValueError(f"Unknown model: {model_key}")

    model_config = CLAUDE_MODELS[model_key]
    if profile_key not in model_config["profiles"]:
        raise ValueError(f"Model {model_key} not available in profile {profile_key}")

    return model_config["profiles"][profile_key]["model_id"]


def get_default_region_for_profile(profile_key: str) -> str:
    """Get the default AWS region for a cross-region profile."""
    if profile_key not in DEFAULT_REGIONS:
        raise ValueError(f"Unknown profile: {profile_key}")

    return DEFAULT_REGIONS[profile_key]


def get_source_regions_for_model_profile(model_key: str, profile_key: str) -> list[str]:
    """Get source regions for a specific model and profile combination."""
    if model_key not in CLAUDE_MODELS:
        raise ValueError(f"Unknown model: {model_key}")

    model_config = CLAUDE_MODELS[model_key]
    if profile_key not in model_config["profiles"]:
        raise ValueError(f"Model {model_key} not available in profile {profile_key}")

    return model_config["profiles"][profile_key]["source_regions"]


def get_destination_regions_for_model_profile(model_key: str, profile_key: str) -> list[str]:
    """Get destination regions for a specific model and profile combination."""
    if model_key not in CLAUDE_MODELS:
        raise ValueError(f"Unknown model: {model_key}")

    model_config = CLAUDE_MODELS[model_key]
    if profile_key not in model_config["profiles"]:
        raise ValueError(f"Model {model_key} not available in profile {profile_key}")

    return model_config["profiles"][profile_key]["destination_regions"]


def get_all_model_display_names() -> dict[str, str]:
    """Get a mapping of all model IDs to their display names for UI purposes."""
    display_names = {}

    for _model_key, model_config in CLAUDE_MODELS.items():
        for profile_key, profile_config in model_config["profiles"].items():
            model_id = profile_config["model_id"]
            base_name = model_config["name"]

            if profile_key == "us":
                display_names[model_id] = base_name
            else:
                profile_suffix = profile_key.upper()
                display_names[model_id] = f"{base_name} ({profile_suffix})"

    return display_names


def get_profile_description(model_key: str, profile_key: str) -> str:
    """Get the description for a specific model profile combination."""
    if model_key not in CLAUDE_MODELS:
        raise ValueError(f"Unknown model: {model_key}")

    model_config = CLAUDE_MODELS[model_key]
    if profile_key not in model_config["profiles"]:
        raise ValueError(f"Model {model_key} not available in profile {profile_key}")

    return model_config["profiles"][profile_key]["description"]


def get_source_region_for_profile(profile, model_key: str = None, profile_key: str = None) -> str:
    """Get the source region for a profile, with model-specific logic if available."""
    # First priority: Use user-selected source region if available
    selected_source_region = getattr(profile, "selected_source_region", None)
    if selected_source_region:
        return selected_source_region

    # Fallback: Use cross-region profile logic
    cross_region_profile = getattr(profile, "cross_region_profile", "us")
    if cross_region_profile and cross_region_profile != "us":
        try:
            # Use centralized configuration for non-US profiles
            return get_default_region_for_profile(cross_region_profile)
        except ValueError:
            # Fallback if profile not found in centralized config
            return "eu-west-3" if cross_region_profile == "europe" else "ap-northeast-1"
    else:
        # Use infrastructure region for US or default
        return profile.aws_region


# ---------------------------------------------------------------------------
# Region-first helpers (wizard UX simplification — Region + Model ID flow)
# ---------------------------------------------------------------------------


# Tier classification — used to bucket model_ids by their tier (haiku/sonnet/opus).
# Order in the regex matters because "sonnet" must match before "opus" never overlaps,
# but sub-key matching is keyword-based (substring) anyway.
_TIER_KEYWORDS: dict[str, str] = {
    "haiku": "haiku",
    "sonnet": "sonnet",
    "opus": "opus",
}


def _classify_tier(model_key: str) -> str | None:
    """Classify a model_key (e.g. 'sonnet-4-5') into one of haiku/sonnet/opus."""
    lower = model_key.lower()
    for tier, kw in _TIER_KEYWORDS.items():
        if kw in lower:
            return tier
    return None


@dataclass(frozen=True)
class TierModelOption:
    """A single picker option for a tier in a given source region.

    Represents one cross-region inference profile that can be invoked from
    ``source_region``. The wizard renders ``display_name`` to the user and
    persists ``model_id`` (the full CRIS profile id, ready for Bedrock).
    """

    tier: str          # 'haiku' | 'sonnet' | 'opus'
    model_id: str      # e.g. 'us.anthropic.claude-sonnet-4-5-20250929-v1:0'
    display_name: str  # e.g. 'Claude Sonnet 4.5 (US CRIS)'
    profile_key: str   # 'us' | 'eu' | 'global' | ...
    base_model_name: str  # e.g. 'Claude Sonnet 4.5'

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "model_id": self.model_id,
            "display_name": self.display_name,
            "profile_key": self.profile_key,
            "base_model_name": self.base_model_name,
        }


def get_tier_options_for_region(source_region: str) -> dict[str, list[TierModelOption]]:
    """Return tier-bucketed CRIS profile options invocable from ``source_region``.

    Output:
        {
          'haiku':  [TierModelOption, ...],
          'sonnet': [TierModelOption, ...],
          'opus':   [TierModelOption, ...],
        }

    Each list contains every ``(model, profile)`` pair whose ``source_regions``
    includes ``source_region``. The list is sorted by tier first, then by base
    model name (newest models first via descending model_key version sort), then
    by profile_key alphabetically.
    """
    buckets: dict[str, list[TierModelOption]] = {"haiku": [], "sonnet": [], "opus": []}
    if not source_region:
        return buckets

    for model_key, model in CLAUDE_MODELS.items():
        tier = _classify_tier(model_key)
        if tier is None:
            continue
        for profile_key, profile in model.profiles.items():
            if source_region in profile.source_regions:
                # Build display: "Claude Sonnet 4.5 (US CRIS)" — using profile_key
                # uppercased as a quick label. Global is already meaningful as 'GLOBAL'.
                profile_label = profile_key.upper()
                display = f"{model.name} ({profile_label} CRIS)"
                buckets[tier].append(
                    TierModelOption(
                        tier=tier,
                        model_id=profile.model_id,
                        display_name=display,
                        profile_key=profile_key,
                        base_model_name=model.name,
                    )
                )

    # Sort each bucket: newest base model first (by descending model_key), then by
    # profile_key alphabetically. We approximate "newest" by sorting model_key in
    # descending order — works for current naming like '4-8', '4-7', '4-5'.
    def _sort_key(opt: TierModelOption) -> tuple:
        # Find the matching model_key for stable sort.
        for mk, m in CLAUDE_MODELS.items():
            if m.name == opt.base_model_name:
                return (-_version_score(mk), opt.profile_key)
        return (0, opt.profile_key)

    for tier in buckets:
        buckets[tier].sort(key=_sort_key)
    return buckets


def _version_score(model_key: str) -> int:
    """Crude version score from a model_key like 'sonnet-4-5' or 'opus-4-8'.

    Returns score = major*1000 + minor*10. Falls back to 0 on parse failure.
    Used only for "newest first" sort within a tier.
    """
    parts = model_key.split("-")
    nums = [p for p in parts if p.isdigit()]
    if len(nums) >= 2:
        try:
            return int(nums[0]) * 1000 + int(nums[1]) * 10
        except ValueError:
            return 0
    if len(nums) == 1:
        try:
            return int(nums[0]) * 1000
        except ValueError:
            return 0
    return 0


def get_invocable_source_regions() -> list[str]:
    """Return all AWS regions that appear in any model profile's source_regions.

    Useful for the wizard's source-region dropdown when the user has not yet
    locked in a region from the Environment page.
    """
    seen: set[str] = set()
    for model in CLAUDE_MODELS.values():
        for profile in model.profiles.values():
            seen.update(profile.source_regions)
    return sorted(seen)
