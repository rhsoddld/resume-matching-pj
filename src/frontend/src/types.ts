// API types mirroring backend Pydantic schemas (src/backend/schemas/job.py)

export interface JobMatchRequest {
  job_description: string;
  top_k: number;
  category?: string;
  min_experience_years?: number;
  education?: string;
  region?: string;
  industry?: string;
}

export interface JobFilterOptions {
  job_families: string[];
  educations: string[];
  regions: string[];
  industries: string[];
}

export interface QueryUnderstandingProfile {
  job_category?: string;
  roles: string[];
  required_skills: string[];
  related_skills: string[];
  skill_signals: Array<{ name: string; strength: string; signal_type: string }>;
  capability_signals: Array<{ name: string; strength: string; signal_type: string }>;
  seniority_hint?: string;
  filters: Record<string, string | number>;
  metadata_filters: Record<string, string | number>;
  transferable_skill_score?: number;
  transferable_skill_evidence?: string[];
  signal_quality: Record<string, string | number>;
  lexical_query: string;
  semantic_query_expansion: string[];
  query_text_for_embedding: string;
  confidence: number;
  fallback_used: boolean;
  fallback_reason?: string;
  fallback_rationale?: string;
  fallback_trigger: Record<string, string | number | boolean>;
}

export interface ScoreDetail {
  semantic_similarity: number;
  experience_fit: number;
  seniority_fit: number;
  category_fit: number;
  retrieval_fusion?: number;
  retrieval_keyword?: number;
  retrieval_metadata?: number;
  must_have_match_rate?: number;
  must_have_penalty?: number;
  adjacent_skill_score?: number;
  agent_weighted?: number;
  rank_policy?: string;
}

export interface SkillOverlapDetail {
  core_overlap: number;
  expanded_overlap: number;
  normalized_overlap: number;
}

export interface JobMatchCandidate {
  candidate_id: string;
  category?: string;
  summary?: string;
  skills: string[];
  normalized_skills: string[];
  core_skills: string[];
  expanded_skills: string[];
  experience_years?: number;
  seniority_level?: string;
  score: number;
  vector_score: number;
  skill_overlap: number;
  score_detail: ScoreDetail;
  skill_overlap_detail: SkillOverlapDetail;
  agent_scores: Record<string, unknown>;
  agent_explanation?: string;
  relevant_experience: string[];
  career_trajectory?: Record<string, unknown>;
  adjacent_skill_matches?: string[];
  possible_gaps: string[];
  bias_warnings?: string[];
  weighting_summary?: string;
}

export interface FairnessWarning {
  code: string;
  severity: string;
  message: string;
  candidate_ids: string[];
  metrics: Record<string, string | number | boolean | string[]>;
}

export interface FairnessAudit {
  enabled: boolean;
  policy_version: string;
  checks_run: string[];
  warnings: FairnessWarning[];
}

export interface JobMatchResponse {
  session_id?: string;
  query_profile: QueryUnderstandingProfile;
  matches: JobMatchCandidate[];
  fairness: FairnessAudit;
}

export type FeedbackRating = "pass" | "reject" | "review";

export interface InterviewEmailDraft {
  subject: string;
  body: string;
  generated_at?: string;
}
