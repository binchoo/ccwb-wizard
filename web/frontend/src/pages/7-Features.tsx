import Container from "@cloudscape-design/components/container";
import Toggle from "@cloudscape-design/components/toggle";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { useWizardStore } from "../store";

export default function FeaturesPage() {
  const { draft, updateDraft } = useWizardStore();

  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">추가 기능</Header>}>
        <SpaceBetween size="m">
          <Toggle
            checked={draft.enable_codebuild_windows}
            onChange={({ detail }) => updateDraft({ enable_codebuild_windows: detail.checked })}
            data-testid="codebuild-toggle"
          >
            Windows 빌드 활성화 (AWS CodeBuild)
          </Toggle>
          <Toggle
            checked={draft.enable_cowork_3p}
            onChange={({ detail }) => updateDraft({ enable_cowork_3p: detail.checked })}
            data-testid="cowork-toggle"
          >
            Claude Cowork 3P MDM 설정 생성
          </Toggle>
          <Toggle
            checked={draft.enable_cc_telemetry}
            onChange={({ detail }) => updateDraft({ enable_cc_telemetry: detail.checked })}
            data-testid="telemetry-toggle"
          >
            Claude Code Telemetry 활성화
          </Toggle>
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}
