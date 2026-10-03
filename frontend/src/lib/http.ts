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

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return (await response.text()) as unknown as T;
  }

  const payload = (await response.json()) as unknown;
  if (!response.ok) {
    const envelope = payload as { error?: ErrorBody };
    if (envelope.error) {
      throw new ApiError(envelope.error);
    }
    throw new ApiError({
      code: "UNKNOWN_ERROR",
      message: `Request failed with status ${response.status}.`,
      request_id: "-",
      retryable: false,
    });
  }
  return payload as T;
}

export const apiGet = <T>(path: string): Promise<T> => api<T>(path);
export const apiPost = <T>(path: string, body: unknown): Promise<T> =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export const apiPostForm = <T>(path: string, form: FormData): Promise<T> =>
  api<T>(path, { method: "POST", body: form });
export const apiDelete = <T>(path: string): Promise<T> =>
  api<T>(path, { method: "DELETE" });
