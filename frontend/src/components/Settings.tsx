import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  type AppVersion,
  clearAuthSession,
  fetchAppVersion,
  fetchCredentialStatus,
  saveCredentials,
} from "../api";

interface SettingsProps {
  onBack: () => void;
}

export function Settings({ onBack }: SettingsProps) {
  const [paprikaEmail, setPaprikaEmail] = useState("");
  const [paprikaPassword, setPaprikaPassword] = useState("");
  const [hasCredentials, setHasCredentials] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [appVersion, setAppVersion] = useState<AppVersion | null>(null);

  useEffect(() => {
    fetchCredentialStatus()
      .then((status) => {
        setHasCredentials(status.has_credentials);
        if (status.paprika_email) {
          setPaprikaEmail(status.paprika_email);
        }
      })
      .catch(() => {
        // Non-fatal: just show empty form
      });
    fetchAppVersion()
      .then(setAppVersion)
      .catch(() => {
        setAppVersion({ message: "Version unavailable", commit_sha: "" });
      });
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!paprikaEmail.trim() || !paprikaPassword.trim()) return;
    setSaving(true);
    setMessage("");
    setError("");
    try {
      await saveCredentials(paprikaEmail.trim(), paprikaPassword.trim());
      setHasCredentials(true);
      setPaprikaPassword("");
      setMessage("Credentials saved successfully.");
    } catch {
      setError("Failed to save credentials. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  async function handleLogout() {
    try {
      await clearAuthSession();
    } finally {
      window.location.reload();
    }
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col gap-8 px-6 py-10">
      <div className="flex items-center gap-4">
        <button
          onClick={onBack}
          className="text-sm text-primary underline underline-offset-2"
        >
          ← Back
        </button>
        <h1 className="text-xl font-semibold">Settings</h1>
      </div>

      <section className="flex flex-col gap-4">
        <h2 className="text-base font-medium text-muted-foreground">
          Paprika Credentials
        </h2>
        {hasCredentials && !message && (
          <p className="text-sm text-green-500">
            Credentials are saved. Update below to change them.
          </p>
        )}
        {message && <p className="text-sm text-green-500">{message}</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}

        <form onSubmit={handleSave} className="flex flex-col gap-4">
          <Input
            type="email"
            placeholder="Paprika account email"
            value={paprikaEmail}
            onChange={(e) => setPaprikaEmail(e.target.value)}
            className="h-12 bg-card"
            autoComplete="email"
          />
          <Input
            type="password"
            placeholder="Paprika account password"
            value={paprikaPassword}
            onChange={(e) => setPaprikaPassword(e.target.value)}
            className="h-12 bg-card"
            autoComplete="current-password"
          />
          <Button
            type="submit"
            size="lg"
            className="h-12 font-semibold"
            disabled={saving}
          >
            {saving ? "Saving…" : "Save Credentials"}
          </Button>
        </form>
      </section>

      <div className="mt-auto flex flex-col gap-6">
        <section
          aria-labelledby="app-version-heading"
          className="border-t border-border/70 pt-5"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h2
                id="app-version-heading"
                className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground"
              >
                App version
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-foreground">
                {appVersion?.message ?? "Loading deployment…"}
              </p>
            </div>
            {appVersion?.commit_sha && (
              <code className="shrink-0 rounded border border-primary/20 bg-primary/10 px-2 py-1 font-mono text-[11px] text-primary">
                {appVersion.commit_sha}
              </code>
            )}
          </div>
        </section>

        <section>
          <Button
            variant="outline"
            size="lg"
            className="h-12 w-full font-semibold text-destructive hover:text-destructive"
            onClick={handleLogout}
          >
            Sign Out
          </Button>
        </section>
      </div>
    </div>
  );
}
