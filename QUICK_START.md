# Quick Start Guide

Complete deployment walkthrough for IT administrators deploying **Claude Code with Amazon Bedrock (ccwb)** using the **web wizard** (`uv run ccwb`).

- **Time required:** 2–3 hours for initial deployment
- **Skill level:** AWS administrator with IAM/CloudFormation experience
- **Primary interface:** local web wizard (browser-based). The legacy interactive CLI (`poetry run ccwb init`) has been retired in this fork.

> **The Critical Path** is the minimal, controlled sequence of steps that is guaranteed to succeed. Each numbered step below is part of it. Optional features are clearly marked — skip them on your first run and come back later.

---

## Critical Path at a glance

```
0. Configure your IdP            (Okta / Entra ID / Auth0 / Google / Cognito / generic OIDC)
        │   → you get: provider domain (or issuer) + client ID
        ▼
1. Install prerequisites         (uv, Node.js + yarn, AWS CLI v2, Git)
        ▼
2. Get the code + build          (uv sync --all-packages → make build)
        ▼
3. Authenticate to AWS           (aws sso login / export AWS_PROFILE → verify)
        ▼
4. Launch the wizard             (uv run ccwb → browser opens)
        ▼
5. Walk the wizard               (profile → AWS → IdP → infra → model → logging → review)
        ▼
6. Deploy → Package → Test       (wizard Step 10 runs all three)
        ▼
7. Distribute to end users       (presigned URL or manual zip)
        ▼
8. End-user onboarding           (install → first login → start Claude Code)
```

Steps 0–6 are the controlled, must-succeed path. Steps 7–8 and every "Optional" callout are additive.

---

## Step 0 — Identity Provider configuration (do this first)

This guide covers the **AWS infrastructure** side. It assumes your identity provider (IdP) is already configured. **You must finish IdP setup before launching the wizard** — it asks for your provider domain and client ID and cannot proceed without them.

| Your IdP | Setup guide |
|---|---|
| **Okta** | [Okta Setup Guide](assets/docs/providers/okta-setup.md) |
| **Microsoft Entra ID (Azure AD)** | [Microsoft Entra ID Setup Guide](assets/docs/providers/microsoft-entra-id-setup.md) |
| **Auth0** | [Auth0 Setup Guide](assets/docs/providers/auth0-setup.md) |
| **Google (Sign in with Google)** | [Google Setup Guide](assets/docs/providers/google-setup.md) |
| **AWS Cognito User Pool** | [Cognito User Pool Setup Guide](assets/docs/providers/cognito-user-pool-setup.md) |
| **PingFederate, Keycloak, ForgeRock, or other generic OIDC** | [Generic OIDC Setup Guide](assets/docs/providers/generic-oidc-setup.md) |

Each guide walks through creating the application, setting the redirect URI to `http://localhost:8400/callback`, enabling PKCE, and noting the two values you need here: your **provider domain** (or issuer URL) and **client ID**.

> **Google is a dedicated path, not generic OIDC.** Google's "Desktop app" OAuth client returns a `client_secret` that must accompany PKCE on the token exchange. You create a **Desktop app** client, enter only the **Client ID** in the wizard, and each end user injects the secret into their OS keyring once after install (covered in [Step 8](#step-8--end-user-onboarding-post-distribution)). The secret never ships in the package.

---

## Step 1 — Prerequisites installation

### Operator (deployment) machine

