import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Field, FormError } from "../components/ui/Field";
import { useToast } from "../components/ui/Toast";
import { useAuth } from "../features/auth/AuthContext";
import { api, errorMessage } from "../services/api";
import { AuthLayout } from "./LoginPage";

export const MIN_PASSWORD = 10;

/** Form shared by the forced first-login screen and the Settings page. */
export function ChangePasswordForm({ onDone }: { onDone: () => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const v: Record<string, string> = {};
    if (!current) v.current = "Enter your current password";
    if (next.length < MIN_PASSWORD) v.next = `Use at least ${MIN_PASSWORD} characters`;
    else if (next === current) v.next = "Choose a password you haven't used here";
    if (confirm !== next) v.confirm = "Passwords don't match";
    setErrors(v);
    setError(null);
    if (Object.keys(v).length) return;
    setSaving(true);
    try {
      await api.post("/auth/change-password", { current_password: current, new_password: next });
      setCurrent("");
      setNext("");
      setConfirm("");
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <FormError message={error} />
      <Field label="Current password" error={errors.current}>
        {(p) => (
          <input
            {...p}
            type="password"
            autoComplete="current-password"
            className="input"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        )}
      </Field>
      <Field label="New password" error={errors.next} hint={`At least ${MIN_PASSWORD} characters.`}>
        {(p) => (
          <input
            {...p}
            type="password"
            autoComplete="new-password"
            className="input"
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
        )}
      </Field>
      <Field label="Confirm new password" error={errors.confirm}>
        {(p) => (
          <input
            {...p}
            type="password"
            autoComplete="new-password"
            className="input"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        )}
      </Field>
      <Button type="submit" variant="primary" loading={saving}>
        Change password
      </Button>
    </form>
  );
}

export function ChangePasswordPage() {
  const { user, setUser, logout } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  return (
    <AuthLayout title="Choose a new password" subtitle="Your account has a temporary password. Set your own to continue.">
      <ChangePasswordForm
        onDone={() => {
          setUser({ ...user!, must_change_password: false });
          toast.success("Password changed");
          navigate("/", { replace: true });
        }}
      />
      <button
        className="mt-4 text-xs text-gray-500 hover:text-gray-800 hover:underline"
        onClick={async () => {
          await logout();
          navigate("/login");
        }}
      >
        Sign out instead
      </button>
    </AuthLayout>
  );
}
