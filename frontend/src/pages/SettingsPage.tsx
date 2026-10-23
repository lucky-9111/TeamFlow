import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Button } from "../components/ui/Button";
import { Field, FormError } from "../components/ui/Field";
import { PageHeader, Section } from "../components/ui/PageHeader";
import { useToast } from "../components/ui/Toast";
import { useAuth } from "../features/auth/AuthContext";
import { useWorkspace } from "../hooks/queries";
import { api, errorMessage } from "../services/api";
import type { CurrentUser } from "../types/api";
import { ChangePasswordForm } from "./ChangePasswordPage";

function timezones(current: string): string[] {
  const supported = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf?.("timeZone") ?? [];
  const list = supported.length ? supported : ["UTC", "Asia/Kolkata", "Europe/London", "America/New_York"];
  return list.includes(current) ? list : [current, ...list];
}

export function SettingsPage() {
  const { isAdmin } = useAuth();
  return (
    <>
      <PageHeader title="Settings" />
      <div className="max-w-2xl space-y-6">
        <ProfileSection />
        <Section title="Password">
          <div className="p-4">
            <PasswordSection />
          </div>
        </Section>
        {isAdmin && <WorkspaceSection />}
      </div>
    </>
  );
}

function ProfileSection() {
  const { user, setUser } = useAuth();
  const [fullName, setFullName] = useState(user!.full_name);
  const [timezone, setTimezone] = useState(user!.timezone);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();
  const qc = useQueryClient();
  const save = useMutation({
    mutationFn: () => api.patch<CurrentUser>("/auth/me", { full_name: fullName.trim(), timezone }),
    onSuccess: (u) => {
      setUser(u);
      qc.invalidateQueries();
      toast.success("Profile saved");
    },
    onError: (e) => setError(errorMessage(e)),
  });
  const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone;

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!fullName.trim()) return setError("Your name can't be empty.");
    save.mutate();
  }

  return (
    <Section title="Profile">
      <form className="space-y-4 p-4" onSubmit={submit} noValidate>
        <FormError message={error} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Full name">{(p) => <input {...p} className="input" value={fullName} onChange={(e) => setFullName(e.target.value)} />}</Field>
          <Field label="Email" hint="Ask an admin to change your email.">
            {(p) => <input {...p} className="input" value={user!.email} disabled />}
          </Field>
        </div>
        <Field
          label="Time zone"
          hint={timezone !== browserTz ? `Your browser is in ${browserTz}. Due dates and "overdue" use this setting.` : 'Due dates and "overdue" use this time zone.'}
        >
          {(p) => (
            <select {...p} className="input" value={timezone} onChange={(e) => setTimezone(e.target.value)}>
              {timezones(timezone).map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Button type="submit" variant="primary" loading={save.isPending}>
          Save profile
        </Button>
      </form>
    </Section>
  );
}

function PasswordSection() {
  const toast = useToast();
  return (
    <>
      <p className="mb-4 text-sm text-gray-500">Changing your password signs you out on your other devices.</p>
      <ChangePasswordForm onDone={() => toast.success("Password changed")} />
    </>
  );
}

function WorkspaceSection() {
  const workspace = useWorkspace();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const qc = useQueryClient();
  const toast = useToast();
  useEffect(() => {
    if (workspace.data) setName(workspace.data.name);
  }, [workspace.data]);
  const save = useMutation({
    mutationFn: () => api.patch("/workspace", { name: name.trim() }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workspace"] });
      toast.success("Workspace saved");
    },
    onError: (e) => setError(errorMessage(e)),
  });
  return (
    <Section title="Workspace (admin)">
      <form
        className="space-y-4 p-4"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          if (!name.trim()) return setError("The workspace needs a name.");
          save.mutate();
        }}
      >
        <FormError message={error} />
        <Field label="Workspace name" hint="Shown in the sidebar for everyone.">
          {(p) => <input {...p} className="input" value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Button type="submit" variant="primary" loading={save.isPending}>
          Save workspace
        </Button>
      </form>
    </Section>
  );
}
