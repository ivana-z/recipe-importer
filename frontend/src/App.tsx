import { useEffect, useState } from "react";
import { Toaster, toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Login } from "./components/Login";
import { ImportForm } from "./components/ImportForm";
import { EditRecipe } from "./components/EditRecipe";
import { StatusBar } from "./components/StatusBar";
import { Settings } from "./components/Settings";
import { useImport } from "./hooks/useImport";

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
  const [authed, setAuthed] = useState(() => !!localStorage.getItem("jwt_token"));
  const [showSettings, setShowSettings] = useState(false);
  const { state, recipe, error, submitUrl, submitImages, sync, reset } = useImport();

  // Handle OAuth callback: extract ?token= from URL and store it
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (token) {
      localStorage.setItem("jwt_token", token);
      // Remove token from URL without reloading
      const url = new URL(window.location.href);
      url.searchParams.delete("token");
      window.history.replaceState({}, "", url.toString());
      setAuthed(true);
    }
  }, []);

  if (!authed) {
    return <Login />;
  }

  if (showSettings) {
    return <Settings onBack={() => setShowSettings(false)} />;
  }

  const showGear = state === "idle" || state === "preview";

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
          <StatusBar state={state} error={error} />
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
          <ImportForm onSubmitUrl={submitUrl} onSubmitImages={submitImages} />
          {state === "loading" && (
            <div className="mt-6 px-6">
              <StatusBar state={state} error={error} />
            </div>
          )}
        </>
      )}

      {(state === "preview" || state === "syncing") && recipe && (
        <>
          <EditRecipe
            recipe={recipe}
            onSync={(overrides) => {
              sync(overrides).then(() => {
                toast.success("Recipe sent to Paprika!");
              });
            }}
            syncing={state === "syncing"}
          />
          {state === "syncing" && (
            <div className="mt-6 px-6">
              <StatusBar state={state} error={error} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default App;
