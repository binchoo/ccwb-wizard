"""Build ANTHROPIC_CUSTOM_HEADERS value from a JWT id_token.

Owner: credential-process (`--get-bedrock-metadata-headers` mode).

The output goes into ``~/.claude/settings.json`` ``env`` block at install time. Claude Code
attaches it to every Bedrock InvokeModel call as the magic header
``X-Amzn-Bedrock-Request-Metadata``. Bedrock's model invocation logging then surfaces the
JSON payload as ``$.requestMetadata.*`` fields.

Design choice — passthrough with dashboard aliases:

We do NOT introduce a per-deployment ``metadata_claim_map`` between JWT claims and the
emitted header. Instead, every JWT claim that is not OIDC boilerplate is forwarded as-is
under its original IdP-published name. On top of that, three fixed alias keys
(``user``/``team``/``dept``) are populated from the most common IdP claim sources so the
shipped CFN metric filters and CloudWatch dashboard work without per-deployment tuning.

The aliases are additive — if the IdP already publishes the alias key directly, that
value wins and no override happens. Consumers can ignore the aliases and query the raw
claim names instead.

AWS-enforced limits this module guards against:

- ≤ 16 keys in the metadata object
- ≤ 256 chars per key, ≤ 256 chars per value
- printable ASCII only (Bedrock client rejects non-ASCII at request time)

Non-ASCII values (e.g. Korean nicknames from Kakao) are auto-encoded as ``b64:<base64>``.
Decoders in dashboards / Athena queries are responsible for the inverse transform.
"""
from __future__ import annotations

import base64
import json
import re

# Bedrock-defined limits
_MAX_KEYS = 16
_MAX_LEN = 256

# Printable ASCII (space through tilde). Bedrock rejects everything else.
_ASCII_RE = re.compile(r"^[\x20-\x7E]*$")

# The exact header name Bedrock recognizes and surfaces in invocation logs.
_HEADER_NAME = "X-Amzn-Bedrock-Request-Metadata"

# OIDC / OAuth2 boilerplate we drop unconditionally — these have no attribution value
# and would just burn slots against the 16-key cap. Includes Cognito-specific noise.
_BOILERPLATE_CLAIMS = frozenset(
    {
        "iss",
        "aud",
        "exp",
        "iat",
        "nbf",
        "jti",
        "azp",
        "auth_time",
        "nonce",
        "at_hash",
        "c_hash",
        "token_use",  # Cognito
        "event_id",  # Cognito
        "origin_jti",  # Cognito
        "ver",
    }
)


def build_metadata_from_jwt(claims: dict, attribution: dict | None = None) -> dict:
    """Convert a JWT claims dict into Bedrock requestMetadata.

    If ``attribution`` config is provided (from Config schema 3.0), operates in
    **mapping mode**:
      - ``attribution.mapping`` maps dashboard dimension keys (user/team/dept) to
        specific IdP claim names. Only mapped dimensions are emitted under the
        dashboard-standard keys.
      - ``attribution.passthrough`` lists additional claim keys to forward under
        their original names.

    If ``attribution`` is None or empty, falls back to **legacy passthrough mode**
    (blacklist + auto-aliases) for backward compatibility with pre-3.0 configs.

    In both modes, ``sanitize_for_bedrock`` enforces AWS limits (16 keys, 256 chars,
    ASCII only).
    """
    mapping = (attribution or {}).get("mapping", {})
    passthrough = (attribution or {}).get("passthrough", [])
    has_config = bool(mapping and any(mapping.values())) or bool(passthrough)

    if has_config:
        # --- Mapping mode (Config 3.0) ---
        out: dict = {}

        # 1. Apply dimension mapping: dashboard key ← IdP claim value
        for dimension_key, claim_name in mapping.items():
            if not claim_name:
                continue
            value = claims.get(claim_name)
            if value is None or value == "" or value == []:
                continue
            out[dimension_key] = _flatten_value(claim_name, value)

        # 2. Apply passthrough: forward under original claim names
        for claim_key in passthrough:
            if claim_key in out:
                continue  # dimension mapping takes precedence
            value = claims.get(claim_key)
            if value is None or value == "" or value == []:
                continue
            out[claim_key] = _flatten_value(claim_key, value)

        return sanitize_for_bedrock(out)
    else:
        # --- Legacy blacklist-passthrough mode (pre-3.0 compat) ---
        out = {}
        for key, value in claims.items():
            if key in _BOILERPLATE_CLAIMS:
                continue
            flat = _flatten_value(key, value)
            if flat in (None, "", []):
                continue
            out[key] = flat
        _apply_dashboard_aliases(out, claims)
        return sanitize_for_bedrock(out)


