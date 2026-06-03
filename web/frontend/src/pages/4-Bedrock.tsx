import { useEffect, useState } from "react";
import Container from "@cloudscape-design/components/container";
import FormField from "@cloudscape-design/components/form-field";
import Select, { SelectProps } from "@cloudscape-design/components/select";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { useWizardStore } from "../store";
import { getScenarios } from "../api";

type ModelData = Record<string, { name: string; profiles: string[]; source_regions: Record<string, string[]> }>;

export default function BedrockPage() {
  const { draft, updateDraft } = useWizardStore();
  const [models, setModels] = useState<ModelData>({});

  useEffect(() => {
    getScenarios().then((d) => setModels(d.models)).catch(() => {});
  }, []);

  const modelKeys = Object.keys(models);
  const selectedModelKey = modelKeys.find((k) => {
    const m = models[k];
    return Object.values(m.source_regions).flat().some(() =>
      draft.model_id.includes(k.replace(/-/g, ""))
    );
  }) || "";

  const selectedModel = models[selectedModelKey];
  const profileOptions: SelectProps.Option[] = selectedModel
    ? selectedModel.profiles.map((p) => ({ value: p, label: p.toUpperCase() }))
    : [];
  const sourceRegionOptions: SelectProps.Option[] =
    selectedModel && draft.cross_region_profile
      ? (selectedModel.source_regions[draft.cross_region_profile] || []).map((r) => ({ value: r, label: r }))
      : [];

  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">Bedrock 모델 선택</Header>}>
        <SpaceBetween size="m">
          <FormField label="Claude 모델" data-testid="model-field">
            <Select
              selectedOption={selectedModelKey ? { value: selectedModelKey, label: models[selectedModelKey]?.name } : null}
              onChange={({ detail }) => {
                const key = detail.selectedOption.value || "";
                const m = models[key];
                if (m && m.profiles.length > 0) {
                  const firstProfile = m.profiles[0];
                  const regions = m.source_regions[firstProfile] || [];
                  updateDraft({
                    model_id: `${firstProfile}.anthropic.${key.replace(/-/g, "-")}`,
                    cross_region_profile: firstProfile,
                    source_region: regions[0] || "",
                  });
                }
              }}
              options={modelKeys.map((k) => ({ value: k, label: models[k].name }))}
              placeholder="모델 선택"
              filteringType="auto"
              data-testid="model-select"
            />
          </FormField>

          <FormField label="Cross-Region Profile" data-testid="profile-field">
            <Select
              selectedOption={profileOptions.find((o) => o.value === draft.cross_region_profile) || null}
              onChange={({ detail }) => {
                const prof = detail.selectedOption.value || "";
                const regions = selectedModel?.source_regions[prof] || [];
                updateDraft({ cross_region_profile: prof, source_region: regions[0] || "" });
              }}
              options={profileOptions}
              placeholder="프로파일 선택"
              data-testid="profile-select"
            />
          </FormField>

          <FormField label="Source Region" data-testid="source-region-field">
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
    </SpaceBetween>
  );
}
