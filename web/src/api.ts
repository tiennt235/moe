// Typed client for the moe-dashboard backend.

export interface Expert {
  name: string;
  description: string;
  chunk: Record<string, unknown>;
  n_sources: number;
  n_chunks: number;
  updated_at: string | null;
}

export interface Source {
  source_id: string;
  expert: string;
  title: string | null;
  author: string | null;
  fmt: string;
  origin: string;
  n_chunks: number;
  status: "pending" | "ingesting" | "ready" | "error";
  error: string | null;
  added_at: string | null;
}

export interface Job {
  id: string;
  kind: string;
  expert: string | null;
  status: "queued" | "running" | "done" | "failed";
  stage: string;
  progress: number;
  error: string | null;
  updated_at: string | null;
}

export interface Citation {
  title: string;
  author: string | null;
  source_id: string;
  url: string | null;
  location: string | null;
}

export interface Passage {
  text: string;
  expert: string;
  citation: Citation;
  score: number;
  rerank_score: number | null;
  chunk_id: string;
  heading_path: string[];
}

export interface RetrievalResult {
  question: string;
  experts_selected: string[];
  passages: Passage[];
  answer: string | null;
}

export interface Health {
  qdrant: string;
  region: string;
  rerank_region: string;
  embed_model: string;
  rerank_model: string;
  experts: number;
}

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetch("/api/health").then(j<Health>),
  experts: () => fetch("/api/experts").then(j<Expert[]>),
  createExpert: (name: string, description: string) =>
    fetch("/api/experts", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name, description }),
    }).then(j<Expert>),
  expert: (name: string) =>
    fetch(`/api/experts/${name}`).then(j<{ expert: Expert; sources: Source[] }>),
  patchExpert: (name: string, description: string) =>
    fetch(`/api/experts/${name}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ description }),
    }).then(j<Expert>),
  deleteExpert: (name: string) =>
    fetch(`/api/experts/${name}`, { method: "DELETE" }).then(j),
  reindex: (name: string) =>
    fetch(`/api/experts/${name}/reindex`, { method: "POST" }).then(j<{ job_id: string }>),
  addSources: (name: string, files: File[], urls: string) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    if (urls.trim()) fd.append("urls", urls);
    return fetch(`/api/experts/${name}/sources`, { method: "POST", body: fd }).then(
      j<{ job_id: string }>,
    );
  },
  deleteSource: (name: string, sid: string) =>
    fetch(`/api/experts/${name}/sources/${sid}`, { method: "DELETE" }).then(j),
  jobs: () => fetch("/api/jobs").then(j<Job[]>),
  query: (body: {
    question: string;
    top_k?: number;
    experts?: string[];
    synthesize?: boolean;
  }) =>
    fetch("/api/query", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }).then(j<RetrievalResult>),
  exportTeam: () => fetch("/api/team/export", { method: "POST" }).then(j<{ path: string }>),
};

// Subscribe to a job's SSE stream; returns an unsubscribe function.
export function streamJob(jobId: string, onUpdate: (job: Job) => void): () => void {
  const es = new EventSource(`/api/jobs/${jobId}/stream`);
  es.addEventListener("progress", (e) => {
    const job = JSON.parse((e as MessageEvent).data) as Job;
    onUpdate(job);
    if (job.status === "done" || job.status === "failed") es.close();
  });
  es.onerror = () => es.close();
  return () => es.close();
}