def _flatten_value(key: str, value) -> str | None:
    """Flatten complex claim values into Bedrock-safe strings.

    - list of primitives → comma-joined (e.g. cognito:groups)
    - list of dicts → extract key identifying fields from first element
      (e.g. identities[0].userId, identities[0].providerName)
    - dict → compact JSON (truncated by sanitize_for_bedrock if needed)
    """
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        first = value[0]
        if isinstance(first, dict):
            useful_keys = ("userId", "providerName", "providerType")
            parts = [f"{k}={first[k]}" for k in useful_keys if k in first and first[k]]
            return ",".join(parts) if parts else json.dumps(first, separators=(",", ":"))
        return ",".join(str(item) for item in value if item not in (None, ""))
    if isinstance(value, dict):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=True)
    return value


# Dashboard-compat aliases: keys the CFN metric filters in bedrock-logging.yaml
# read from. Each entry maps an alias key to an ordered list of source claim
# names; the first non-empty source wins. We do NOT overwrite an alias if the
# IdP already publishes that key directly.
_DASHBOARD_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("user", ("email", "cognito:username", "preferred_username", "upn", "sub")),
    ("team", ("custom:team", "cognito:groups", "groups")),
    ("dept", ("custom:department", "custom:dept", "department")),
)


def _apply_dashboard_aliases(out: dict, claims: dict) -> None:
    """Populate user/team/dept aliases from the most likely IdP claim names.

    Mutates ``out`` in place. Already-set keys are preserved; this is purely
    additive. List-valued sources (e.g. ``cognito:groups``) are reduced to
    their first element so the alias remains a single string.
    """
    for alias_key, sources in _DASHBOARD_ALIASES:
        if alias_key in out:
            continue
        for source in sources:
            value = claims.get(source)
            if isinstance(value, (list, tuple)):
                value = next((str(v) for v in value if v not in (None, "")), None)
            if value not in (None, ""):
                out[alias_key] = value
                break


def sanitize_for_bedrock(raw: dict) -> dict:
    """Apply AWS Bedrock requestMetadata limits to a raw {key: value} dict.

    Rules (in order):

    1. Keep only the first ``_MAX_KEYS`` (16) keys, preserving input order. Anything
       beyond that is silently dropped — keep claim sets small by design.
    2. Drop entries with ``None`` or empty-string values.
    3. Coerce values to str.
    4. If a value contains non-ASCII bytes, base64-encode it and prefix ``b64:`` so
       downstream consumers can detect the encoding. (Korean names, kanji, etc.)
    5. Truncate values to ``_MAX_LEN`` (256) chars. After base64 the value is ASCII so
       a simple slice is byte-safe.
    6. Drop keys that themselves are non-ASCII. Schema keys are conventionally ASCII
       English identifiers, so this should not trigger in practice.
    """
    out: dict = {}
    for key, value in list(raw.items())[:_MAX_KEYS]:
        if value is None or value == "":
            continue
        v = str(value)
        if not _ASCII_RE.match(v):
            v = "b64:" + base64.b64encode(v.encode("utf-8")).decode("ascii")
        if len(v) > _MAX_LEN:
            v = v[:_MAX_LEN]
        if not _ASCII_RE.match(key):
            continue
        if len(key) > _MAX_LEN:
            key = key[:_MAX_LEN]
        out[key] = v
    return out


def build_header_line(metadata: dict) -> str:
    """Serialize a sanitized metadata dict to the single header line value.

    Output format matches the contract documented in ANTHROPIC_CUSTOM_HEADERS_GUIDE.md:

        X-Amzn-Bedrock-Request-Metadata: {"key1":"v1","key2":"v2"}

    The JSON uses compact separators (no whitespace) so multiple metadata sets in the
    same env var stay distinguishable when split on newlines by the Anthropic SDK.
    """
    payload = json.dumps(metadata, separators=(",", ":"), ensure_ascii=True)
    return f"{_HEADER_NAME}: {payload}"
