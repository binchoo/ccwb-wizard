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


def build_metadata_from_jwt(claims: dict) -> dict:
    """Convert a JWT claims dict into Bedrock requestMetadata, passthrough-style.

    Strategy:
      - Drop OIDC boilerplate claims (``iss``, ``exp``, ``nonce``, ...).
      - Drop empty values (``None``, empty string, empty list).
      - Coerce list values to a comma-joined string (e.g. ``cognito:groups``).
      - Add three dashboard-compat aliases (``user``/``team``/``dept``) populated
        from the most likely IdP claims if those keys are not already present.
        Without these aliases the CFN metric filters in bedrock-logging.yaml
        would not match anything for IdPs that publish ``email`` instead of
        ``user`` etc.
      - Hand off to ``sanitize_for_bedrock`` for AWS limit enforcement.

    Whatever remains gets serialized into the magic header verbatim. CW Logs Insights
    can address the resulting fields by their original IdP-published names, e.g.
    ``requestMetadata.email`` or ``requestMetadata.\"custom:team\"`` — and dashboards
    written against ``requestMetadata.user`` / ``requestMetadata.team`` / ``requestMetadata.dept``
    keep working through the aliases.
    """
    out: dict = {}
    for key, value in claims.items():
        if key in _BOILERPLATE_CLAIMS:
            continue
        if isinstance(value, (list, tuple)):
            value = ",".join(str(item) for item in value if item not in (None, ""))
        if value in (None, "", []):
            continue
        out[key] = value
    _apply_dashboard_aliases(out, claims)
    return sanitize_for_bedrock(out)


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
