import { useCallback, useRef, useState } from "react";
import {
  ApiError,
  GENERIC_API_ERROR_MESSAGE,
  importImages,
  importText,
  importUrl,
  syncRecipe,
} from "../api";
import type { AppState, ImportResult, Recipe } from "../types";

interface SyncOverrides {
  name: string;
  source: string;
  categories: string[];
}

export function useImport() {
  const [state, setState] = useState<AppState>("idle");
  const [importedRecipes, setImportedRecipes] = useState<Recipe[]>([]);
  const [selectedIndices, setSelectedIndices] = useState<number[]>([]);
  const [queue, setQueue] = useState<Recipe[]>([]);
  const [queueIndex, setQueueIndex] = useState(0);
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [completedCount, setCompletedCount] = useState(0);
  const [error, setError] = useState("");
  const submitLockRef = useRef(false);

  const submitSource = useCallback(async (load: () => Promise<ImportResult>) => {
    if (submitLockRef.current) return;

    submitLockRef.current = true;
    setState("loading");
    setError("");
    setImportedRecipes([]);
    setSelectedIndices([]);
    setQueue([]);
    setQueueIndex(0);
    setRecipe(null);
    setCompletedCount(0);

    try {
      const result = await load();
      if (!Array.isArray(result.recipes) || result.recipes.length === 0) {
        throw new Error("Import returned no recipes");
      }

      setImportedRecipes(result.recipes);
      if (result.recipes.length === 1) {
        setQueue(result.recipes);
        setRecipe(result.recipes[0]);
        setState("preview");
      } else {
        setState("selecting");
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : GENERIC_API_ERROR_MESSAGE);
      setState("error");
    } finally {
      submitLockRef.current = false;
    }
  }, []);

  const submitUrl = useCallback(
    async (url: string) => {
      await submitSource(() => importUrl(url));
    },
    [submitSource]
  );

  const submitImages = useCallback(
    async (files: File[]) => {
      await submitSource(() => importImages(files));
    },
    [submitSource]
  );

  const submitText = useCallback(
    async (text: string) => {
      await submitSource(() => importText(text));
    },
    [submitSource]
  );

  const toggleSelection = useCallback((index: number) => {
    setSelectedIndices((current) =>
      current.includes(index)
        ? current.filter((selected) => selected !== index)
        : [...current, index].sort((left, right) => left - right)
    );
  }, []);

  const selectAll = useCallback(() => {
    setSelectedIndices(importedRecipes.map((_, index) => index));
  }, [importedRecipes]);

  const clearSelection = useCallback(() => {
    setSelectedIndices([]);
  }, []);

  const confirmSelection = useCallback(() => {
    const selected = new Set(selectedIndices);
    const selectedRecipes = importedRecipes.filter((_, index) => selected.has(index));
    if (selectedRecipes.length === 0) return;

    setQueue(selectedRecipes);
    setQueueIndex(0);
    setRecipe(selectedRecipes[0]);
    setCompletedCount(0);
    setError("");
    setState("preview");
  }, [importedRecipes, selectedIndices]);

  const sync = useCallback(
    async (overrides: SyncOverrides): Promise<boolean> => {
      if (!recipe) return false;

      setState("syncing");
      setError("");
      try {
        const result = await syncRecipe({ ...recipe, ...overrides });
        if (!result.success) {
          throw new Error("Paprika sync failed");
        }

        const nextIndex = queueIndex + 1;
        setCompletedCount(nextIndex);
        if (nextIndex < queue.length) {
          setQueueIndex(nextIndex);
          setRecipe(queue[nextIndex]);
          setState("preview");
        } else {
          setState("success");
        }
        return true;
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : GENERIC_API_ERROR_MESSAGE);
        setState("preview");
        return false;
      }
    },
    [queue, queueIndex, recipe]
  );

  const reset = useCallback(() => {
    submitLockRef.current = false;
    setState("idle");
    setImportedRecipes([]);
    setSelectedIndices([]);
    setQueue([]);
    setQueueIndex(0);
    setRecipe(null);
    setCompletedCount(0);
    setError("");
  }, []);

  return {
    state,
    importedRecipes,
    selectedIndices,
    recipe,
    queueIndex,
    completedCount,
    totalToSync: queue.length,
    error,
    submitUrl,
    submitImages,
    submitText,
    toggleSelection,
    selectAll,
    clearSelection,
    confirmSelection,
    sync,
    reset,
  };
}
