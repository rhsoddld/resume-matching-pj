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

export async function streamMatchCandidates(
  request: JobMatchRequest,
  onEvent: (type: string, data: any) => void
): Promise<void> {
  const response = await fetch(`${BASE_URL}/jobs/match/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Stream failed with status ${response.status}`);
  }

  if (!response.body) {
    throw new Error("No readable stream available");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    
    // Process all fully received double-newline separated chunks
    const parts = buffer.split("\n\n");
    // Keep the last part in buffer as it might be incomplete
    buffer = parts.pop() || "";

    for (const part of parts) {
      if (!part.trim()) continue;
      
      const lines = part.split("\n");
      let eventType = "message";
      let eventData = "";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          eventData = line.slice(6).trim();
        }
      }

      if (eventData) {
        try {
          const parsedData = JSON.parse(eventData);
          onEvent(eventType, parsedData);
        } catch (e) {
          console.error("Failed to parse SSE data", e);
        }
      }
    }
  }
}
