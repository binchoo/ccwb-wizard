import { useEffect, useState } from "react";
import Container from "@cloudscape-design/components/container";
import FormField from "@cloudscape-design/components/form-field";
import Select, { SelectProps } from "@cloudscape-design/components/select";
import Input from "@cloudscape-design/components/input";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { useWizardStore } from "../store";
import { getRegions } from "../api";

export default function InfraPage() {
  const { draft, updateDraft } = useWizardStore();
  const [regions, setRegions] = useState<SelectProps.Option[]>([]);

  useEffect(() => {
    getRegions().then((r) => setRegions(r.map((v) => ({ value: v, label: v })))).catch(() => {});
  }, []);

  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">AWS 인프라 설정</Header>}>
        <SpaceBetween size="m">
          <FormField label="AWS Region" data-testid="aws-region-field">
            <Select
              selectedOption={regions.find((o) => o.value === draft.aws_region) || null}
              onChange={({ detail }) => updateDraft({ aws_region: detail.selectedOption.value || "" })}
              options={regions}
              placeholder="인프라 배포 리전 선택"
              filteringType="auto"
              data-testid="aws-region-select"
            />
          </FormField>
          <FormField
            label="Stack Base Name"
            constraintText="영문 소문자, 숫자, 하이픈만 (≤32자). 모든 CFN 스택의 접두사로 사용됩니다."
            data-testid="stack-base-name-field"
          >
            <Input
              value={draft.stack_base_name}
              onChange={({ detail }) => updateDraft({ stack_base_name: detail.value })}
              placeholder="claude-code-auth"
              data-testid="stack-base-name-input"
            />
          </FormField>
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}
