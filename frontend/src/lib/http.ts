import type { ErrorBody } from "../types/api";

/** Typed error carrying the backend's §8.6 envelope. */
export class ApiError extends Error {
  readonly body: ErrorBody;

  constructor(body: ErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.body = body;
  }
}

const API_BASE = "/api/v1";

function statusError(response: Response): ApiError {
  // Covers every non-2xx that did not carry the backend's JSON envelope —
  // e.g. the Vite dev-proxy's own error page when the API is unreachable.
  // Failures must NEVER be mistaken for successful payloads.
  const backendDown = response.status >= 502;
  return new ApiError({
    code: `HTTP_${response.status}`,
    message: backendDown
      ? `The API server is unreachable (status ${response.status}). Is the backend running on port 8000?`
      : `Request failed with status ${response.status}.`,
    request_id: "-",
    retryable: response.status >= 500 || response.status === 429,
  });
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: init?.body instanceof FormData ? init?.headers : { "Content-Type": "application/json", ...init?.headers },
      ...init,
    });
  } catch {
    throw new ApiError({
      code: "NETWORK_ERROR",
      message: "The backend is unreachable. Is it running on port 8000?",
      request_id: "-",
      retryable: true,
    });
  }

  if (response.status === 204) {
    return {} as T;
  }

  // Error status first, regardless of content type: a proxy error page must
  // surface as an error, not as a malformed payload (PRD §8.6/§6.3).
  if (!response.ok) {
    if ((response.headers.get("content-type") ?? "").includes("application/json")) {
      const payload = (await response.json().catch(() => null)) as { error?: ErrorBody } | null;
      if (payload?.error) {
        throw new ApiError(payload.error);
      }
    }
    throw statusError(response);
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    // Legitimate non-JSON success: the Markdown report export (FR-41).
    return (await response.text()) as unknown as T;
  }

  return (await response.json()) as T;
}

export const apiGet = <T>(path: string): Promise<T> => api<T>(path);
export const apiPost = <T>(path: string, body: unknown): Promise<T> =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export const apiPostForm = <T>(path: string, form: FormData): Promise<T> =>
  api<T>(path, { method: "POST", body: form });
export const apiDelete = <T>(path: string): Promise<T> =>
  api<T>(path, { method: "DELETE" });
