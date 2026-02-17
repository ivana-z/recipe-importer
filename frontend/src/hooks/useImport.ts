import { useCallback, useState } from "react";
import { importImages, importUrl, syncRecipe } from "../api";
import type { AppState, Recipe } from "../types";

export function useImport() {
  const [state, setState] = useState<AppState>("idle");
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [error, setError] = useState<string>("");

  const submitUrl = useCallback(async (url: string) => {
    setState("loading");
    setError("");
    try {
      const result = await importUrl(url);
      setRecipe(result.recipe);
      setState("preview");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
      setState("error");
    }
  }, []);

  const submitImages = useCallback(async (files: File[]) => {
    setState("loading");
    setError("");
    try {
      const result = await importImages(files);
      setRecipe(result.recipe);
      setState("preview");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
      setState("error");
    }
  }, []);

  const sync = useCallback(
    async (overrides: { name: string; source: string; categories: string[] }) => {
      if (!recipe) return;
      setState("syncing");
      setError("");
      try {
        const result = await syncRecipe({
          ...recipe,
          ...overrides,
        });
        if (result.success) {
          setRecipe((r) => (r ? { ...r, name: result.name } : r));
          setState("success");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Sync failed");
        setState("error");
      }
    },
    [recipe]
  );

  const reset = useCallback(() => {
    setState("idle");
    setRecipe(null);
    setError("");
  }, []);

  return { state, recipe, error, submitUrl, submitImages, sync, reset };
}
