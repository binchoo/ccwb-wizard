import { useEffect, useState } from "react";
import Container from "@cloudscape-design/components/container";
import FormField from "@cloudscape-design/components/form-field";
import Select, { SelectProps } from "@cloudscape-design/components/select";
import Input from "@cloudscape-design/components/input";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { useWizardStore } from "../store";
import { getScenarios } from "../api";

const PROVIDER_OPTIONS: SelectProps.Option[] = [
  { value: "okta", label: "Okta" },
  { value: "azure", label: "Microsoft Entra ID (Azure AD)" },
  { value: "cognito", label: "AWS Cognito User Pool" },
  { value: "auth0", label: "Auth0" },
  { value: "generic", label: "Generic OIDC (Keycloak, PingFederate, etc.)" },
];

export default function ProviderPage() {
  const { draft, updateDraft } = useWizardStore();
  const [wizardInputs, setWizardInputs] = useState<Array<Record<string, unknown>>>([]);
  const providerType = (draft.provider?.type as string) || "";

  useEffect(() => {
    getScenarios().then((data) => {
      const prov = data.providers.find((p) => p.type === providerType);
      if (prov) setWizardInputs(prov.wizard_inputs);
    }).catch(() => {});
  }, [providerType]);

  const updateProvider = (key: string, value: string) => {
    updateDraft({ provider: { ...draft.provider, [key]: value } });
  };

  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">Identity Provider 선택</Header>}>
        <SpaceBetween size="m">
          <FormField label="Provider Type" data-testid="provider-type-field">
            <Select
              selectedOption={PROVIDER_OPTIONS.find((o) => o.value === providerType) || null}
              onChange={({ detail }) =>
                updateDraft({ provider: { type: detail.selectedOption.value || "" } })
              }
              options={PROVIDER_OPTIONS}
              placeholder="IdP를 선택하세요"
              data-testid="provider-type-select"
            />
          </FormField>

          {/* Dynamic fields from provider strategy wizard_inputs */}
          {wizardInputs.map((field) => (
            <FormField
              key={field.name as string}
              label={field.label as string}
              constraintText={field.help_text as string || undefined}
              data-testid={`provider-${field.name}-field`}
            >
              <Input
                value={(draft.provider?.[field.name as string] as string) || ""}
                onChange={({ detail }) => updateProvider(field.name as string, detail.value)}
                placeholder={field.placeholder as string || ""}
                type={(field.sensitive as boolean) ? "password" : "text" as never}
                data-testid={`provider-${field.name}-input`}
              />
            </FormField>
          ))}
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}
