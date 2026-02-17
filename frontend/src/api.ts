import type { CategoriesResponse, ImportResult, Recipe, SyncResult } from "./types";

function getToken(): string {
  return localStorage.getItem("app_secret") || "";
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const res = await fetch(path, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `Request failed: ${res.status}`);
  }

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
