/**
 * Root App component — Cloudscape Wizard with 10 steps (0-9).
 */

import Wizard, { WizardProps } from "@cloudscape-design/components/wizard";
import AppLayout from "@cloudscape-design/components/app-layout";
import Header from "@cloudscape-design/components/header";
import { useWizardStore } from "./store";
import { saveDraft } from "./api";

import ProfilePage from "./pages/0-Profile";
import EnvironmentPage from "./pages/1-Environment";
import ProviderPage from "./pages/2-Provider";
import InfraPage from "./pages/3-Infra";
import BedrockPage from "./pages/4-Bedrock";
import LoggingQuotaPage from "./pages/5-LoggingQuota";
import DistributionPage from "./pages/6-Distribution";
import FeaturesPage from "./pages/7-Features";
import TagsPage from "./pages/8-Tags";
import ReviewPage from "./pages/9-Review";
import DeployTestPage from "./pages/10-DeployTest";

const STEPS: WizardProps.Step[] = [
  { title: "프로필", description: "신규 생성, 기존 편집, 또는 복제 모드를 선택하고 프로필 이름을 결정합니다.", content: <ProfilePage /> },
  { title: "AWS 환경", description: "배포에 사용할 AWS 자격증명(named profile)과 인프라 배포 리전을 결정합니다.", content: <EnvironmentPage /> },
  { title: "Identity Provider", description: "사용자 인증에 사용할 OIDC IdP (Okta, Azure AD, Cognito, Auth0, Generic)를 선택하고 연결 정보를 입력합니다.", content: <ProviderPage /> },
  { title: "인프라 이름", description: "CloudFormation 스택의 공통 접두사(base name)를 결정합니다. 모든 스택이 이 이름으로 시작합니다.", content: <InfraPage /> },
  { title: "Bedrock 모델", description: "개발자가 사용할 Claude 모델과 cross-region inference 프로파일을 결정합니다. Source region은 모델 호출의 기점이며 인프라 리전과 다를 수 있습니다.", content: <BedrockPage /> },
  { title: "로깅 & 할당량", description: "Bedrock invocation 로깅 대상(CloudWatch Logs / S3)과 사용자별 토큰 할당량(quota) 기본 정책을 설정합니다. 여기서 설정하는 quota는 전체 사용자의 기본값이며, 개별 사용자/그룹별 세분화 정책은 'Enable Fine-grained Quotas' 활성화 후 별도 관리합니다.", content: <LoggingQuotaPage /> },
  { title: "배포 방식", description: "사용자에게 installer를 전달하는 방법을 결정합니다. Presigned S3 URL(간단) 또는 자체 호스팅 Landing Page(SSO 다운로드 포털) 중 선택합니다.", content: <DistributionPage /> },
  { title: "추가 기능", description: "Windows 빌드(CodeBuild), Claude Cowork 3P MDM 설정 생성, 텔레메트리 등 선택적 기능을 토글합니다.", content: <FeaturesPage /> },
  { title: "리소스 태그", description: "모든 CloudFormation 스택에 일괄 적용될 AWS 리소스 태그를 정의합니다. 비용 추적 및 거버넌스에 활용됩니다.", content: <TagsPage /> },
  { title: "검토 및 저장", description: "입력한 모든 설정을 검토하고 materialize 결과(CFN 파라미터, settings.json)를 미리 확인한 뒤 프로필로 저장합니다.", content: <ReviewPage /> },
  { title: "배포 및 테스트", description: "인프라 배포, 패키지 빌드, 로컬 테스트, 사용자 배포를 수행합니다.", content: <DeployTestPage />, isOptional: true },
];

export default function App() {
  const { currentStep, setStep, draft } = useWizardStore();

  const handleNavigate: WizardProps["onNavigate"] = async (event) => {
    const nextStep = event.detail.requestedStepIndex;
    // Auto-save draft on page transition
    if (draft.profile_name) {
      try {
        await saveDraft(draft.profile_name, draft as unknown as Record<string, unknown>);
      } catch {
        // Draft save failure is non-blocking (NFR-1)
      }
    }
    setStep(nextStep);
  };

  return (
    <AppLayout
      content={
        <Wizard
          i18nStrings={{
            stepNumberLabel: (stepNumber) => `단계 ${stepNumber}`,
            collapsedStepsLabel: (stepNumber, stepsCount) => `단계 ${stepNumber} / ${stepsCount}`,
            submitButton: "프로필 저장",
            previousButton: "이전",
            nextButton: "다음",
            cancelButton: "취소",
            optional: "선택사항",
          }}
          steps={STEPS}
          activeStepIndex={currentStep}
          onNavigate={handleNavigate}
          onSubmit={() => {
            // Final save handled by ReviewPage
          }}
          onCancel={() => {
            // Draft preserved, profile unaffected (Spec Req 1.7)
          }}
        />
      }
      headerSelector="#header"
      navigationHide
      toolsHide
      contentHeader={
        <Header variant="h1" description="Claude Code with Amazon Bedrock — 배포 환경 구성 위자드">
          ccwb
        </Header>
      }
    />
  );
}
