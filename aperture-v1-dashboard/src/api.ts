// Tiny API client for /api/v3.1.

export interface UsageBucket {
  group_value: string | number | null;
  total_input_tokens_contributed: number;
  total_calls: number;
  average_per_call: number;
}

export interface CacheBucket {
  group_value: string | number | null;
  hits: number;
  misses: number;
  api_calls_avoided: number;
  tokens_saved: number;
}

export interface ApiResponse<T> {
  data: T[];
  page: number;
  page_size: number;
  total_groups: number;
  queried_at?: string;
  warning?: string;
}

export interface HealthResponse {
  status: string;
  aperture_version: string;
  sqlite_log_configured: boolean;
  token_event_count: number;
  cache_event_count: number;
}

async function postJson<T>(path: string, body: object): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`${path} → ${response.status} ${response.statusText}`);
  }
  return response.json();
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${path} → ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export const api = {
  health: () => getJson<HealthResponse>("/api/v3.1/health"),
  inputTokensContributed: (body: object) =>
    postJson<ApiResponse<UsageBucket>>(
      "/api/v3.1/project/usage/input_tokens_contributed",
      body
    ),
  cacheTokensSaved: (body: object) =>
    postJson<ApiResponse<CacheBucket>>(
      "/api/v3.1/project/usage/cache_tokens_saved",
      body
    ),
};
