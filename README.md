# Guidance for Claude Code and Cowork on Amazon Bedrock

This guidance provides enterprise deployment patterns for Claude Code and Claude Cowork (Claude Desktop) with Amazon Bedrock using existing identity providers. Deploy once to enable both Claude Code CLI and Claude Cowork Desktop across your organization, with centralized access control, audit trails, and usage monitoring.

## Key Features

### For Organizations

- **Enterprise IdP Integration**: Leverage existing OIDC identity providers (Okta, Azure AD, Auth0, etc.)
- **AWS SSO / IAM Identity Center**: Native AWS identity path for teams already using IAM Identity Center — no external IdP required
- **Centralized Access Control**: Manage Claude Code access through your identity provider
- **No API Key Management**: Eliminate the need to distribute or rotate long-lived credentials
- **Usage Monitoring**: Optional CloudWatch dashboards for tracking usage and costs
- **Multi-Region Support**: Configure which AWS regions users can access Bedrock in
- **Multi-Partition Support**: Deploy to AWS Commercial or AWS GovCloud (US) regions
- **Multi-Platform Support**: Windows, macOS (ARM & Intel), and Linux distributions
- **Claude Cowork 3P Compatible**: Same credential helper works with Claude Desktop in third-party platform mode — one deployment covers both Claude Code CLI and Claude Cowork

### For End Users

- **Seamless Authentication**: Log in with corporate credentials
- **Automatic Credential Refresh**: No manual token management required
- **AWS CLI/SDK Integration**: Works with any AWS tool or SDK
- **Multi-Profile Support**: Manage multiple authentication profiles
- **Cross-Platform**: Works on Windows, macOS, and Linux

### For Users (Claude Cowork)

