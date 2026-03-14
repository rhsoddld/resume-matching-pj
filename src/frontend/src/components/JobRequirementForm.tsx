import { useMemo, useState, type FormEvent } from "react";
import type { JobMatchRequest } from "../types";

interface JobRequirementFormProps {
  onSubmit: (request: JobMatchRequest) => void;
  isLoading: boolean;
}

const JOB_FAMILY = ["", "Data Science", "Python Developer", "Java Developer", "Business Analyst", "DevOps Engineer", "HR"];
const EDUCATION = ["", "Any", "Bachelor", "Master", "PhD"];
const REGION = ["", "Remote", "India", "United States", "APAC", "EMEA"];
const INDUSTRY = ["", "Technology", "Finance", "Healthcare", "E-commerce", "Manufacturing"];
const SENIORITY = ["", "Junior", "Mid", "Senior"];

function seniorityToExperience(seniority: string): number | undefined {
  if (seniority === "Junior") {
    return 1;
  }
  if (seniority === "Mid") {
    return 3;
  }
  if (seniority === "Senior") {
    return 6;
  }
  return undefined;
}

export default function JobRequirementForm({ onSubmit, isLoading }: JobRequirementFormProps) {
  const [jobDescription, setJobDescription] = useState("");
  const [seniority, setSeniority] = useState("");
  const [jobFamily, setJobFamily] = useState("");
  const [education, setEducation] = useState("");
  const [region, setRegion] = useState("");
  const [industry, setIndustry] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const characterCount = useMemo(() => jobDescription.length, [jobDescription]);

  function submitForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = jobDescription.trim();
    if (normalized.length < 20) {
      setError("JD는 최소 20자 이상 입력해주세요.");
      return;
    }

    setError(null);
    onSubmit({
      job_description: normalized,
      top_k: 12,
      category: jobFamily || undefined,
      min_experience_years: seniorityToExperience(seniority),
      education: education || undefined,
      region: region || undefined,
      industry: industry || undefined,
    });
  }

  return (
    <section className="job-form-panel" aria-label="Job requirement input">
      <form onSubmit={submitForm}>
        <div className="field-group">
          <label htmlFor="jd-input">Job Description</label>
          <textarea
            id="jd-input"
            aria-label="Natural language job description"
            placeholder="자연어로 JD를 입력하세요. 예: Python 기반 추천 시스템 운영 경험과 대규모 데이터 파이프라인 구축 경험이 있는 시니어 엔지니어"
            value={jobDescription}
            onChange={(event) => setJobDescription(event.target.value)}
            rows={7}
          />
          <div className="field-meta">
            <span>{characterCount} chars</span>
            {error && <span role="alert">{error}</span>}
          </div>
        </div>

        <div className="filter-toggle-wrap">
          <button
            className="filter-toggle"
            type="button"
            aria-expanded={filtersOpen}
            aria-controls="jd-filters"
            onClick={() => setFiltersOpen((value) => !value)}
          >
            {filtersOpen ? "필터 접기" : "필터 열기"}
          </button>
        </div>

        <div className={`filters-grid ${filtersOpen ? "is-open" : ""}`} id="jd-filters">
          <div className="field-group">
            <label htmlFor="seniority">경력</label>
            <select id="seniority" value={seniority} onChange={(event) => setSeniority(event.target.value)}>
              {SENIORITY.map((option) => (
                <option key={option || "all"} value={option}>{option || "전체"}</option>
              ))}
            </select>
          </div>

          <div className="field-group">
            <label htmlFor="job-family">직무군</label>
            <select id="job-family" value={jobFamily} onChange={(event) => setJobFamily(event.target.value)}>
              {JOB_FAMILY.map((option) => (
                <option key={option || "all"} value={option}>{option || "전체"}</option>
              ))}
            </select>
          </div>

          <div className="field-group">
            <label htmlFor="education">학력</label>
            <select id="education" value={education} onChange={(event) => setEducation(event.target.value)}>
              {EDUCATION.map((option) => (
                <option key={option || "all"} value={option}>{option || "전체"}</option>
              ))}
            </select>
          </div>

          <div className="field-group">
            <label htmlFor="region">지역</label>
            <select id="region" value={region} onChange={(event) => setRegion(event.target.value)}>
              {REGION.map((option) => (
                <option key={option || "all"} value={option}>{option || "전체"}</option>
              ))}
            </select>
          </div>

          <div className="field-group">
            <label htmlFor="industry">산업</label>
            <select id="industry" value={industry} onChange={(event) => setIndustry(event.target.value)}>
              {INDUSTRY.map((option) => (
                <option key={option || "all"} value={option}>{option || "전체"}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="cta-wrap">
          <button type="submit" className="cta-button" disabled={isLoading} aria-label="Find candidates">
            {isLoading ? "Finding..." : "Find Candidates"}
          </button>
        </div>
      </form>
    </section>
  );
}
