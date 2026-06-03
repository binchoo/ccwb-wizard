import Container from "@cloudscape-design/components/container";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import RadioGroup from "@cloudscape-design/components/radio-group";
import { useWizardStore } from "../store";

export default function ProfilePage() {
  const { draft, updateDraft, mode, setMode } = useWizardStore();

  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">프로필 선택</Header>}>
        <SpaceBetween size="m">
          <FormField label="모드">
            <RadioGroup
              value={mode}
              onChange={({ detail }) => setMode(detail.value as "new" | "edit" | "clone")}
              items={[
                { value: "new", label: "신규 프로필 생성" },
                { value: "edit", label: "기존 프로필 편집" },
                { value: "clone", label: "기존 프로필 복제" },
              ]}
            />
          </FormField>
          <FormField
            label="프로필 이름"
            constraintText="영문 소문자, 숫자, 하이픈만 가능 (1-64자)"
            data-testid="profile-name-field"
          >
            <Input
              value={draft.profile_name}
              onChange={({ detail }) => updateDraft({ profile_name: detail.value })}
              placeholder="my-production"
              data-testid="profile-name-input"
            />
          </FormField>
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}
