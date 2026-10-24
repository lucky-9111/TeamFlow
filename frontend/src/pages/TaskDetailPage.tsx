import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, MessageSquare, Pencil, Trash2 } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ActivityItem } from "../components/ActivityItem";
import { StatusBadge, TypeIcon } from "../components/tasks/TaskBits";
import { Avatar } from "../components/ui/Avatar";
import { Button } from "../components/ui/Button";
import { useConfirm } from "../components/ui/Confirm";
import { PageHeader } from "../components/ui/PageHeader";
import { ErrorState, Spinner } from "../components/ui/States";
import { useToast } from "../components/ui/Toast";
import { invalidateTaskViews, useComments, useProject, useTask, useTaskActivity } from "../hooks/queries";
import { ApiError, api, errorMessage } from "../services/api";
import type { Comment, TaskDetail, TaskStatus } from "../types/api";
import { formatDate, formatDateTime, timeAgo } from "../utils/format";
import { PRIORITIES, PRIORITY_LABEL, STATUS_LABEL, TYPES, TYPE_LABEL } from "../utils/labels";
import { NotFoundPage } from "./NotFoundPage";

type Patch = Partial<Pick<TaskDetail, "title" | "description" | "type" | "priority" | "start_date" | "due_date">> & {
  assignee_id?: number | null;
};

