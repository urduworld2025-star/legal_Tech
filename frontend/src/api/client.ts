import { clearToken, getToken } from "../auth/tokenStore";

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

type UnauthorizedListener = () => void;
const unauthorizedListeners = new Set<UnauthorizedListener>();

// Lets AuthContext react to a 401 from *any* call (not just the one it's
// currently awaiting) by clearing the session immediately.
export function onUnauthorized(listener: UnauthorizedListener): () => void {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

function notifyUnauthorized(): void {
  clearToken();
  unauthorizedListeners.forEach((listener) => listener());
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    if (response.status === 401) notifyUnauthorized();
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // response body wasn't JSON; fall back to statusText
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function postMultipart<T>(
  path: string,
  file: File,
  matterId: number | null
): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);
  if (matterId !== null) {
    formData.append("matter_id", String(matterId));
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: authHeaders(),
      body: formData,
    });
  } catch {
    throw new ApiError(0, `Could not reach the API at ${API_BASE_URL} — is the backend running?`);
  }

  return handleResponse<T>(response);
}

export async function requestJson<T>(
  path: string,
  options: { method?: "GET" | "POST" | "DELETE" | "PATCH"; body?: unknown } = {}
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? "GET",
      headers: {
        ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...authHeaders(),
      },
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError(0, `Could not reach the API at ${API_BASE_URL} — is the backend running?`);
  }

  return handleResponse<T>(response);
}

export async function requestBlob(path: string): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders() });
  } catch {
    throw new ApiError(0, `Could not reach the API at ${API_BASE_URL} — is the backend running?`);
  }
  if (!response.ok) {
    if (response.status === 401) notifyUnauthorized();
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // response body wasn't JSON; fall back to statusText
    }
    throw new ApiError(response.status, detail);
  }
  return response.blob();
}
