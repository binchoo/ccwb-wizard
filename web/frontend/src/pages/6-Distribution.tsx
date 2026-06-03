import Container from "@cloudscape-design/components/container";
import FormField from "@cloudscape-design/components/form-field";
import RadioGroup from "@cloudscape-design/components/radio-group";
import Input from "@cloudscape-design/components/input";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { useWizardStore } from "../store";

export default function DistributionPage() {
  const { draft, updateDraft } = useWizardStore();
  const distType = (draft.distribution?.type as string) || "none";

  const setDistType = (type: string) => {
    if (type === "none") updateDraft({ distribution: null });
    else if (type === "presigned-s3") updateDraft({ distribution: { type: "presigned-s3" } });
    else updateDraft({ distribution: { type: "landing-page", vpc_id: "", public_subnets: [], private_subnets: [], idp_provider: "", idp_config: {}, custom_domain: "" } });
  };

  const updateDist = (key: string, value: unknown) => {
    updateDraft({ distribution: { ...draft.distribution, [key]: value } });
  };

  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">Distribution</Header>}>
        <SpaceBetween size="m">
          <FormField label="배포 방식">
            <RadioGroup
              value={distType}
              onChange={({ detail }) => setDistType(detail.value)}
              items={[
                { value: "none", label: "비활성 (수동 배포)" },
                { value: "presigned-s3", label: "Presigned S3 URL" },
                { value: "landing-page", label: "Self-service Landing Page (ALB + Lambda)" },
              ]}
              data-testid="distribution-radio"
            />
          </FormField>

          {distType === "landing-page" && (
            <SpaceBetween size="s">
              <FormField label="VPC ID">
                <Input value={(draft.distribution?.vpc_id as string) || ""} onChange={({ detail }) => updateDist("vpc_id", detail.value)} data-testid="dist-vpc-input" />
              </FormField>
              <FormField label="Custom Domain (FQDN)">
                <Input value={(draft.distribution?.custom_domain as string) || ""} onChange={({ detail }) => updateDist("custom_domain", detail.value)} placeholder="downloads.company.com" data-testid="dist-domain-input" />
              </FormField>
            </SpaceBetween>
          )}
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}
