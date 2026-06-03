import { useEffect, useState } from "react";
import Container from "@cloudscape-design/components/container";
import Header from "@cloudscape-design/components/header";
import Alert from "@cloudscape-design/components/alert";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import SpaceBetween from "@cloudscape-design/components/space-between";

export default function EnvironmentPage() {
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    fetch("/api/health")
      .then((r) => {
        if (r.ok) setStatus("ok");
        else throw new Error(`HTTP ${r.status}`);
      })
      .catch((e) => {
        setStatus("error");
        setErrorMsg(e.message);
      });
  }, []);

  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">환경 확인</Header>}>
        <SpaceBetween size="m">
          {status === "loading" && <StatusIndicator type="loading">AWS 자격증명 확인 중...</StatusIndicator>}
          {status === "ok" && <StatusIndicator type="success">Backend 연결 정상</StatusIndicator>}
          {status === "error" && (
            <Alert type="error" header="AWS 자격증명 확인 실패">
              {errorMsg || "AWS_PROFILE 환경변수 또는 ~/.aws/credentials를 확인해주세요."}
            </Alert>
          )}
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}
