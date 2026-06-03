"""Identity Provider strategy registry.

5종 IdP를 strategy 패턴으로 응집. 각 strategy는 IdentityProvider ABC를 구현한다.
Federation은 IAM Direct 단일 경로 (rule-of-thumb §2) — strategy 없음.
"""

from __future__ import annotations

from .base import FormField, IdentityProvider

PROVIDERS: dict[str, type[IdentityProvider]] = {}


def register(cls: type[IdentityProvider]) -> type[IdentityProvider]:
    """Class decorator — register a provider strategy in PROVIDERS."""
    PROVIDERS[cls.provider_type] = cls
    return cls


def provider_strategy(provider_dict: dict) -> IdentityProvider:
    """Dispatch a provider dict to the correct strategy instance."""
    ptype = provider_dict.get("type", "")
    if ptype not in PROVIDERS:
        raise ValueError(
            f"Unknown provider type '{ptype}'. "
            f"Known types: {list(PROVIDERS.keys())}"
        )
    cls = PROVIDERS[ptype]
    return cls.from_dict(provider_dict)


# Import submodules to trigger @register
from . import okta, azure, cognito, auth0, generic  # noqa: E402, F401

__all__ = [
    "PROVIDERS",
    "register",
    "provider_strategy",
    "IdentityProvider",
    "FormField",
]
