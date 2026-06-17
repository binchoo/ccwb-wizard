# Per-user / per-team attribution for Claude Code on Amazon Bedrock

This guide documents the configuration pattern that we verified works for tagging
Claude Code invocations with arbitrary user/team metadata, without modifying any
AWS infrastructure (no IAM Identity Center plumbing, no Application Inference
Profiles, no Lambda log-enrichment).

The pattern is empirically reproducible — see "Verification" below.

## What it does

Set one environment variable before launching `claude`:

```sh
export ANTHROPIC_CUSTOM_HEADERS='X-Amzn-Bedrock-Request-Metadata: {"team":"blue","user":"alice"}'
```

Claude Code attaches the header to every Bedrock `InvokeModelWithResponseStream`
call. AWS Bedrock records the JSON body of that header as a top-level
`requestMetadata` field in each model invocation log event:

```json
{
  "timestamp": "2026-05-22T16:40:00Z",
  "modelId": "arn:aws:bedrock:...:inference-profile/global.anthropic.claude-opus-4-7",
  "identity": { "arn": "arn:aws:sts::487498333664:assumed-role/ClaudeUserRole-1/..." },
  "input":  { "inputTokenCount": 299, ... },
  "output": { "outputTokenCount": 22, ... },
  "requestMetadata": { "team": "blue", "user": "alice" }
}
```

CloudWatch metric filters can then extract `$.requestMetadata.team` (or any
other key) as a metric dimension — your dashboards segment by team without
hard-coding role-name patterns.

## Why this is "static" config (and why that's fine)

The env var is parsed once when `claude` starts. The metadata you set ships with
every call for the life of that process. To change it, restart `claude` with
different values.

For the launcher pattern in this repo (`user1/launch.sh`, `user2/launch.sh`,
`user3/launch.sh`) that's exactly the right granularity: each launcher
represents one identity, so each launcher hard-pins its own metadata. If a
single process needs to emit different `user` values across calls (e.g. a
shared multi-tenant agent), this pattern does **not** apply — see "Alternatives".

## Where to put it

In each launcher, beside the existing `ANTHROPIC_MODEL` line:

```sh
# user1/launch.sh
export ANTHROPIC_CUSTOM_HEADERS='X-Amzn-Bedrock-Request-Metadata: {"team":"blue","user":"user1"}'
```

```sh
# user2/launch.sh
export ANTHROPIC_CUSTOM_HEADERS='X-Amzn-Bedrock-Request-Metadata: {"team":"red","user":"user2"}'
```

```sh
# user3/launch.sh   (bearer token; no IAM role to tag, so we mark explicitly)
export ANTHROPIC_CUSTOM_HEADERS='X-Amzn-Bedrock-Request-Metadata: {"team":"untagged","user":"user3"}'
```

## Format rules (verified)

| Rule | Detail |
|---|---|
| Syntax | `Header-Name: value` — same as an HTTP header line |
| Multiple headers | Newline-separated. Use `$'h1: v1\nh2: v2'` (ANSI-C quoting) or a real LF in a JSON config |
| Value encoding | ASCII only. Non-ASCII (UTF-8 bytes such as Korean) is rejected at the client with `API Error: Header has invalid value` — encode with Base64 or percent-encoding if you need non-ASCII |
| Bedrock metadata limit | Up to 16 keys per call, 256 chars per key/value (AWS-enforced) |
| Static | Parsed once at process start; cannot rotate mid-session |
| Cache impact | None — Anthropic's prompt cache key does not hash custom headers |

## Verification (5 reproducibility tests)

We ran five distinct invocations and confirmed each landed in CloudWatch Logs
with the expected `requestMetadata` payload.

| # | Scenario | Result |
|---|---|---|
| 1 | user1 + `team=blue`, `user=user1` | PASS — `requestMetadata={"team":"blue","user":"user1","probe":"..."}` |
| 2 | user2 + `team=red`, `user=user2` | PASS |
| 3 | user3 (bearer token, no IAM role) + `team=untagged` | PASS — even with non-role principal |
| 4 | user1 + 240-char ASCII value | PASS — value preserved verbatim |
| 5 | user2 + 16 keys (Bedrock maximum) + a second custom header | PASS — all 16 keys preserved; second header silently dropped from log (Bedrock only logs its own metadata header) |

Reproduce yourself:

```sh
M="probe-$(date +%s)"
ANTHROPIC_CUSTOM_HEADERS="X-Amzn-Bedrock-Request-Metadata: {\"team\":\"blue\",\"probe\":\"$M\"}" \
  ./user1/launch.sh -p "verify $M"
sleep 20
aws logs filter-log-events \
  --log-group-name /claude-code/amazon-bedrock-logs \
  --filter-pattern "{ \$.requestMetadata.probe = \"$M\" }" \
  --query 'events[0].message' --output text
```

