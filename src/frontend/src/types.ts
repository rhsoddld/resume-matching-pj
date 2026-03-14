// API types mirroring backend Pydantic schemas (src/backend/schemas/job.py)

export interface JobMatchRequest {
  job_description: string;
  top_k: number;
  category?: string;
  min_experience_years?: number;
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
  possible_gaps: string[];
  weighting_summary?: string;
}

export interface JobMatchResponse {
  query_profile: QueryUnderstandingProfile;
  matches: JobMatchCandidate[];
}
