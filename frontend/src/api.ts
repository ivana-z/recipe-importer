import type { CategoriesResponse, ImportResult, Recipe, SyncResult } from "./types";

export interface CredentialsStatus {
  has_credentials: boolean;
  paprika_email: string;
}

function getToken(): string {
  return localStorage.getItem("jwt_token") || "";
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const res = await fetch(path, {
    ...options,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `Request failed: ${res.status}`);
  }

  return res.json();
}

export async function getGoogleLoginUrl(): Promise<{ auth_url: string; state: string }> {
  const res = await fetch("/api/auth/login");
  if (!res.ok) throw new Error("Failed to get login URL");
  return res.json();
}

export async function importUrl(
  url: string,
  quick = false
): Promise<ImportResult> {
  return apiFetch<ImportResult>("/api/import/url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, quick }),
  });
}

export async function importImages(
  files: File[],
  quick = false
): Promise<ImportResult> {
  const form = new FormData();
  for (const f of files) {
    form.append("images", f);
  }
  form.append("quick", String(quick));

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
