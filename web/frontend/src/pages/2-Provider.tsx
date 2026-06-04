import { useEffect, useState } from "react";
import Container from "@cloudscape-design/components/container";
import FormField from "@cloudscape-design/components/form-field";
import Select, { SelectProps } from "@cloudscape-design/components/select";
import Input from "@cloudscape-design/components/input";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Spinner from "@cloudscape-design/components/spinner";
import { useWizardStore } from "../store";
import { getScenarios } from "../api";

const PROVIDER_OPTIONS: SelectProps.Option[] = [
  { value: "okta", label: "Okta" },
  { value: "azure", label: "Microsoft Entra ID (Azure AD)" },
  { value: "cognito", label: "AWS Cognito User Pool" },
  { value: "auth0", label: "Auth0" },
  { value: "generic", label: "Generic OIDC (Keycloak, PingFederate, etc.)" },
];

interface CognitoPool {
  user_pool_id: string;
  name: string;
  domain: string;
  clients: Array<{ client_id: string; client_name: string }>;
}

export default function ProviderPage() {
  const { draft, updateDraft } = useWizardStore();
  const [wizardInputs, setWizardInputs] = useState<Array<Record<string, unknown>>>([]);
  const [cognitoPools, setCognitoPools] = useState<CognitoPool[]>([]);
  const [loadingPools, setLoadingPools] = useState(false);
  const providerType = (draft.provider?.type as string) || "";

  useEffect(() => {
    getScenarios().then((data) => {
      const prov = data.providers.find((p) => p.type === providerType);
      if (prov) setWizardInputs(prov.wizard_inputs);
    }).catch(() => {});
  }, [providerType]);

  // Fetch Cognito User Pools when provider type is "cognito"
  useEffect(() => {
    if (providerType === "cognito" && draft.aws_region) {
      setLoadingPools(true);
      fetch(`/api/aws/cognito-pools?region=${draft.aws_region}`)
        .then((r) => r.json())
        .then((pools: CognitoPool[]) => setCognitoPools(pools))
        .catch(() => setCognitoPools([]))
        .finally(() => setLoadingPools(false));
    }
  }, [providerType, draft.aws_region]);

  const updateProvider = (key: string, value: string) => {
    updateDraft({ provider: { ...draft.provider, [key]: value } });
  };

  // Cognito-specific: select pool → auto-fill user_pool_id + domain
  const handlePoolSelect = (poolId: string) => {
    const pool = cognitoPools.find((p) => p.user_pool_id === poolId);
    if (pool) {
      updateDraft({
        provider: {
          ...draft.provider,
          type: "cognito",
          user_pool_id: pool.user_pool_id,
          user_pool_domain: pool.domain,
          client_id: pool.clients.length === 1 ? pool.clients[0].client_id : (draft.provider?.client_id as string) || "",
        },
      });
    }
  };

  // Cognito-specific: select client from chosen pool
  const selectedPool = cognitoPools.find((p) => p.user_pool_id === (draft.provider?.user_pool_id as string));

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

          {/* Cognito: pool dropdown + client dropdown */}
          {providerType === "cognito" && (
            <>
              {loadingPools ? (
                <Spinner size="normal" />
              ) : cognitoPools.length > 0 ? (
                <>
                  <FormField label="User Pool" description="현재 AWS 계정의 Cognito User Pool에서 선택" data-testid="cognito-pool-field">
                    <Select
                      selectedOption={
                        selectedPool
                          ? { value: selectedPool.user_pool_id, label: `${selectedPool.name} (${selectedPool.user_pool_id})` }
                          : null
                      }
                      onChange={({ detail }) => handlePoolSelect(detail.selectedOption.value || "")}
                      options={cognitoPools.map((p) => ({
                        value: p.user_pool_id,
                        label: `${p.name} (${p.user_pool_id})`,
                        description: p.domain ? `Domain: ${p.domain}` : undefined,
                      }))}
                      placeholder="User Pool 선택"
                      data-testid="cognito-pool-select"
                    />
                  </FormField>

                  {selectedPool && selectedPool.clients.length > 1 && (
                    <FormField label="App Client" description="해당 Pool의 클라이언트 선택" data-testid="cognito-client-field">
                      <Select
                        selectedOption={
                          (draft.provider?.client_id as string)
                            ? { value: draft.provider.client_id as string, label: selectedPool.clients.find((c) => c.client_id === draft.provider?.client_id)?.client_name || (draft.provider.client_id as string) }
                            : null
                        }
                        onChange={({ detail }) => updateProvider("client_id", detail.selectedOption.value || "")}
                        options={selectedPool.clients.map((c) => ({
                          value: c.client_id,
                          label: c.client_name ? `${c.client_name} (${c.client_id})` : c.client_id,
                        }))}
                        placeholder="Client 선택"
                        data-testid="cognito-client-select"
                      />
                    </FormField>
                  )}

                  {selectedPool && (
                    <FormField label="User Pool Domain" data-testid="cognito-domain-field">
                      <Input
                        value={(draft.provider?.user_pool_domain as string) || ""}
                        onChange={({ detail }) => updateProvider("user_pool_domain", detail.value)}
                        placeholder="myteam-claude"
                        data-testid="cognito-domain-input"
                      />
                    </FormField>
                  )}
                </>
              ) : (
                /* Fallback: manual input if no pools found or region not set */
                <>
                  {wizardInputs.map((field) => (
                    <FormField key={field.name as string} label={field.label as string} data-testid={`provider-${field.name}-field`}>
                      <Input
                        value={(draft.provider?.[field.name as string] as string) || ""}
                        onChange={({ detail }) => updateProvider(field.name as string, detail.value)}
                        placeholder={field.placeholder as string || ""}
                        data-testid={`provider-${field.name}-input`}
                      />
                    </FormField>
                  ))}
                </>
              )}
            </>
          )}

          {/* Non-Cognito: dynamic fields from provider strategy wizard_inputs */}
          {providerType && providerType !== "cognito" && wizardInputs.map((field) => (
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
