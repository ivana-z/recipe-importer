import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { fetchCategories } from "../api";
import type { CategoryItem } from "../types";

export interface SelectedCategory {
  /** Display label shown as chip, e.g. "Dinner > Chicken" */
  label: string;
  /** Actual Paprika category name, e.g. "Chicken" */
  value: string;
}

export function CategoryPicker({
  open,
  onClose,
  onSelect,
  alreadySelected,
}: {
  open: boolean;
  onClose: () => void;
  onSelect: (categories: SelectedCategory[]) => void;
  alreadySelected: SelectedCategory[];
}) {
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [drillInto, setDrillInto] = useState<CategoryItem | null>(null);
  const [selected, setSelected] = useState<Map<string, SelectedCategory>>(new Map());

  // Seed with already-selected categories when opening
  useEffect(() => {
    if (open) {
      const map = new Map<string, SelectedCategory>();
      for (const cat of alreadySelected) {
        map.set(cat.label, cat);
      }
      setSelected(map);
    }
  }, [open, alreadySelected]);

  useEffect(() => {
    if (open && categories.length === 0) {
      setLoading(true);
      fetchCategories()
        .then((res) => setCategories(res.categories))
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [open, categories.length]);

  function toggleItem(label: string, value: string) {
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(label)) {
        next.delete(label);
      } else {
        next.set(label, { label, value });
      }
      return next;
    });
  }

  function handleDone() {
    onSelect(Array.from(selected.values()));
    setDrillInto(null);
    onClose();
  }

  function handleBack() {
    setDrillInto(null);
  }

  function handleCategoryTap(cat: CategoryItem) {
    if (cat.children.length > 0) {
      setDrillInto(cat);
    } else {
      toggleItem(cat.name, cat.uid);
    }
  }

  function isSelected(label: string) {
    return selected.has(label);
  }

  const Checkmark = () => (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );

  return (
    <Drawer open={open} onOpenChange={(o) => !o && onClose()}>
      <DrawerContent className="max-h-[85dvh]">
        <DrawerHeader className="flex items-center justify-between border-b border-border px-4 pb-3">
          <div className="flex items-center gap-3">
            {drillInto && (
              <button
                onClick={handleBack}
                className="text-foreground"
              >
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="m15 18-6-6 6-6" />
                </svg>
              </button>
            )}
            <DrawerTitle>
              {drillInto ? drillInto.name : "Select Category"}
            </DrawerTitle>
          </div>
          <DrawerClose asChild>
            <button className="text-muted-foreground">
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 6 6 18" />
                <path d="m6 6 12 12" />
              </svg>
            </button>
          </DrawerClose>
        </DrawerHeader>

        <div className="flex-1 overflow-y-auto px-4 py-2">
          {loading && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Loading categories...
            </p>
          )}

          {!loading && !drillInto && (
            <div className="flex flex-col gap-2">
              {categories.map((cat) => {
                const active = cat.children.length === 0 && isSelected(cat.name);
                return (
                  <button
                    key={cat.name}
                    onClick={() => handleCategoryTap(cat)}
                    className={`flex items-center justify-between rounded-lg border border-border px-4 py-3.5 text-left text-sm transition-colors ${
                      active
                        ? "border-foreground bg-foreground text-background"
                        : "bg-popover text-popover-foreground"
                    }`}
                  >
                    {cat.name}
                    {cat.children.length > 0 ? (
                      <svg className="h-4 w-4 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="m9 18 6-6-6-6" />
                      </svg>
                    ) : active ? (
                      <Checkmark />
                    ) : null}
                  </button>
                );
              })}
            </div>
          )}

          {!loading && drillInto && (
            <div className="flex flex-col gap-2">
              {/* Parent "All" option */}
              {(() => {
                const label = drillInto.name;
                const active = isSelected(label);
                return (
                  <button
                    onClick={() => toggleItem(label, drillInto.uid)}
                    className={`flex items-center justify-between rounded-lg border border-border px-4 py-3.5 text-left text-sm transition-colors ${
                      active
                        ? "border-foreground bg-foreground text-background"
                        : "bg-popover text-popover-foreground"
                    }`}
                  >
                    {drillInto.name} (All)
                    {active && <Checkmark />}
                  </button>
                );
              })()}

              {/* Subcategories */}
              {drillInto.children.map((child) => {
                const label = `${drillInto.name} > ${child.name}`;
                const active = isSelected(label);
                return (
                  <button
                    key={child.uid}
                    onClick={() => toggleItem(label, child.uid)}
                    className={`flex items-center justify-between rounded-lg border border-border px-4 py-3.5 text-left text-sm transition-colors ${
                      active
                        ? "border-foreground bg-foreground text-background"
                        : "bg-popover text-popover-foreground"
                    }`}
                  >
                    {child.name}
                    {active && <Checkmark />}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <DrawerFooter className="border-t border-border">
          <Button
            onClick={handleDone}
            className="h-12 text-base font-semibold bg-foreground text-background hover:bg-foreground/90"
          >
            Done{selected.size > 0 ? ` (${selected.size})` : ""}
          </Button>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}
