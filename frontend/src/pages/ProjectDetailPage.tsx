import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Archive, ArchiveRestore, ListChecks, Pencil, Plus, SquareKanban, Trash2, UserPlus } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ActivityItem } from "../components/ActivityItem";
import { TaskRow } from "../components/tasks/TaskRow";
import { CreateTaskDialog } from "../components/tasks/TaskForm";
import { Avatar } from "../components/ui/Avatar";
import { Button } from "../components/ui/Button";
import { Dialog } from "../components/ui/Dialog";
import { Field, FormError } from "../components/ui/Field";
import { PageHeader, Section } from "../components/ui/PageHeader";
import { EmptyState, ErrorState, Spinner } from "../components/ui/States";
import { useConfirm } from "../components/ui/Confirm";
import { useToast } from "../components/ui/Toast";
import { invalidateTaskViews, useActivity, useProject, useTasks, useTeam } from "../hooks/queries";
import { ApiError, api, errorMessage } from "../services/api";
import type { ProjectDetail, ProjectRole, ProjectStatus } from "../types/api";
import { formatDate } from "../utils/format";
import { PROJECT_ROLES, PROJECT_STATUSES, PROJECT_STATUS_LABEL, ROLE_LABEL, STATUSES, STATUS_LABEL } from "../utils/labels";
import { NotFoundPage } from "./NotFoundPage";
import { ProjectStatusBadge } from "./ProjectsPage";

