export type ProfileWizardStep = "understanding" | "experiences" | "questions" | "validation";

export type WizardValidationMeta = {
  validated_at?: string;
  version?: "v1";
};

export type StructuringQuestionType = "autonomy" | "tool" | "skill" | "context";

export type StructuringQuestion = {
  type?: StructuringQuestionType;
  experience_index?: number;
  skill_link_index?: number | null;
  target_field?: "autonomy_level" | "tool" | "tools" | "skill" | "skill_link" | "context";
  question?: string;
};

export type EnrichmentAutoFilled = {
  experience_index?: number;
  skill_link_index?: number | null;
  target_field?: "tools" | "context" | "autonomy_level" | "skill_link";
  value?: string;
  confidence?: number;
  reason?: string;
};

export type EnrichmentQuestionType = "autonomy" | "tool" | "skill" | "context";

export type EnrichmentQuestion = {
  type?: EnrichmentQuestionType;
  experience_index?: number;
  skill_link_index?: number | null;
  target_field?: "tool" | "tools" | "context" | "autonomy_level" | "skill_link" | "skill";
  question?: string;
  confidence?: number;
};

export type EnrichmentReport = {
  auto_filled?: EnrichmentAutoFilled[];
  suggestions?: Array<Record<string, unknown>>;
  questions?: EnrichmentQuestion[];
  reused_rejected?: Array<Record<string, unknown>>;
  confidence_scores?: Array<Record<string, unknown>>;
  priority_signals?: Array<Record<string, unknown>>;
  canonical_candidates?: Array<Record<string, unknown>>;
  learning_candidates?: Array<Record<string, unknown>>;
  stats?: Record<string, number>;
};

export type EnrichmentTraceEntry = {
  source?: string;
  confidence?: number;
};

export type WizardQuestion = {
  type?: StructuringQuestionType | EnrichmentQuestionType;
  experience_index?: number;
  skill_link_index?: number | null;
  target_field?: "autonomy_level" | "tool" | "tools" | "skill" | "skill_link" | "context";
  question?: string;
  source?: "structuring" | "enrichment";
  confidence?: number;
};

export type StructuringReport = {
  used_signals?: Array<Record<string, unknown>>;
  uncertain_links?: Array<Record<string, unknown>>;
  questions_for_user?: StructuringQuestion[];
  canonical_candidates?: Array<Record<string, unknown>>;
  rejected_noise?: Array<Record<string, unknown>>;
  unresolved_candidates?: Array<Record<string, unknown>>;
  stats?: {
    experiences_processed?: number;
    skill_links_created?: number;
    questions_generated?: number;
    coverage_ratio?: number;
  };
};
