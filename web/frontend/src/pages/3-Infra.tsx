import Container from "@cloudscape-design/components/container";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Box from "@cloudscape-design/components/box";
import { useWizardStore } from "../store";

export default function InfraPage() {
  const { draft, updateDraft } = useWizardStore();

  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">AWS 인프라 설정</Header>}>
        <SpaceBetween size="m">
          <FormField label="인프라 배포 리전">
            <Box variant="p">
              <strong>{draft.aws_region || "(미선택 — Environment 단계에서 선택하세요)"}</strong>
            </Box>
          </FormField>

          <FormField
            label="Stack Base Name"
            description="모든 CloudFormation 스택의 접두사. 예: 'my-stack' → my-stack-auth, my-stack-bedrock-logging, my-stack-dashboard, ..."
            constraintText="영문 소문자, 숫자, 하이픈만 (≤32자)"
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
