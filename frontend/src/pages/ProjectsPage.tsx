import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Archive, FolderKanban, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Dialog } from "../components/ui/Dialog";
import { Field, FormError } from "../components/ui/Field";
import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState, ErrorState, Spinner } from "../components/ui/States";
import { useToast } from "../components/ui/Toast";
import { useAuth } from "../features/auth/AuthContext";
import { useProjects } from "../hooks/queries";
import { ApiError, api, errorMessage } from "../services/api";
import type { Project, ProjectDetail } from "../types/api";
import { formatDate, plural } from "../utils/format";
import { PROJECT_STATUS_LABEL, ROLE_LABEL } from "../utils/labels";

export function ProjectStatusBadge({ project }: { project: Pick<Project, "status" | "archived_at"> }) {
  if (project.archived_at)
    return <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs font-medium text-gray-600">Archived</span>;
  const cls = {
    active: "bg-green-50 text-green-700",
    on_hold: "bg-amber-50 text-amber-800",
    completed: "bg-blue-50 text-blue-700",
  }[project.status];
  return <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${cls}`}>{PROJECT_STATUS_LABEL[project.status]}</span>;
}

export function ProjectsPage() {
  const { isAdmin } = useAuth();
  const [showArchived, setShowArchived] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const { data, isPending, isError, error, refetch } = useProjects(showArchived);

  return (
    <>
      <PageHeader
        title="Projects"
        description={isAdmin ? "All projects in the workspace." : "Projects you're a member of."}
        actions={
          <>
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-gray-300 text-brand-600"
                checked={showArchived}
                onChange={(e) => setShowArchived(e.target.checked)}
              />
              Show archived
            </label>
            {isAdmin && (
              <Button variant="primary" onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" aria-hidden /> New project
              </Button>
            )}
          </>
        }
      />

      {isPending ? (
        <Spinner />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : data.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={FolderKanban}
            title="No projects yet"
            description={isAdmin ? "Create a project, then add your team to it." : "Ask an admin to add you to a project."}
            action={
              isAdmin && (
                <Button variant="primary" size="sm" onClick={() => setCreateOpen(true)}>
                  New project
                </Button>
              )
            }
          />
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[640px]">
            <thead className="border-b border-gray-200 bg-gray-50">
              <tr>
                <th className="table-head">Project</th>
                <th className="table-head">Status</th>
                <th className="table-head">Progress</th>
                <th className="table-head">Open</th>
                <th className="table-head hidden md:table-cell">Members</th>
                <th className="table-head hidden md:table-cell">Your role</th>
                <th className="table-head hidden lg:table-cell">Dates</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.map((p) => {
                const pct = p.counts.total ? Math.round((p.counts.done / p.counts.total) * 100) : 0;
                const open = p.counts.total - p.counts.done;
                return (
                  <tr key={p.id} className="group hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <Link to={`/projects/${p.key}`} className="flex items-center gap-3">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-brand-50 text-xs font-semibold text-brand-700">
                          {p.key.slice(0, 3)}
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate font-medium text-gray-900 group-hover:text-brand-700">{p.name}</span>
                          <span className="text-xs text-gray-500">{p.key}</span>
                        </span>
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <ProjectStatusBadge project={p} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-24 overflow-hidden rounded-full bg-gray-100">
                          <div className="h-full rounded-full bg-brand-600" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-xs text-gray-500">{pct}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {open}
                      {p.counts.overdue > 0 && (
                        <span className="ml-2 text-xs font-medium text-red-600">{p.counts.overdue} overdue</span>
                      )}
                    </td>
                    <td className="hidden px-4 py-3 text-gray-700 md:table-cell">{p.member_count}</td>
                    <td className="hidden px-4 py-3 text-gray-700 md:table-cell">
                      {p.my_role ? ROLE_LABEL[p.my_role] : <span className="text-gray-400">Admin</span>}
                    </td>
                    <td className="hidden whitespace-nowrap px-4 py-3 text-xs text-gray-500 lg:table-cell">
                      {p.start_date || p.end_date ? `${formatDate(p.start_date)} – ${formatDate(p.end_date)}` : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {showArchived && data.some((p) => p.archived_at) && (
            <p className="flex items-center gap-1.5 border-t border-gray-100 px-4 py-2 text-xs text-gray-500">
              <Archive className="h-3.5 w-3.5" aria-hidden /> Archived projects are read-only.{" "}
              {plural(data.filter((p) => p.archived_at).length, "archived project")} shown.
            </p>
          )}
        </div>
      )}

      <CreateProjectDialog open={createOpen} onClose={() => setCreateOpen(false)} />
    </>
  );
}

function CreateProjectDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [name, setName] = useState("");
  const [key, setKey] = useState("");
  const [keyTouched, setKeyTouched] = useState(false);
  const [description, setDescription] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();

  function suggestKey(value: string) {
    const words = value.toUpperCase().replace(/[^A-Z0-9 ]/g, "").split(/\s+/).filter(Boolean);
    const k = words.length > 1 ? words.map((w) => w[0]).join("") : (words[0] ?? "").slice(0, 4);
    return k.replace(/^[0-9]+/, "").slice(0, 10);
  }

  const create = useMutation({
    mutationFn: () =>
      api.post<ProjectDetail>("/projects", {
        name: name.trim(),
        key,
        description,
        start_date: startDate || null,
        end_date: endDate || null,
      }),
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success(`Project ${p.name} created`);
      reset();
      onClose();
      navigate(`/projects/${p.key}`);
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 422) setErrors(err.fieldErrors());
      setFormError(errorMessage(err));
    },
  });

  function reset() {
    setName("");
    setKey("");
    setKeyTouched(false);
    setDescription("");
    setStartDate("");
    setEndDate("");
    setErrors({});
    setFormError(null);
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    const v: Record<string, string> = {};
    if (!name.trim()) v.name = "Give the project a name";
    if (!/^[A-Z][A-Z0-9]{1,9}$/.test(key)) v.key = "2–10 capital letters or digits, starting with a letter";
    if (startDate && endDate && endDate < startDate) v.end_date = "End date can't be before the start date";
    setErrors(v);
    setFormError(null);
    if (!Object.keys(v).length) create.mutate();
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="New project"
      description="You'll be the project's manager. Add members after it's created."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" form="create-project" loading={create.isPending}>
            Create project
          </Button>
        </>
      }
    >
      <form id="create-project" onSubmit={submit} className="space-y-4" noValidate>
        <FormError message={formError} />
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <Field label="Name" error={errors.name}>
              {(p) => (
                <input
                  {...p}
                  className="input"
                  value={name}
                  maxLength={120}
                  onChange={(e) => {
                    setName(e.target.value);
                    if (!keyTouched) setKey(suggestKey(e.target.value));
                  }}
                />
              )}
            </Field>
          </div>
          <Field label="Key" error={errors.key} hint="Used in task IDs, e.g. TF-12">
            {(p) => (
              <input
                {...p}
                className="input uppercase"
                value={key}
                maxLength={10}
                onChange={(e) => {
                  setKeyTouched(true);
                  setKey(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""));
                }}
              />
            )}
          </Field>
        </div>
        <Field label="Description">
          {(p) => (
            <textarea {...p} className="input min-h-[70px]" value={description} onChange={(e) => setDescription(e.target.value)} />
          )}
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Start date">
            {(p) => <input {...p} type="date" className="input" value={startDate} onChange={(e) => setStartDate(e.target.value)} />}
          </Field>
          <Field label="End date" error={errors.end_date}>
            {(p) => <input {...p} type="date" className="input" value={endDate} onChange={(e) => setEndDate(e.target.value)} />}
          </Field>
        </div>
      </form>
    </Dialog>
  );
}
