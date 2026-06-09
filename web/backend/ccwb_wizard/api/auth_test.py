"""IdP connection test — OIDC PKCE flow to validate provider config and inspect JWT claims.

Flow:
  1. Frontend calls POST /auth/test-connection with provider config + aws_region.
  2. Backend resolves authorize/token endpoints per provider type, generates PKCE,
     starts a single-shot callback server on :8410 (background thread), returns
     authorize_url + code_verifier + state.
  3. Frontend opens authorize_url in a popup. User completes IdP login.
  4. IdP redirects to http://localhost:8410/callback?code=...&state=...
  5. Callback server serves a small HTML page that posts the code via
     window.opener.postMessage() to the wizard window, then closes.
  6. Frontend receives the code via postMessage and calls
     POST /auth/test-connection/exchange with provider + code + code_verifier.
  7. Backend exchanges code for id_token, decodes JWT claims, returns them.
"""

from __future__ import annotations

import hashlib
import http.server
import secrets
import threading
import urllib.parse
from base64 import urlsafe_b64encode
from typing import Any

import jwt
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["auth_test"])

CALLBACK_PORT = 8410  # Separate from wizard (8400~) to avoid conflict
CALLBACK_PATH = "/callback"


class TestConnectionRequest(BaseModel):
    provider: dict[str, Any]
    aws_region: str = ""  # required for cognito (prefix domain composition)


class TestConnectionResponse(BaseModel):
    status: str  # "awaiting_callback" | "success" | "error"
    claims: dict[str, Any] | None = None
    error: str | None = None
    authorize_url: str | None = None
    code_verifier: str | None = None
    state: str | None = None
    redirect_uri: str | None = None


@router.post("/auth/test-connection")
async def test_connection(body: TestConnectionRequest) -> TestConnectionResponse:
    """Initiate OIDC PKCE flow. Returns authorize_url + code_verifier for the
    frontend to complete the popup handshake."""
    provider = body.provider
    ptype = provider.get("type", "")

    try:
        endpoints = _resolve_endpoints(ptype, provider, body.aws_region)
    except KeyError as e:
        return TestConnectionResponse(
            status="error",
            error=f"Provider config missing field: {e!s}. Check that provider type='{ptype}' has all required fields.",
        )
    except ValueError as e:
        return TestConnectionResponse(status="error", error=str(e))

    code_verifier = secrets.token_urlsafe(64)
    code_challenge = (
        urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    state = secrets.token_urlsafe(32)

    client_id = provider.get("client_id", "")
    if not client_id:
        return TestConnectionResponse(status="error", error="provider.client_id is empty")

    redirect_uri = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"

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

    # Start one-shot callback listener (60s timeout, background thread).
    try:
        _start_callback_server()
    except OSError as e:
        return TestConnectionResponse(
            status="error",
            error=f"Cannot bind callback server on port {CALLBACK_PORT}: {e}",
        )

    return TestConnectionResponse(
        status="awaiting_callback",
        authorize_url=authorize_url,
        code_verifier=code_verifier,
        state=state,
        redirect_uri=redirect_uri,
    )


@router.post("/auth/test-connection/exchange")
async def exchange_code(body: dict) -> TestConnectionResponse:
    """Exchange authorization code for id_token and return decoded claims."""
    try:
        provider = body.get("provider", {})
        code = body.get("code", "")
        code_verifier = body.get("code_verifier", "")
        aws_region = body.get("aws_region", "")
        ptype = provider.get("type", "")

        if not code:
            return TestConnectionResponse(status="error", error="No authorization code received")
        if not code_verifier:
            return TestConnectionResponse(status="error", error="No code_verifier — PKCE state lost")

        endpoints = _resolve_endpoints(ptype, provider, aws_region)
        client_id = provider.get("client_id", "")
        redirect_uri = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"

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
                error=f"Token exchange failed: HTTP {resp.status_code} — {resp.text[:300]}",
            )

        tokens = resp.json()
        id_token = tokens.get("id_token", "")

        if not id_token:
            return TestConnectionResponse(
                status="error",
                error=f"No id_token in response. Got keys: {list(tokens.keys())}",
            )

        # Decode without signature verification — UI just inspects claims shape.
        claims = jwt.decode(id_token, options={"verify_signature": False})

        # Strip OIDC boilerplate for cleaner display.
        boilerplate = {
            "iss", "aud", "exp", "iat", "nbf", "jti", "azp",
            "auth_time", "nonce", "at_hash", "c_hash", "token_use", "ver",
        }
        display_claims = {k: v for k, v in claims.items() if k not in boilerplate}

        return TestConnectionResponse(status="success", claims=display_claims)

    except Exception as e:
        return TestConnectionResponse(status="error", error=f"{type(e).__name__}: {e}")


