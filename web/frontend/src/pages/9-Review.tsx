import { useEffect, useState } from "react";
import Container from "@cloudscape-design/components/container";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Alert from "@cloudscape-design/components/alert";
import ExpandableSection from "@cloudscape-design/components/expandable-section";
import { useWizardStore } from "../store";
import { saveProfile, materializePreview } from "../api";

export default function ReviewPage() {
  const { draft } = useWizardStore();
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (draft.profile_name) {
      // Save draft first, then materialize preview
      saveProfile(draft.profile_name, draft as unknown as Record<string, unknown>)
        .then(() => materializePreview(draft.profile_name))
        .then(setPreview)
        .catch((e) => setError(e.message));
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveProfile(draft.profile_name, draft as unknown as Record<string, unknown>);
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">검토 및 저장</Header>}>
        <SpaceBetween size="m">
          <Box variant="p">
            <strong>프로필:</strong> {draft.profile_name}<br />
            <strong>Region:</strong> {draft.aws_region}<br />
            <strong>Stack:</strong> {draft.stack_base_name}<br />
            <strong>Provider:</strong> {(draft.provider?.type as string) || "미선택"}<br />
            <strong>Model:</strong> {draft.models?.sonnet || "미선택"} (Sonnet)<br />
            <strong>Logging:</strong> {draft.bedrock_logging?.destination || "미선택"}<br />
            <strong>Quota:</strong> {draft.quota ? "활성" : "비활성"}<br />
            <strong>Distribution:</strong> {(draft.distribution?.type as string) || "비활성"}<br />
          </Box>

          {preview && (
            <ExpandableSection headerText="Materialize Preview (CFN Stacks)" data-testid="materialize-preview">
              <pre style={{ fontSize: "12px", whiteSpace: "pre-wrap" }}>
                {JSON.stringify(preview, null, 2)}
              </pre>
            </ExpandableSection>
          )}

          {error && <Alert type="error">{error}</Alert>}
          {saved && <Alert type="success">프로필이 저장되었습니다: ~/.ccwb/profiles/{draft.profile_name}.json</Alert>}

          <Button variant="primary" onClick={handleSave} loading={saving} disabled={saved} data-testid="save-profile-button">
            프로필 저장
          </Button>
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}
