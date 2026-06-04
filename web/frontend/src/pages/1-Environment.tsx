import { useEffect, useState } from "react";
import Container from "@cloudscape-design/components/container";
import FormField from "@cloudscape-design/components/form-field";
import Select, { SelectProps } from "@cloudscape-design/components/select";
import Header from "@cloudscape-design/components/header";
import Alert from "@cloudscape-design/components/alert";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Button from "@cloudscape-design/components/button";
import { useWizardStore } from "../store";
import { getRegions } from "../api";

export default function EnvironmentPage() {
  const { draft, updateDraft } = useWizardStore();
  const [profiles, setProfiles] = useState<SelectProps.Option[]>([]);
  const [selectedProfile, setSelectedProfile] = useState<SelectProps.Option | null>(null);
  const [regions, setRegions] = useState<SelectProps.Option[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "expired" | "error">("idle");
  const [detail, setDetail] = useState("");

  useEffect(() => {
    // Load AWS profiles
    fetch("/api/aws/profiles")
      .then((r) => r.json())
      .then((data: Array<{ name: string; source: string }>) => {
        const opts = data.map((p) => ({
          value: p.name,
          label: p.name,
          description: p.source,
        }));
        opts.unshift({ value: "", label: "(기본 — 환경변수/default profile)", description: "" });
        setProfiles(opts);
      })
      .catch(() => setProfiles([{ value: "", label: "(기본)", description: "" }]));

    // Load regions
    getRegions()
      .then((r) => setRegions(r.map((v) => ({ value: v, label: v }))))
      .catch(() => {});
  }, []);

  const handleValidate = async () => {
    setStatus("loading");
    setDetail("");
    try {
      const res = await fetch("/api/aws/profiles/select", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_name: selectedProfile?.value || "" }),
      });
      const data = await res.json();
      if (data.status === "ok") {
        setStatus("ok");
        setDetail(`Account: ${data.account} | ${data.arn}`);
      } else if (data.status === "expired") {
        setStatus("expired");
        setDetail(data.detail);
      } else {
        setStatus("error");
        setDetail(data.detail || "Unknown error");
      }
    } catch (e) {
      setStatus("error");
      setDetail((e as Error).message);
    }
  };

  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">AWS 환경 설정</Header>}>
        <SpaceBetween size="m">
          <FormField
            label="AWS Profile"
            description="~/.aws/config 또는 ~/.aws/credentials에 정의된 named profile을 선택하세요."
            data-testid="aws-profile-field"
          >
            <Select
              selectedOption={selectedProfile}
              onChange={({ detail }) => {
                setSelectedProfile(detail.selectedOption);
                setStatus("idle");
              }}
              options={profiles}
              placeholder="AWS profile 선택"
              filteringType="auto"
              data-testid="aws-profile-select"
            />
          </FormField>

          <Button onClick={handleValidate} loading={status === "loading"} data-testid="validate-button">
            자격증명 확인
          </Button>

          {status === "ok" && (
            <StatusIndicator type="success" data-testid="cred-status-ok">
              {detail}
            </StatusIndicator>
          )}
          {status === "expired" && (
            <Alert type="warning" header="자격증명 만료" data-testid="cred-status-expired">
              {detail}
            </Alert>
          )}
          {status === "error" && (
            <Alert type="error" header="AWS 자격증명 확인 실패" data-testid="cred-status-error">
              {detail || "AWS_PROFILE 환경변수 또는 ~/.aws/credentials를 확인해주세요."}
            </Alert>
          )}

          <FormField
            label="AWS Region"
            description="CloudFormation 인프라 배포 리전. Cognito User Pool, IAM OIDC Provider, Quota DynamoDB 등이 이 리전에 생성됩니다. Bedrock 모델 호출 리전은 이후 'Bedrock Model' 단계에서 별도 결정합니다."
            data-testid="env-region-field"
          >
            <Select
              selectedOption={regions.find((o) => o.value === draft.aws_region) || null}
              onChange={({ detail }) => updateDraft({ aws_region: detail.selectedOption.value || "" })}
              options={regions}
              placeholder="리전 선택"
              filteringType="auto"
              data-testid="env-region-select"
            />
          </FormField>
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}
