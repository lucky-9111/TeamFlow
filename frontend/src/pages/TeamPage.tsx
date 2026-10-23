import { useMutation, useQueryClient } from "@tanstack/react-query";
import { KeyRound, UserPlus, Users } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Avatar } from "../components/ui/Avatar";
import { Button } from "../components/ui/Button";
import { useConfirm } from "../components/ui/Confirm";
import { Dialog } from "../components/ui/Dialog";
import { Field, FormError } from "../components/ui/Field";
import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState, ErrorState, Spinner } from "../components/ui/States";
import { useToast } from "../components/ui/Toast";
import { useAuth } from "../features/auth/AuthContext";
import { useTeam } from "../hooks/queries";
import { ApiError, api, errorMessage } from "../services/api";
import type { TeamMember, WorkspaceRole } from "../types/api";
import { timeAgo } from "../utils/format";
import { ROLE_LABEL } from "../utils/labels";
import { MIN_PASSWORD } from "./ChangePasswordPage";

function temporaryPassword(): string {
  const alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = crypto.getRandomValues(new Uint8Array(14));
  return Array.from(bytes, (b) => alphabet[b % alphabet.length]).join("");
}

export function TeamPage() {
  const { isAdmin, user } = useAuth();
  const [showInactive, setShowInactive] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [resetFor, setResetFor] = useState<TeamMember | null>(null);
  const team = useTeam(showInactive);
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["users"] });
    qc.invalidateQueries({ queryKey: ["activity"] });
  };
  const setActive = useMutation({
    mutationFn: (v: { id: number; active: boolean }) => api.post(`/users/${v.id}/${v.active ? "activate" : "deactivate"}`),
    onSuccess: (_d, v) => {
      refresh();
      toast.success(v.active ? "Member reactivated" : "Member deactivated");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const setRole = useMutation({
    mutationFn: (v: { id: number; role: WorkspaceRole }) => api.patch(`/users/${v.id}`, { workspace_role: v.role }),
    onSuccess: refresh,
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <>
      <PageHeader
        title="Team"
        description="Everyone in the workspace and what they're working on."
        actions={
          isAdmin && (
            <>
              <label className="flex items-center gap-2 text-sm text-gray-600">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-gray-300 text-brand-600"
                  checked={showInactive}
                  onChange={(e) => setShowInactive(e.target.checked)}
                />
                Show deactivated
              </label>
              <Button variant="primary" onClick={() => setAddOpen(true)}>
                <UserPlus className="h-4 w-4" aria-hidden /> Add member
              </Button>
            </>
          )
        }
      />

      {team.isPending ? (
        <Spinner />
      ) : team.isError ? (
        <ErrorState error={team.error} onRetry={() => team.refetch()} />
      ) : team.data.length === 0 ? (
        <div className="card">
          <EmptyState icon={Users} title="No team members found" />
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[720px]">
            <thead className="border-b border-gray-200 bg-gray-50">
              <tr>
                <th className="table-head">Member</th>
                <th className="table-head">Role</th>
                <th className="table-head">Projects</th>
                <th className="table-head">Open tasks</th>
                <th className="table-head hidden lg:table-cell">Last active</th>
                {isAdmin && <th className="table-head text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {team.data.map((m) => {
                const self = m.id === user!.id;
                return (
                  <tr key={m.id} className={m.is_active ? "" : "bg-gray-50 text-gray-400"}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <Avatar user={m} size="md" />
                        <div className="min-w-0">
                          <p className="truncate font-medium text-gray-900">
                            {m.full_name} {self && <span className="text-xs font-normal text-gray-400">(you)</span>}
                            {!m.is_active && <span className="ml-1 text-xs font-normal text-gray-500">· deactivated</span>}
                          </p>
                          <p className="truncate text-xs text-gray-500">{m.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {isAdmin && !self && m.is_active ? (
                        <select
                          aria-label={`Workspace role of ${m.full_name}`}
                          className="input h-8 w-28 py-0 text-xs"
                          value={m.workspace_role}
                          onChange={(e) => setRole.mutate({ id: m.id, role: e.target.value as WorkspaceRole })}
                        >
                          <option value="member">Member</option>
                          <option value="admin">Admin</option>
                        </select>
                      ) : (
                        <span className={`text-xs font-medium ${m.workspace_role === "admin" ? "text-brand-700" : "text-gray-600"}`}>
                          {m.workspace_role === "admin" ? "Admin" : "Member"}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {m.projects.length === 0 ? (
                        <span className="text-xs text-gray-400">None</span>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {m.projects.map((p) => (
                            <Link
                              key={p.key}
                              to={`/projects/${p.key}`}
                              className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700 hover:bg-gray-200"
                              title={`${p.name} · ${ROLE_LABEL[p.role]}`}
                            >
                              {p.key} · {ROLE_LABEL[p.role]}
                            </Link>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {m.open_task_count > 0 ? (
                        <Link to={`/tasks?assignee=${m.id}&status=todo&status=in_progress&status=in_review`} className="text-brand-700 hover:underline">
                          {m.open_task_count}
                        </Link>
                      ) : (
                        <span className="text-gray-400">0</span>
                      )}
                    </td>
                    <td className="hidden whitespace-nowrap px-4 py-3 text-xs text-gray-500 lg:table-cell">
                      {m.last_login_at ? timeAgo(m.last_login_at) : "Never signed in"}
                    </td>
                    {isAdmin && (
                      <td className="whitespace-nowrap px-4 py-3 text-right">
                        {!self && (
                          <div className="flex justify-end gap-1">
                            {m.is_active && (
                              <Button variant="ghost" size="sm" onClick={() => setResetFor(m)}>
                                <KeyRound className="h-3.5 w-3.5" aria-hidden /> Reset password
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              className={m.is_active ? "hover:!text-red-600" : ""}
                              onClick={async () => {
                                if (
                                  !m.is_active ||
                                  (await confirm({
                                    title: `Deactivate ${m.full_name}?`,
                                    message: "They'll be signed out and can't log in. Their tasks and history are kept, and you can reactivate them later.",
                                    confirmLabel: "Deactivate",
                                    danger: true,
                                  }))
                                ) {
                                  setActive.mutate({ id: m.id, active: !m.is_active });
                                }
                              }}
                            >
                              {m.is_active ? "Deactivate" : "Reactivate"}
                            </Button>
                          </div>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {isAdmin && <AddMemberDialog open={addOpen} onClose={() => setAddOpen(false)} />}
      {resetFor && <ResetPasswordDialog member={resetFor} onClose={() => setResetFor(null)} />}
    </>
  );
}

function AddMemberDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [role, setRole] = useState<WorkspaceRole>("member");
  const [password, setPassword] = useState(temporaryPassword);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ email: string; password: string } | null>(null);
  const qc = useQueryClient();

  const create = useMutation({
    mutationFn: () =>
      api.post<TeamMember>("/users", {
        full_name: fullName.trim(),
        email: email.trim(),
        username: username.trim().toLowerCase(),
        workspace_role: role,
        temporary_password: password,
      }),
    onSuccess: (m) => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setCreated({ email: m.email, password });
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 422) setErrors(e.fieldErrors());
      setFormError(errorMessage(e));
    },
  });

  function close() {
    setFullName("");
    setEmail("");
    setUsername("");
    setRole("member");
    setPassword(temporaryPassword());
    setErrors({});
    setFormError(null);
    setCreated(null);
    onClose();
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    const v: Record<string, string> = {};
    if (!fullName.trim()) v.full_name = "Enter their name";
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) v.email = "Enter a valid email";
    if (!/^[a-z0-9][a-z0-9_.-]{2,31}$/.test(username.trim().toLowerCase()))
      v.username = "3–32 characters: lowercase letters, digits, . _ or -";
    if (password.length < MIN_PASSWORD) v.temporary_password = `At least ${MIN_PASSWORD} characters`;
    setErrors(v);
    setFormError(null);
    if (!Object.keys(v).length) create.mutate();
  }

  if (created) {
    return (
      <Dialog open={open} onClose={close} title="Member added" footer={<Button variant="primary" onClick={close}>Done</Button>}>
        <p className="text-sm text-gray-600">
          Share these sign-in details privately. They'll be asked to choose their own password on first login.
        </p>
        <dl className="mt-3 space-y-1 rounded-md bg-gray-50 p-3 font-mono text-sm">
          <div>
            <dt className="inline text-gray-500">Email: </dt>
            <dd className="inline">{created.email}</dd>
          </div>
          <div>
            <dt className="inline text-gray-500">Temporary password: </dt>
            <dd className="inline">{created.password}</dd>
          </div>
        </dl>
      </Dialog>
    );
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      title="Add team member"
      description="They'll sign in with a temporary password and set their own."
      footer={
        <>
          <Button onClick={close}>Cancel</Button>
          <Button variant="primary" type="submit" form="add-member" loading={create.isPending}>
            Add member
          </Button>
        </>
      }
    >
      <form id="add-member" className="space-y-4" onSubmit={submit} noValidate>
        <FormError message={formError} />
        <Field label="Full name" error={errors.full_name}>
          {(p) => (
            <input
              {...p}
              className="input"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          )}
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Email" error={errors.email}>
            {(p) => (
              <input
                {...p}
                type="email"
                className="input"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  const local = e.target.value.split("@")[0].toLowerCase().replace(/[^a-z0-9_.-]/g, "");
                  setUsername(local.slice(0, 32));
                }}
              />
            )}
          </Field>
          <Field label="Username" error={errors.username}>
            {(p) => <input {...p} className="input" value={username} onChange={(e) => setUsername(e.target.value)} />}
          </Field>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Workspace role" hint="Admins manage people and projects.">
            {(p) => (
              <select {...p} className="input" value={role} onChange={(e) => setRole(e.target.value as WorkspaceRole)}>
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </select>
            )}
          </Field>
          <Field label="Temporary password" error={errors.temporary_password}>
            {(p) => (
              <div className="flex gap-2">
                <input {...p} className="input font-mono" value={password} onChange={(e) => setPassword(e.target.value)} />
                <Button size="sm" className="h-9" onClick={() => setPassword(temporaryPassword())}>
                  New
                </Button>
              </div>
            )}
          </Field>
        </div>
      </form>
    </Dialog>
  );
}

function ResetPasswordDialog({ member, onClose }: { member: TeamMember; onClose: () => void }) {
  const [password] = useState(temporaryPassword);
  const [done, setDone] = useState(false);
  const toast = useToast();
  const reset = useMutation({
    mutationFn: () => api.post(`/users/${member.id}/reset-password`, { temporary_password: password }),
    onSuccess: () => setDone(true),
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog
      open
      onClose={onClose}
      title={`Reset password for ${member.full_name}`}
      footer={
        done ? (
          <Button variant="primary" onClick={onClose}>
            Done
          </Button>
        ) : (
          <>
            <Button onClick={onClose}>Cancel</Button>
            <Button variant="danger" loading={reset.isPending} onClick={() => reset.mutate()}>
              Reset password
            </Button>
          </>
        )
      }
    >
      {done ? (
        <>
          <p className="text-sm text-gray-600">Share this temporary password privately. They'll choose a new one when they sign in.</p>
          <p className="mt-3 rounded-md bg-gray-50 p-3 font-mono text-sm">{password}</p>
        </>
      ) : (
        <p className="text-sm text-gray-600">
          They'll be signed out everywhere and must sign in with a new temporary password.
        </p>
      )}
    </Dialog>
  );
}
