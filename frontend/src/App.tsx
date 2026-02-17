import { useState } from "react";
import { Toaster, toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Login } from "./components/Login";
import { ImportForm } from "./components/ImportForm";
import { EditRecipe } from "./components/EditRecipe";
import { StatusBar } from "./components/StatusBar";
import { useImport } from "./hooks/useImport";

function App() {
  const [authed, setAuthed] = useState(() => !!localStorage.getItem("app_secret"));
  const { state, recipe, error, submitUrl, submitImages, sync, reset } = useImport();

  if (!authed) {
    return <Login onLogin={() => setAuthed(true)} />;
  }

  return (
    <div className="mx-auto min-h-dvh max-w-md pb-8">
      <Toaster position="top-center" richColors />

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
