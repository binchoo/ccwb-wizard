import { useEffect, useState } from "react";
import Container from "@cloudscape-design/components/container";
import FormField from "@cloudscape-design/components/form-field";
import Select, { SelectProps } from "@cloudscape-design/components/select";
import Input from "@cloudscape-design/components/input";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import ExpandableSection from "@cloudscape-design/components/expandable-section";
import { useWizardStore } from "../store";
import { getScenarios } from "../api";

type ModelData = Record<string, { name: string; profiles: string[]; source_regions: Record<string, string[]> }>;

const TIERS = [
  { key: "sonnet", label: "Sonnet (기본 — 대부분의 개발 작업)", required: true },
  { key: "haiku", label: "Haiku (빠른 응답 — autocomplete 등)", required: false },
  { key: "opus", label: "Opus (복잡한 추론 — 아키텍처 설계 등)", required: false },
] as const;

export default function BedrockPage() {
  const { draft, updateDraft } = useWizardStore();
  const [allModels, setAllModels] = useState<ModelData>({});

  useEffect(() => {
    getScenarios().then((d) => setAllModels(d.models)).catch(() => {});
  }, []);

  const getModelOptionsForTier = (tier: string): SelectProps.Option[] => {
    return Object.entries(allModels)
      .filter(([key]) => key.includes(tier))
      .map(([key, m]) => ({ value: key, label: m.name }));
  };

  // Cross-region profile options — derived from the first selected tier model
  const firstSelectedModelKey = Object.values(draft.models)
    .filter(Boolean)
    .map((mid) => Object.keys(allModels).find((k) => mid.includes(`claude-${k}`)))
    .find(Boolean) || "";

  const selectedModelData = firstSelectedModelKey ? allModels[firstSelectedModelKey] : null;
  const profileOptions: SelectProps.Option[] = selectedModelData
    ? selectedModelData.profiles.map((p) => ({ value: p, label: p.toUpperCase() }))
    : [];

  // Source region options based on selected profile
  const sourceRegionOptions: SelectProps.Option[] =
    selectedModelData && draft.cross_region_profile
      ? (selectedModelData.source_regions[draft.cross_region_profile] || []).map((r) => ({ value: r, label: r }))
      : [];

  const findModelKeyByModelId = (modelId: string): string => {
    for (const [key] of Object.entries(allModels)) {
      if (modelId && modelId.includes(key.replace(/-/g, "-"))) return key;
    }
    return "";
  };

  const buildModelId = (modelKey: string, profile: string): string => {
    if (!modelKey || !allModels[modelKey]) return "";
    return `${profile}.anthropic.claude-${modelKey}`;
  };

  const handleTierModelChange = (tier: string, modelKey: string) => {
    const profile = draft.cross_region_profile || "us";
    const modelId = buildModelId(modelKey, profile);
    updateDraft({ models: { ...draft.models, [tier]: modelId } });
  };

  const handleProfileChange = (profile: string) => {
    // Update all selected models to use new profile
    const newModels = { ...draft.models };
    for (const [tier, currentModelId] of Object.entries(newModels)) {
      if (currentModelId) {
        const key = findModelKeyByModelId(currentModelId);
        if (key) {
          newModels[tier] = buildModelId(key, profile);
        }
      }
    }
    const regions = selectedModelData?.source_regions[profile] || [];
    updateDraft({ models: newModels, cross_region_profile: profile, source_region: regions[0] || "" });
  };

  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">Tier별 모델 선택</Header>} >
        <SpaceBetween size="m">
          {TIERS.map((tier) => {
            const tierOptions = getModelOptionsForTier(tier.key);
            return (
            <FormField
              key={tier.key}
              label={tier.label}
              constraintText={tier.required ? "필수" : "선택사항 — 비워두면 Sonnet과 동일 모델 사용"}
              data-testid={`model-${tier.key}-field`}
            >
              <Select
                selectedOption={
                  draft.models[tier.key]
                    ? tierOptions.find((o) => draft.models[tier.key]?.includes(o.value!.replace(/-/g, "-"))) || { value: "", label: draft.models[tier.key] }
                    : null
                }
                onChange={({ detail }) => handleTierModelChange(tier.key, detail.selectedOption.value || "")}
                options={tierOptions}
                placeholder={tier.required ? "모델 선택 (필수)" : "모델 선택 (선택사항)"}
                data-testid={`model-${tier.key}-select`}
              />
            </FormField>
            );
          })}
        </SpaceBetween>
      </Container>

      <Container header={<Header variant="h2">Cross-Region Inference</Header>}>
        <SpaceBetween size="m">
          <FormField label="Cross-Region Profile" description="선택한 모델들이 라우팅되는 지역 범위. 데이터 레지던시 요구에 맞춰 선택하세요." data-testid="profile-field">
            <Select
              selectedOption={profileOptions.find((o) => o.value === draft.cross_region_profile) || null}
              onChange={({ detail }) => handleProfileChange(detail.selectedOption.value || "")}
              options={profileOptions}
              placeholder="프로파일 선택"
              data-testid="profile-select"
            />
          </FormField>

          <FormField label="Source Region" description="Bedrock 모델 호출의 기점 리전. 인프라 배포 리전과 다를 수 있습니다." data-testid="source-region-field">
            <Select
              selectedOption={sourceRegionOptions.find((o) => o.value === draft.source_region) || null}
              onChange={({ detail }) => updateDraft({ source_region: detail.selectedOption.value || "" })}
              options={sourceRegionOptions}
              placeholder="소스 리전 선택"
              data-testid="source-region-select"
            />
          </FormField>
        </SpaceBetween>
      </Container>

      <ExpandableSection
        headerText="Application Inference Profile ARN (선택사항)"
        headerDescription="빌링/quota 분리가 필요한 경우에만 설정합니다. 비워두면 기본 모델을 그대로 사용합니다."
        data-testid="inference-profile-section"
      >
        <Container>
          <SpaceBetween size="s">
            <FormField label="Opus tier ARN" constraintText="비워두면 skip">
              <Input
                value={draft.inference_profiles?.opus || ""}
                onChange={({ detail }) => updateDraft({ inference_profiles: { ...draft.inference_profiles, opus: detail.value || null } })}
                placeholder="arn:aws:bedrock:...:application-inference-profile/..."
                data-testid="arn-opus-input"
              />
            </FormField>
            <FormField label="Sonnet tier ARN" constraintText="비워두면 skip">
              <Input
                value={draft.inference_profiles?.sonnet || ""}
                onChange={({ detail }) => updateDraft({ inference_profiles: { ...draft.inference_profiles, sonnet: detail.value || null } })}
                placeholder="arn:aws:bedrock:...:application-inference-profile/..."
                data-testid="arn-sonnet-input"
              />
            </FormField>
            <FormField label="Haiku tier ARN" constraintText="비워두면 skip">
              <Input
                value={draft.inference_profiles?.haiku || ""}
                onChange={({ detail }) => updateDraft({ inference_profiles: { ...draft.inference_profiles, haiku: detail.value || null } })}
                placeholder="arn:aws:bedrock:...:application-inference-profile/..."
                data-testid="arn-haiku-input"
              />
            </FormField>
          </SpaceBetween>
        </Container>
      </ExpandableSection>
    </SpaceBetween>
  );
}
