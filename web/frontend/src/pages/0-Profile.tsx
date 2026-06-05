import { useEffect, useState } from "react";
import Container from "@cloudscape-design/components/container";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import RadioGroup from "@cloudscape-design/components/radio-group";
import Select from "@cloudscape-design/components/select";
import Alert from "@cloudscape-design/components/alert";
import { useWizardStore, ConfigDraft } from "../store";
import { listProfiles, getProfile } from "../api";

export default function ProfilePage() {
  const { draft, updateDraft, mode, setMode } = useWizardStore();
  const [profiles, setProfiles] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    listProfiles().then(setProfiles).catch(() => {});
  }, []);

  const handleLoadProfile = async (name: string) => {
    if (!name) return;
    setLoading(true);
    setError("");
    try {
      const data = await getProfile(name);
      // Merge loaded profile into draft
      updateDraft(data as Partial<ConfigDraft>);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

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

          {(mode === "edit" || mode === "clone") && profiles.length > 0 ? (
            <FormField label="기존 프로필 선택" data-testid="profile-select-field">
              <Select
                selectedOption={
                  draft.profile_name
                    ? { value: draft.profile_name, label: draft.profile_name }
                    : null
                }
                onChange={({ detail }) => {
                  const name = detail.selectedOption.value || "";
                  updateDraft({ profile_name: name });
                  handleLoadProfile(name);
                }}
                options={profiles.map((p) => ({ value: p, label: p }))}
                placeholder="프로필을 선택하세요"
                loadingText="불러오는 중..."
                statusType={loading ? "loading" : "finished"}
              />
            </FormField>
          ) : (
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
          )}

          {error && <Alert type="error">{error}</Alert>}
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}