export function ProjectDetailPage() {
  const { key } = useParams();
  const project = useProject(key);
  const tasks = useTasks({ project: key, page_size: 8, sort: "updated", order: "desc" });
  const activity = useActivity(key, 1);
  const [editOpen, setEditOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const archive = useMutation({
    mutationFn: (archived: boolean) => api.post<ProjectDetail>(`/projects/${key}/${archived ? "archive" : "unarchive"}`),
    onSuccess: (p) => {
      invalidateTaskViews(qc);
      toast.success(p.archived_at ? "Project archived" : "Project restored");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (project.isPending) return <Spinner />;
  if (project.isError) {
    if (project.error instanceof ApiError && project.error.status === 404) return <NotFoundPage what="project" />;
    return <ErrorState error={project.error} onRetry={() => project.refetch()} />;
  }
  const p = project.data;
  const pct = p.counts.total ? Math.round((p.counts.done / p.counts.total) * 100) : 0;

  return (
    <>
      <PageHeader
        breadcrumb={[{ label: "Projects", to: "/projects" }]}
        title={
          <span className="flex flex-wrap items-center gap-2">
            {p.name} <span className="text-sm font-normal text-gray-400">{p.key}</span> <ProjectStatusBadge project={p} />
          </span>
        }
        description={p.description || undefined}
        actions={
          <>
            <Link to={`/board/${p.key}`}>
              <Button>
                <SquareKanban className="h-4 w-4" aria-hidden /> Board
              </Button>
            </Link>
            {p.permissions.can_create_task && (
              <Button variant="primary" onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" aria-hidden /> Task
              </Button>
            )}
            {p.permissions.can_edit && (
              <Button variant="ghost" onClick={() => setEditOpen(true)} aria-label="Edit project">
                <Pencil className="h-4 w-4" aria-hidden /> Edit
              </Button>
            )}
            {p.permissions.can_archive && (
              <Button
                variant="ghost"
                loading={archive.isPending}
                onClick={async () => {
                  const ok =
                    !!p.archived_at ||
                    (await confirm({
                      title: `Archive ${p.name}?`,
                      message: "The project becomes read-only and is hidden from lists until an admin restores it.",
                      confirmLabel: "Archive",
                    }));
                  if (ok) archive.mutate(!p.archived_at);
                }}
              >
                {p.archived_at ? <ArchiveRestore className="h-4 w-4" aria-hidden /> : <Archive className="h-4 w-4" aria-hidden />}
                {p.archived_at ? "Restore" : "Archive"}
              </Button>
            )}
          </>
        }
      />

      {p.archived_at && (
        <div className="mb-4 rounded-md border border-gray-200 bg-gray-100 px-4 py-2.5 text-sm text-gray-700">
          This project is archived and read-only.
        </div>
      )}

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-6">
        {STATUSES.map((s) => (
          <Link key={s} to={`/tasks?project=${p.key}&status=${s}`} className="card px-4 py-3 hover:border-gray-300">
            <p className="text-xs font-medium text-gray-500">{STATUS_LABEL[s]}</p>
            <p className="mt-1 text-xl font-semibold text-gray-900">{p.counts[s]}</p>
          </Link>
        ))}
        <Link to={`/tasks?project=${p.key}&overdue=true`} className="card px-4 py-3 hover:border-gray-300">
          <p className="text-xs font-medium text-gray-500">Overdue</p>
          <p className={`mt-1 text-xl font-semibold ${p.counts.overdue ? "text-red-600" : "text-gray-900"}`}>{p.counts.overdue}</p>
        </Link>
        <div className="card px-4 py-3">
          <p className="text-xs font-medium text-gray-500">Progress</p>
          <p className="mt-1 text-xl font-semibold text-gray-900">{pct}%</p>
          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-gray-100">
            <div className="h-full bg-brand-600" style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Section
            title="Recently updated tasks"
            action={
              <Link to={`/tasks?project=${p.key}`} className="text-xs font-medium text-brand-600 hover:underline">
                All tasks
              </Link>
            }
          >
            {tasks.isPending ? (
              <Spinner />
            ) : tasks.isError ? (
              <ErrorState error={tasks.error} />
            ) : tasks.data.items.length === 0 ? (
              <EmptyState icon={ListChecks} title="No tasks in this project yet" />
            ) : (
              <div className="divide-y divide-gray-100">
                {tasks.data.items.map((t) => (
                  <TaskRow key={t.id} task={t} showProject={false} />
                ))}
              </div>
            )}
          </Section>
          <Section title="Project activity">
            {activity.isPending ? (
              <Spinner />
            ) : !activity.data?.items.length ? (
              <p className="px-4 py-6 text-sm text-gray-500">No activity yet.</p>
            ) : (
              <ul className="divide-y divide-gray-100">
                {activity.data.items.slice(0, 10).map((e) => (
                  <ActivityItem key={e.id} event={e} />
                ))}
              </ul>
            )}
          </Section>
        </div>

        <div className="space-y-6">
          <Section title="Details">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 px-4 py-3 text-sm">
              <dt className="text-gray-500">Owner</dt>
              <dd className="text-gray-900">{p.owner.full_name}</dd>
              <dt className="text-gray-500">Start</dt>
              <dd className="text-gray-900">{formatDate(p.start_date)}</dd>
              <dt className="text-gray-500">End</dt>
              <dd className="text-gray-900">{formatDate(p.end_date)}</dd>
              <dt className="text-gray-500">Task creation</dt>
              <dd className="text-gray-900">{p.members_can_create_tasks ? "All members" : "Managers only"}</dd>
            </dl>
          </Section>
          <MembersSection project={p} />
        </div>
      </div>

      {p.permissions.can_edit && <EditProjectDialog project={p} open={editOpen} onClose={() => setEditOpen(false)} />}
      <CreateTaskDialog open={createOpen} onClose={() => setCreateOpen(false)} defaultProject={p.key} />
    </>
  );
}

function MembersSection({ project }: { project: ProjectDetail }) {
  const team = useTeam();
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<ProjectRole>("developer");
  const canManage = project.permissions.can_manage_members;
  const memberIds = new Set(project.members.map((m) => m.user.id));
  const candidates = (team.data ?? []).filter((u) => u.is_active && !memberIds.has(u.id));

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["project", project.key] });
    qc.invalidateQueries({ queryKey: ["users"] });
    qc.invalidateQueries({ queryKey: ["activity"] });
  };
  const add = useMutation({
    mutationFn: () => api.post(`/projects/${project.key}/members`, { user_id: Number(userId), role }),
    onSuccess: () => {
      setUserId("");
      refresh();
      toast.success("Member added");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const changeRole = useMutation({
    mutationFn: (v: { userId: number; role: ProjectRole }) =>
      api.patch(`/projects/${project.key}/members/${v.userId}`, { role: v.role }),
    onSuccess: refresh,
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/projects/${project.key}/members/${id}`),
    onSuccess: () => {
      refresh();
      invalidateTaskViews(qc);
      toast.success("Member removed");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <Section title={`Members (${project.members.length})`}>
      <ul className="divide-y divide-gray-100">
        {project.members.map((m) => (
          <li key={m.user.id} className="flex items-center gap-3 px-4 py-2.5">
            <Avatar user={m.user} />
            <div className="min-w-0 flex-1">
              <p className={`truncate text-sm ${m.is_active ? "text-gray-900" : "text-gray-400 line-through"}`}>
                {m.user.full_name}
              </p>
              <p className="text-xs text-gray-500">{m.open_task_count} open tasks</p>
            </div>
            {canManage ? (
              <>
                <select
                  aria-label={`Role of ${m.user.full_name}`}
                  className="input h-8 w-28 py-0 text-xs"
                  value={m.role}
                  onChange={(e) => changeRole.mutate({ userId: m.user.id, role: e.target.value as ProjectRole })}
                >
                  {PROJECT_ROLES.map((r) => (
                    <option key={r} value={r}>
                      {ROLE_LABEL[r]}
                    </option>
                  ))}
                </select>
                <button
                  className="rounded p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600"
                  aria-label={`Remove ${m.user.full_name}`}
                  onClick={async () => {
                    const ok = await confirm({
                      title: `Remove ${m.user.full_name}?`,
                      message: m.open_task_count
                        ? `They will lose access to ${project.name}, and their ${m.open_task_count} open tasks will become unassigned.`
                        : `They will lose access to ${project.name}.`,
                      confirmLabel: "Remove",
                      danger: true,
                    });
                    if (ok) remove.mutate(m.user.id);
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </>
            ) : (
              <span className="text-xs text-gray-500">{ROLE_LABEL[m.role]}</span>
            )}
          </li>
        ))}
      </ul>
      {canManage && (
        <form
          className="flex flex-wrap gap-2 border-t border-gray-100 p-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (userId) add.mutate();
          }}
        >
          <select aria-label="Person to add" className="input h-8 min-w-0 flex-1 py-0 text-xs" value={userId} onChange={(e) => setUserId(e.target.value)}>
            <option value="">{candidates.length ? "Add a team member…" : "Everyone is already a member"}</option>
            {candidates.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name}
              </option>
            ))}
          </select>
          <select aria-label="Role" className="input h-8 w-28 py-0 text-xs" value={role} onChange={(e) => setRole(e.target.value as ProjectRole)}>
            {PROJECT_ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r]}
              </option>
            ))}
          </select>
          <Button type="submit" size="sm" disabled={!userId} loading={add.isPending}>
            <UserPlus className="h-3.5 w-3.5" aria-hidden /> Add
          </Button>
        </form>
      )}
    </Section>
  );
}

function EditProjectDialog({ project, open, onClose }: { project: ProjectDetail; open: boolean; onClose: () => void }) {
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description);
  const [status, setStatus] = useState<ProjectStatus>(project.status);
  const [startDate, setStartDate] = useState(project.start_date ?? "");
  const [endDate, setEndDate] = useState(project.end_date ?? "");
  const [membersCreate, setMembersCreate] = useState(project.members_can_create_tasks);
  const [error, setError] = useState<string | null>(null);
  const qc = useQueryClient();
  const toast = useToast();

  useEffect(() => {
    if (!open) return;
    setName(project.name);
    setDescription(project.description);
    setStatus(project.status);
    setStartDate(project.start_date ?? "");
    setEndDate(project.end_date ?? "");
    setMembersCreate(project.members_can_create_tasks);
    setError(null);
  }, [open, project]);

  const save = useMutation({
    mutationFn: () =>
      api.patch(`/projects/${project.key}`, {
        name: name.trim(),
        description,
        status,
        start_date: startDate || null,
        end_date: endDate || null,
        members_can_create_tasks: membersCreate,
      }),
    onSuccess: () => {
      invalidateTaskViews(qc);
      toast.success("Project updated");
      onClose();
    },
    onError: (e) => setError(errorMessage(e)),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return setError("The project needs a name.");
    if (startDate && endDate && endDate < startDate) return setError("End date can't be before the start date.");
    save.mutate();
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={`Edit ${project.key}`}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" form="edit-project" loading={save.isPending}>
            Save
          </Button>
        </>
      }
    >
      <form id="edit-project" onSubmit={submit} className="space-y-4" noValidate>
        <FormError message={error} />
        <Field label="Name">{(p) => <input {...p} className="input" value={name} onChange={(e) => setName(e.target.value)} />}</Field>
        <Field label="Description">
          {(p) => <textarea {...p} className="input min-h-[80px]" value={description} onChange={(e) => setDescription(e.target.value)} />}
        </Field>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Status">
            {(p) => (
              <select {...p} className="input" value={status} onChange={(e) => setStatus(e.target.value as ProjectStatus)}>
                {PROJECT_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {PROJECT_STATUS_LABEL[s]}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Start date">
            {(p) => <input {...p} type="date" className="input" value={startDate} onChange={(e) => setStartDate(e.target.value)} />}
          </Field>
          <Field label="End date">
            {(p) => <input {...p} type="date" className="input" value={endDate} onChange={(e) => setEndDate(e.target.value)} />}
          </Field>
        </div>
        <label className="flex items-start gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 rounded border-gray-300 text-brand-600"
            checked={membersCreate}
            onChange={(e) => setMembersCreate(e.target.checked)}
          />
          <span>
            All members can create tasks
            <span className="block text-xs text-gray-500">When off, only project managers and admins can create tasks.</span>
          </span>
        </label>
      </form>
    </Dialog>
  );
}
