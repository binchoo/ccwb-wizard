"""Secret API — write secrets to OS keyring."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["secret"])


class KeyringWriteRequest(BaseModel):
    profile_name: str
    secret_name: str
    value: str


@router.post("/secret/keyring")
async def write_to_keyring(body: KeyringWriteRequest) -> dict:
    """Write a secret to the OS keyring. Returns the _keyring_ref string."""
    try:
        from ccwb_domain.secrets import write_secret
        ref = write_secret(body.profile_name, body.secret_name, body.value)
        return {"status": "stored", "_keyring_ref": ref}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Keyring write failed: {e}. Ensure OS keyring is available (macOS Keychain / Windows Credential Manager / Linux Secret Service).",
        )
