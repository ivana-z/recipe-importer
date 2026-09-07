import { Button } from "@/components/ui/button";
import { ChefIcon } from "./ChefIcon";
import type { Recipe } from "../types";

interface RecipeSelectionProps {
  recipes: Recipe[];
  selectedIndices: number[];
  onToggle: (index: number) => void;
  onSelectAll: () => void;
  onClear: () => void;
  onContinue: () => void;
}

export function RecipeSelection({
  recipes,
  selectedIndices,
  onToggle,
  onSelectAll,
  onClear,
  onContinue,
}: RecipeSelectionProps) {
  const selected = new Set(selectedIndices);
  const allSelected = selectedIndices.length === recipes.length;

  return (
    <main className="flex min-h-dvh flex-col items-center gap-7 px-6 pb-8 pt-10">
      <ChefIcon className="h-16 w-16" />

      <header className="w-full max-w-sm space-y-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Choose recipes</h1>
        <p className="text-sm leading-6 text-muted-foreground">
          {recipes.length} recipes were found. Select the ones to review and send.
        </p>
      </header>

      <div className="flex w-full max-w-sm items-center justify-between gap-3">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onSelectAll}
          disabled={allSelected}
        >
          Select all
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onClear}
          disabled={selectedIndices.length === 0}
        >
          Clear
        </Button>
      </div>

      <fieldset className="flex w-full max-w-sm flex-col gap-3">
        <legend className="sr-only">Recipes to import</legend>
        {recipes.map((recipe, index) => {
          const checked = selected.has(index);
          return (
            <label
              key={`${index}-${recipe.name}`}
              className={`flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-left transition-colors ${
                checked
                  ? "border-primary bg-primary/10 text-foreground"
                  : "border-border bg-card text-card-foreground"
              }`}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => onToggle(index)}
                className="h-5 w-5 shrink-0 accent-primary"
              />
              <span className="min-w-0 flex-1 break-words text-sm font-medium leading-5">
                {recipe.name}
              </span>
            </label>
          );
        })}
      </fieldset>

      <div className="mt-auto w-full max-w-sm space-y-3">
        <p className="text-center text-sm text-muted-foreground" aria-live="polite">
          {selectedIndices.length} selected
        </p>
        <Button
          type="button"
          size="lg"
          className="h-14 w-full text-base font-semibold"
          onClick={onContinue}
          disabled={selectedIndices.length === 0}
        >
          Continue
        </Button>
      </div>
    </main>
  );
}
