import React, { useState } from "react";
import type { JobMatchRequest } from "../types";

interface Props {
  onSubmit: (request: JobMatchRequest) => void;
  isLoading: boolean;
}

const CATEGORIES = [
  "", "Data Science", "Java Developer", "Python Developer", "Web Designing",
  "HR", "DevOps Engineer", "DotNet Developer", "Database", "Hadoop",
  "ETL Developer", "Operations Manager", "PMO", "SAP Developer",
  "Business Analyst", "Automation Testing", "Network Security Engineer",
  "Testing", "Mechanical Engineer", "Civil Engineer",
];

export default function MatchForm({ onSubmit, isLoading }: Props) {
  const [jobDescription, setJobDescription] = useState("");
  const [category, setCategory] = useState("");
  const [minExp, setMinExp] = useState("");
  const [topK, setTopK] = useState(10);
  const [charCount, setCharCount] = useState(0);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!jobDescription.trim()) return;
    const request: JobMatchRequest = {
      job_description: jobDescription,
      top_k: topK,
      category: category || undefined,
      min_experience_years: minExp !== "" ? parseFloat(minExp) : undefined,
    };
    onSubmit(request);
  }

  function handleDescChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setJobDescription(e.target.value);
    setCharCount(e.target.value.length);
  }

  return (
    <form className="match-form" onSubmit={handleSubmit}>
      <div className="form-group">
        <label htmlFor="job-description">Job Description</label>
        <textarea
          id="job-description"
          value={jobDescription}
          onChange={handleDescChange}
          placeholder="Paste a job description here… e.g. 'Looking for a Senior Machine Learning Engineer with 5+ years experience in Python, PyTorch, and MLOps pipelines...'"
          rows={8}
          maxLength={10000}
          required
        />
        <span className="char-count">{charCount.toLocaleString()} / 10,000</span>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label htmlFor="category">Category (optional)</label>
          <select id="category" value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c === "" ? "All categories" : c}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="min-exp">Min. Experience (yrs)</label>
          <input
            id="min-exp"
            type="number"
            min={0}
            max={60}
            step={0.5}
            placeholder="e.g. 3"
            value={minExp}
            onChange={(e) => setMinExp(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label htmlFor="top-k">Top-K Results</label>
          <input
            id="top-k"
            type="number"
            min={1}
            max={50}
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
          />
        </div>
      </div>

      <button type="submit" className="submit-btn" disabled={isLoading || !jobDescription.trim()}>
        {isLoading ? (
          <>
            <span className="spinner" />
            Matching…
          </>
        ) : (
          "🔍 Find Matches"
        )}
      </button>
    </form>
  );
}
