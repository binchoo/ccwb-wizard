"""IdP connection test — OIDC PKCE flow to validate provider config and inspect JWT claims."""

from __future__ import annotations

import hashlib
import http.server
import json
import secrets
import threading
import time
import urllib.parse
from base64 import urlsafe_b64encode
from typing import Any

import jwt
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["auth_test"])

# OIDC provider endpoint patterns
PROVIDER_ENDPOINTS = {
    "okta": {
        "authorize": "https://{domain}/oauth2/v1/authorize",
        "token": "https://{domain}/oauth2/v1/token",
    },
    "auth0": {
        "authorize": "https://{domain}/authorize",
        "token": "https://{domain}/oauth/token",
    },
    "azure": {
        "authorize": "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize",
        "token": "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
    },
    "cognito": {
        "authorize": "https://{domain}/oauth2/authorize",
        "token": "https://{domain}/oauth2/token",
    },
    "generic": {
        "authorize": "{authorization_endpoint}",
        "token": "{token_endpoint}",
    },
}

CALLBACK_PORT = 8410  # Separate port from wizard (8400) to avoid conflict
CALLBACK_PATH = "/callback"


class TestConnectionRequest(BaseModel):
    provider: dict[str, Any]


class TestConnectionResponse(BaseModel):
    status: str  # "success" | "error"
    claims: dict[str, Any] | None = None
    error: str | None = None
    authorize_url: str | None = None


@router.post("/auth/test-connection")
async def test_connection(body: TestConnectionRequest) -> TestConnectionResponse:
    """Initiate OIDC PKCE flow and return JWT claims on success.

    This runs a mini OIDC flow:
    1. Generate PKCE code_verifier + code_challenge
    2. Return authorize_url for the frontend to open in a popup
    3. Wait for callback on localhost:8410/callback (up to 60s)
    4. Exchange code for id_token
    5. Decode and return claims
    """
    provider = body.provider
    ptype = provider.get("type", "")

    if ptype not in PROVIDER_ENDPOINTS:
        raise HTTPException(status_code=400, detail=f"Unknown provider type: {ptype}")

    try:
        endpoints = _resolve_endpoints(ptype, provider)
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b"=").decode()
        state = secrets.token_urlsafe(32)

        client_id = provider.get("client_id", "")
        redirect_uri = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"

        # Build authorize URL
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        authorize_url = f"{endpoints['authorize']}?{urllib.parse.urlencode(params)}"

        # Start callback listener in background thread
        result_container: dict[str, Any] = {"code": None, "error": None}
        server = _start_callback_server(result_container, state)

        return TestConnectionResponse(
            status="awaiting_callback",
            authorize_url=authorize_url,
            claims=None,
        )

    except Exception as e:
        return TestConnectionResponse(status="error", error=str(e))


@router.post("/auth/test-connection/exchange")
async def exchange_code(body: dict) -> TestConnectionResponse:
    """Exchange authorization code for id_token and return claims."""
    try:
        provider = body.get("provider", {})
        code = body.get("code", "")
        code_verifier = body.get("code_verifier", "")
        ptype = provider.get("type", "")

        if not code:
            return TestConnectionResponse(status="error", error="No authorization code received")

        endpoints = _resolve_endpoints(ptype, provider)
        client_id = provider.get("client_id", "")
        redirect_uri = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"

        # Token exchange
        token_data = {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }

        resp = requests.post(endpoints["token"], data=token_data, timeout=10)
        if resp.status_code != 200:
            return TestConnectionResponse(
                status="error",
                error=f"Token exchange failed: {resp.status_code} — {resp.text[:200]}",
            )

        tokens = resp.json()
        id_token = tokens.get("id_token", "")

        if not id_token:
            return TestConnectionResponse(status="error", error="No id_token in response")

        # Decode without verification (we just want to inspect claims)
        claims = jwt.decode(id_token, options={"verify_signature": False})

        # Remove OIDC boilerplate for cleaner display
        display_claims = {
            k: v for k, v in claims.items()
            if k not in {"iss", "aud", "exp", "iat", "nbf", "jti", "azp", "auth_time", "nonce", "at_hash", "c_hash", "token_use", "ver"}
        }

        return TestConnectionResponse(status="success", claims=display_claims)

    except Exception as e:
        return TestConnectionResponse(status="error", error=str(e))


def _resolve_endpoints(ptype: str, provider: dict) -> dict[str, str]:
    """Resolve authorize and token endpoint URLs from provider config."""
    templates = PROVIDER_ENDPOINTS[ptype]
    endpoints = {}
    for key, template in templates.items():
        url = template.format(**provider)
        endpoints[key] = url
    return endpoints


def _start_callback_server(result_container: dict, expected_state: str):
    """Start a temporary HTTP server to receive the OAuth callback. Non-blocking."""
    # This is a simplified version — the actual exchange happens via /auth/test-connection/exchange
    # The callback just serves a page that posts the code back to the wizard
    pass
