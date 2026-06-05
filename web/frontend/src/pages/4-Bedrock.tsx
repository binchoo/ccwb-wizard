import { useEffect, useState } from "react";
import Container from "@cloudscape-design/components/container";
import FormField from "@cloudscape-design/components/form-field";
import Select, { SelectProps } from "@cloudscape-design/components/select";
import Input from "@cloudscape-design/components/input";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import ExpandableSection from "@cloudscape-design/components/expandable-section";
import Alert from "@cloudscape-design/components/alert";
import { useWizardStore } from "../store";

interface TierOption {
  tier: string;
  model_id: string;
  display_name: string;
  profile_key: string;
  base_model_name: string;
}

type TierBuckets = Record<"haiku" | "sonnet" | "opus", TierOption[]>;

const TIERS = [
  {
    key: "sonnet" as const,
    label: "Sonnet — 기본 (대부분의 개발 작업)",
    required: true,
  },
  {
    key: "haiku" as const,
    label: "Haiku — 빠른 응답 (autocomplete 등)",
    required: false,
  },
  {
    key: "opus" as const,
    label: "Opus — 복잡한 추론 (아키텍처 설계 등)",
    required: false,
  },
];

export default function BedrockPage() {
  const { draft, updateDraft } = useWizardStore();
  const [regions, setRegions] = useState<string[]>([]);
  const [tierBuckets, setTierBuckets] = useState<TierBuckets>({
    haiku: [],
    sonnet: [],
    opus: [],
  });
  const [loading, setLoading] = useState(false);

  // 1) Load all invocable source regions on mount.
  useEffect(() => {
    fetch("/api/scenarios/source-regions")
      .then((r) => r.json())
      .then((rs: string[]) => setRegions(rs))
      .catch(() => setRegions([]));
  }, []);

  // 2) When source_region changes, load tier options for that region.
  useEffect(() => {
    if (!draft.source_region) {
      setTierBuckets({ haiku: [], sonnet: [], opus: [] });
      return;
    }
    setLoading(true);
    fetch(`/api/scenarios/tier-options?region=${encodeURIComponent(draft.source_region)}`)
      .then((r) => r.json())
      .then((data: TierBuckets) => setTierBuckets(data))
      .catch(() => setTierBuckets({ haiku: [], sonnet: [], opus: [] }))
      .finally(() => setLoading(false));
  }, [draft.source_region]);

  // 3) When source_region changes and the previously-selected model_id is no
  //    longer in the new tier bucket, clear it. This avoids an invalid stale
  //    selection silently surviving across region changes.
  useEffect(() => {
    if (!draft.source_region) return;
    // Skip stale check while buckets are still loading (all empty)
    const hasAnyOptions = Object.values(tierBuckets).some((arr) => arr.length > 0);
    if (!hasAnyOptions) return;

    const updated: Record<string, string> = { ...draft.models };
    let changed = false;
    for (const t of TIERS) {
      const current = draft.models[t.key];
      if (!current) continue;
      const ok = tierBuckets[t.key].some((o) => o.model_id === current);
      if (!ok) {
        updated[t.key] = "";
        changed = true;
      }
    }
    if (changed) updateDraft({ models: updated });
    // We only want this to fire when buckets change after a region switch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tierBuckets]);

  const regionOptions: SelectProps.Option[] = regions.map((r) => ({
    value: r,
    label: r,
  }));

  const buildTierOptions = (tier: keyof TierBuckets): SelectProps.Option[] =>
    tierBuckets[tier].map((o) => ({
      value: o.model_id,
      label: o.display_name,
      description: o.model_id,
    }));

  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">Bedrock 모델 호출 설정</Header>}>
        <SpaceBetween size="m">
          <Alert type="info">
            <strong>Source Region</strong>은 Bedrock 모델 호출의 기점입니다.
            인프라 배포 리전(Environment 단계의 AWS Region)과 다를 수 있습니다.
            Region을 먼저 선택하면 해당 region에서 호출 가능한
            Cross-Region Inference Profile들이 tier별 드롭다운에 표시됩니다.
          </Alert>

          <FormField
            label="Source Region"
            description="Bedrock 모델 invocation의 기점 AWS 리전"
            data-testid="source-region-field"
          >
            <Select
              selectedOption={
                regionOptions.find((o) => o.value === draft.source_region) || null
              }
              onChange={({ detail }) =>
                updateDraft({ source_region: detail.selectedOption.value || "" })
              }
              options={regionOptions}
              placeholder="소스 리전 선택"
              filteringType="auto"
              empty="가용한 리전이 없습니다"
              data-testid="source-region-select"
            />
          </FormField>
        </SpaceBetween>
      </Container>

      <Container header={<Header variant="h2">Tier별 모델 선택</Header>}>
        <SpaceBetween size="m">
          {!draft.source_region && (
            <Alert type="warning">
              먼저 Source Region을 선택하세요. 리전에 따라 사용 가능한
              Inference Profile이 달라집니다.
            </Alert>
          )}

          {TIERS.map((tier) => {
            const opts = buildTierOptions(tier.key);
            const empty = draft.source_region && opts.length === 0;
            return (
              <FormField
                key={tier.key}
                label={tier.label}
                constraintText={
                  tier.required
                    ? "필수"
                    : "선택사항 — 비워두면 Sonnet과 동일 모델 사용"
                }
                errorText={
                  empty
                    ? `이 region에서 호출 가능한 ${tier.key.toUpperCase()} 모델이 없습니다`
                    : undefined
                }
                data-testid={`model-${tier.key}-field`}
              >
                <Select
                  selectedOption={
                    opts.find((o) => o.value === draft.models[tier.key]) || null
                  }
                  onChange={({ detail }) => {
                    const newModelId = detail.selectedOption.value || "";
                    const picked = tierBuckets[tier.key].find(
                      (o) => o.model_id === newModelId,
                    );
                    // Persist the chosen model_id and also the derived
                    // cross_region_profile (used by domain Config / CFN params).
                    // We use the profile of the most-recently selected tier as
                    // a representative — all tiers in a single Config
                    // historically shared one profile_key. If the user picks
                    // mixed profiles across tiers, the LAST one wins for the
                    // shared cross_region_profile field.
                    updateDraft({
                      models: {
                        ...draft.models,
                        [tier.key]: newModelId,
                      },
                      cross_region_profile: picked?.profile_key || draft.cross_region_profile,
                    });
                  }}
                  options={opts}
                  placeholder={
                    !draft.source_region
                      ? "Region을 먼저 선택하세요"
                      : empty
                      ? "가용 모델 없음"
                      : tier.required
                      ? "모델 선택 (필수)"
                      : "모델 선택 (선택사항)"
                  }
                  disabled={!draft.source_region || loading}
                  data-testid={`model-${tier.key}-select`}
                />
              </FormField>
            );
          })}
        </SpaceBetween>
      </Container>

      <ExpandableSection
        headerText="Application Inference Profile ARN (선택사항)"
        headerDescription="빌링/quota 분리가 필요한 경우에만 설정합니다. 비워두면 기본 모델을 그대로 사용합니다."
        data-testid="inference-profile-section"
      >
        <Container>
          <SpaceBetween size="s">
            {(["sonnet", "haiku", "opus"] as const).map((tier) => (
              <FormField
                key={tier}
                label={`${tier} tier ARN`}
                constraintText="비워두면 skip"
              >
                <Input
                  value={draft.inference_profiles?.[tier] || ""}
                  onChange={({ detail }) =>
                    updateDraft({
                      inference_profiles: {
                        ...draft.inference_profiles,
                        [tier]: detail.value || null,
                      },
                    })
                  }
                  placeholder="arn:aws:bedrock:...:application-inference-profile/..."
                  data-testid={`arn-${tier}-input`}
                />
              </FormField>
            ))}
          </SpaceBetween>
        </Container>
      </ExpandableSection>
    </SpaceBetween>
  );
}
