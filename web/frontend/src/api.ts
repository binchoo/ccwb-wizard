/**
 * Backend HTTP client wrapper.
 * In dev, Vite proxies /api → backend (127.0.0.1:8400).
 * In production, frontend is served by backend's static mount.
 */

const BASE = "/api";

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...opts?.headers },
    ...opts,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// --- Profiles ---
export const listProfiles = () => request<string[]>("/profile");
export const getProfile = (name: string) => request<Record<string, unknown>>(`/profile/${name}`);
export const saveProfile = (name: string, body: Record<string, unknown>) =>
  request<{ status: string }>(`/profile/${name}`, { method: "POST", body: JSON.stringify(body) });
export const deleteProfile = (name: string) =>
  request<{ status: string }>(`/profile/${name}`, { method: "DELETE" });

// --- Drafts ---
export const getDraft = (name: string) => request<Record<string, unknown>>(`/profile/${name}/draft`);
export const saveDraft = (name: string, body: Record<string, unknown>) =>
  request<{ status: string }>(`/profile/${name}/draft`, { method: "POST", body: JSON.stringify(body) });

// --- Materialize ---
export const materializePreview = (name: string) =>
  request<Record<string, unknown>>(`/profile/${name}/materialize`, { method: "POST" });

// --- Scenarios ---
export const getScenarios = () => request<{
  providers: Array<{ type: string; wizard_inputs: Array<Record<string, unknown>> }>;
  distribution_types: string[];
  models: Record<string, { name: string; profiles: string[]; source_regions: Record<string, string[]> }>;
}>("/scenarios");

// --- AWS Lookup ---
export const getRegions = () => request<string[]>("/aws/regions");
export const getVpcs = (region: string) => request<Array<Record<string, unknown>>>(`/aws/vpcs?region=${region}`);
export const getSubnets = (vpcId: string, region: string) =>
  request<Array<Record<string, unknown>>>(`/aws/subnets?vpc_id=${vpcId}&region=${region}`);

// --- Secret ---
export const writeKeyring = (profileName: string, secretName: string, value: string) =>
  request<{ status: string; _keyring_ref: string }>("/secret/keyring", {
    method: "POST",
    body: JSON.stringify({ profile_name: profileName, secret_name: secretName, value }),
  });


// --- Deploy ---
export const deployProfile = (name: string) =>
  fetch(`${BASE}/profile/${name}/deploy`, { method: "POST" });

export const getDeployStatus = (name: string) =>
  request<Array<{ stack_name: string; status: string; outputs: Record<string, string> }>>(`/profile/${name}/deploy/status`);

// --- Package ---
export const buildPackage = (name: string) =>
  request<{ status: string; platform: string; zip_path: string; zip_size_mb: number; contents: string[] }>(
    `/profile/${name}/package`, { method: "POST" }
  );

export const getPackageStatus = (name: string) =>
  request<{ status: string; platform?: string; zip_path?: string; zip_size_mb?: number; contents?: string[] }>(
    `/profile/${name}/package/status`
  );
