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

const STEPS: WizardProps.Step[] = [
  { title: "Profile", content: <ProfilePage /> },
  { title: "Environment", content: <EnvironmentPage /> },
  { title: "Provider", content: <ProviderPage /> },
  { title: "Infrastructure", content: <InfraPage /> },
  { title: "Bedrock Model", content: <BedrockPage /> },
  { title: "Logging & Quota", content: <LoggingQuotaPage /> },
  { title: "Distribution", content: <DistributionPage /> },
  { title: "Features", content: <FeaturesPage /> },
  { title: "Tags", content: <TagsPage /> },
  { title: "Review", content: <ReviewPage /> },
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
