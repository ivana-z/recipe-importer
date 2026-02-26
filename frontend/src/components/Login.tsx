import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ChefIcon } from "./ChefIcon";
import { getGoogleLoginUrl } from "../api";

export function Login() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleGoogleLogin() {
    setLoading(true);
    setError("");
    try {
      const { auth_url } = await getGoogleLoginUrl();
      window.location.href = auth_url;
    } catch {
      setError("Could not reach the server. Please try again.");
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-10 px-6">
      <div className="flex flex-col items-center gap-5">
        <ChefIcon className="h-20 w-20" />
        <p className="text-lg text-muted-foreground">
          Fast recipe capture for Paprika
        </p>
      </div>

      <div className="flex w-full max-w-sm flex-col gap-5">
        {error && (
          <p className="text-center text-sm text-destructive">{error}</p>
        )}
        <Button
          size="lg"
          className="h-14 text-base font-semibold"
          onClick={handleGoogleLogin}
          disabled={loading}
        >
          {loading ? "Redirecting…" : "Sign in with Google"}
        </Button>
      </div>
    </div>
  );
}
