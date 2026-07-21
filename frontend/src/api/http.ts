// Thin typed wrapper over fetch for the same-origin /api surface (ADR-017).
// Non-2xx responses throw ApiError so callers — and TanStack Query — see failures.

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init);
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

// FastAPI reports errors as `{ "detail": "..." }`; fall back to the status line.
async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Non-JSON body — use the status line below.
  }
  return response.statusText || `HTTP ${response.status}`;
}

export const http = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: FormData) =>
    request<T>(path, { method: "POST", body }),
  delete: (path: string) => request<void>(path, { method: "DELETE" }),
};
