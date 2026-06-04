import { useEffect, useState } from "react";
import Container from "@cloudscape-design/components/container";
import FormField from "@cloudscape-design/components/form-field";
import Checkbox from "@cloudscape-design/components/checkbox";
import Input from "@cloudscape-design/components/input";
import Toggle from "@cloudscape-design/components/toggle";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Alert from "@cloudscape-design/components/alert";
import Select from "@cloudscape-design/components/select";
import { useWizardStore } from "../store";

export default function LoggingQuotaPage() {
  const { draft, updateDraft } = useWizardStore();
  const [existingLogging, setExistingLogging] = useState<{ exists: boolean | "unknown"; destination?: string; cloudwatch_log_group?: string; s3_bucket?: string; detail?: string } | null>(null);

  useEffect(() => {
    if (draft.aws_region) {
      fetch(`/api/aws/bedrock-logging-status?region=${draft.aws_region}`)
        .then((r) => r.json())
        .then(setExistingLogging)
        .catch(() => setExistingLogging(null));
    }
  }, [draft.aws_region]);

  const dest = draft.bedrock_logging?.destination || "cloudwatch";
  const cwLogs = dest === "cloudwatch" || dest === "both";
  const s3 = dest === "s3" || dest === "both";
  const quotaEnabled = draft.quota !== null;

  const setDestination = (cw: boolean, s3on: boolean) => {
    let d = "";
    if (cw && s3on) d = "both";
    else if (cw) d = "cloudwatch";
    else if (s3on) d = "s3";
    updateDraft({ bedrock_logging: { ...draft.bedrock_logging, destination: d } });
  };

  return (
    <SpaceBetween size="l">
      {existingLogging?.exists === true && (
        <Alert type="warning" header="기존 Bedrock Logging 설정 감지" data-testid="existing-logging-alert">
          이 계정/리전({draft.aws_region})에 이미 Bedrock model invocation logging이 설정되어 있습니다.
          현재 설정: <strong>{existingLogging.destination}</strong>
          {existingLogging.cloudwatch_log_group && <> (CW: {existingLogging.cloudwatch_log_group})</>}
          {existingLogging.s3_bucket && <> (S3: {existingLogging.s3_bucket})</>}
          <br /><br />
          <Checkbox
            checked={draft.bedrock_logging?.skip_if_exists === true}
            onChange={({ detail }) => updateDraft({ bedrock_logging: { ...draft.bedrock_logging, skip_if_exists: detail.checked } })}
            data-testid="skip-if-exists-checkbox"
          >
            <strong>기존 설정 유지</strong> — Deploy 시 bedrock-logging 스택을 건너뜁니다 (기존 설정을 덮어쓰지 않음)
          </Checkbox>
        </Alert>
      )}
      {existingLogging?.exists === "unknown" && (
        <Alert type="info" header="기존 Bedrock Logging 설정 확인 불가" data-testid="logging-check-unknown">
          bedrock:GetModelInvocationLoggingConfiguration 권한이 없거나 조회에 실패했습니다. Deploy 전에 기존 설정 여부를 수동 확인하세요.
        </Alert>
      )}

      <Container header={<Header variant="h2">Bedrock Logging</Header>}>
        <SpaceBetween size="m">
          <FormField label="Logging Destination (최소 하나는 켜야 합니다)">
            <SpaceBetween size="s" direction="horizontal">
              <Checkbox checked={cwLogs} onChange={({ detail }) => setDestination(detail.checked, s3)} data-testid="logging-cw-checkbox">
                CloudWatch Logs
              </Checkbox>
              <Checkbox checked={s3} onChange={({ detail }) => setDestination(cwLogs, detail.checked)} data-testid="logging-s3-checkbox">
                S3
              </Checkbox>
            </SpaceBetween>
          </FormField>
          {!cwLogs && !s3 && (
            <Alert type="error">Logging이 없으면 quota·attribution이 깨집니다. 최소 하나를 선택하세요.</Alert>
          )}
          <FormField label="Data Retention (일)" constraintText="1–3653">
            <Input
              type="number"
              value={String(draft.bedrock_logging?.retention_days || 90)}
              onChange={({ detail }) =>
                updateDraft({ bedrock_logging: { ...draft.bedrock_logging, retention_days: Number(detail.value) || 90 } })
              }
              data-testid="retention-input"
            />
          </FormField>
        </SpaceBetween>
      </Container>

      <Container header={<Header variant="h2" description="여기서 설정하는 값은 전체 사용자에게 적용되는 기본(default) 정책입니다. 개별 사용자/그룹별 세분화 정책은 Fine-grained Quotas를 활성화한 뒤 DynamoDB QuotaPolicies 테이블에서 관리합니다.">Quota Monitoring</Header>}>
        <SpaceBetween size="m">
          <Toggle checked={quotaEnabled} onChange={({ detail }) => updateDraft({ quota: detail.checked ? { monthly_token_limit: 225000000, daily_token_limit: 0, burst_buffer_percent: 10, daily_enforcement: "alert", monthly_enforcement: "block" } : null })} data-testid="quota-toggle">
            Quota 활성화
          </Toggle>
          {quotaEnabled && draft.quota && (
            <SpaceBetween size="s">
              <FormField label="Monthly Token Limit">
                <Input type="number" value={String(draft.quota.monthly_token_limit || 225000000)} onChange={({ detail }) => updateDraft({ quota: { ...draft.quota!, monthly_token_limit: Number(detail.value) } })} data-testid="monthly-limit-input" />
              </FormField>
              <FormField label="Daily Enforcement">
                <Select selectedOption={{ value: (draft.quota.daily_enforcement as string) || "alert" }} onChange={({ detail }) => updateDraft({ quota: { ...draft.quota!, daily_enforcement: detail.selectedOption.value } })} options={[{ value: "alert", label: "Alert" }, { value: "block", label: "Block" }]} data-testid="daily-enforcement-select" />
              </FormField>
              <FormField label="Monthly Enforcement">
                <Select selectedOption={{ value: (draft.quota.monthly_enforcement as string) || "block" }} onChange={({ detail }) => updateDraft({ quota: { ...draft.quota!, monthly_enforcement: detail.selectedOption.value } })} options={[{ value: "alert", label: "Alert" }, { value: "block", label: "Block" }]} data-testid="monthly-enforcement-select" />
              </FormField>
            </SpaceBetween>
          )}
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}
