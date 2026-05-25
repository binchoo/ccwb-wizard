# Migrating from OTEL pipeline to Bedrock-native logging

This fork replaces the v2.x OpenTelemetry pipeline with Amazon Bedrock's own
model invocation logging. The migration removes 4 CloudFormation stacks
(networking, monitoring, analytics, cowork-dashboard) and the otel-helper
binary from end-user packages, in exchange for a single new
``bedrock-logging`` stack.

## What changes

### For operators

- **Stack count**: 9 → 5 (or 6 with ``s3bucket``).
- **Per-month infra cost**: roughly ``$80–150`` (NAT + ALB + Fargate + CW
  custom metrics + Firehose + Athena) → ``$10–15`` (CloudWatch Logs ingest +
  Custom Metrics + Athena queries on demand).
- **Setup time**: removes the VPC + ECS bootstrap (~30 min) and Athena
  workgroup boilerplate.

### For end users

- **Helper binaries**: ``otel-helper`` and ``otelcol`` no longer included in
  the install zip.
- **settings.json**: ``OTEL_EXPORTER_OTLP_*`` keys removed; one new key
  ``ANTHROPIC_CUSTOM_HEADERS`` carries per-user metadata as a magic Bedrock
  header.
- **install.sh**: opens browser once during install to fetch the user's JWT,
  then bakes the metadata into ``~/.claude/settings.json``.

### What stays the same

- Authentication: Cognito UP / Direct OIDC, ``AssumeRoleWithWebIdentity``,
  ``RoleSessionName=email`` (PR #245).
- Quota: same DynamoDB schema, same ``credential-process`` gate, same
  enforcement modes.
- Distribution: same presigned-S3 / landing-page paths.

## Migration steps (existing v2.x deployments)

1. **Pull the fork**:

   ```bash
   git fetch origin
   git checkout feat/bedrock-native-logging
   poetry install
   ```

2. **Verify the bedrock-native pipeline first** (Wave 1 evidence). On a
   spare profile, run the e2e procedure in
   ``.kiro/specs/bedrock-native-logging/wave5-verification.md`` to confirm
   that ``ANTHROPIC_CUSTOM_HEADERS`` produces ``$.requestMetadata`` entries
   in ``/aws/bedrock/modelinvocations`` for *your* Cognito setup.

3. **Snapshot DynamoDB UserQuotaMetrics** (optional, defensive). Schema is
   unchanged so a logical export is sufficient:

   ```bash
   aws dynamodb scan \
     --table-name <UserQuotaMetricsTableName> \
     --output json > pre-migration-quota.json
   ```

4. **Tear down the legacy OTEL stacks**:

   ```bash
   poetry run ccwb deploy --remove-otel-stacks --profile <name>
   ```

   Deletes networking → monitoring → analytics → cowork-dashboard in
   dependency order. Leaves auth, quota, dashboard, distribution, s3bucket
   untouched.

5. **Deploy the new pipeline**:

   ```bash
   poetry run ccwb deploy --profile <name>
   ```

   Brings up ``bedrock-logging`` (new), refreshes ``dashboard`` with the new
   namespace ``ClaudeCodeBedrock``, and updates ``quota`` to read from
   CloudWatch ``GetMetricData`` instead of PromQL.

6. **Repackage and redistribute**:

   ```bash
   poetry run ccwb package --profile <name>
   poetry run ccwb distribute --profile <name>
   ```

   New zips no longer ship ``otel-helper-*`` or ``otelcol-*`` binaries.
   Hand the new presigned URL out to users.

7. **Users re-run install.sh**. The new install:
   - removes ``~/claude-code-with-bedrock/otel-helper`` and ``otelcol`` if
     present (left over from v2.x);
   - rewrites ``~/.claude/settings.json`` with the new env block.

   Existing AWS profiles in ``~/.aws/config`` keep working — the
   credential_process line is unchanged.

## Rollback

Roll back per-stack by restoring v2.x branch and redeploying. The DynamoDB
data and CloudWatch Custom Metrics namespaces (``ClaudeCode`` for v2.x vs.
``ClaudeCodeBedrock`` for v3.0) are independent so neither overwrites the
other. Running both pipelines in parallel for verification is supported.

## Caveats

- **Mantle endpoint**: Bedrock's ``bedrock-mantle`` endpoint silently drops
  invocation logging. v3.0 ``settings.json`` sets ``CLAUDE_CODE_USE_MANTLE=0``
  defensively. Don't override.
- **Static metadata**: ``ANTHROPIC_CUSTOM_HEADERS`` is parsed once at Claude
  Code start and pinned for the process lifetime. Org changes (new team,
  cost center, etc.) require ``install.sh`` re-run.
- **JWT email visibility**: ``$.requestMetadata.email`` in invocation logs
  carries the plain-text email IdP issued. v3.0 forwards every non-boilerplate
  JWT claim verbatim — there is no mapping layer to redact. If your data
  classification policy disallows plain emails, configure your IdP to issue
  a hashed or pseudonymous identifier in place of ``email`` (or omit the
  claim entirely from the ID token scope).
- **CUR / Cost Explorer**: ``requestMetadata`` does **not** show up in CUR.
  Cost attribution remains a separate concern from invocation logging — for
  per-user/team cost allocation use AWS Cost Categories with resource tagging.