You should see the JSON event with your `requestMetadata` block.

## Wiring the metric filter

To make a CloudWatch metric dimension from `$.requestMetadata.team`:

```json
{
  "logGroupName": "/claude-code/amazon-bedrock-logs",
  "filterName": "BedrockTokensByTeam",
  "filterPattern": "{ ($.requestMetadata.team = \"*\") && ($.input.inputTokenCount = *) }",
  "metricTransformations": [
    {
      "metricName": "InputTokensByTeam",
      "metricNamespace": "BedrockUsage",
      "metricValue": "$.input.inputTokenCount",
      "unit": "Count",
      "dimensions": {
        "Team": "$.requestMetadata.team",
        "User": "$.requestMetadata.user",
        "ModelId": "$.modelId"
      }
    }
  ]
}
```

Calls without `requestMetadata.team` simply don't match the filter and don't
emit. To track that ratio (callers who forgot to tag), add a second filter:

```json
"filterPattern": "{ $.requestMetadata NOT EXISTS }"
```

## Limits and gotchas

- **No CUR / Cost Explorer integration.** AWS docs are explicit: request metadata
  is *not* a cost-allocation tag and never appears in Cost Explorer or the
  Cost and Usage Report. To get team-level spend in Cost Explorer you still
  need Application Inference Profiles, Bedrock Projects, or Workspaces.
  This pattern only segments **CloudWatch metrics and logs**.
- **`bedrock-mantle` endpoint silently drops it.** Model invocation logging is
  not captured for the Mantle (Responses API) endpoint. If `CLAUDE_CODE_USE_MANTLE=1`
  is ever set, this entire mechanism produces no records.
- **Claude Code uses `InvokeModelWithResponseStream` only**, never `Converse`.
  That's why we use the `X-Amzn-Bedrock-Request-Metadata` *header* and not the
  `requestMetadata` *body field*.
- **Logs contain plaintext prompts and responses.** Anyone with read access to
  `/claude-code/amazon-bedrock-logs` can read both. Do not put PII (real user
  emails, customer data) into `requestMetadata` values.
- **Static-only.** The Claude Code CLI parses `ANTHROPIC_CUSTOM_HEADERS` at
  process start. Per-call dynamic headers (e.g. W3C `traceparent`) are not
  supported as of 2026-05-22. Tracking issue:
  https://github.com/anthropics/claude-code/issues/58219
- **Header values must be ASCII.** Non-ASCII bytes raise `API Error: Header has
  invalid value` *before* the request leaves the client. Use ASCII or encode
  (Base64, percent-encoding).
- **Auxiliary calls inherit the same metadata.** Claude Code makes Haiku-class
  background calls (session-title generation, etc.). They carry your metadata
  too. Treat metric counts as "all activity by this principal," not "only the
  user-typed prompt."

## Alternatives we considered

| Approach | Native? | Per-call dynamic? | CUR / Cost Explorer? | Cost to set up |
|---|---|---|---|---|
| `ANTHROPIC_CUSTOM_HEADERS` (this guide) | client-side | no | no | zero infra |
| Application Inference Profile (AIP) per team×model | yes | no (one ARN per segment) | yes | N profiles, role policy update |
| Bedrock Project / Workspace (`bedrock-mantle` only) | yes | no | yes | mantle endpoint only |
| OTel sidecar (AWS guidance-for-claude-code-with-amazon-bedrock) | yes | yes (dynamic dims) | no | OTel collector + Athena |
| LiteLLM / Helicone / Portkey gateway | proxy | yes | depends | gateway deployment |
| Lambda subscription enriching logs with IAM role tags | yes | no | no | Lambda + iam:ListRoleTags + extra metric publish |
| IAM Identity Center → Bedrock trusted-identity propagation | — | — | — | **does not exist as of 2026-05-22**; Bedrock is not in the TIP integrations list |

## Reference

- AWS Bedrock — Tagging requests with metadata:
  https://docs.aws.amazon.com/bedrock/latest/userguide/cost-mgmt-request-metadata.html
- AWS Bedrock — Model invocation logging:
  https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html
- Claude Code env vars (`ANTHROPIC_CUSTOM_HEADERS`):
  https://code.claude.com/docs/en/env-vars
- Claude Code on Amazon Bedrock — Guardrails example uses the same header pattern:
  https://code.claude.com/docs/en/amazon-bedrock
- Issue tracking dynamic-per-call headers (open):
  https://github.com/anthropics/claude-code/issues/58219
