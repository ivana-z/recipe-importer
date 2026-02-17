import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ChefIcon } from "./ChefIcon";
import { CategoryPicker, type SelectedCategory } from "./CategoryPicker";
import type { Recipe } from "../types";

export function EditRecipe({
  recipe,
  onSync,
  syncing,
}: {
  recipe: Recipe;
  onSync: (overrides: { name: string; source: string; categories: string[] }) => void;
  syncing: boolean;
}) {
  const [name, setName] = useState(recipe.name);
  const [source, setSource] = useState(recipe.source);
  const [categories, setCategories] = useState<SelectedCategory[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    // Send only the real Paprika category names (values), not display labels
    onSync({ name, source, categories: categories.map((c) => c.value) });
  }

  function removeCategory(label: string) {
    setCategories((prev) => prev.filter((c) => c.label !== label));
  }

  return (
    <>
      <form
        onSubmit={handleSubmit}
        className="flex flex-col items-center gap-8 px-6 pt-12"
      >
        <ChefIcon className="h-20 w-20" />

        <div className="flex w-full max-w-sm flex-col gap-5">
          <Input
            placeholder="Enter recipe name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="h-14 bg-card text-base"
          />
          <Input
            placeholder="Enter recipe source"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="h-14 bg-card text-base"
          />
        </div>

        <div className="flex w-full max-w-sm flex-col gap-3">
          {categories.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {categories.map((cat) => (
                <Badge
                  key={cat.label}
                  variant="secondary"
                  className="gap-1.5 bg-accent py-1.5 pl-3 pr-2 text-sm text-accent-foreground"
                >
                  {cat.label}
                  <button
                    type="button"
                    onClick={() => removeCategory(cat.label)}
                    className="text-destructive hover:text-destructive/80"
                  >
                    <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M18 6 6 18" />
                      <path d="m6 6 12 12" />
                    </svg>
                  </button>
                </Badge>
              ))}
            </div>
          )}

          <Button
            type="button"
            variant="secondary"
            className="h-14 text-base"
            onClick={() => setPickerOpen(true)}
          >
            {categories.length > 0 ? "Add More Categories" : "Select Categories"}
          </Button>
        </div>

        <div className="w-full max-w-sm">
          <Button
            type="submit"
            size="lg"
            className="h-14 w-full gap-2 text-base font-semibold"
            disabled={!name.trim() || syncing}
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m22 2-7 20-4-9-9-4Z" />
              <path d="M22 2 11 13" />
            </svg>
            Send to Paprika
          </Button>
        </div>
      </form>

      <CategoryPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={setCategories}
        alreadySelected={categories}
      />
    </>
  );
}
