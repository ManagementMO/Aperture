export class ApiError extends Error {
  status: number;
  body: string;

  constructor(message: string, status: number, body: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function readJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!res.ok) {
    throw new ApiError(`API ${res.status} ${res.statusText}`, res.status, text);
  }
  if (!text) return {} as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError("Invalid JSON from API", res.status, text);
  }
}

export async function apiPost<T = unknown>(path: string, body: object): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJson<T>(res);
}

export async function apiGet<T = unknown>(path: string): Promise<T> {
  const res = await fetch(path);
  return readJson<T>(res);
}

/**
 * Read an NDJSON stream and dispatch every parsed line to `onEvent`.
 * Resolves when the server closes the stream.
 */
export async function apiPostStream(
  path: string,
  body: object,
  onEvent: (evt: Record<string, unknown>) => void,
): Promise<void> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => "");
    throw new ApiError(`API ${res.status} ${res.statusText}`, res.status, text);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 1);
      if (!line) continue;
      try {
        onEvent(JSON.parse(line) as Record<string, unknown>);
      } catch {
        // ignore parse errors on partial lines
      }
    }
  }
  // flush any trailing partial
  const tail = buf.trim();
  if (tail) {
    try {
      onEvent(JSON.parse(tail) as Record<string, unknown>);
    } catch {
      // ignore
    }
  }
}

export function describeApiError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404) {
      return "Backend isn't reachable. Start it with `uv run uvicorn api.main:app --port 8000` and retry.";
    }
    return `${err.message} — ${err.body.slice(0, 120)}`;
  }
  if (err instanceof TypeError) {
    return "Backend isn't reachable. Start it with `uv run uvicorn api.main:app --port 8000`.";
  }
  if (err instanceof Error) return err.message;
  return "Unexpected error";
}
