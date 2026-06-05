import { useEffect, useState } from "react";
import Container from "@cloudscape-design/components/container";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Alert from "@cloudscape-design/components/alert";
import ExpandableSection from "@cloudscape-design/components/expandable-section";
import ProgressBar from "@cloudscape-design/components/progress-bar";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import { useWizardStore } from "../store";
import {
  saveProfile,
  materializePreview,
  deployProfile,
  buildPackage,
} from "../api";

interface StackEvent {
  type: string;
  stack?: string;
  step?: number;
  total?: number;
  status?: string;
  message?: string;
  reason?: string;
  synced?: string[];
}

export default function ReviewPage() {
  const { draft } = useWizardStore();
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  // Deploy state
  const [deploying, setDeploying] = useState(false);
  const [deployEvents, setDeployEvents] = useState<StackEvent[]>([]);
  const [deployStatus, setDeployStatus] = useState<"idle" | "running" | "success" | "error">("idle");
  const [deployError, setDeployError] = useState("");

  // Package state
  const [packaging, setPackaging] = useState(false);
  const [packageResult, setPackageResult] = useState<Record<string, unknown> | null>(null);
  const [packageError, setPackageError] = useState("");

  useEffect(() => {
    if (draft.profile_name) {
      materializePreview(draft.profile_name).then(setPreview).catch(() => {});
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      await saveProfile(draft.profile_name, draft as unknown as Record<string, unknown>);
      setSaved(true);
      const p = await materializePreview(draft.profile_name);
      setPreview(p);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleDeploy = async () => {
    setDeploying(true);
    setDeployEvents([]);
    setDeployStatus("running");
    setDeployError("");

    try {
      const response = await deployProfile(draft.profile_name);
      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response stream");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const dataLine = line.trim();
          if (!dataLine.startsWith("data: ")) continue;
          const event: StackEvent = JSON.parse(dataLine.slice(6));
          setDeployEvents((prev) => [...prev, event]);
          if (event.type === "complete") setDeployStatus("success");
          if (event.type === "error") {
            setDeployStatus("error");
            setDeployError(event.message || "Unknown deploy error");
          }
        }
      }
    } catch (e) {
      setDeployStatus("error");
      setDeployError((e as Error).message);
    } finally {
      setDeploying(false);
    }
  };

  const handleRetryDeploy = () => {
    setDeployStatus("idle");
    setDeployEvents([]);
    setDeployError("");
  };

  const handlePackage = async () => {
    setPackaging(true);
    setPackageError("");
    try {
      const result = await buildPackage(draft.profile_name);
      setPackageResult(result as unknown as Record<string, unknown>);
    } catch (e) {
      setPackageError((e as Error).message);
    } finally {
      setPackaging(false);
    }
  };

  const lastProgressEvent = [...deployEvents].reverse().find((e) => e.type === "progress");
  const progress = lastProgressEvent?.step && lastProgressEvent?.total
    ? Math.round((lastProgressEvent.step / lastProgressEvent.total) * 100)
    : 0;

  // Count successful stacks for partial success display
  const successCount = deployEvents.filter(
    (e) => e.type === "progress" && (e.status?.includes("COMPLETE") || e.status === "NO_CHANGE")
  ).length;

  return (
    <SpaceBetween size="l">
      {/* Summary */}
      <Container header={<Header variant="h2">검토 및 배포</Header>}>
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
            <strong>Attribution:</strong>{" "}
            {draft.attribution?.mapping?.user ? `user←${draft.attribution.mapping.user}` : "미설정"}
            {draft.attribution?.mapping?.team ? `, team←${draft.attribution.mapping.team}` : ""}
          </Box>

          {preview && (
            <ExpandableSection headerText="Materialize Preview (CFN Stacks)">
              <pre style={{ fontSize: "12px", whiteSpace: "pre-wrap" }}>
                {JSON.stringify(preview, null, 2)}
              </pre>
            </ExpandableSection>
          )}

          {error && <Alert type="error" dismissible onDismiss={() => setError("")}>{error}</Alert>}
          {saved && <Alert type="success">프로필 저장 완료</Alert>}

          <Button variant="primary" onClick={handleSave} loading={saving} disabled={saved}>
            1. 프로필 저장
          </Button>
        </SpaceBetween>
      </Container>

      {/* Deploy */}
      <Container header={<Header variant="h2">인프라 배포 (CloudFormation)</Header>}>
        <SpaceBetween size="m">
          <Box variant="small" color="text-body-secondary">
            프로필 저장 후 AWS 계정에 인프라를 배포합니다. 5~15분 소요.
            이미 배포된 스택은 변경 사항이 없으면 건너뜁니다.
          </Box>

          <SpaceBetween size="s" direction="horizontal">
            <Button
              variant="primary"
              onClick={handleDeploy}
              loading={deploying}
              disabled={!saved || deployStatus === "running"}
            >
              {deployStatus === "error" ? "2. 재시도" : "2. Deploy"}
            </Button>
            {deployStatus === "error" && (
              <Button variant="link" onClick={handleRetryDeploy}>
                초기화
              </Button>
            )}
          </SpaceBetween>

          {/* Error alert with guidance */}
          {deployStatus === "error" && (
            <Alert type="error" header="배포 실패" dismissible onDismiss={handleRetryDeploy}>
              {deployError}
              {successCount > 0 && (
                <Box margin={{ top: "xs" }} variant="small">
                  ℹ️ {successCount}개 스택은 성공. 재시도 시 성공한 스택은 "NO_CHANGE"로 건너뜁니다.
                </Box>
              )}
            </Alert>
          )}

          {/* Progress */}
          {deployEvents.length > 0 && (
            <SpaceBetween size="xs">
              <ProgressBar
                value={deployStatus === "success" ? 100 : progress}
                status={deployStatus === "error" ? "error" : deployStatus === "success" ? "success" : "in-progress"}
                resultText={deployStatus === "success" ? "배포 완료" : deployStatus === "error" ? "실패" : undefined}
              />
              {deployEvents.map((ev, i) => (
                <Box key={i} variant="small">
                  {ev.type === "progress" && (
                    <StatusIndicator
                      type={
                        ev.status === "NO_CHANGE" ? "info" :
                        ev.status === "DEPLOYING" ? "in-progress" :
                        ev.status?.includes("COMPLETE") ? "success" :
                        ev.status?.includes("FAILED") ? "error" : "in-progress"
                      }
                    >
                      [{ev.step}/{ev.total}] {ev.stack} — {ev.status}
                      {ev.reason ? ` (${ev.reason})` : ""}
                    </StatusIndicator>
                  )}
                  {ev.type === "sync" && (
                    <StatusIndicator type="success">
                      🔗 프로필에 동기화: {ev.synced?.join(", ")}
                    </StatusIndicator>
                  )}
                  {ev.type === "complete" && (
                    <StatusIndicator type="success">{ev.message}</StatusIndicator>
                  )}
                </Box>
              ))}
            </SpaceBetween>
          )}
        </SpaceBetween>
      </Container>

      {/* Package */}
      <Container header={<Header variant="h2">배포 패키지 빌드</Header>}>
        <SpaceBetween size="m">
          <Box variant="small" color="text-body-secondary">
            개발자용 installer zip (credential-process 바이너리 + config.json + install.sh).
            Deploy 완료 후 사용 가능합니다.
          </Box>

          <Button
            variant="primary"
            onClick={handlePackage}
            loading={packaging}
            disabled={deployStatus !== "success"}
          >
            3. Package
          </Button>

          {deployStatus !== "success" && !packaging && !packageResult && (
            <Box variant="small" color="text-body-secondary">
              ⏳ Deploy가 완료되어야 Package를 빌드할 수 있습니다 (FederatedRoleArn이 필요).
            </Box>
          )}

          {packageError && (
            <Alert type="error" dismissible onDismiss={() => setPackageError("")}>
              {packageError}
            </Alert>
          )}

          {packageResult && (
            <Alert type="success" header="패키지 빌드 완료">
              <strong>Platform:</strong> {String(packageResult.platform)}<br />
              <strong>Size:</strong> {String(packageResult.zip_size_mb)} MB<br />
              <strong>경로:</strong> <code>{String(packageResult.zip_path)}</code><br />
              <strong>내용:</strong> {(packageResult.contents as string[])?.join(", ")}
            </Alert>
          )}
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}
