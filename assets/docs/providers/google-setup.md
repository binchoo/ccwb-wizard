# Google Setup Guide (Sign in with Google)

This guide covers using **Google** as the OIDC identity provider for Amazon Bedrock
access. Google is a dedicated path (not the Generic OIDC path) because Google's
"Desktop app" OAuth client requires a `client_secret` on the token exchange **in
addition to** PKCE, and its authorize/token endpoints live on different hosts.

> **Why a dedicated path?** Generic OIDC is public-client + PKCE only (no secret).
> Google's installed/desktop client always returns a secret that must be sent at token
> exchange. We keep that secret out of the distributed package and inject it per-machine
> into the OS keyring. See [Threat model](#threat-model) for why this is safe.

## Table of Contents

1. [How it works](#1-how-it-works)
2. [Create the Google OAuth client](#2-create-the-google-oauth-client)
3. [Run the wizard](#3-run-the-wizard)
4. [Deploy](#4-deploy)
5. [Install the client secret on each machine](#5-install-the-client-secret-on-each-machine)
6. [Threat model](#6-threat-model)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. How it works

| Property | Value |
|---|---|
| Issuer (`iss`) | `https://accounts.google.com` |
| Authorization endpoint | `https://accounts.google.com/o/oauth2/v2/auth` |
| Token endpoint | `https://oauth2.googleapis.com/token` |
| Scopes | `openid email profile` |
| Client type | **Desktop app** (PKCE + client secret) |

The credential helper performs Authorization Code + PKCE in the browser, then exchanges
the code at Google's token endpoint **with both the PKCE verifier and the client
secret**. The secret is read from the OS keyring at runtime — it is never stored in
`config.json`, `settings.json`, or the profile.

## 2. Create the Google OAuth client

1. Open **Google Cloud Console → APIs & Services → Credentials**.
2. **Create Credentials → OAuth client ID**.
3. **Application type: Desktop app**. Give it a name (e.g. `claude-code-cli`).
4. Create. Copy the **Client ID** (`xxxx.apps.googleusercontent.com`) and the
   **Client secret** (`GOCSPX-...`).
5. On the **OAuth consent screen**, ensure the `openid`, `email`, and `profile` scopes
   are available and the app is published to your users (Internal for Workspace orgs).

Desktop app clients allow loopback redirect URIs automatically, so the helper's
`http://localhost:8400/callback` works without extra allowlisting.

## 3. Run the wizard

In the **Identity Provider** step, choose **Google** and enter the **Client ID** only.
The wizard does **not** ask for the client secret — by design (see step 5). Complete the
attribution mapping and the remaining steps as usual.

## 4. Deploy

Deploy applies `deployment/infrastructure/bedrock-auth-google.yaml`, which provisions the
IAM OIDC Provider for `https://accounts.google.com` (no thumbprint needed — Google chains
to a trusted CA), the federated role, and the Bedrock access policy.

## 5. Install the client secret on each machine

The secret is injected per-machine into the OS keyring, never shipped in the package.
After running `install.sh` / `install.bat`, each user runs once:

```bash
# Interactive (prompts; not echoed, not in shell history)
credential-process --set-client-secret --profile ClaudeCode
```

For MDM / scripted rollout, pass it via env var instead of an argument (avoids shell
history and process listings):

```bash
CCWB_CLIENT_SECRET="GOCSPX-..." credential-process --set-client-secret --profile ClaudeCode
```

To clear a stored secret, run `--set-client-secret` and submit an empty value.

The helper refuses to store or read the secret unless the active keyring is a recognized
**OS secure store** (macOS Keychain, Windows Credential Manager, freedesktop Secret
Service, or KWallet). On a headless/insecure backend it fails with guidance rather than
falling back to a plaintext file.

## 6. Threat model

- **The Google Desktop-app `client_secret` is not a confidential credential.** Google
  explicitly treats installed/desktop client secrets as non-secret; the real protection
  against code interception is **PKCE**. A leaked secret cannot be used to obtain tokens
  without the per-session PKCE `code_verifier`.
- **Storage**: secret lives only in the OS keyring, never in `config.json` /
  `settings.json` / profile JSON, and is never printed (even in debug).
- **Secure-backend enforcement**: the helper hard-fails on insecure keyring backends so
  the secret cannot land in a plaintext fallback store.
- **Residual risk**: any process running as the **same OS user** can read the secret via
  the keyring API — this is an inherent keyring limitation, not specific to this tool.
  Given the secret is non-confidential and PKCE is the actual defense, this residual risk
  is acceptable and not over-engineered against.

## 7. Troubleshooting

### `Insecure keyring backend ...` error

The active keyring is not an OS secure store (common on headless Linux/CI). Install and
enable a Secret Service provider (e.g. `gnome-keyring`) or run on a desktop session.

### `Token is not from a supported provider` from STS

The IAM OIDC Provider's URL must be exactly `https://accounts.google.com` and the client
ID must be listed. Re-deploy the auth stack if the client ID changed.

### Token exchange fails with `invalid_client`

The client secret in the keyring is missing or wrong. Re-run
`credential-process --set-client-secret --profile <name>` with the correct secret.

### `redirect_uri_mismatch`

Use a **Desktop app** OAuth client (loopback redirects are auto-allowed). Web application
clients reject `http://localhost` unless explicitly configured.

---

## Next Steps

```bash
credential-process --set-client-secret --profile ClaudeCode   # one-time per machine
credential-process --profile ClaudeCode                        # first auth (browser)
```

Then start Claude Code — it uses Bedrock automatically.