| Tool | Why | Install |
|---|---|---|
| **Python 3.10–3.12** | runtime for the wizard backend | python.org or your package manager |
| **[uv](https://docs.astral.sh/uv/)** | Python package/workspace manager | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Node.js ≥ 18 + yarn** | builds the wizard frontend | `npm install -g yarn` |
| **AWS CLI v2** | AWS authentication + validation | [AWS docs](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| **Git** | clone the repository | your package manager |

### AWS requirements

- AWS account with IAM permissions to create:
  - CloudFormation stacks
  - IAM OIDC Providers (or Cognito Identity Pools), roles, and policies
  - Bedrock model-invocation logging + CloudWatch resources
  - (Optional) S3, Lambda, SNS, DynamoDB for quota/distribution
  - (Optional) AWS CodeBuild for Windows builds
- Amazon Bedrock model access enabled in your target region(s)

### Supported AWS regions

Deploy in any region that supports IAM OIDC Providers (or Cognito Identity Pools), Amazon Bedrock model-invocation logging, and CloudWatch. Optional features (quota, distribution, CodeBuild) require their respective services in that region.

### Cross-region inference

Claude Code uses Bedrock cross-region inference. In the wizard you select a Claude model, a cross-region profile (US / EU / APAC / Global), and a source region. Modern Claude models (3.7+) **require** cross-region inference.

---

## Step 2 — Source checkout and build

```bash
# Clone the repository
git clone <repository-url>
cd ccwb

# Install all Python workspace deps (domain + backend)
uv sync --all-packages

# Build the frontend into the backend's static folder
make build
```

`make build` runs `yarn install && yarn build` in `web/frontend`, then copies the built assets into `web/backend/ccwb_wizard/static`. When it finishes you will see:

```
Build complete. Run 'uv run ccwb' to start.
```

> **Optional — developer hot-reload mode:** instead of `make build`, run `make dev` to start the Vite dev server and uvicorn with reload (frontend on `:5173`, backend on `:8400`). Use this only when modifying the wizard itself, not for production deployment.

---

## Step 3 — AWS authentication

The wizard calls AWS APIs (using your **administrator** credentials — not developer credentials) to validate your account and deploy stacks. Make sure your terminal has a valid AWS session before launching.

boto3 (used internally) resolves credentials in this order — **the first source that returns a non-expired credential wins**:

| Priority | Source | How to set it |
|---|---|---|
| **1 — highest** | Environment variables | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` (+ optional `AWS_SESSION_TOKEN`) |
| **2** | `~/.aws/credentials` | `[default]` or named profile via `AWS_PROFILE` |
| **3** | `~/.aws/config` | SSO profiles, `credential_process`, assumed-role profiles |
| **4** | IAM instance profile | Automatic on EC2 |
| **5 — lowest** | ECS container role | Automatic on ECS tasks |

**Recommended (controlled path):**

```bash
# If your org uses IAM Identity Center (SSO)
aws sso login --profile <your-admin-profile>
export AWS_PROFILE=<your-admin-profile>

# Verify BEFORE launching the wizard
aws sts get-caller-identity
```

> **Most common failure:** stale environment variables. If `AWS_ACCESS_KEY_ID` is exported but expired, boto3 stops at priority 1 and never falls back to your credential file. See [Troubleshooting](#troubleshooting) if the wizard reports a credentials error even though `aws sts get-caller-identity` works.

---

## Step 4 — Wizard launch

```bash
uv run ccwb
```

This builds (if needed), starts the FastAPI backend bound to **localhost only** (`127.0.0.1:8400`), and opens your browser to the wizard. The backend is not reachable from other machines.

Nothing is deployed to AWS until you reach Step 10 inside the wizard. Everything before that only writes a local profile to `~/.ccwb/profiles/<name>.json`.

---

## Step 5 — Wizard walkthrough (11 pages)

The wizard is the operator interface. Each page fills part of one `Config` object saved to `~/.ccwb/profiles/<name>.json`.

| Page | Name | What you provide | On the Critical Path? |
|---|---|---|---|
| 0 | **Profile** | new/edit/clone + profile name (`[a-z0-9-]`) | Required |
| 1 | **AWS environment** | deployment named-profile + region | Required |
| 2 | **Identity Provider** | OIDC IdP + **connection test (claims preview)** + **attribution mapping** | Required |
| 3 | **Infrastructure name** | CFN stack base name (prefix) | Required |
| 4 | **Bedrock model** | model tier + cross-region profile + source region | Required |
| 5 | **Logging & quota** | Bedrock invocation logging destination + retention; quota (optional) | Logging required; quota optional |
| 6 | **Distribution** | presigned S3 / landing page | Optional |
| 7 | **Additional features** | Windows builds, CoWork 3P | Optional |
| 8 | **Resource tags** | tags applied to all CFN stacks | Optional |
| 9 | **Review & save** | review config + materialize preview + save profile | Required |
| 10 | **Deploy & test** | Deploy → Package → Test → Distribute | Required (deploy/package/test) |

### Page 2 — Identity Provider and attribution

Enter your **provider domain** (or issuer URL) and **client ID** from Step 0. The wizard auto-detects Okta, Entra ID, Auth0, and Cognito from the domain; select **Google** or **generic OIDC** manually when prompted.

- **Connection test:** the wizard performs a login and shows the **claims preview** so you can confirm which IdP claims (e.g. `email`, `cognito:groups`, `custom:dept`) are available before mapping.
- **Attribution mapping:** map IdP claims to dashboard dimensions (`user` / `team` / `dept`). This mapping is applied **dynamically at every authentication** by the credential helper — org changes flow through on the next login without re-packaging. See [ANTHROPIC_CUSTOM_HEADERS_GUIDE.md](assets/docs/ANTHROPIC_CUSTOM_HEADERS_GUIDE.md) for the header contract.
- **Google note:** for the Google path you enter only the **Client ID** here. The `client_secret` is handled per end-user machine in [Step 8](#step-8--end-user-onboarding-post-distribution), not in the wizard.

### Page 4 — Bedrock model

Pick the default model developers use (the wizard pins the tier-specific `ANTHROPIC_DEFAULT_SONNET_MODEL` / `ANTHROPIC_DEFAULT_HAIKU_MODEL` / `ANTHROPIC_DEFAULT_OPUS_MODEL` env keys in `settings.json`), a cross-region inference profile (US / EU / APAC / Global), and a source region. Claude 3.7+ requires a cross-region profile.

### Page 5 — Bedrock logging (required) and quota (optional)

Usage attribution is read directly from **Amazon Bedrock model-invocation logs** — there is no OTEL collector, ECS, or ALB in this fork.

- **Logging destination:** CloudWatch Logs (default — needed for metric filters + quota), S3 (for Athena historical SQL), or both. A "neither" choice is blocked because it breaks attribution.
- **Retention:** 1–3653 days (default 90).
- **Quota (optional):** per-user monthly/daily token limits with SNS alerts and optional block-on-exceed.

### Page 9 — Review & save

The Review page renders the materialized `DeploymentArtifacts` — the exact CFN stacks, parameters, `settings.json` template, and `~/.aws/config` body that will be produced. Saving writes the profile locally. **Still nothing deployed.**

---

## Step 6 — Deployment, packaging, and test (wizard Page 10)

Page 10 runs the controlled deployment sequence with live progress (SSE). Run the actions in order:

### 1. Deploy

Deploys CloudFormation stacks in dependency order, recognizing existing stacks and skipping duplicate OIDC/logging setup. Stack outputs are synced back into your profile.

| Stack | Purpose | When |
|---|---|---|
| `{base}-s3` | S3 bucket for CFN/Lambda packaging artifacts | Always |
| `{base}-auth` | IAM OIDC provider (or Cognito Identity Pool) + Bedrock-scoped federated role (12h session) | Always |
| `{base}-bedrock-logging` | Enables Bedrock model-invocation logging + metric filters | Always |
| `{base}-dashboard` | CloudWatch Logs Insights dashboard keyed on `user`/`team`/`dept` | Always |
| `{base}-quota` | Per-user limits, SNS alerts, optional block | If quota enabled |
| `{base}-distribution` | Presigned-URL or landing-page distribution | If distribution enabled |
| `{base}-codebuild` | Windows `.exe` build via CodeBuild | If Windows builds enabled |

Deployment takes 5–15 minutes depending on enabled stacks.

### 2. Package

Builds the `credential-process` binary (PyInstaller) plus `config.json`, `install.sh` / `install.bat`, and a `settings.json` template, bundled into a zip in `dist/`.

**macOS architecture — check before building:**

```bash
uname -m
```

| Output | Your Mac | Build target |
|---|---|---|
| `arm64` | Apple Silicon | `macos-arm64` — Apple Silicon only |
| `x86_64` | Intel | `macos-intel` — runs on all Macs (native on Intel, Rosetta on Apple Silicon) |

> Intel binaries cover your entire Mac fleet via Rosetta; ARM64 binaries only run on Apple Silicon. Ask your developers to run `uname -m` and build for what they report.

> **Optional — Windows builds:** require CodeBuild enabled on Page 7. Windows builds run in the cloud (~20 min) so you do not need a Windows machine. If not enabled, Windows is skipped and other platforms continue.

### 3. Test

The wizard simulates the end-user install: OIDC authentication → AWS credential retrieval → Bedrock access check. This is the final gate of the Critical Path — once it passes, the deployment is verified.

---

## Step 7 — Distribution to end users (optional infrastructure)

How you deliver the package depends on what you chose on Page 6.

### Option 1 — Manual sharing (no infrastructure)

```bash
cd dist
zip -r claude-code-packages.zip .
# Share via email / internal file share. Users run install.sh (Unix) or install.bat (Windows).
```

Best for any team size with no automation needs.

### Option 2 — Presigned S3 URLs

The wizard's **Distribute** action uploads to S3 and returns a time-limited URL (48h default) you share via Slack/email. Requires "Presigned S3" selected on Page 6.

### Option 3 — Authenticated landing page

A self-service portal where users log in with SSO and download the right binary for their OS. Requires "Landing Page" selected on Page 6 (with custom domain + IdP details). Best for large orgs needing audit trails.

See [Distribution Comparison](assets/docs/distribution/comparison.md) for details.

End users run `install.sh` / `install.bat`, then authenticate once via `credential-process --profile <name>`. They need only Claude Code and a browser — no AWS account, Python, or Git. The full onboarding sequence is in [Step 8](#step-8--end-user-onboarding-post-distribution).

---

## Step 8 — End-user onboarding (post-distribution)

Deployment and distribution put the package in your developers' hands, but **each developer must complete a short one-time setup on their own machine** before Claude Code reaches Bedrock. Hand them the steps below — they require no AWS knowledge.

### Overview — what the end user does

```
1. Extract the package        (the zip you distributed in Step 7)
2. Run the installer          (install.sh on macOS/Linux, install.bat on Windows)
3. (Google IdP only) Set the client secret into the OS keyring   ← one time
4. First login                (credential-process --profile <name> → browser opens)
5. Start Claude Code          (it routes to Bedrock automatically)
```

The installer does the plumbing — it places the `credential-process` binary, writes the `[profile <name>]` entry into `~/.aws/config`, and installs the `~/.claude/settings.json` template. It does **not** install Claude Code itself; that must already be present.

### Step 8.1 — Installer execution

After extracting the package, the user runs the installer for their platform:

```bash
# macOS / Linux
./install.sh

# Windows (PowerShell or cmd, from the extracted folder)
install.bat
```

If `aws` or `claude` is missing from `PATH`, the installer prints an advisory so the user can install the prerequisite before continuing.

### Step 8.2 — Client secret injection (Google IdP only)

This step applies **only when you deployed the Google path**. Every other IdP uses PKCE alone and skips it.

Because the Google client secret never ships in the package, each user injects it into their OS secure store once:

```bash
# Interactive — prompts for the secret; the value is not echoed or stored in shell history
credential-process --set-client-secret --profile <name>
```

For MDM or scripted rollout, supply the secret through an environment variable instead of a command argument so it stays out of process listings and shell history:

```bash
CCWB_CLIENT_SECRET="GOCSPX-..." credential-process --set-client-secret --profile <name>
```

The helper stores the secret only in a recognized OS secure store (macOS Keychain, Windows Credential Manager, freedesktop Secret Service, or KWallet) and refuses to run on an insecure backend. To remove a stored secret later, run `--set-client-secret` and submit an empty value.

> **Why this is safe:** Google treats Desktop-app client secrets as non-confidential — PKCE is the real defense against code interception, so a leaked secret is unusable without the per-session verifier. See the [Google Setup Guide](assets/docs/providers/google-setup.md#6-threat-model) for the full threat model.

### Step 8.3 — First login

The user triggers the initial authentication, which opens a browser for the corporate login:

```bash
credential-process --profile <name>
```

After a successful login the helper caches temporary AWS credentials, writes the attribution "magic header" into `~/.claude/settings.json`, and prints the resolved `user` / `team` / `dept` values. AWS credentials are never printed to the terminal.

### Step 8.4 — Claude Code startup

From here the user simply runs Claude Code as usual — the `~/.claude/settings.json` env block routes every request through Bedrock (`CLAUDE_CODE_USE_BEDROCK=1`) using the cached credentials. No model configuration is required; the wizard already pinned the Sonnet/Haiku/Opus model IDs.

### When the user's team or department changes

Attribution claims are captured at login and cached, so an org change in your IdP is **not** reflected until the user re-authenticates. After you update their group/department in the IdP, ask the user to run:

```bash
credential-process --profile <name> --refresh-identity
```

This clears the cached credentials and ID token, opens a fresh login, rewrites the magic header, and prints the new attribution. The user then restarts Claude Code, and subsequent usage is billed to the new team/department. For the complete member-lifecycle playbook (onboarding, team change, offboarding), see the [User Lifecycle Runbook](web/binaries/credential_provider/USER_LIFECYCLE_RUNBOOK.md).

---

## Cleanup

You are responsible for AWS costs while this guidance runs. To remove infrastructure, delete the CloudFormation stacks created by the deployment (in reverse dependency order) via the AWS Console or CLI. Deleting stacks is irreversible — confirm you no longer need the dashboards or logged data first.

---

## Troubleshooting

### Wizard reports an AWS credentials error even though `aws sts get-caller-identity` works

Almost always caused by **expired AWS environment variables** overriding your credential file. boto3 stops at the first source that returns values (even expired ones) and will not fall back.

```bash
# 1. Check what is set
env | grep AWS_

# 2. Unset stale values
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

# 3. Verify boto3 resolves correctly
python3 -c "import boto3; print(boto3.client('sts').get_caller_identity())"

# 4. Re-launch
uv run ccwb
```

If you use SSO, ensure the session is active first:

```bash
aws sso login --profile <your-profile>
export AWS_PROFILE=<your-profile>
uv run ccwb
```

### Browser does not open / cannot reach the wizard

The backend binds to `127.0.0.1:8400` only. Open `http://localhost:8400` manually. If port 8400 is occupied (e.g. by Vault or Commvault), stop the conflicting process — the same port is used for the OAuth callback registered in your IdP (`http://localhost:8400/callback`).

### `make build` fails on the frontend step

Confirm Node.js ≥ 18 and yarn are installed (`node -v`, `yarn -v`). Re-run `cd web/frontend && yarn install` then `make build`. To rule out a stale build, run `make clean` first.

### End-user credential refresh

Force re-authentication after deployment:

```bash
~/claude-code-with-bedrock/credential-process --clear-cache
```

To reflect an org change (team/dept) — because cached/refreshed sessions reuse the previous token's claims:

```bash
~/claude-code-with-bedrock/credential-process --profile <name> --refresh-identity
```

This clears cached credentials + ID token, opens a fresh login, rewrites the magic header in `~/.claude/settings.json`, and prints the new `user/team/dept` attribution. Restart Claude Code afterward.

### CoWork Desktop 3P fails with `403 The security token included in the request is invalid`

If the user was previously on a session-files build, `~/.aws/credentials` may contain a stale `[<profile-name>]` stanza with literal `EXPIRED` values shadowing the `credential_process` entry in `~/.aws/config`. Re-run `install.sh` / `install.bat` — it purges that stanza before writing the new profile. Keyring mode avoids this entirely and is recommended for CoWork.

### `Exec format error` on the credential-process binary (end user)

A CPU architecture mismatch — the binary was built for a different architecture than the user's machine (`chmod +x` will not fix it).

```bash
uname -m                                              # their CPU arch
file ~/claude-code-with-bedrock/credential-process    # binary's arch
```

| `uname -m` | Binary arch | Cause |
|---|---|---|
| `x86_64` (Intel) | `arm64` | Intel binary not built — only ARM64 packaged |
| `arm64` (Apple Silicon) | `x86_64` | Wrong binary copied |

Fix: rebuild with the correct macOS target on Page 10 (install a universal2 Python from python.org to produce the Intel binary from Apple Silicon), then redistribute. The installer auto-detects architecture.

---

## Next steps

- [Architecture Deep Dive](assets/docs/ARCHITECTURE.md) — technical architecture
- [Monitoring](assets/docs/MONITORING.md) — Bedrock-native usage monitoring
- [Analytics](assets/docs/ANALYTICS.md) — S3 data lake + Athena queries
- [Quota Monitoring](assets/docs/QUOTA_MONITORING.md) — per-user token limits
- [CLI Reference](assets/docs/CLI_REFERENCE.md) — command reference
- [Web Wizard internals](web/README.md) — wizard architecture + dev setup
