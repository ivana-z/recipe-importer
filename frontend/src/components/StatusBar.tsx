import type { AppState } from "../types";

const messages: Record<AppState, string> = {
  idle: "",
  loading: "Processing recipe...",
  preview: "",
  syncing: "Sending to Paprika...",
  success: "Recipe sent to Paprika!",
  error: "",
};

export function StatusBar({
  state,
  error,
}: {
  state: AppState;
  error: string;
}) {
  if (state === "idle" || state === "preview") return null;

  if (state === "error") {
    return (
      <div className="rounded-lg bg-destructive/15 px-4 py-3 text-sm text-destructive">
        {error || "Something went wrong"}
      </div>
    );
  }

  if (state === "success") {
    return (
      <div className="rounded-lg bg-primary/15 px-4 py-3 text-sm text-primary">
        {messages.success}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 rounded-lg bg-card px-4 py-3 text-sm text-muted-foreground">
      <svg
        className="h-4 w-4 animate-spin"
        viewBox="0 0 24 24"
        fill="none"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
        />
      </svg>
      {messages[state]}
    </div>
  );
}
