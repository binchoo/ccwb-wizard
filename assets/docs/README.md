# User Documentation

Documentation for IT administrators implementing and operating **Claude Code with Amazon Bedrock (ccwb)** via the web wizard (`uv run ccwb`).

Docs are numbered to show the recommended reading order. **01–04 are the deployment Critical Path** — read them in sequence. 10+ are operational references you reach for as needed.

## Deployment — read in order

| # | Document | Purpose |
|---|----------|---------|
| 01 | **Configure your IdP** (see table below) | Set up your identity provider first — the wizard needs its domain + client ID |
| 02 | [QUICK_START.md](../../QUICK_START.md) | **Primary** step-by-step deployment walkthrough (the Critical Path) |
| 03 | [DEPLOYMENT.md](./DEPLOYMENT.md) | Conceptual/narrative walkthrough of the same steps |
| 04 | [LOCAL_TESTING.md](./LOCAL_TESTING.md) | Verify the setup before full rollout |

### 01 — Identity Provider setup guides

Complete your IdP **before** launching the wizard. Each guide ends with the **provider domain** and **client ID** the wizard asks for.

| Identity Provider | Guide |
|---|---|
| **Okta** | [providers/okta-setup.md](./providers/okta-setup.md) |
| **Microsoft Entra ID (Azure AD)** | [providers/microsoft-entra-id-setup.md](./providers/microsoft-entra-id-setup.md) |
| **Auth0** | [providers/auth0-setup.md](./providers/auth0-setup.md) |
| **AWS Cognito User Pool** | [providers/cognito-user-pool-setup.md](./providers/cognito-user-pool-setup.md) |
| **PingFederate / Keycloak / other generic OIDC** | [providers/generic-oidc-setup.md](./providers/generic-oidc-setup.md) |

## Reference

| # | Document | Purpose |
|---|----------|---------|
| 10 | [ARCHITECTURE.md](./ARCHITECTURE.md) | Technical architecture details |
| 11 | [CLI_REFERENCE.md](./CLI_REFERENCE.md) | `ccwb` command reference |
| 12 | [ANTHROPIC_CUSTOM_HEADERS_GUIDE.md](./ANTHROPIC_CUSTOM_HEADERS_GUIDE.md) | Magic-header / attribution contract (16-key / 256-char limits, `b64:` encoding) |

## Operations

| # | Document | Purpose | Audience |
|---|----------|---------|----------|
| 20 | [MONITORING.md](./MONITORING.md) | Bedrock-native usage monitoring + CloudWatch dashboard | IT admins |
| 21 | [ANALYTICS.md](./ANALYTICS.md) | S3 data lake + Athena queries for historical usage | IT admins |
| 22 | [QUOTA_MONITORING.md](./QUOTA_MONITORING.md) | Per-user/per-group token quota enforcement + alerts | IT admins |
| 23 | [COST_ATTRIBUTION.md](./COST_ATTRIBUTION.md) | Per-user/per-team cost tracking | IT admins, finance |

## Claude Cowork (Desktop)

| # | Document | Purpose | Audience |
|---|----------|---------|----------|
| 30 | [COWORK_3P.md](./COWORK_3P.md) | Credential helper with Claude Desktop in third-party platform mode | IT admins deploying CoWork |
