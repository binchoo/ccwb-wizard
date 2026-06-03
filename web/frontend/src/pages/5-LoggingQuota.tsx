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

      <Container header={<Header variant="h2">Quota Monitoring</Header>}>
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
