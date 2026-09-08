import type { CategoriesResponse, ImportResult, Recipe, SyncResult } from "./types";

export interface CredentialsStatus {
  has_credentials: boolean;
  paprika_email: string;
}

export interface AppVersion {
  message: string;
  commit_sha: string;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export const GENERIC_API_ERROR_MESSAGE = "Something went wrong. Please try again.";

function parseErrorDetail(body: string): ApiErrorDetail | null {
  if (!body) return null;

  let payload: unknown;
  try {
    payload = JSON.parse(body);
  } catch {
    return null;
  }

  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return null;
  }

  const detail = payload.detail;
  if (
    typeof detail !== "object" ||
    detail === null ||
    !("message" in detail) ||
    typeof detail.message !== "string" ||
    !detail.message.trim()
  ) {
    return null;
  }

  return {
    code:
      "code" in detail && typeof detail.code === "string" && detail.code.trim()
        ? detail.code
        : "request_failed",
    message: detail.message,
  };
}

const TOKEN_STORAGE_KEY = "jwt_token";
const LEGACY_API_CACHE = "api-cache";

export async function clearLegacyApiCache(): Promise<void> {
  if ("caches" in window) {
    await window.caches.delete(LEGACY_API_CACHE);
  }
}

export async function clearAuthSession(): Promise<void> {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  await clearLegacyApiCache();
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY) || "";
  const res = await fetch(path, {
    ...options,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (res.status === 401) {
    await clearAuthSession();
    window.location.href = "/";
    throw new Error("Session expired");
  }

  if (!res.ok) {
    const body = await res.text();
    const detail = parseErrorDetail(body);
    if (detail) {
      throw new ApiError(detail.message, res.status, detail.code);
    }
    throw new ApiError(GENERIC_API_ERROR_MESSAGE, res.status, "request_failed");
  }

  return res.json();
}

export async function getGoogleLoginUrl(): Promise<{ auth_url: string; state: string }> {
  const res = await fetch("/api/auth/login");
  if (!res.ok) throw new Error("Failed to get login URL");
  return res.json();
}

export async function importUrl(url: string): Promise<ImportResult> {
  return apiFetch<ImportResult>("/api/import/url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
}

export async function importText(text: string): Promise<ImportResult> {
  return apiFetch<ImportResult>("/api/import/text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

export async function importImages(files: File[]): Promise<ImportResult> {
  const form = new FormData();
  for (const file of files) {
    form.append("images", file);
  }

  return apiFetch<ImportResult>("/api/import/images", {
    method: "POST",
    body: form,
  });
}

export async function fetchCategories(): Promise<CategoriesResponse> {
  return apiFetch<CategoriesResponse>("/api/categories");
}

export async function syncRecipe(recipe: Recipe & { categories: string[] }): Promise<SyncResult> {
  return apiFetch<SyncResult>("/api/sync", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(recipe),
  });
}

export async function fetchAppVersion(): Promise<AppVersion> {
  return apiFetch<AppVersion>("/api/version");
}

export async function fetchCredentialStatus(): Promise<CredentialsStatus> {
  return apiFetch<CredentialsStatus>("/api/me/credentials");
}

export async function saveCredentials(
  paprika_email: string,
  paprika_password: string
): Promise<CredentialsStatus> {
  return apiFetch<CredentialsStatus>("/api/me/credentials", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paprika_email, paprika_password }),
  });
}