export function TaskDetailPage() {
  const { key = "" } = useParams();
  const task = useTask(key);
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const confirm = useConfirm();
  const [tab, setTab] = useState<"comments" | "activity">("comments");

  const onConflict = (err: unknown) => {
    if (err instanceof ApiError && err.code === "stale_version") {
      toast.error("Someone else changed this task. Showing the latest version.");
      qc.invalidateQueries({ queryKey: ["task", key] });
    } else {
      toast.error(errorMessage(err));
    }
  };

  const update = useMutation({
    mutationFn: (patch: Patch) => api.patch<TaskDetail>(`/tasks/${key}`, { ...patch, version: task.data!.version }),
    onSuccess: (t) => {
      qc.setQueryData(["task", key], t);
      invalidateTaskViews(qc, key);
    },
    onError: onConflict,
  });

  const transition = useMutation({
    mutationFn: (to: TaskStatus) =>
      api.post<TaskDetail>(`/tasks/${key}/transitions`, { to_status: to, version: task.data!.version }),
    onSuccess: (t) => {
      qc.setQueryData(["task", key], t);
      invalidateTaskViews(qc, key);
      toast.success(`Moved to ${STATUS_LABEL[t.status]}`);
    },
    onError: onConflict,
  });

  const remove = useMutation({
    mutationFn: () => api.delete(`/tasks/${key}`),
    onSuccess: () => {
      invalidateTaskViews(qc);
      qc.removeQueries({ queryKey: ["task", key] });
      toast.success(`${key} deleted`);
      navigate(`/projects/${task.data!.project.key}`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (task.isPending) return <Spinner />;
  if (task.isError) {
    if (task.error instanceof ApiError && task.error.status === 404) return <NotFoundPage what="task" />;
    return <ErrorState error={task.error} onRetry={() => task.refetch()} />;
  }
  const t = task.data;
  const canEdit = t.permissions.can_edit;

  return (
    <>
      <PageHeader
        breadcrumb={[
          { label: t.project.name, to: `/projects/${t.project.key}` },
          { label: "Board", to: `/board/${t.project.key}` },
        ]}
        title={
          <span className="flex items-center gap-2 text-sm font-medium text-gray-500">
            <TypeIcon type={t.type} /> {t.key}
          </span>
        }
        actions={
          t.permissions.can_delete && (
            <Button
              variant="ghost"
              size="sm"
              loading={remove.isPending}
              onClick={async () => {
                const ok = await confirm({
                  title: `Delete ${t.key}?`,
                  message: "The task, its comments and its history will be removed permanently.",
                  confirmLabel: "Delete task",
                  danger: true,
                });
                if (ok) remove.mutate();
              }}
            >
              <Trash2 className="h-4 w-4" aria-hidden /> Delete
            </Button>
          )
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="min-w-0 space-y-6 lg:col-span-2">
          <EditableTitle value={t.title} canEdit={canEdit} onSave={(title) => update.mutateAsync({ title })} />

          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={t.status} />
            {t.allowed_transitions.map((s) => (
              <Button key={s} size="sm" onClick={() => transition.mutate(s)} loading={transition.isPending && transition.variables === s}>
                <ArrowRight className="h-3.5 w-3.5" aria-hidden /> {STATUS_LABEL[s]}
              </Button>
            ))}
            {t.allowed_transitions.length === 0 && t.status !== "done" && (
              <span className="text-xs text-gray-500">
                {t.status === "in_review" ? "Waiting for a tester or manager to review." : "Only the assignee or a manager can move this task."}
              </span>
            )}
          </div>

          <EditableDescription value={t.description} canEdit={canEdit} onSave={(description) => update.mutateAsync({ description })} />

          <section className="card">
            <div className="flex border-b border-gray-100 px-2" role="tablist">
              {(["comments", "activity"] as const).map((name) => (
                <button
                  key={name}
                  role="tab"
                  aria-selected={tab === name}
                  onClick={() => setTab(name)}
                  className={`border-b-2 px-3 py-2.5 text-sm font-medium capitalize ${
                    tab === name ? "border-brand-600 text-brand-700" : "border-transparent text-gray-500 hover:text-gray-800"
                  }`}
                >
                  {name}
                </button>
              ))}
            </div>
            {tab === "comments" ? <Comments taskKey={key} canComment={t.permissions.can_comment} /> : <History taskKey={key} />}
          </section>
        </div>

        <aside className="card h-fit divide-y divide-gray-100">
          <Details task={t} onChange={(patch) => update.mutate(patch)} saving={update.isPending} />
        </aside>
      </div>
    </>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[96px_1fr] items-center gap-3 px-4 py-2.5 text-sm">
      <span className="text-gray-500">{label}</span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function Details({ task: t, onChange, saving }: { task: TaskDetail; onChange: (p: Patch) => void; saving: boolean }) {
  const project = useProject(t.project.key);
  const canEdit = t.permissions.can_edit && !saving;
  const select = "input h-8 py-0 text-sm";
  return (
    <>
      <Row label="Assignee">
        {t.permissions.can_assign ? (
          <select
            aria-label="Assignee"
            className={select}
            disabled={!canEdit}
            value={t.assignee?.id ?? ""}
            onChange={(e) => onChange({ assignee_id: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="">Unassigned</option>
            {(project.data?.members ?? [])
              .filter((m) => m.is_active || m.user.id === t.assignee?.id)
              .map((m) => (
                <option key={m.user.id} value={m.user.id}>
                  {m.user.full_name}
                </option>
              ))}
          </select>
        ) : (
          <span className="flex items-center gap-2">
            <Avatar user={t.assignee} /> {t.assignee?.full_name ?? "Unassigned"}
          </span>
        )}
      </Row>
      <Row label="Priority">
        <select aria-label="Priority" className={select} disabled={!canEdit} value={t.priority} onChange={(e) => onChange({ priority: e.target.value as TaskDetail["priority"] })}>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {PRIORITY_LABEL[p]}
            </option>
          ))}
        </select>
      </Row>
      <Row label="Type">
        <select aria-label="Type" className={select} disabled={!canEdit} value={t.type} onChange={(e) => onChange({ type: e.target.value as TaskDetail["type"] })}>
          {TYPES.map((ty) => (
            <option key={ty} value={ty}>
              {TYPE_LABEL[ty]}
            </option>
          ))}
        </select>
      </Row>
      <Row label="Start date">
        <input aria-label="Start date" type="date" className={select} disabled={!canEdit} value={t.start_date ?? ""} onChange={(e) => onChange({ start_date: e.target.value || null })} />
      </Row>
      <Row label="Due date">
        <input
          aria-label="Due date"
          type="date"
          className={`${select} ${t.is_overdue ? "border-red-300 text-red-700" : ""}`}
          disabled={!canEdit}
          value={t.due_date ?? ""}
          onChange={(e) => onChange({ due_date: e.target.value || null })}
        />
      </Row>
      <Row label="Reporter">
        <span className="flex items-center gap-2 text-gray-800">
          <Avatar user={t.reporter} /> {t.reporter.full_name}
        </span>
      </Row>
      <Row label="Created">
        <span className="text-gray-700" title={formatDateTime(t.created_at)}>
          {formatDate(t.created_at)}
        </span>
      </Row>
      <Row label="Updated">
        <span className="text-gray-700" title={formatDateTime(t.updated_at)}>
          {timeAgo(t.updated_at)}
        </span>
      </Row>
      {t.completed_at && (
        <Row label="Completed">
          <span className="text-gray-700">{formatDateTime(t.completed_at)}</span>
        </Row>
      )}
      {!t.permissions.can_edit && (
        <p className="px-4 py-2.5 text-xs text-gray-500">
          Only the assignee, the reporter and project managers can edit this task.
        </p>
      )}
    </>
  );
}

function EditableTitle({ value, canEdit, onSave }: { value: string; canEdit: boolean; onSave: (v: string) => Promise<unknown> }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  // Enter submits and the following blur would save again with a stale version; allow one save at a time.
  const saving = useRef(false);
  useEffect(() => setDraft(value), [value]);

  async function save(e?: FormEvent) {
    e?.preventDefault();
    if (saving.current) return;
    const next = draft.trim();
    if (!next || next === value) {
      setDraft(value);
      setEditing(false);
      return;
    }
    saving.current = true;
    try {
      await onSave(next);
      setEditing(false);
    } catch {
      // The mutation's onError already showed a toast; keep the editor open.
    } finally {
      saving.current = false;
    }
  }

  if (editing) {
    return (
      <form onSubmit={save}>
        <input
          autoFocus
          aria-label="Title"
          className="input text-lg font-semibold"
          value={draft}
          maxLength={200}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => save()}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              setDraft(value);
              setEditing(false);
            }
          }}
        />
      </form>
    );
  }
  return (
    <h1 className="group flex items-start gap-2 text-xl font-semibold text-gray-900">
      <span className="min-w-0 break-words">{value}</span>
      {canEdit && (
        <button onClick={() => setEditing(true)} className="mt-1 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700" aria-label="Edit title">
          <Pencil className="h-4 w-4" />
        </button>
      )}
    </h1>
  );
}

function EditableDescription({ value, canEdit, onSave }: { value: string; canEdit: boolean; onSave: (v: string) => Promise<unknown> }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  useEffect(() => setDraft(value), [value]);

  async function save() {
    setSaving(true);
    try {
      await onSave(draft);
      setEditing(false);
    } catch {
      // Toast already shown.
    } finally {
      setSaving(false);
    }
  }

  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-900">Description</h2>
        {canEdit && !editing && (
          <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
            <Pencil className="h-3.5 w-3.5" aria-hidden /> Edit
          </Button>
        )}
      </div>
      {editing ? (
        <div className="space-y-2">
          <textarea
            autoFocus
            aria-label="Description"
            className="input min-h-[140px]"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <div className="flex gap-2">
            <Button variant="primary" size="sm" onClick={save} loading={saving}>
              Save
            </Button>
            <Button
              size="sm"
              onClick={() => {
                setDraft(value);
                setEditing(false);
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : value ? (
        <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-gray-800">{value}</p>
      ) : (
        <p className="text-sm text-gray-400">{canEdit ? "No description yet. Add one to explain the work." : "No description."}</p>
      )}
    </section>
  );
}

function Comments({ taskKey, canComment }: { taskKey: string; canComment: boolean }) {
  const comments = useComments(taskKey);
  const [body, setBody] = useState("");
  const qc = useQueryClient();
  const toast = useToast();
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["task", taskKey, "comments"] });
    qc.invalidateQueries({ queryKey: ["task", taskKey, "activity"] });
    qc.invalidateQueries({ queryKey: ["activity"] });
  };
  const add = useMutation({
    mutationFn: () => api.post<Comment>(`/tasks/${taskKey}/comments`, { body: body.trim() }),
    onSuccess: () => {
      setBody("");
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <div>
      {comments.isPending ? (
        <Spinner />
      ) : comments.isError ? (
        <ErrorState error={comments.error} onRetry={() => comments.refetch()} />
      ) : comments.data.length === 0 ? (
        <p className="flex items-center gap-2 px-4 py-6 text-sm text-gray-500">
          <MessageSquare className="h-4 w-4" aria-hidden /> No comments yet.
        </p>
      ) : (
        <ul className="divide-y divide-gray-100">
          {comments.data.map((c) => (
            <CommentItem key={c.id} comment={c} onChanged={refresh} />
          ))}
        </ul>
      )}
      {canComment && (
        <form
          className="space-y-2 border-t border-gray-100 p-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (body.trim()) add.mutate();
          }}
        >
          <textarea
            aria-label="Add a comment"
            className="input min-h-[72px]"
            placeholder="Add a comment…"
            value={body}
            maxLength={10000}
            onChange={(e) => setBody(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && body.trim()) add.mutate();
            }}
          />
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400">Ctrl + Enter to send</span>
            <Button type="submit" variant="primary" size="sm" disabled={!body.trim()} loading={add.isPending}>
              Comment
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

function CommentItem({ comment: c, onChanged }: { comment: Comment; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(c.body);
  const toast = useToast();
  const confirm = useConfirm();
  const edit = useMutation({
    mutationFn: () => api.patch(`/comments/${c.id}`, { body: draft.trim() }),
    onSuccess: () => {
      setEditing(false);
      onChanged();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: () => api.delete(`/comments/${c.id}`),
    onSuccess: onChanged,
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <li className="flex gap-3 px-4 py-3">
      <Avatar user={c.author} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="text-sm font-medium text-gray-900">{c.author.full_name}</span>
          <span className="text-xs text-gray-400" title={formatDateTime(c.created_at)}>
            {timeAgo(c.created_at)}
            {c.edited_at && " · edited"}
          </span>
          {c.can_edit && !editing && (
            <span className="ml-auto flex gap-2 text-xs">
              <button className="text-gray-500 hover:text-gray-800" onClick={() => setEditing(true)}>
                Edit
              </button>
              <button
                className="text-gray-500 hover:text-red-600"
                onClick={async () => {
                  if (await confirm({ title: "Delete this comment?", confirmLabel: "Delete", danger: true })) remove.mutate();
                }}
              >
                Delete
              </button>
            </span>
          )}
        </div>
        {editing ? (
          <div className="mt-1 space-y-2">
            <textarea aria-label="Edit comment" className="input min-h-[60px]" value={draft} onChange={(e) => setDraft(e.target.value)} />
            <div className="flex gap-2">
              <Button size="sm" variant="primary" disabled={!draft.trim()} loading={edit.isPending} onClick={() => edit.mutate()}>
                Save
              </Button>
              <Button
                size="sm"
                onClick={() => {
                  setDraft(c.body);
                  setEditing(false);
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <p className="mt-0.5 whitespace-pre-wrap break-words text-sm text-gray-800">{c.body}</p>
        )}
      </div>
    </li>
  );
}

function History({ taskKey }: { taskKey: string }) {
  const history = useTaskActivity(taskKey);
  if (history.isPending) return <Spinner />;
  if (history.isError) return <ErrorState error={history.error} onRetry={() => history.refetch()} />;
  if (!history.data.length) return <p className="px-4 py-6 text-sm text-gray-500">No history yet.</p>;
  return (
    <ul className="divide-y divide-gray-100">
      {history.data.map((e) => (
        <ActivityItem key={e.id} event={e} showTarget={false} />
      ))}
    </ul>
  );
}
