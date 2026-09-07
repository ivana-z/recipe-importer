import { useState } from "react";
import { Toaster, toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Login } from "./components/Login";
import { ImportForm } from "./components/ImportForm";
import { EditRecipe } from "./components/EditRecipe";
import { RecipeSelection } from "./components/RecipeSelection";
import { StatusBar } from "./components/StatusBar";
import { Settings } from "./components/Settings";
import { useImport } from "./hooks/useImport";
import { clearLegacyApiCache } from "./api";

void clearLegacyApiCache().catch(() => {});

interface InitialLocation {
  authed: boolean;
  sharedUrl: string;
}

function initializeLocation(): InitialLocation {
  const cleanUrl = new URL(window.location.href);
  const fragmentParams = new URLSearchParams(cleanUrl.hash.slice(1));
  const hasToken = fragmentParams.has("token");
  const token = fragmentParams.get("token");

  if (token) {
    localStorage.setItem("jwt_token", token);
  }
  if (hasToken) {
    fragmentParams.delete("token");
    const remainingFragment = fragmentParams.toString();
    cleanUrl.hash = remainingFragment ? `#${remainingFragment}` : "";
  }

  const candidate =
    cleanUrl.searchParams.get("url") ||
    cleanUrl.searchParams.get("text") ||
    "";
  const sharedUrl = candidate.startsWith("http")
    ? candidate
    : candidate.match(/https?:\/\/\S+/)?.[0] || "";

  if (sharedUrl) {
    cleanUrl.searchParams.delete("url");
    cleanUrl.searchParams.delete("text");
    cleanUrl.searchParams.delete("title");
  }
  if (hasToken || sharedUrl) {
    window.history.replaceState({}, "", cleanUrl.toString());
  }

  return {
    authed: !!localStorage.getItem("jwt_token"),
    sharedUrl,
  };
}

function GearIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function App() {
  const [{ authed, sharedUrl }] = useState(initializeLocation);
  const [showSettings, setShowSettings] = useState(false);
  const {
    state,
    importedRecipes,
    selectedIndices,
    recipe,
    queueIndex,
    completedCount,
    totalToSync,
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
  } = useImport();

  if (!authed) {
    return <Login />;
  }

  if (showSettings) {
    return <Settings onBack={() => setShowSettings(false)} />;
  }

  const showGear =
    state === "idle" || state === "selecting" || state === "preview";
  const isImporting = state === "loading";

  return (
    <div className="mx-auto min-h-dvh max-w-md pb-8">
      <Toaster position="top-center" richColors />

      {showGear && (
        <div className="flex justify-end px-6 pt-4">
          <button
            onClick={() => setShowSettings(true)}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Settings"
          >
            <GearIcon className="h-6 w-6" />
          </button>
        </div>
      )}

      {state === "success" && (
        <div className="flex min-h-dvh flex-col items-center justify-center gap-6 px-6">
          <StatusBar
            state={state}
            error={error}
            completedCount={completedCount}
          />
          <Button onClick={reset} size="lg" className="h-14 w-full max-w-sm text-base font-semibold">
            New Import
          </Button>
        </div>
      )}

      {state === "error" && (
        <div className="flex min-h-dvh flex-col items-center justify-center gap-6 px-6">
          <StatusBar state={state} error={error} />
          <button
            onClick={reset}
            className="text-sm text-primary underline underline-offset-2"
          >
            Try again
          </button>
        </div>
      )}

      {(state === "idle" || state === "loading") && (
        <>
          <ImportForm
            onSubmitUrl={submitUrl}
            onSubmitImages={submitImages}
            onSubmitText={submitText}
            initialUrl={sharedUrl}
            disabled={isImporting}
          />
          {state === "loading" && (
            <div className="mt-6 px-6">
              <StatusBar state={state} error={error} />
            </div>
          )}
        </>
      )}

      {state === "selecting" && (
        <RecipeSelection
          recipes={importedRecipes}
          selectedIndices={selectedIndices}
          onToggle={toggleSelection}
          onSelectAll={selectAll}
          onClear={clearSelection}
          onContinue={confirmSelection}
        />
      )}

      {(state === "preview" || state === "syncing") && recipe && (
        <>
          <EditRecipe
            key={queueIndex}
            position={queueIndex + 1}
            total={totalToSync}
            recipe={recipe}
            onSync={async (overrides) => {
              if (await sync(overrides)) {
                toast.success("Recipe sent to Paprika!");
              }
            }}
            syncing={state === "syncing"}
          />
          {(state === "syncing" || error) && (
            <div className="mt-6 px-6">
              <StatusBar
                state={state}
                error={error}
                completedCount={completedCount}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default App;
