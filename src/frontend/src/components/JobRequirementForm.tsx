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
      setError("Please enter at least 20 characters for the job description.");
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
            placeholder="Enter a natural-language JD. Example: Senior engineer with Python-based recommendation system operations and large-scale data pipeline experience."
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
            {filtersOpen ? "Hide filters" : "Show filters"}
          </button>
        </div>

        <div className={`filters-grid ${filtersOpen ? "is-open" : ""}`} id="jd-filters">
          <div className="field-group">
            <label htmlFor="seniority">Seniority</label>
            <select id="seniority" value={seniority} onChange={(event) => setSeniority(event.target.value)}>
              {SENIORITY.map((option) => (
                <option key={option || "all"} value={option}>{option || "All"}</option>
              ))}
            </select>
          </div>

          <div className="field-group">
            <label htmlFor="job-family">Job family</label>
            <select id="job-family" value={jobFamily} onChange={(event) => setJobFamily(event.target.value)}>
              {JOB_FAMILY.map((option) => (
                <option key={option || "all"} value={option}>{option || "All"}</option>
              ))}
            </select>
          </div>

          <div className="field-group">
            <label htmlFor="education">Education</label>
            <select id="education" value={education} onChange={(event) => setEducation(event.target.value)}>
              {EDUCATION.map((option) => (
                <option key={option || "all"} value={option}>{option || "All"}</option>
              ))}
            </select>
          </div>

          <div className="field-group">
            <label htmlFor="region">Region</label>
            <select id="region" value={region} onChange={(event) => setRegion(event.target.value)}>
              {REGION.map((option) => (
                <option key={option || "all"} value={option}>{option || "All"}</option>
              ))}
            </select>
          </div>

          <div className="field-group">
            <label htmlFor="industry">Industry</label>
            <select id="industry" value={industry} onChange={(event) => setIndustry(event.target.value)}>
              {INDUSTRY.map((option) => (
                <option key={option || "all"} value={option}>{option || "All"}</option>
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
