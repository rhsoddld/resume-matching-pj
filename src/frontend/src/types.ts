// API types mirroring backend Pydantic schemas (src/backend/schemas/job.py)

export interface JobMatchRequest {
  job_description: string;
  top_k: number;
  category?: string;
  min_experience_years?: number;
}

export interface ScoreDetail {
  semantic_similarity: number;
  experience_fit: number;
  seniority_fit: number;
  category_fit: number;
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
  agent_scores: Record<string, number>;
  agent_explanation?: string;
}

export interface JobMatchResponse {
  matches: JobMatchCandidate[];
}