def _resolve_endpoints(ptype: str, provider: dict, aws_region: str) -> dict[str, str]:
    """Build authorize and token endpoint URLs from provider config.

    Each branch maps the strategy's actual field names (per ccwb_domain.providers.*)
    to the IdP-specific endpoint URLs. NO format(**provider) — fields differ per type.
    """
    if ptype == "okta":
        domain = provider.get("domain", "").strip().rstrip("/")
        if not domain:
            raise ValueError("okta: provider.domain is empty (e.g. 'mycompany.okta.com')")
        return {
            "authorize": f"https://{domain}/oauth2/v1/authorize",
            "token": f"https://{domain}/oauth2/v1/token",
        }

    if ptype == "auth0":
        domain = provider.get("domain", "").strip().rstrip("/")
        if not domain:
            raise ValueError("auth0: provider.domain is empty (e.g. 'mycompany.auth0.com')")
        return {
            "authorize": f"https://{domain}/authorize",
            "token": f"https://{domain}/oauth/token",
        }

    if ptype == "azure":
        tenant = provider.get("tenant_id", "").strip()
        if not tenant:
            raise ValueError("azure: provider.tenant_id is empty")
        base = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0"
        return {"authorize": f"{base}/authorize", "token": f"{base}/token"}

    if ptype == "cognito":
        prefix = provider.get("user_pool_domain", "").strip()
        if not prefix:
            raise ValueError("cognito: provider.user_pool_domain is empty")
        # Allow the user to enter a full domain (custom domain) OR just the prefix.
        if prefix.startswith("http://") or prefix.startswith("https://"):
            base = prefix.rstrip("/")
        elif "." in prefix:
            # Looks like a full custom domain (e.g. 'auth.example.com')
            base = f"https://{prefix.rstrip('/')}"
        else:
            # Prefix domain — needs region to compose
            if not aws_region:
                raise ValueError(
                    "cognito: aws_region required to compose prefix domain "
                    f"'{prefix}.auth.<region>.amazoncognito.com'"
                )
            base = f"https://{prefix}.auth.{aws_region}.amazoncognito.com"
        return {
            "authorize": f"{base}/oauth2/authorize",
            "token": f"{base}/oauth2/token",
        }

    if ptype == "generic":
        auth_ep = provider.get("authorization_endpoint", "").strip()
        token_ep = provider.get("token_endpoint", "").strip()
        if not auth_ep or not token_ep:
            raise ValueError(
                "generic: provider.authorization_endpoint and token_endpoint required"
            )
        return {"authorize": auth_ep, "token": token_ep}

    raise ValueError(f"Unknown provider type: '{ptype}'")


# --- Callback server (one-shot, background thread) ---

_callback_server_lock = threading.Lock()
_callback_server: http.server.HTTPServer | None = None


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Receives the OAuth redirect, serves an HTML bridge page that posts
    code/state back to window.opener via postMessage, then closes itself."""

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != CALLBACK_PATH:
            self.send_response(404)
            self.end_headers()
            return

        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [""])[0]
        state = params.get("state", [""])[0]
        error = params.get("error", [""])[0]
        error_description = params.get("error_description", [""])[0]

        # Build bridge HTML — posts to wizard window then closes popup.
        # Wizard runs at http://localhost:8400~8499; using "*" simplifies handshake
        # for local development. The wizard's listener checks event.data.type.
        html = _bridge_html(code=code, state=state, error=error, error_description=error_description)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

        # One-shot: shut down server in a separate thread (can't join from handler).
        threading.Thread(target=_shutdown_callback_server, daemon=True).start()

    def log_message(self, format: str, *args: Any) -> None:  # silence default access log
        return


def _bridge_html(code: str, state: str, error: str, error_description: str) -> str:
    """HTML page that posts the result to window.opener and closes."""
    payload = {
        "type": "oidc-callback",
        "code": code,
        "state": state,
        "error": error,
        "error_description": error_description,
    }
    import json as _json

    payload_js = _json.dumps(payload)
    msg = "IdP 로그인 완료. 위자드 창으로 돌아가세요." if not error else f"IdP 로그인 실패: {error}"
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>IdP Callback</title>
<style>body{{font-family:-apple-system,sans-serif;padding:2rem;text-align:center}}</style>
</head><body>
<h2>{msg}</h2>
<p>이 창은 자동으로 닫힙니다.</p>
<script>
  try {{
    if (window.opener) {{
      window.opener.postMessage({payload_js}, "*");
    }}
  }} catch (e) {{ console.error(e); }}
  setTimeout(function() {{ window.close(); }}, 500);
</script>
</body></html>
"""


def _start_callback_server() -> None:
    """Start the callback HTTP server on CALLBACK_PORT in a background thread.
    Idempotent — reuses an existing server if one is already running."""
    global _callback_server
    with _callback_server_lock:
        if _callback_server is not None:
            return
        server = http.server.HTTPServer(("127.0.0.1", CALLBACK_PORT), _CallbackHandler)
        _callback_server = server
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()


def _shutdown_callback_server() -> None:
    """Shutdown the callback server. Called after the first callback is handled."""
    global _callback_server
    with _callback_server_lock:
        srv = _callback_server
        _callback_server = None
    if srv is not None:
        try:
            srv.shutdown()
            srv.server_close()
        except Exception:
            pass
