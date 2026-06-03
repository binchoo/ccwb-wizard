"""OS keyring helper for secret storage.

Secrets (e.g. Azure client_secret) are stored in the OS keyring, never
in ~/.ccwb/profiles/*.json. The Config file holds only a ``_keyring_ref``
metadata string that identifies the keyring entry.
"""

from __future__ import annotations

SERVICE_NAME = "claude-code-with-bedrock"


def keyring_ref(profile_name: str, secret_name: str) -> str:
    """Generate a _keyring_ref string for a secret."""
    return f"{SERVICE_NAME}:{profile_name}-{secret_name}"


def write_secret(profile_name: str, secret_name: str, value: str) -> str:
    """Write a secret to OS keyring. Returns the _keyring_ref string.

    Raises RuntimeError if keyring is unavailable.
    """
    import keyring as kr

    account = f"{profile_name}-{secret_name}"
    kr.set_password(SERVICE_NAME, account, value)
    return keyring_ref(profile_name, secret_name)


def read_secret(profile_name: str, secret_name: str) -> str | None:
    """Read a secret from OS keyring. Returns None if not found."""
    import keyring as kr

    account = f"{profile_name}-{secret_name}"
    return kr.get_password(SERVICE_NAME, account)


def delete_secret(profile_name: str, secret_name: str) -> None:
    """Delete a secret from OS keyring. No-op if not found."""
    import keyring as kr

    account = f"{profile_name}-{secret_name}"
    try:
        kr.delete_password(SERVICE_NAME, account)
    except kr.errors.PasswordDeleteError:
        pass
