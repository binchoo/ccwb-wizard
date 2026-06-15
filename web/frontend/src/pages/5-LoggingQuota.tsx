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
import Button from "@cloudscape-design/components/button";
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

  // Quota helpers (quota is a free-form dict in the draft).
  const q = (draft.quota || {}) as Record<string, any>;
  const finegrained = !!q.enable_finegrained_quotas;
  const policies: any[] = Array.isArray(q.policies) ? q.policies : [];
  const emails: string[] = Array.isArray(q.alert_emails) ? q.alert_emails : [];
  const setQuota = (patch: Record<string, unknown>) => updateDraft({ quota: { ...(draft.quota || {}), ...patch } });
  const setPolicy = (idx: number, patch: Record<string, unknown>) =>
    setQuota({ policies: policies.map((p, i) => (i === idx ? { ...p, ...patch } : p)) });
  const addPolicy = () =>
    setQuota({ policies: [...policies, { type: "user", id: "", monthly_limit: 225000000, daily_limit: 0, enforcement: "block" }] });
  const removePolicy = (idx: number) => setQuota({ policies: policies.filter((_, i) => i !== idx) });

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

      <Container header={<Header variant="h2" description="기본(default) 정책은 전체 사용자에게 적용됩니다. Fine-grained Quotas를 켜면 User/Team/Dept별 개별 상한을 여기서 직접 할당하고, Deploy 시 QuotaPolicies 테이블에 주입합니다.">Quota Monitoring</Header>}>
        <SpaceBetween size="m">
          <Toggle checked={quotaEnabled} onChange={({ detail }) => updateDraft({ quota: detail.checked ? { monthly_token_limit: 225000000, daily_token_limit: 0, burst_buffer_percent: 10, daily_enforcement: "alert", monthly_enforcement: "block", enable_finegrained_quotas: false, alert_emails: [], policies: [] } : null })} data-testid="quota-toggle">
            Quota 활성화
          </Toggle>
          {quotaEnabled && draft.quota && (
            <SpaceBetween size="s">
              <FormField label="Monthly Token Limit (기본 정책)">
                <Input type="number" value={String(draft.quota.monthly_token_limit || 225000000)} onChange={({ detail }) => setQuota({ monthly_token_limit: Number(detail.value) })} data-testid="monthly-limit-input" />
              </FormField>
              <FormField label="Daily Token Limit (기본 정책, 0=비활성)">
                <Input type="number" value={String((draft.quota.daily_token_limit as number) ?? 0)} onChange={({ detail }) => setQuota({ daily_token_limit: Number(detail.value) })} data-testid="daily-limit-input" />
              </FormField>
              <FormField label="Daily Enforcement">
                <Select selectedOption={{ value: (draft.quota.daily_enforcement as string) || "alert" }} onChange={({ detail }) => setQuota({ daily_enforcement: detail.selectedOption.value })} options={[{ value: "alert", label: "Alert" }, { value: "block", label: "Block" }]} data-testid="daily-enforcement-select" />
              </FormField>
              <FormField label="Monthly Enforcement">
                <Select selectedOption={{ value: (draft.quota.monthly_enforcement as string) || "block" }} onChange={({ detail }) => setQuota({ monthly_enforcement: detail.selectedOption.value })} options={[{ value: "alert", label: "Alert" }, { value: "block", label: "Block" }]} data-testid="monthly-enforcement-select" />
              </FormField>

              <FormField label="알림 Email (SNS 구독, 쉼표로 구분)" description="Deploy 시 SNS 토픽에 구독되며, 각 주소로 확인 메일이 발송됩니다.">
                <Input
                  value={emails.join(", ")}
                  onChange={({ detail }) => setQuota({ alert_emails: detail.value.split(",").map((e) => e.trim()).filter(Boolean) })}
                  placeholder="ops@example.com, admin@example.com"
                  data-testid="alert-emails-input"
                />
              </FormField>

              <Toggle checked={finegrained} onChange={({ detail }) => setQuota({ enable_finegrained_quotas: detail.checked })} data-testid="finegrained-toggle">
                Fine-grained Quotas (User/Team/Dept별 개별 상한)
              </Toggle>

              {finegrained && (
                <SpaceBetween size="xs">
                  <Alert type="info">
                    Team/Dept 상한은 <strong>합산 집계</strong> 기준입니다 — 해당 팀/부서 구성원의 토큰 합계가 상한을 넘으면 enforcement가 block일 때 전원 차단됩니다.
                    Team/Dept identifier는 Attribution 매핑으로 도출된 값과 일치해야 합니다.
                  </Alert>
                  {policies.map((p, idx) => (
                    <SpaceBetween key={idx} size="xs" direction="horizontal">
                      <Select
                        selectedOption={{ value: p.type || "user", label: p.type || "user" }}
                        onChange={({ detail }) => setPolicy(idx, { type: detail.selectedOption.value })}
                        options={[{ value: "user", label: "user" }, { value: "team", label: "team" }, { value: "dept", label: "dept" }, { value: "default", label: "default" }]}
                        data-testid={`policy-type-${idx}`}
                      />
                      <Input value={String(p.id ?? "")} placeholder="identifier (예: alice@x.com / blue)" onChange={({ detail }) => setPolicy(idx, { id: detail.value })} data-testid={`policy-id-${idx}`} />
                      <Input type="number" value={String(p.monthly_limit ?? 0)} placeholder="monthly" onChange={({ detail }) => setPolicy(idx, { monthly_limit: Number(detail.value) })} data-testid={`policy-monthly-${idx}`} />
                      <Input type="number" value={String(p.daily_limit ?? 0)} placeholder="daily(0=off)" onChange={({ detail }) => setPolicy(idx, { daily_limit: Number(detail.value) })} data-testid={`policy-daily-${idx}`} />
                      <Select
                        selectedOption={{ value: p.enforcement || "block", label: p.enforcement || "block" }}
                        onChange={({ detail }) => setPolicy(idx, { enforcement: detail.selectedOption.value })}
                        options={[{ value: "alert", label: "alert" }, { value: "block", label: "block" }]}
                        data-testid={`policy-enforcement-${idx}`}
                      />
                      <Button onClick={() => removePolicy(idx)} data-testid={`policy-remove-${idx}`}>삭제</Button>
                    </SpaceBetween>
                  ))}
                  <Button onClick={addPolicy} iconName="add-plus" data-testid="policy-add">정책 추가</Button>
                </SpaceBetween>
              )}
            </SpaceBetween>
          )}
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}