- **Claude Desktop Experience**: Research, document analysis, data processing, and report generation
- **No CLI Required**: Users just open Claude Desktop — authentication is handled by the credential helper
- **MDM Deployment**: Configure via Jamf, Intune, or Group Policy using generated .mobileconfig/.reg files
- **Projects, Artifacts, and MCP**: Full Claude Desktop capabilities including connectors and plugins
- **Consumption-Based Pricing**: No Anthropic seat licensing — billed through your existing AWS agreement

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Overview](#architecture-overview)
3. [Prerequisites](#prerequisites)
4. [AWS Partition Support](#aws-partition-support)
5. [What Gets Deployed](#what-gets-deployed)
6. [Monitoring and Operations](#monitoring-and-operations)
7. [Additional Resources](#additional-resources)

## Quick Start

This guidance integrates Claude Code with your existing OIDC identity provider (Okta, Azure AD, Auth0, or Cognito User Pools) to provide federated access to Amazon Bedrock.

### What You Need

**Existing Identity Provider:**
You must have an active OIDC provider with the ability to create application registrations. The guidance federates this IdP with AWS IAM to issue temporary credentials for Bedrock access.

**AWS Environment:**

- AWS account with IAM and CloudFormation permissions
- Amazon Bedrock activated in target regions
- Python 3.10+ development environment for deployment

### What Gets Deployed

The deployment creates:

- IAM OIDC Provider or Cognito Identity Pool for federation
- IAM roles with scoped Bedrock access policies
- Platform-specific installation packages (Windows, macOS, Linux)
- Optional: OpenTelemetry monitoring infrastructure

**Deployment time:** 2-3 hours for initial setup including IdP configuration.

See [QUICK_START.md](QUICK_START.md) for complete step-by-step deployment instructions.

### Extend to Claude Cowork

If you've deployed this guidance for Claude Code, extend it to Claude Cowork (Claude Desktop) with one command:

```bash
poetry run ccwb cowork generate
```

This generates MDM configuration files (JSON, macOS .mobileconfig, Windows .reg) using your existing deployment profile. See the [CoWork 3P Guide](assets/docs/COWORK_3P.md) for setup and deployment details.

## Architecture Overview

This guidance uses Direct IAM OIDC federation as the recommended authentication pattern. This provides temporary AWS credentials with complete user attribution for audit trails and usage monitoring.

**Alternative:** Cognito Identity Pool is also supported for legacy IdP integrations. See [Deployment Guide](assets/docs/DEPLOYMENT.md) for comparison.

### Authentication Flow (Direct IAM Federation)

![Architecture Diagram](assets/images/credential-flow-direct-diagram.png)

1. **User initiates authentication**: User requests access to Amazon Bedrock through Claude Code or Claude Cowork
2. **OIDC authentication**: User authenticates with their OIDC provider and receives an ID token
3. **Token submission to IAM**: Application sends the OIDC ID token to Amazon Cognito
4. **IAM returns credentials**: AWS IAM validates and returns temporary AWS credentials
5. **Access Amazon Bedrock**: Application uses the temporary credentials to call Amazon Bedrock
6. **Bedrock response**: Amazon Bedrock processes the request and returns the response

### Optional: Deploy Without SSO Authentication

**New in v2.1+:** You can now deploy the observability and analytics solution without SSO authentication. This is ideal for:

- **Internal tools and development environments** where user authentication isn't required
- **Analytics-only deployments** where you want usage tracking without managing IdP integrations
- **Simplified deployments** using AWS IAM roles for access control

When SSO authentication is disabled:

- **Access Control**: Uses AWS IAM roles and policies directly (no OIDC provider required)
- **Identity Detection**: Automatically detects how users authenticate to AWS:
  - **AWS IAM Identity Center (SSO) users**: Real username/email is extracted from the assumed-role ARN — no configuration needed. Each SSO user gets full identity attribution (name, email, permission set) in the observability dashboard.
  - **IAM users**: Username is extracted from the IAM user ARN.
  - **Non-SSO assumed roles**: Usage is tracked using a hashed anonymous identifier (consistent per IAM principal, but individual identity cannot be determined).
- **No IdP Configuration**: Skip OIDC provider setup entirely — if your organization uses AWS IAM Identity Center for Bedrock access, identity "just works"

**When to use this:**
- You're deploying only the observability/analytics infrastructure
- Your users already have AWS IAM access to Bedrock
- You want simplified deployment without IdP integration
- You need usage monitoring but don't require individual user authentication

**When to use SSO authentication:**
- You need centralized access control through your identity provider
- You require user-level attribution with real identities (email, department, etc.)
- You want to enforce organization-wide access policies
- You need detailed audit trails with user information

To deploy without SSO authentication, select **"None (use existing AWS credentials)"** when prompted for the authentication method during `ccwb init`. The deployment will skip the authentication stack and use anonymous tracking for metrics.

> **New in v2.2+:** IAM Identity Center is now a first-class authentication option. Select **"AWS IAM Identity Center (SSO)"** in `ccwb init` to get guided setup, `~/.aws/config` generation, and the correct CloudFormation stack — without the undocumented workaround of disabling SSO. See the [IAM Identity Center Setup Guide](assets/docs/providers/iam-identity-center-setup.md) for details.

## Authentication Modes

This guidance supports three identity paths. All paths deliver per-user identity resolution, centralized access control, audit trails, and usage monitoring.

| Mode | `ccwb init` choice | Identity Source | Session Length | Quota Enforcement | Best For |
|------|--------------------|----------------|----------------|-------------------|----------|
| **External IdP (OIDC)** | `OIDC / Direct IdP` | Okta, Azure AD, Auth0, Cognito User Pools JWT claims | Refresh token lifetime | ✅ Full | Orgs with an existing enterprise IdP |
| **AWS IAM Identity Center** | `AWS IAM Identity Center` | `AWSReservedSSO_*` IAM role ARN (email + permission set) | Up to 90 days (recommended: 7 days) | ❌ Not available | Orgs on native AWS identity, or where OIDC localhost callback is blocked |
| **None** | `None` | IAM user ARN or hashed role principal | AWS credential TTL | ❌ Not available | Internal tools / analytics-only deployments |

**Choosing a path:**

- Use **External IdP (OIDC)** when you need full quota enforcement, rich user attribution (department, team, cost centre from JWT claims), and have an OIDC provider (Okta, Azure AD, Auth0, or Cognito).
- Use **AWS IAM Identity Center** when your team already uses IAM IDC, or when corporate policies block `localhost:8400`, or when you want sessions up to 7 days without browser re-prompts. See [IAM Identity Center Setup Guide](assets/docs/providers/iam-identity-center-setup.md).
- Use **None** when deploying the observability/analytics stack only, or when users already have IAM access to Bedrock and need no additional authentication layer.

For deployment patterns and best practices, see the [Claude Code deployment patterns and best practices with Amazon Bedrock](https://aws.amazon.com/blogs/machine-learning/claude-code-deployment-patterns-and-best-practices-with-amazon-bedrock/) blog post.

## Prerequisites

### For Deployment (IT Administrators)

**Software Requirements:**

- Python 3.10-3.13
- Poetry (dependency management)
- AWS CLI v2
- Git
- Go 1.23+ (optional — only needed for building the OTEL collector sidecar)

**AWS Requirements:**

- AWS account with appropriate IAM permissions to create:
  - CloudFormation stacks
  - IAM OIDC Providers or Cognito Identity Pools
  - IAM roles and policies
  - (Optional) Amazon Elastic Container Service (Amazon ECS) tasks and Amazon CloudWatch dashboards
  - (Optional) Amazon Athena, AWS Glue, AWS Lambda, and Amazon Data Firehose resources
  - (Optional) AWS CodeBuild
- Amazon Bedrock activated in target regions

**OIDC Provider Requirements:**

- Existing OIDC identity provider (Okta, Azure AD, Auth0, etc.)
- Ability to create OIDC applications
- Redirect URI support for `http://localhost:8400/callback`

### For End Users

**Claude Code:**

- Claude Code installed
- Web browser for SSO authentication
- AWS CLI v2 (optional)

**Claude Cowork:**

- Claude Desktop installed ([download](https://claude.com/download))
- MDM configuration deployed by IT admin (generated via `ccwb cowork generate`)

**No AWS account required** - users authenticate through your organization's identity provider and receive temporary credentials automatically.

**No Python, Poetry, or Git required** - users receive pre-built installation packages from IT administrators.

### Supported AWS Regions

The guidance can be deployed in any AWS region that supports:

- IAM OIDC Providers or Amazon Cognito Identity Pools
- Amazon Bedrock
- (Optional) Amazon Elastic Container Service (Amazon ECS) tasks and Amazon CloudWatch dashboards
- (Optional) Amazon Athena, AWS Glue, AWS Lambda, and Amazon Data Firehose resources
- (Optional) AWS CodeBuild

Both AWS Commercial and AWS GovCloud (US) partitions are supported. See [AWS Partition Support](#aws-partition-support) for details.

### Cross-Region Inference

Claude Code uses Amazon Bedrock's cross-region inference for optimal performance and availability. During setup, you can:

- Select your preferred Claude model (Opus, Sonnet, Haiku)
- Choose a cross-region profile (US, Europe, APAC) for optimal regional routing
- Select a specific source region within your profile for model inference

This automatically routes requests across multiple AWS regions to ensure the best response times and highest availability. Modern Claude models (3.7+) require cross-region inference for access.

### Platform Support

The authentication tools support all major platforms:

| Platform | Architecture          | Build Method                | Installation |
| -------- | --------------------- | --------------------------- | ------------ |
| Windows  | x64                   | AWS CodeBuild (Nuitka)      | install.bat  |
| macOS    | ARM64 (Apple Silicon) | Native (PyInstaller)        | install.sh   |
| macOS    | Intel (x86_64)        | Cross-compile (PyInstaller) | install.sh   |
| macOS    | Universal (both)      | Universal2 (PyInstaller)    | install.sh   |
| Linux    | x86_64                | Docker (PyInstaller)        | install.sh   |
| Linux    | ARM64                 | Docker (PyInstaller)        | install.sh   |

**Build System:**

The package builder automatically creates executables for all platforms using PyInstaller (macOS/Linux) and AWS CodeBuild with Nuitka (Windows). All builds create standalone executables - no Python installation required for end users.

See [QUICK_START.md](QUICK_START.md#platform-builds) for detailed build configuration.

## AWS Partition Support

This guidance supports deployment across multiple AWS partitions with a single, unified codebase. The same CloudFormation templates and deployment process work seamlessly in both AWS Commercial and AWS GovCloud (US) regions.

### Supported Partitions

| Partition | Regions | Use Cases |
|-----------|---------|-----------|
| **AWS Commercial** (`aws`) | All regions where Bedrock is available | Standard commercial workloads |
| **AWS GovCloud (US)** (`aws-us-gov`) | us-gov-west-1, us-gov-east-1 | US government agencies, contractors, and regulated workloads |

### How It Works

The guidance automatically detects the AWS partition at deployment time and configures resources appropriately:

**Resource ARNs:**
- CloudFormation uses the `${AWS::Partition}` pseudo-parameter
- Automatically resolves to `aws` or `aws-us-gov`
- Example: `arn:${AWS::Partition}:bedrock:*::foundation-model/*`

**Service Principals:**
- Cognito Identity service principals are partition-specific
- Commercial: `cognito-identity.amazonaws.com`
- GovCloud West: `cognito-identity-us-gov.amazonaws.com`
- GovCloud East: `cognito-identity.us-gov-east-1.amazonaws.com`
- IAM role trust policies automatically use the correct principal based on region

**S3 Endpoints:**
- Commercial: `s3.region.amazonaws.com`
- GovCloud: `s3.region.amazonaws.com`

### Deploying to AWS GovCloud

Follow the same [Quick Start](#quick-start) instructions with your GovCloud credentials active. During `ccwb init`, select a GovCloud region (us-gov-west-1 or us-gov-east-1) and the wizard will automatically configure GovCloud-compatible models and endpoints.

**GovCloud-Specific Considerations:**

1. **Credentials:** GovCloud requires separate AWS credentials from commercial accounts
2. **Model IDs:** GovCloud uses region-prefixed model IDs (e.g., `us-gov.anthropic.*`)
3. **FIPS Endpoints:** Cognito hosted UI uses `{prefix}.auth-fips.{region}.amazoncognito.com`
4. **Managed Login:** Branding must be created for each Cognito app client

### Validation

After deployment, verify the correct partition configuration:

```bash
# Check IAM role ARN uses correct partition
aws iam get-role \
  --role-name BedrockCognitoFederatedRole \
  --region <region> \
  --query 'Role.Arn'

# Expected ARN formats:
# Commercial: arn:aws:iam::ACCOUNT:role/BedrockCognitoFederatedRole
# GovCloud: arn:aws-us-gov:iam::ACCOUNT:role/BedrockCognitoFederatedRole
```

### Backward Compatibility

✅ **All changes are fully backward compatible**

- Existing commercial deployments continue to work without modification
- CloudFormation updates can be applied to existing stacks
- No changes to user-facing functionality
- No data migration required

## What Gets Deployed

### Authentication Infrastructure

The `ccwb deploy` command creates:

**IAM Resources:**

- IAM OIDC Provider (for Direct IAM federation) or Cognito Identity Pool (for legacy IdP)
- IAM role with trust relationship for federated access
- IAM policies scoped to:
  - Bedrock model invocation in configured regions
  - CloudWatch metric publishing (if monitoring enabled)

**User Distribution Packages:**

- Platform-specific executables (Windows, macOS ARM64/Intel, Linux x64/ARM64)
- Installation scripts that configure AWS CLI credential process
- Pre-configured settings (OIDC provider, model selection, monitoring endpoints)

### Distribution Options (Optional)

After building packages, you can share them with users in three ways:

| Method                | Best For               | Authentication                 |
| --------------------- | ---------------------- | ------------------------------ |
| **Manual Sharing**    | Any size team          | None                           |
| **Presigned S3 URLs** | Automated distribution | None                           |
| **Landing Page**      | Self-service portal    | IdP (Okta/Azure/Auth0/Cognito) |

**Manual Sharing:** Zip the `dist/` folder and share via email or internal file sharing. No additional infrastructure required.

**Presigned URLs:** Generate time-limited S3 URLs for direct downloads. Automated but requires S3 bucket setup.

**Landing Page:** Self-service portal with IdP authentication, platform detection, and custom domain support. Full automation with compliance features.

See [Distribution Comparison](assets/docs/distribution/comparison.md) for detailed setup guides.

### Monitoring Infrastructure (Optional)

Enable usage visibility with **Bedrock model invocation logging** (new in v3.0+).
The OpenTelemetry pipeline (otel-helper + ECS Fargate + ALB + Firehose + Glue) is
replaced by a single ``bedrock-logging`` CloudFormation stack that wires Bedrock's
own logs into CloudWatch Custom Metrics for dashboards and quota enforcement.

| Mode | Description | Infrastructure | Cost |
|------|-------------|----------------|------|
| **Bedrock-native** (default) | Server-side logging via Bedrock model invocation logs | S3 + CW Logs + metric filters | ~$10–15/mo |
| **None** | No logging | — | $0 |

**Bedrock-native components:**

- S3 bucket holding raw invocation logs (90-day lifecycle by default)
- CloudWatch Logs group ``/aws/bedrock/modelinvocations/<profile>``
- 4 metric filters extracting ``$.requestMetadata.user`` / ``team`` / ``ModelId`` into the ``ClaudeCodeBedrock`` Custom Metrics namespace
- CloudWatch dashboard with KPI widgets and time-series segmented by user/team/model
- Athena workgroup for historical SQL queries against the S3 archive

User attribution flows through ``ANTHROPIC_CUSTOM_HEADERS``, which Claude Code
attaches to every Bedrock call as the magic header
``X-Amzn-Bedrock-Request-Metadata``. The header value is built once at install time
by ``credential-process --get-bedrock-metadata-headers`` from the user's JWT.

See [Migration Guide](assets/docs/MIGRATION_OTEL_TO_BEDROCK_NATIVE.md) if upgrading from v2.x.

## Monitoring and Operations

Bedrock model invocation logging provides comprehensive usage visibility for
cost attribution, quota enforcement, and capacity planning.

### Available Metrics

**Token economics:**

- Input/output token counts per user, team, and model
- Invocation count per user, team, and model
- Untagged-invocation counter (catches users who skipped install.sh)

**Operational health:**

- Top consumers (single-value KPI widgets, 24h windows)
- Tokens by team, tokens by model time-series
- Invocation rate (per-minute granularity)

### Infrastructure

A single ``bedrock-logging`` CloudFormation stack provides:

- S3 bucket for long-term invocation log archive (default 90-day lifecycle)
- CloudWatch Logs group with metric filters publishing to the ``ClaudeCodeBedrock`` namespace
- IAM role for the Bedrock service to write logs
- Custom resource Lambda that toggles ``PutModelInvocationLoggingConfiguration``
- Athena workgroup pre-configured for ad-hoc SQL on the S3 archive

The dashboard stack reads exclusively from CloudWatch Custom Metrics, so all
widgets render without round-trips to OTLP collectors or PromQL APIs.

See [Migration Guide](assets/docs/MIGRATION_OTEL_TO_BEDROCK_NATIVE.md) for details.

## Additional Resources

### Getting Started

- [Quick Start Guide](QUICK_START.md) - Step-by-step deployment walkthrough
- [CLI Reference](assets/docs/CLI_REFERENCE.md) - Complete command reference for the `ccwb` tool
- [Claude Code deployment patterns and best practices with Amazon Bedrock](https://aws.amazon.com/blogs/machine-learning/claude-code-deployment-patterns-and-best-practices-with-amazon-bedrock/) - Blog post covering deployment patterns and best practices

### Architecture & Deployment

- [Architecture Guide](assets/docs/ARCHITECTURE.md) - System architecture and design decisions
- [Deployment Guide](assets/docs/DEPLOYMENT.md) - Advanced deployment options
- [Distribution Comparison](assets/docs/distribution/comparison.md) - Presigned URLs vs Landing Page
- [Local Testing Guide](assets/docs/LOCAL_TESTING.md) - Testing before deployment

### Monitoring & Analytics

- [Monitoring Guide](assets/docs/MONITORING.md) - OpenTelemetry setup and dashboards
- [Analytics Guide](assets/docs/ANALYTICS.md) - S3 data lake and Athena SQL queries

### Claude Cowork (Desktop)

- [CoWork 3P Guide](assets/docs/COWORK_3P.md) - Setup and deployment for Claude Desktop with Bedrock
- [AWS Blog: Running Claude Cowork in Amazon Bedrock](https://aws.amazon.com/blogs/machine-learning/from-developer-desks-to-the-whole-organization-running-claude-cowork-in-amazon-bedrock/)

### Identity Provider Setup

- [Okta](assets/docs/providers/okta-setup.md)
- [Microsoft Entra ID (Azure AD)](assets/docs/providers/microsoft-entra-id-setup.md)
- [Auth0](assets/docs/providers/auth0-setup.md)
- [Generic OIDC (PingFederate, Keycloak, ForgeRock, etc.)](assets/docs/providers/generic-oidc-setup.md)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
