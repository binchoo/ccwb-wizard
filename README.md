# Claude Code with Amazon Bedrock (ccwb)

Enterprise deployment tooling for running **Claude Code** (and Claude Cowork / Desktop)
on **Amazon Bedrock** with your existing identity provider — federated access, temporary
credentials, and per-user usage attribution. No long-lived API keys to distribute.

This project is based on the AWS Solutions guidance
[guidance-for-claude-code-with-amazon-bedrock](https://github.com/aws-solutions-library-samples/guidance-for-claude-code-with-amazon-bedrock)
and diverges from it in three significant ways:

1. **Web deployment wizard** — an operator-facing local web app (`uv run ccwb`) drives the
   whole deploy → package → distribute flow, in addition to the original CLI.
2. **Bedrock-native usage logging** — the OTEL/ECS pipeline is replaced by Amazon Bedrock
   model-invocation logging. Attribution is read straight from each invocation log's
   `$.requestMetadata.*` fields, surfaced in a CloudWatch Logs Insights dashboard.
3. **Dynamic attribution mapping** — operators map IdP claims to dashboard dimensions
   (`user` / `team` / `dept`) in the wizard; the credential helper applies the mapping at
   every authentication, so org changes flow through without re-packaging.

---

## How attribution works

The credential helper builds a Bedrock "magic header" from the signed OIDC ID token and
writes it into `~/.claude/settings.json`. Claude Code attaches it to every Bedrock call,
and Bedrock logging surfaces it per request.

```
IdP claims (email, cognito:groups, custom:dept, ...)
   │  attribution.mapping  (user←email, team←cognito:groups, dept←custom:dept)
   │  attribution.passthrough  (sub, cognito:username, ...)
   ▼
X-Amzn-Bedrock-Request-Metadata: {"user":..., "team":..., "dept":..., ...}
   ▼
Bedrock model-invocation log  $.requestMetadata.{user,team,dept}
   ▼
CloudWatch Logs Insights dashboard (grouped by user / team / dept, cost by model)
```

The mapping is **dynamic** — re-evaluated on each auth event, not frozen at install time.
See [ANTHROPIC_CUSTOM_HEADERS_GUIDE.md](ANTHROPIC_CUSTOM_HEADERS_GUIDE.md) for the header
contract (16-key / 256-char limits, `b64:` encoding of non-ASCII values, untagged-call
handling).

---

## Architecture

```
Operator browser ─▶ FastAPI wizard (127.0.0.1) ─▶ ccwb_domain ─▶ boto3 / CloudFormation
                                                       │
End user laptop ─▶ credential-process ─▶ OIDC login ─▶ STS AssumeRoleWithWebIdentity
                                                       │           (12h session)
                                                       ▼
                                          Claude Code ─▶ Amazon Bedrock
                                                       ▼
                                  Bedrock model-invocation logging (CloudWatch Logs)
                                                       ▼
                                  metric filters + Logs Insights dashboard
```

- **Federation**: Direct STS (`AssumeRoleWithWebIdentity`, 12h) is the default; Cognito
  Identity Pool is also supported.
- **Trust anchor**: the STS role-session name (IdP-asserted), not the header (which is
  client-supplied) — the header is for attribution, not authorization.
- **Backend** binds to localhost only; profiles live in `~/.ccwb/profiles/<name>.json`.

---

## Two ways to deploy

### A. Web wizard (this fork's primary path)

```bash
cd ccwb
uv sync --all-packages
cd web/frontend && yarn install && cd ../..

uv run ccwb            # production build + serve, then open the printed localhost URL
# or: make dev         # hot-reload dev mode (vite + uvicorn)
```

The wizard walks 11 steps (profile → AWS env → IdP + attribution → infra name → models →
logging/quota → distribution → features → tags → review → deploy/package/test/distribute).
See [web/README.md](web/README.md) for the full step list and developer setup.

### B. CLI (upstream-style)

```bash
cd source
poetry install
poetry run ccwb init       # interactive wizard → ~/.ccwb/profiles/<name>.json
poetry run ccwb deploy     # CloudFormation stacks
poetry run ccwb package    # build installer(s)
poetry run ccwb distribute # presigned S3 URL (optional)
```

See [QUICK_START.md](QUICK_START.md) for the complete CLI walkthrough.

---

## Prerequisites

**Operator (deployment):**
- Python 3.10–3.13, [uv](https://docs.astral.sh/uv/) (wizard) or Poetry (CLI)
- Node.js ≥ 18 + yarn (wizard frontend only)
- AWS CLI v2, Git
- AWS account with permissions for CloudFormation, IAM (OIDC provider / roles), Bedrock
  model-invocation logging, CloudWatch, S3, and optionally Lambda / CodeBuild
- Amazon Bedrock model access enabled in the target region(s)

**OIDC provider:** an existing provider (Okta, Microsoft Entra ID, Auth0, or Cognito User
Pool) with an app registration whose redirect URI includes `http://localhost:8400/callback`
and PKCE enabled. You need the **provider domain** and **client ID**.

**End user:** Claude Code installed and a browser. No AWS account, Python, or Git required —
they receive a pre-built package and log in with corporate credentials.

---

## What gets deployed

| Stack | Purpose |
|-------|---------|
| `*-s3` | S3 bucket for CFN/Lambda packaging artifacts |
| `*-auth` | IAM OIDC provider (or Cognito Identity Pool) + Bedrock-scoped federated role |
| `*-bedrock-logging` | Enables Bedrock model-invocation logging + metric filters on the invocation log group (reuses an existing log group when one is already configured) |
| `*-dashboard` | CloudWatch Logs Insights dashboard keyed on `user` / `team` / `dept`, with per-model cost estimation |
| `*-quota` (optional) | User / team / dept **aggregate** token limits (monthly/daily), SNS email alerts, optional block-on-exceed |
| `*-distribution` (optional) | Presigned-URL or authenticated landing-page distribution |
| `*-codebuild` (optional) | Windows `.exe` build via CodeBuild |

End users receive an **OS-specific, self-contained** package:

- **macOS / Linux** — `<profile>-<platform>.zip`: the `credential-process` binary, `config.json`,
  `settings.json`, and `install.sh`. Built locally on the operator machine.
- **Windows** — `<profile>-windows.zip`: `credential-process-windows.exe`, `config.json`,
  `settings.json`, and `install.bat`. Built in the cloud via the `*-codebuild` stack (no
  Windows machine needed), then assembled by the wizard.

Each package is independent — the end user runs `install.sh` (macOS/Linux) or `install.bat`
(Windows), then authenticates once via `credential-process --profile <name>`. The installers
place the binary, write the `~/.aws/config` profile, and install the `~/.claude/settings.json`
template; they do not install Claude Code itself (assumed pre-installed) and emit an advisory
if `aws`/`claude` are missing from `PATH`.

---

## Monitoring (Bedrock-native)

Usage is read directly from Amazon Bedrock model-invocation logs — no OTEL collector, ECS,
or ALB. The dashboard (`deployment/infrastructure/claude-code-dashboard.yaml`) uses
CloudWatch Logs Insights queries:

- KPIs: invocations, total tokens, estimated cost (USD), active users, untagged calls
- Token trends and breakdowns by **user / team / dept / model**
- Top-users table and recent-invocations table
- Cost estimation per model tier (Opus / Sonnet / Haiku list prices)

Untagged invocations (no `requestMetadata`) flag users who skipped `install.sh` or whose
environment overrode `ANTHROPIC_CUSTOM_HEADERS`.

---

## Quotas (User / Team / Dept aggregate)

Quotas are optional and aggregate at three scopes. The `*-bedrock-logging` metric filters
emit single-dimension token metrics per axis (`InputTokensBy{User,Team,Dept}` /
`OutputTokensBy{...}` in the `ClaudeCodeBedrock` namespace). Every 15 minutes an EventBridge
rule runs the quota-monitor Lambda, which sums each scope into DynamoDB rollups
(`USER#` / `TEAM#` / `DEPT#`).

- **Default policy** — a single monthly/daily limit applied to every user, set in the wizard.
- **Fine-grained policies** — enable the toggle in the wizard and assign per-`user`/`team`/`dept`
  limits in the policy table. On deploy these are seeded into the `QuotaPolicies` table.
- **Enforcement** — `alert` (SNS notification only) or `block` (deny credential issuance). The
  credential helper calls the quota-check API before issuing credentials; access is denied if
  **any** scope (user, team, or dept) is over a `block`-mode limit. Team/dept enforcement is a
  true aggregate — when a team's combined usage exceeds its limit, every member is blocked.
- **Alerts** — add operator emails in the wizard; they are subscribed to the quota SNS topic at
  deploy time (each address must confirm the AWS subscription email).

Team/dept identifiers come from the attribution mapping, so a policy's identifier must match
the value carried in `$.requestMetadata.{team,dept}` (non-ASCII values are `b64:`-encoded).

---

## Operations

For day-to-day operator tasks (new member, team/department change, offboarding, usage
checks, quotas) see
[web/binaries/credential_provider/USER_LIFECYCLE_RUNBOOK.md](web/binaries/credential_provider/USER_LIFECYCLE_RUNBOOK.md).

**Reflecting an org change (team/dept):** because cached credentials and silently-refreshed
sessions reuse the previous token's claims, an org change is only picked up on a full
re-login. Ask the affected user to run:

```bash
~/claude-code-with-bedrock/credential-process --profile <name> --refresh-identity
```

This clears the cached credentials + ID token, opens a fresh browser login, rewrites the
magic header in `~/.claude/settings.json`, and prints the new `user/team/dept` attribution.
Restart Claude Code afterward.

---

## Documentation

| Doc | What it covers |
|-----|----------------|
| [QUICK_START.md](QUICK_START.md) | Full CLI deployment walkthrough |
| [web/README.md](web/README.md) | Web wizard architecture, dev setup, step-by-step flow |
| [ANTHROPIC_CUSTOM_HEADERS_GUIDE.md](ANTHROPIC_CUSTOM_HEADERS_GUIDE.md) | Magic-header / attribution contract |
| [USER_LIFECYCLE_RUNBOOK.md](web/binaries/credential_provider/USER_LIFECYCLE_RUNBOOK.md) | Operator runbook for member lifecycle |
| [MIGRATION.md](MIGRATION.md) | Migration notes |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

---

## License

MIT — see [LICENSE](LICENSE).

> Content reflects this fork's behavior; the upstream guidance is the basis and may differ.
