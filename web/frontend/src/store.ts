/**
 * Zustand store — wizard draft state + page navigation.
 */

import { create } from "zustand";

export interface ConfigDraft {
  profile_name: string;
  schema_version: string;
  aws_region: string;
  stack_base_name: string;
  provider: Record<string, unknown>;
  models: Record<string, string>;  // {haiku: "model_id", sonnet: "model_id", opus: "model_id"}
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
  setStep: (step: number) => void;
  updateDraft: (partial: Partial<ConfigDraft>) => void;
  resetDraft: () => void;
  setMode: (mode: "new" | "edit" | "clone") => void;
}

const EMPTY_DRAFT: ConfigDraft = {
  profile_name: "",
  schema_version: "3.0",
  aws_region: "",
  stack_base_name: "",
  provider: {},
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
  setStep: (step) => set({ currentStep: step }),
  updateDraft: (partial) => set((s) => ({ draft: { ...s.draft, ...partial } })),
  resetDraft: () => set({ draft: { ...EMPTY_DRAFT }, currentStep: 0, mode: "new" }),
  setMode: (mode) => set({ mode }),
}));
