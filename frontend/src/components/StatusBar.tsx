import type { AppState } from "../types";

const messages: Record<AppState, string> = {
  idle: "",
  loading: "Processing recipe...",
  selecting: "",
  preview: "",
  syncing: "Sending to Paprika...",
  success: "",
  error: "",
};

export function StatusBar({
  state,
  error,
  completedCount = 0,
}: {
  state: AppState;
  error: string;
  completedCount?: number;
}) {
  if (!error && (state === "idle" || state === "selecting" || state === "preview")) {
    return null;
  }

  if (error) {
    return (
      <div
        role="alert"
        className="w-full max-w-sm break-words rounded-lg bg-destructive/15 px-4 py-3 text-sm leading-6 text-destructive"
      >
        {error || "Something went wrong. Please try again."}
      </div>
    );
  }

  if (state === "success") {
    return (
      <div className="w-full max-w-sm rounded-lg bg-primary/15 px-4 py-3 text-sm text-primary">
        {completedCount === 1 ? "Recipe sent to Paprika!" : `${completedCount} recipes sent to Paprika!`}
      </div>
    );
  }

  return (
    <div className="flex w-full max-w-sm items-center gap-3 rounded-lg bg-card px-4 py-3 text-sm text-muted-foreground">
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
