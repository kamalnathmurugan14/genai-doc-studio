// Tiny typed fetch wrapper. Every backend error has the shape { error: { code, message } }.
export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError("NETWORK", "Cannot reach the backend. Is it running on " + API_URL + "?", 0);
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError(
      body?.error?.code ?? "HTTP_" + res.status,
      body?.error?.message ?? res.statusText,
      res.status,
    );
  }
  return body as T;
}

export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });

export const qs = (params: Record<string, string | number | undefined>) =>
  new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== "")
      .map(([k, v]) => [k, String(v)]),
  ).toString();

// ---- types -------------------------------------------------------------
export interface Entry {
  name: string;
  type: "dir" | "file";
  size: number;
  modified: string;
  path: string;
}
export interface Tree {
  path: string;
  entries: Entry[];
}
export interface Params {
  model?: string;
  temperature?: number;
  top_p?: number;
  max_tokens?: number;
}
export interface Evidenced {
  value: string;
  evidence: string;
  verified?: boolean;
}
export interface ExtractResult {
  data: Record<string, unknown> | null;
  valid: boolean;
  attempts: number;
  raw: string;
  errors?: string;
  unverified: { path: string; value: string }[];
  truncated: boolean;
  schema_name: string;
  run_id: number;
}
export interface ChunkSummary {
  index: number;
  total: number;
  level: number;
  text: string;
}
export interface PromptInfo {
  name: string;
  version: number;
  variables: string[];
}
export interface PromptFull extends PromptInfo {
  body: string;
}
export interface PromptVersion {
  version: number;
  note: string | null;
  created_at: string;
  body: string;
}
export interface Run {
  id: number;
  task: string;
  file_rel_path: string | null;
  prompt_name: string | null;
  prompt_version: number | null;
  model: string;
  params: Params;
  output_text: string | null;
  output_json: ExtractResult | null;
  tokens_in: number;
  tokens_out: number;
  duration_ms: number;
  status: string;
  error: string | null;
  created_at: string;
}
export interface CompareSide {
  output: string;
  tokens_in: number;
  tokens_out: number;
  ms: number;
  run_id: number;
  chunk_summaries: ChunkSummary[];
}
