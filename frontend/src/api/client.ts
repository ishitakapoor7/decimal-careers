import type {
  Application,
  ApplyRequest,
  Job,
  JobFilters,
  JobsPage,
  SavedJob,
} from "./types";

// In dev, Vite proxies "/api" → the backend (see vite.config.ts). In a built
// deploy, point VITE_API_BASE at the API origin.
const BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(0, "Can't reach the server. Is the backend running?");
  }
  if (!res.ok) {
    // FastAPI returns {detail: ...}; surface it when present.
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body — keep the generic message */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

function buildQuery(params: Record<string, unknown>): string {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value == null) continue;
    if (Array.isArray(value)) {
      for (const v of value) if (v != null) q.append(key, String(v));
    } else {
      q.append(key, String(value));
    }
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const api = {
  listJobs(opts: {
    filters?: JobFilters;
    candidateId?: string | null;
    limit?: number;
    offset?: number;
  }): Promise<JobsPage> {
    const { filters = {}, candidateId, limit = 20, offset = 0 } = opts;
    const query = buildQuery({
      ...filters,
      candidate_id: candidateId,
      limit,
      offset,
    });
    return request<JobsPage>(`/jobs${query}`);
  },

  getJob(id: string): Promise<Job> {
    return request<Job>(`/jobs/${encodeURIComponent(id)}`);
  },

  async uploadResume(
    file: File,
    candidateId?: string | null,
  ): Promise<{ candidate_id: string; char_count: number }> {
    const form = new FormData();
    form.append("file", file);
    if (candidateId) form.append("candidate_id", candidateId);
    return request("/upload-resume", { method: "POST", body: form });
  },

  apply(req: ApplyRequest): Promise<Application> {
    return request<Application>("/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
  },

  listApplications(candidateId: string): Promise<{ items: Application[] }> {
    return request(`/applications${buildQuery({ candidate_id: candidateId })}`);
  },

  saveJob(candidateId: string, jobId: string): Promise<{ saved: boolean }> {
    return request("/saved", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate_id: candidateId, job_id: jobId }),
    });
  },

  unsaveJob(candidateId: string, jobId: string): Promise<{ saved: boolean }> {
    return request(
      `/saved${buildQuery({ candidate_id: candidateId, job_id: jobId })}`,
      { method: "DELETE" },
    );
  },

  listSaved(candidateId: string): Promise<{ items: SavedJob[] }> {
    return request(`/saved${buildQuery({ candidate_id: candidateId })}`);
  },
};
