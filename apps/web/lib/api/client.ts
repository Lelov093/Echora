/** Echora API Client — base fetch wrapper.

All API calls go through this module. No page should use raw fetch().
*/

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8010/api/v1";

export interface ApiResponse<T = unknown> {
  data: T | null;
  error: { code: string; message: string; details?: Record<string, unknown> } | null;
  meta: Record<string, unknown> | null;
}

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const res = await fetch(url, {
    ...options,
    headers,
  });

  let body: ApiResponse<T> | { detail?: unknown };
  try {
    body = await res.json();
  } catch {
    throw new ApiError(
      `HTTP_${res.status}`,
      res.ok ? "API returned an unreadable response." : `API request failed with status ${res.status}.`,
    );
  }

  if (!res.ok) {
    const apiError = "error" in body ? body.error : null;
    const detail = "detail" in body && typeof body.detail === "string" ? body.detail : null;
    throw new ApiError(
      apiError?.code || `HTTP_${res.status}`,
      apiError?.message || detail || `API request failed with status ${res.status}.`,
      apiError?.details,
    );
  }

  if (!("error" in body) || !("data" in body)) {
    throw new ApiError("API_INVALID_RESPONSE", "API response is missing the Echora data envelope.");
  }

  if (body.error) {
    throw new ApiError(body.error.code, body.error.message, body.error.details);
  }

  return body.data as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(data) }),
  put: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(data) }),
  patch: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(data) }),
  delete: <T>(path: string, data?: unknown) =>
    request<T>(path, {
      method: "DELETE",
      body: data === undefined ? undefined : JSON.stringify(data),
    }),
};

// Alias exports for convenience
export const apiGet = api.get;
export const apiPost = api.post;
export const apiPatch = api.patch;
export const apiDelete = api.delete;

export type QueryParams = Record<string, string | number | boolean | null | undefined>;

export function queryString(params?: QueryParams): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}
