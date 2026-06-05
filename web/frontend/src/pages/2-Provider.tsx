import { useEffect, useRef, useState } from "react";
import Container from "@cloudscape-design/components/container";
import FormField from "@cloudscape-design/components/form-field";
import Select, { SelectProps } from "@cloudscape-design/components/select";
import Input from "@cloudscape-design/components/input";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Spinner from "@cloudscape-design/components/spinner";
import Button from "@cloudscape-design/components/button";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Checkbox from "@cloudscape-design/components/checkbox";
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

          {providerType && providerType !== "cognito" ? (wizardInputs as Array<{name: string; label: string; help_text?: string; placeholder?: string; sensitive?: boolean}>).map((field) => (
            <FormField
              key={field.name}
              label={field.label}
              constraintText={field.help_text || undefined}
              data-testid={`provider-${field.name}-field`}
            >
              <Input
                value={(draft.provider?.[field.name] as string) || ""}
                onChange={({ detail }) => updateProvider(field.name, detail.value)}
                placeholder={field.placeholder || ""}
                type={field.sensitive ? "password" : "text" as never}
                data-testid={`provider-${field.name}-input`}
              />
            </FormField>
          )) : null}

          {/* IdP Connection Test */}
          {providerType && draft.provider?.client_id && (
            <ConnectionTest
              provider={draft.provider as Record<string, string>}
              awsRegion={draft.aws_region}
            />
          )}
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}


// --- Connection Test Sub-component ---

function ConnectionTest({
  provider,
  awsRegion,
}: {
  provider: Record<string, string>;
  awsRegion: string;
}) {
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [claims, setClaims] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");

  const handleTest = async () => {
    setStatus("loading");
    setClaims(null);
    setError("");

    try {
      // Step 1: Get authorize URL + PKCE params from backend
      const res = await fetch("/api/auth/test-connection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, aws_region: awsRegion }),
      });
      const data = await res.json();

      if (data.status === "error") {
        setStatus("error");
        setError(data.error || "Backend returned error");
        return;
      }

      if (!data.authorize_url) {
        setStatus("error");
        setError("No authorize URL returned from backend");
        return;
      }

      const codeVerifier = data.code_verifier || "";
      const expectedState = data.state || "";

      // Step 2: Open popup for OIDC login
      const popup = window.open(
        data.authorize_url,
        "idp-test",
        "width=600,height=700,scrollbars=yes"
      );

      // Step 3: Listen for callback message from popup. The bridge HTML served
      // by the callback server (http://localhost:8410) posts back via
      // window.opener.postMessage with target "*" — so we accept any origin
      // but verify by message type + state to avoid spoofing.
      const handleMessage = async (event: MessageEvent) => {
        if (event.data?.type !== "oidc-callback") return;

        window.removeEventListener("message", handleMessage);
        popup?.close();

        const code = event.data.code;
        const state = event.data.state;

        if (event.data.error) {
          setStatus("error");
          setError(
            `${event.data.error}: ${event.data.error_description || "(no description)"}`
          );
          return;
        }

        if (!code) {
          setStatus("error");
          setError("No authorization code in callback");
          return;
        }

        if (expectedState && state !== expectedState) {
          setStatus("error");
          setError("State mismatch — possible CSRF attempt. Aborted.");
          return;
        }

        // Step 4: Exchange code for claims
        const exchangeRes = await fetch("/api/auth/test-connection/exchange", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            provider,
            aws_region: awsRegion,
            code,
            code_verifier: codeVerifier,
          }),
        });
        const exchangeData = await exchangeRes.json();

        if (exchangeData.status === "success") {
          setStatus("success");
          setClaims(exchangeData.claims);
        } else {
          setStatus("error");
          setError(exchangeData.error || "Token exchange failed");
        }
      };

      window.addEventListener("message", handleMessage);

      // Timeout after 120s (was 60s) — IdP login + MFA can take a while
      setTimeout(() => {
        window.removeEventListener("message", handleMessage);
        setStatus((cur) => {
          if (cur === "loading") {
            popup?.close();
            setError("연결 테스트 시간 초과 (120초). IdP 로그인을 완료하지 못했습니다.");
            return "error";
          }
          return cur;
        });
      }, 120000);
    } catch (e) {
      setStatus("error");
      setError((e as Error).message);
    }
  };

  return (
    <SpaceBetween size="s">
      <Alert type="info" header="IdP 연결 테스트 사전 준비">
        IdP의 App Client에 다음 callback URL을 Allowed Sign-in Redirect URI로
        등록해야 합니다: <strong>http://localhost:8410/callback</strong>
        <br />
        Cognito의 경우 App Client 설정 → "Allowed callback URLs"에 추가하고
        OAuth 2.0 grant types에 "Authorization code grant" 활성화, OpenID
        Connect scopes에 openid/email/profile를 포함해야 합니다.
      </Alert>
      <Button
        onClick={handleTest}
        loading={status === "loading"}
        iconName="external"
        data-testid="test-connection-button"
      >
        IdP 연결 테스트
      </Button>

      {status === "success" && claims && (
        <Container header={<Header variant="h3">✓ IdP 연결 성공 — JWT Claims</Header>}>
          <SpaceBetween size="xs">
            {Object.entries(claims).map(([key, value]) => (
              <div key={key}>
                <strong>{key}</strong>: {String(typeof value === "object" ? JSON.stringify(value) : value)}
              </div>
            ))}
          </SpaceBetween>
          <Box variant="small" color="text-body-secondary" margin={{ top: "s" }}>
            이 claims가 Bedrock invocation 로그에 사용자 attribution으로 기록됩니다.
          </Box>
          <AttributionMappingEditor claimKeys={Object.keys(claims)} />
        </Container>
      )}

      {status === "error" && (
        <Alert type="error" header="IdP 연결 실패" data-testid="connection-error">
          {error}
        </Alert>
      )}
    </SpaceBetween>
  );
}


