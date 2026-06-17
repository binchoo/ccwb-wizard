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
import { deployProfile, buildPackage, distributePackage, getDeployStatus, startWindowsBuild, getWindowsBuildStatus } from "../api";

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

  // Distribute state (per artifact: current OS package vs windows package)
  const [distributing, setDistributing] = useState<string>("");
  const [distributeResult, setDistributeResult] = useState<Record<string, Record<string, unknown>>>({});
  const [distributeError, setDistributeError] = useState("");

  // Windows build (CodeBuild) state
  const [winBuilding, setWinBuilding] = useState(false);
  const [winStatus, setWinStatus] = useState<string>("");
  const [winResult, setWinResult] = useState<Record<string, unknown> | null>(null);
  const [winError, setWinError] = useState("");

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

  const handleDistribute = async (artifact: "current" | "windows") => {
    setDistributing(artifact);
    setDistributeError("");
    try {
      const result = await distributePackage(draft.profile_name, 48, artifact);
      setDistributeResult((prev) => ({ ...prev, [artifact]: result as unknown as Record<string, unknown> }));
    } catch (e) {
      setDistributeError((e as Error).message);
    } finally {
      setDistributing("");
    }
  };

  // Start the Windows CodeBuild and poll until it finishes (or fails).
  const handleWindowsBuild = async () => {
    setWinBuilding(true);
    setWinError("");
    setWinResult(null);
    setWinStatus("STARTING");
    try {
      await startWindowsBuild(draft.profile_name);
      // Poll every 15s. CodeBuild Windows builds take ~15-20 min.
      // eslint-disable-next-line no-constant-condition
      while (true) {
        await new Promise((r) => setTimeout(r, 15000));
        const s = await getWindowsBuildStatus(draft.profile_name);
        setWinStatus(s.status);
        if (["SUCCEEDED", "FAILED", "FAULT", "STOPPED", "TIMED_OUT"].includes(s.status)) {
          setWinResult(s as unknown as Record<string, unknown>);
          break;
        }
      }
    } catch (e) {
      setWinError((e as Error).message);
    } finally {
      setWinBuilding(false);
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

      {/* 2. Package (macOS/Linux) */}
      <Container header={<Header variant="h2">② macOS/Linux 패키지 빌드</Header>}>
        <SpaceBetween size="m">
          <Box variant="small" color="text-body-secondary">
            현재 OS용 credential-process 바이너리 + config.json + settings.json + <strong>install.sh</strong>를 담은
            자기완결 zip(<code>{draft.profile_name}-&lt;platform&gt;.zip</code>)을 빌드합니다. mac/Linux 유저는 이것만 받으면 됩니다.
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

      {/* 2-W. Windows package via CodeBuild (only when enabled) */}
      {draft.enable_codebuild_windows && (
        <Container header={<Header variant="h2">②-W Windows 패키지 빌드 (CodeBuild)</Header>}>
          <SpaceBetween size="m">
            <Box variant="small" color="text-body-secondary">
              Windows .exe를 클라우드(CodeBuild)에서 빌드(약 15–20분)한 뒤, .exe + config.json + settings.json + <strong>install.bat</strong>를
              담은 자기완결 <code>{draft.profile_name}-windows.zip</code>을 생성합니다. macOS 패키지와 독립이며, Deploy만 끝나면 실행됩니다.
            </Box>
            <Button onClick={handleWindowsBuild} loading={winBuilding}
              disabled={deployStatus !== "success"}>
              Windows 빌드 시작
            </Button>
            {deployStatus !== "success" && (
              <Box variant="small" color="text-body-secondary">⏳ Deploy 완료 후 사용 가능 (codebuild 스택 포함)</Box>
            )}
            {winBuilding && (
              <StatusIndicator type="in-progress">빌드 상태: {winStatus} — 폴링 중(15s 간격)…</StatusIndicator>
            )}
            {winError && <Alert type="error" dismissible onDismiss={() => setWinError("")}>{winError}</Alert>}
            {winResult && (
              winResult.status === "SUCCEEDED" ? (
                <Alert type="success" header="Windows 패키지 빌드 완료">
                  {winResult.merged
                    ? <>자기완결 패키지 생성: <code>{String(winResult.zip_path)}</code> ({String(winResult.zip_size_mb)} MB)</>
                    : <>빌드는 성공했으나 패키지 조립 실패: {String(winResult.message)}</>}
                </Alert>
              ) : (
                <Alert type="error" header={`Windows 빌드 ${String(winResult.status)}`}>
                  CodeBuild 콘솔에서 로그를 확인하세요. {String(winResult.message || "")}
                </Alert>
              )
            )}
          </SpaceBetween>
        </Container>
      )}

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
      {(packageResult || (draft.enable_codebuild_windows && winResult && winResult.status === "SUCCEEDED")) && (
        <Container header={<Header variant="h2">④ 패키지 배포 (Presigned URL)</Header>}>
          <SpaceBetween size="m">
            <Box variant="small" color="text-body-secondary">
              패키지를 S3에 업로드하고 시한부 다운로드 URL을 생성합니다 (기본 48시간). OS별로 따로 배포합니다.
            </Box>
            <SpaceBetween size="s" direction="horizontal">
              <Button variant="primary" onClick={() => handleDistribute("current")} loading={distributing === "current"}
                disabled={!packageResult}>
                macOS/Linux 패키지 배포
              </Button>
              {draft.enable_codebuild_windows && (
                <Button onClick={() => handleDistribute("windows")} loading={distributing === "windows"}
                  disabled={!(winResult && winResult.status === "SUCCEEDED")}>
                  Windows 패키지 배포
                </Button>
              )}
            </SpaceBetween>
            {!packageResult && (
              <Box variant="small" color="text-body-secondary">ℹ️ macOS/Linux 패키지는 ② 빌드 후 배포 버튼이 활성화됩니다.</Box>
            )}
            {draft.enable_codebuild_windows && !(winResult && winResult.status === "SUCCEEDED") && (
              <Box variant="small" color="text-body-secondary">⏳ Windows 패키지는 ②-W 빌드 완료 후 활성화됩니다.</Box>
            )}
            {distributeError && <Alert type="error" dismissible onDismiss={() => setDistributeError("")}>{distributeError}</Alert>}
            {(["current", "windows"] as const).map((art) =>
              distributeResult[art] ? (
                <Alert key={art} type="success" header={`${art === "windows" ? "Windows" : "macOS/Linux"} Presigned URL 생성 완료`}>
                  <Box variant="code">
                    <pre style={{ fontSize: "12px", wordBreak: "break-all", whiteSpace: "pre-wrap" }}>
                      {String(distributeResult[art].presigned_url)}
                    </pre>
                  </Box>
                  <Box margin={{ top: "xs" }} variant="small">
                    만료: {String(distributeResult[art].expiry_hours)}시간 | Platform: {String(distributeResult[art].platform)} | Size: {String(distributeResult[art].zip_size_mb)} MB
                  </Box>
                </Alert>
              ) : null
            )}
          </SpaceBetween>
        </Container>
      )}
    </SpaceBetween>
  );
}
