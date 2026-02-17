import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ChefIcon } from "./ChefIcon";

export function Login({ onLogin }: { onLogin: () => void }) {
  const [secret, setSecret] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!secret.trim()) return;
    localStorage.setItem("app_secret", secret.trim());
    onLogin();
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex min-h-dvh flex-col items-center justify-center gap-10 px-6"
    >
      <div className="flex flex-col items-center gap-5">
        <ChefIcon className="h-20 w-20" />
        <p className="text-lg text-muted-foreground">
          Fast recipe capture for Paprika
        </p>
      </div>

      <div className="flex w-full max-w-sm flex-col gap-5">
        <Input
          type="password"
          placeholder="App secret"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          className="h-14 bg-card text-base"
        />
        <Button type="submit" size="lg" className="h-14 text-base font-semibold">
          Sign In
        </Button>
      </div>
    </form>
  );
}
