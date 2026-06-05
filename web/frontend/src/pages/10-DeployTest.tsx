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
import { deployProfile, buildPackage, distributePackage, getDeployStatus } from "../api";

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

export default function DeployTestPage() {
  const { draft } = useWizardStore();

  // Deploy state
  const [deploying, setDeploying] = useState(false);
  const [deployEvents, setDeployEvents] = useState<StackEvent[]>([]);
  const [deployStatus, setDeployStatus] = useState<"idle" | "running" | "success" | "error">("idle");
  const [deployError, setDeployError] = useState("");

  // Check existing stack status on mount
  useEffect(() => {
    if (!draft.profile_name) return;
    getDeployStatus(draft.profile_name).then((stacks) => {
      const allDeployed = stacks.length > 0 && stacks.every(
        (s) => s.status === "CREATE_COMPLETE" || s.status === "UPDATE_COMPLETE"
      );
      if (allDeployed) {
        setDeployStatus("success");
        setDeployEvents(stacks.map((s, i) => ({
          type: "progress", stack: s.stack_name,
          step: i + 1, total: stacks.length, status: s.status,
        })));
      }
    }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Package state
  const [packaging, setPackaging] = useState(false);
  const [packageResult, setPackageResult] = useState<Record<string, unknown> | null>(null);
  const [packageError, setPackageError] = useState("");

  // Distribute state
  const [distributing, setDistributing] = useState(false);
  const [distributeResult, setDistributeResult] = useState<Record<string, unknown> | null>(null);
  const [distributeError, setDistributeError] = useState("");

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

  const handleDistribute = async () => {
    setDistributing(true);
    setDistributeError("");
    try {
      const result = await distributePackage(draft.profile_name);
      setDistributeResult(result as unknown as Record<string, unknown>);
    } catch (e) {
      setDistributeError((e as Error).message);
    } finally {
      setDistributing(false);
    }
  };

  const lastProgressEvent = [...deployEvents].reverse().find((e) => e.type === "progress");
  const progress = lastProgressEvent?.step && lastProgressEvent?.total
    ? Math.round((lastProgressEvent.step / lastProgressEvent.total) * 100) : 0;
  const successCount = deployEvents.filter(
    (e) => e.type === "progress" && (e.status?.includes("COMPLETE") || e.status === "NO_CHANGE")
  ).length;

  return (
    <SpaceBetween size="l">
      {/* 1. Deploy */}
      <Container header={<Header variant="h2">① 인프라 배포 (CloudFormation)</Header>}>
        <SpaceBetween size="m">
          <Box variant="small" color="text-body-secondary">
            AWS 계정에 인프라를 배포합니다. 이미 배포된 스택은 변경 없으면 건너뜁니다.
          </Box>
          <SpaceBetween size="s" direction="horizontal">
            <Button variant="primary" onClick={handleDeploy} loading={deploying}
              disabled={deployStatus === "running"}>
              {deployStatus === "error" ? "재시도" : "Deploy"}
            </Button>
            {deployStatus === "error" && (
              <Button variant="link" onClick={() => { setDeployStatus("idle"); setDeployEvents([]); setDeployError(""); }}>초기화</Button>
            )}
          </SpaceBetween>
          {deployStatus === "error" && (
            <Alert type="error" header="배포 실패" dismissible onDismiss={() => setDeployError("")}>
              {deployError}
              {successCount > 0 && <Box margin={{ top: "xs" }} variant="small">ℹ️ {successCount}개 스택 성공. 재시도 시 건너뜁니다.</Box>}
            </Alert>
          )}
          {deployEvents.length > 0 && (
            <SpaceBetween size="xs">
              <ProgressBar value={deployStatus === "success" ? 100 : progress}
                status={deployStatus === "error" ? "error" : deployStatus === "success" ? "success" : "in-progress"}
                resultText={deployStatus === "success" ? "배포 완료" : deployStatus === "error" ? "실패" : undefined} />
              {deployEvents.map((ev, i) => (
                <Box key={i} variant="small">
                  {ev.type === "progress" && (
                    <StatusIndicator type={ev.status === "NO_CHANGE" ? "info" : ev.status === "DEPLOYING" ? "in-progress" : ev.status?.includes("COMPLETE") ? "success" : ev.status?.includes("FAILED") ? "error" : ev.status?.includes("SKIPPED") ? "info" : "in-progress"}>
                      [{ev.step}/{ev.total}] {ev.stack} — {ev.status}{ev.reason ? ` (${ev.reason})` : ""}
                    </StatusIndicator>
                  )}
                  {ev.type === "sync" && <StatusIndicator type="success">🔗 프로필 동기화: {ev.synced?.join(", ")}</StatusIndicator>}
                  {ev.type === "complete" && <StatusIndicator type="success">{ev.message}</StatusIndicator>}
                </Box>
              ))}
            </SpaceBetween>
          )}
        </SpaceBetween>
      </Container>

      {/* 2. Package */}
      <Container header={<Header variant="h2">② 패키지 빌드</Header>}>
        <SpaceBetween size="m">
          <Box variant="small" color="text-body-secondary">
            credential-process 바이너리 + config.json + install.sh를 zip으로 빌드합니다.
          </Box>
          <Button variant="primary" onClick={handlePackage} loading={packaging}
            disabled={deployStatus !== "success"}>
            Package
          </Button>
          {deployStatus !== "success" && !packageResult && (
            <Box variant="small" color="text-body-secondary">⏳ Deploy 완료 후 사용 가능</Box>
          )}
          {packageError && <Alert type="error" dismissible onDismiss={() => setPackageError("")}>{packageError}</Alert>}
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

      {/* 3. Local Test */}
      {packageResult && (
        <Container header={<Header variant="h2">③ 로컬 테스트</Header>}>
          <SpaceBetween size="m">
            <ExpandableSection headerText="테스트 절차" defaultExpanded>
              <Box variant="code">
                <pre style={{ fontSize: "13px", whiteSpace: "pre-wrap", lineHeight: 1.6 }}>
{`# 1. 패키지 압축 해제
cd ${String(packageResult.dist_dir)}

# 2. install.sh 실행
./install.sh

# 3. 첫 인증 (브라우저 OIDC 로그인)
~/claude-code-with-bedrock/credential-process --profile ${draft.profile_name}

# 4. settings.json 확인 (attribution 헤더)
cat ~/.claude/settings.json | python3 -m json.tool

# 5. Claude Code 실행
claude

# 6. Bedrock invocation log 확인
aws logs filter-log-events \\
  --log-group-name /aws/bedrock/invocation-logs \\
  --filter-pattern '{ $.requestMetadata.user = "*" }' \\
  --limit 3 --region ${draft.aws_region} \\
  --query 'events[].message' --output text | python3 -m json.tool`}
                </pre>
              </Box>
              <Alert type="info" header="검증 포인트">
                <strong>Step 4:</strong> ANTHROPIC_CUSTOM_HEADERS에 매핑된 키(user, team, sub)가 보여야 함<br />
                <strong>Step 6:</strong> requestMetadata.user = 내 이메일
              </Alert>
            </ExpandableSection>
          </SpaceBetween>
        </Container>
      )}

      {/* 4. Distribute */}
      {packageResult && (
        <Container header={<Header variant="h2">④ 패키지 배포 (Presigned URL)</Header>}>
          <SpaceBetween size="m">
            <Box variant="small" color="text-body-secondary">
              패키지를 S3에 업로드하고 시한부 다운로드 URL을 생성합니다 (기본 48시간).
            </Box>
            <Button variant="primary" onClick={handleDistribute} loading={distributing}>
              Distribute
            </Button>
            {distributeError && <Alert type="error" dismissible onDismiss={() => setDistributeError("")}>{distributeError}</Alert>}
            {distributeResult && (
              <Alert type="success" header="Presigned URL 생성 완료">
                <Box variant="code">
                  <pre style={{ fontSize: "12px", wordBreak: "break-all", whiteSpace: "pre-wrap" }}>
                    {String(distributeResult.presigned_url)}
                  </pre>
                </Box>
                <Box margin={{ top: "xs" }} variant="small">
                  만료: {String(distributeResult.expiry_hours)}시간 | Platform: {String(distributeResult.platform)} | Size: {String(distributeResult.zip_size_mb)} MB
                </Box>
              </Alert>
            )}
          </SpaceBetween>
        </Container>
      )}
    </SpaceBetween>
  );
}
