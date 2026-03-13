import type { JobMatchRequest, JobMatchResponse } from "../types";

const BASE_URL = "/api";

export async function matchCandidates(request: JobMatchRequest): Promise<JobMatchResponse> {
  const response = await fetch(`${BASE_URL}/jobs/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      const detail = data?.detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        // FastAPI validation errors are usually an array of {loc, msg, type}
        const first = detail[0];
        if (first?.loc && first?.msg) {
          const fieldPath = Array.isArray(first.loc) ? first.loc.join(".") : String(first.loc);
          message = `${fieldPath}: ${first.msg}`;
        } else {
          message = JSON.stringify(detail);
        }
      }
    } catch {
      // Ignore parse errors
    }
    throw new Error(message);
  }

  return response.json() as Promise<JobMatchResponse>;
}