// --- Attribution Mapping Editor ---

const DIMENSION_LABELS: Record<string, { label: string; description: string }> = {
  user: { label: "User (사용자 식별)", description: "대시보드에서 개별 사용자를 식별하는 키" },
  team: { label: "Team (팀/그룹)", description: "팀 또는 그룹별 사용량 집계" },
  dept: { label: "Dept (부서)", description: "부서별 비용 귀속" },
};

/** Claims that carry low attribution value and are noisy in headers. */
const DISCOURAGED_CLAIMS = new Set(["email_verified", "identities", "origin_jti", "at_hash", "c_hash"]);

function AttributionMappingEditor({ claimKeys }: { claimKeys: string[] }) {
  const { draft, updateDraft } = useWizardStore();
  const attribution = draft.attribution || { mapping: { user: "", team: "", dept: "" }, passthrough: [] };
  const mapping = attribution.mapping || { user: "", team: "", dept: "" };
  const passthrough = new Set(attribution.passthrough || []);

  const updateMapping = (dimension: string, claimKey: string) => {
    const next = { ...mapping, [dimension]: claimKey };
    updateDraft({ attribution: { ...attribution, mapping: next } });
  };

  const togglePassthrough = (key: string, checked: boolean) => {
    const next = new Set(passthrough);
    if (checked) next.add(key); else next.delete(key);
    updateDraft({ attribution: { ...attribution, passthrough: [...next] } });
  };

  // Claim options for dropdowns (with empty option)
  const claimOptions = [
    { value: "", label: "(매핑 안 함)" },
    ...claimKeys
      .filter((k) => !DISCOURAGED_CLAIMS.has(k))
      .map((k) => ({ value: k, label: k })),
  ];

  // Passthrough candidates: all claims NOT already used in mapping
  const mappedValues = new Set(Object.values(mapping).filter(Boolean));
  const passthroughCandidates = claimKeys.filter(
    (k) => !mappedValues.has(k) && !DISCOURAGED_CLAIMS.has(k)
  );

  const totalKeys = Object.values(mapping).filter(Boolean).length + passthrough.size;

  return (
    <SpaceBetween size="m">
      <Box margin={{ top: "m" }}>
        <Header
          variant="h3"
          description="대시보드 dimension에 IdP claim을 매핑하세요. credential-process가 매 인증 시 동적으로 적용합니다."
        >
          Attribution Mapping
        </Header>
      </Box>

      {/* Dimension mapping dropdowns */}
      <SpaceBetween size="s">
        {Object.entries(DIMENSION_LABELS).map(([dim, meta]) => (
          <FormField key={dim} label={meta.label} description={meta.description}>
            <Select
              selectedOption={
                mapping[dim as keyof typeof mapping]
                  ? { value: mapping[dim as keyof typeof mapping], label: mapping[dim as keyof typeof mapping] }
                  : { value: "", label: "(매핑 안 함)" }
              }
              onChange={({ detail }) => updateMapping(dim, detail.selectedOption.value || "")}
              options={claimOptions}
              placeholder="IdP claim 선택"
            />
          </FormField>
        ))}
      </SpaceBetween>

      {/* Passthrough selection */}
      <FormField
        label="추가 Passthrough"
        description="원본 claim 이름 그대로 헤더에 포함할 키 (dimension 매핑과 별도)"
      >
        <SpaceBetween size="xxs">
          {passthroughCandidates.map((key) => (
            <Checkbox
              key={key}
              checked={passthrough.has(key)}
              onChange={({ detail }) => togglePassthrough(key, detail.checked)}
            >
              {key}
            </Checkbox>
          ))}
        </SpaceBetween>
      </FormField>

      {totalKeys > 16 && (
        <Alert type="warning">
          Bedrock 헤더 제한(16키)을 초과합니다. 현재 {totalKeys}개 — 16개 이하로 줄여주세요.
        </Alert>
      )}

      {totalKeys > 0 && (
        <Box variant="small" color="text-body-secondary">
          매핑 {Object.values(mapping).filter(Boolean).length}개 + passthrough {passthrough.size}개 = 총 {totalKeys}개 키.
          미설정 시 기존 동작(블랙리스트 passthrough + 자동 alias) 유지.
        </Box>
      )}
    </SpaceBetween>
  );
}
