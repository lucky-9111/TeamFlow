/**
 * The single place the app talks to the backend.
 *
 * - Sends the session cookie (same origin) and echoes the CSRF cookie in X-CSRF-Token on writes.
 * - Turns the backend's {error: {code, message, details}} body into an ApiError.
 * - Broadcasts "unauthorized" on 401 so the auth layer can send the user back to the login page.
 */

const BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const CSRF_COOKIE = "teamflow_csrf";
const CSRF_HEADER = "X-CSRF-Token";
export const UNAUTHORIZED_EVENT = "teamflow:unauthorized";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }

  /** Field-level messages from a 422 response, keyed by the last part of the location. */
  fieldErrors(): Record<string, string> {
    if (!Array.isArray(this.details)) return {};
    const out: Record<string, string> = {};
    for (const item of this.details as { loc?: unknown[]; msg?: string }[]) {
      const field = item.loc?.[item.loc.length - 1];
      if (typeof field === "string" && item.msg) out[field] = item.msg.replace(/^Value error, /, "");
    }
    return out;
  }
}

function readCookie(name: string): string | null {
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

type Query = Record<string, string | number | boolean | (string | number)[] | null | undefined>;

export function toQuery(params: Query = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => search.append(key, String(v)));
    else search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

async function request<T>(method: string, path: string, body?: unknown, retried = false): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) headers[CSRF_HEADER] = csrf;
  }

  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the server. Check that the backend is running.");
  }

  if (response.status === 204) return undefined as T;

  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    // Non-JSON body (e.g. a proxy error page); handled below.
  }

  if (!response.ok) {
    const err = (data as { error?: { code: string; message: string; details?: unknown } })?.error;
    const apiError = new ApiError(
      response.status,
      err?.code ?? "http_error",
      err?.message ?? (response.status >= 500 ? "Something went wrong on the server." : response.statusText),
      err?.details,
    );
    // The CSRF cookie can go missing (cleared cookies, new tab); fetch a fresh one and retry once.
    if (apiError.code === "csrf_failed" && !retried) {
      await request("GET", "/auth/csrf");
      return request<T>(method, path, body, true);
    }
    if (response.status === 401 && path !== "/auth/login") {
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT, { detail: apiError }));
    }
    throw apiError;
  }
  return data as T;
}

export const api = {
  get: <T>(path: string, params?: Query) => request<T>("GET", path + toQuery(params)),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  delete: (path: string) => request<void>("DELETE", path),
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}
