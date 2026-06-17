/**
 * Zustand store — wizard draft state + page navigation.
 */

import { create } from "zustand";

export interface ConfigDraft {
  profile_name: string;
  schema_version: string;
  aws_region: string;
  aws_profile: string;
  stack_base_name: string;
  provider: Record<string, unknown>;
  attribution: {
    mapping: { user: string; team: string; dept: string };
    passthrough: string[];
  };
  models: Record<string, string>;
  cross_region_profile: string;
  source_region: string;
  inference_profiles: Record<string, string | null>;
  bedrock_logging: { destination: string; retention_days: number; skip_if_exists?: boolean };
  quota: Record<string, unknown> | null;
  distribution: Record<string, unknown> | null;
  enable_codebuild_windows: boolean;
  enable_cowork_3p: boolean;
  enable_cc_telemetry: boolean;
  tags: Record<string, string>;
}

interface WizardState {
  currentStep: number;
  draft: ConfigDraft;
  mode: "new" | "edit" | "clone";
  lastClaimKeys: string[];  // claim keys from last successful IdP test
  setStep: (step: number) => void;
  updateDraft: (partial: Partial<ConfigDraft>) => void;
  resetDraft: () => void;
  setMode: (mode: "new" | "edit" | "clone") => void;
  setLastClaimKeys: (keys: string[]) => void;
}

const EMPTY_DRAFT: ConfigDraft = {
  profile_name: "",
  schema_version: "3.0",
  aws_region: "",
  aws_profile: "",
  stack_base_name: "",
  provider: {},
  attribution: { mapping: { user: "", team: "", dept: "" }, passthrough: [] },
  models: { haiku: "", sonnet: "", opus: "" },
  cross_region_profile: "",
  source_region: "",
  inference_profiles: { opus: null, sonnet: null, haiku: null },
  bedrock_logging: { destination: "cloudwatch", retention_days: 90 },
  quota: null,
  distribution: null,
  enable_codebuild_windows: false,
  enable_cowork_3p: true,
  enable_cc_telemetry: false,
  tags: {},
};

export const useWizardStore = create<WizardState>((set) => ({
  currentStep: 0,
  draft: { ...EMPTY_DRAFT },
  mode: "new",
  lastClaimKeys: [],
  setStep: (step) => set({ currentStep: step }),
  updateDraft: (partial) => set((s) => ({ draft: { ...s.draft, ...partial } })),
  resetDraft: () => set({ draft: { ...EMPTY_DRAFT }, currentStep: 0, mode: "new", lastClaimKeys: [] }),
  setMode: (mode) => set({ mode }),
  setLastClaimKeys: (keys) => set({ lastClaimKeys: keys }),
}));
