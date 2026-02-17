export interface Recipe {
  name: string;
  ingredients: string;
  directions: string;
  prep_time: string;
  cook_time: string;
  servings: string;
  notes: string;
  source_url: string;
  source: string;
  photo_data: string;
  image_url: string;
}

export interface ImportResult {
  recipe: Recipe;
  synced: boolean;
}

export interface SyncResult {
  success: boolean;
  name: string;
}

export interface CategoryChild {
  name: string;
  uid: string;
}

export interface CategoryItem {
  name: string;
  uid: string;
  children: CategoryChild[];
}

export interface CategoriesResponse {
  categories: CategoryItem[];
}

export type AppState =
  | "idle"
  | "loading"
  | "preview"
  | "syncing"
  | "success"
  | "error";
