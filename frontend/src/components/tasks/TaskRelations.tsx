import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Eye, EyeOff, Plus, X } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { invalidateTaskViews, useDependencies, useProject, useProjectLabels, useSubtasks } from "../../hooks/queries";
import { api, errorMessage } from "../../services/api";
import type { TaskDependencies, TaskDetail } from "../../types/api";
import { Button } from "../ui/Button";
import { ErrorState, Spinner } from "../ui/States";
import { useToast } from "../ui/Toast";
import { TaskRow } from "./TaskRow";

function SectionHeader({ title, extra }: { title: string; extra?: ReactNode }) {
  return (
    <div className="mb-2 flex items-center justify-between gap-3">
      <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
      {extra}
    </div>
  );
}

/** Child tasks (one level only) with "x of y done" progress. */
export function Subtasks({ task }: { task: TaskDetail }) {
  const subtasks = useSubtasks(task.key);
  const project = useProject(task.project.key);
  const qc = useQueryClient();
  const toast = useToast();
  const [title, setTitle] = useState("");
  const add = useMutation({
    mutationFn: () => api.post<TaskDetail>(`/tasks/${task.key}/subtasks`, { title: title.trim() }),
    onSuccess: (t) => {
      setTitle("");
      invalidateTaskViews(qc, task.key);
      toast.success(`${t.key} added`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const canAdd = !!project.data?.permissions.can_create_task;

  function submit(e: FormEvent) {
    e.preventDefault();
    if (title.trim()) add.mutate();
  }

  const data = subtasks.data;
  return (
    <section>
      <SectionHeader
        title="Subtasks"
        extra={data && data.total > 0 && <span className="text-xs text-gray-500">{data.done} of {data.total} done</span>}
      />
      {data && data.total > 0 && (
        <div className="mb-2 h-1.5 overflow-hidden rounded-full bg-gray-100" aria-hidden>
          <div className="h-full bg-green-500" style={{ width: `${(data.done / data.total) * 100}%` }} />
        </div>
      )}
      <div className="card overflow-hidden">
        {subtasks.isPending ? (
          <Spinner />
        ) : subtasks.isError ? (
          <ErrorState error={subtasks.error} onRetry={() => subtasks.refetch()} />
        ) : data!.items.length === 0 ? (
          <p className="px-4 py-3 text-sm text-gray-500">No subtasks. Split bigger work into smaller steps here.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {data!.items.map((s) => (
              <li key={s.id}>
                <TaskRow task={s} showProject={false} />
              </li>
            ))}
          </ul>
        )}
        {canAdd && (
          <form onSubmit={submit} className="flex gap-2 border-t border-gray-100 p-2">
            <input
              aria-label="New subtask title"
              className="input h-8 py-0 text-sm"
              placeholder="Add a subtask…"
              maxLength={200}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <Button type="submit" size="sm" disabled={!title.trim()} loading={add.isPending}>
              <Plus className="h-3.5 w-3.5" aria-hidden /> Add
            </Button>
          </form>
        )}
      </div>
    </section>
  );
}

/** "Depends on" and "Blocks" lists. A warning only: unfinished prerequisites never block status changes. */
export function Dependencies({ task }: { task: TaskDetail }) {
  const deps = useDependencies(task.key);
  const qc = useQueryClient();
  const toast = useToast();
  const [other, setOther] = useState("");
  const canEdit = task.permissions.can_edit;
  const onSuccess = (d: TaskDependencies) => {
    qc.setQueryData(["task", task.key, "dependencies"], d);
    qc.invalidateQueries({ queryKey: ["task", task.key, "activity"] });
  };
  const add = useMutation({
    mutationFn: () => api.post<TaskDependencies>(`/tasks/${task.key}/dependencies`, { depends_on: other.trim() }),
    onSuccess: (d) => {
      setOther("");
      onSuccess(d);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (key: string) => api.delete(`/tasks/${task.key}/dependencies/${key}`) as Promise<unknown>,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["task", task.key, "dependencies"] });
      qc.invalidateQueries({ queryKey: ["task", task.key, "activity"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (deps.isPending) return <Spinner />;
  if (deps.isError) return <ErrorState error={deps.error} onRetry={() => deps.refetch()} />;
  const d = deps.data;
  const empty = d.depends_on.length === 0 && d.blocks.length === 0;
  if (empty && !canEdit) return null;

  return (
    <section>
      <SectionHeader title="Dependencies" />
      {d.unfinished > 0 && task.status !== "done" && (
        <p className="mb-2 flex items-center gap-2 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800" role="status">
          <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
          {d.unfinished === 1 ? "1 prerequisite is" : `${d.unfinished} prerequisites are`} not done yet.
        </p>
      )}
      <div className="card overflow-hidden">
        {empty && <p className="px-4 py-3 text-sm text-gray-500">No dependencies.</p>}
        {d.depends_on.length > 0 && (
          <>
            <p className="px-4 pt-2 text-xs font-medium uppercase tracking-wide text-gray-500">Depends on</p>
            <ul className="divide-y divide-gray-100">
              {d.depends_on.map((t) => (
                <li key={t.id} className="flex items-center">
                  <div className="min-w-0 flex-1">
                    <TaskRow task={t} showProject={false} />
                  </div>
                  {canEdit && (
                    <button
                      className="mr-2 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-red-600"
                      aria-label={`Remove dependency on ${t.key}`}
                      disabled={remove.isPending}
                      onClick={() => remove.mutate(t.key)}
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
        {d.blocks.length > 0 && (
          <>
            <p className="px-4 pt-2 text-xs font-medium uppercase tracking-wide text-gray-500">Blocks</p>
            <ul className="divide-y divide-gray-100">
              {d.blocks.map((t) => (
                <li key={t.id}>
                  <TaskRow task={t} showProject={false} />
                </li>
              ))}
            </ul>
          </>
        )}
        {canEdit && (
          <form
            className="flex gap-2 border-t border-gray-100 p-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (other.trim()) add.mutate();
            }}
          >
            <input
              aria-label="Prerequisite task key"
              className="input h-8 py-0 text-sm"
              placeholder={`Depends on… e.g. ${task.project.key}-1`}
              maxLength={30}
              value={other}
              onChange={(e) => setOther(e.target.value)}
            />
            <Button type="submit" size="sm" disabled={!other.trim()} loading={add.isPending}>
              <Plus className="h-3.5 w-3.5" aria-hidden /> Add
            </Button>
          </form>
        )}
      </div>
    </section>
  );
}

/** Label chips with add/remove for editors; suggestions come from labels already used in the project. */
export function Labels({ task }: { task: TaskDetail }) {
  const qc = useQueryClient();
  const toast = useToast();
  const suggestions = useProjectLabels(task.permissions.can_edit ? task.project.key : undefined);
  const [name, setName] = useState("");
  const onSuccess = (t: TaskDetail) => {
    qc.setQueryData(["task", task.key], t);
    invalidateTaskViews(qc, task.key);
  };
  const add = useMutation({
    mutationFn: () => api.post<TaskDetail>(`/tasks/${task.key}/labels`, { name: name.trim() }),
    onSuccess: (t) => {
      setName("");
      onSuccess(t);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (label: string) => api.delete(`/tasks/${task.key}/labels/${encodeURIComponent(label)}`),
    onSuccess: () => invalidateTaskViews(qc, task.key),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const canEdit = task.permissions.can_edit;
  const listId = `labels-${task.key}`;

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap gap-1">
        {task.labels.length === 0 && !canEdit && <span className="text-gray-500">None</span>}
        {task.labels.map((l) => (
          <span key={l} className="inline-flex items-center gap-1 rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700">
            {l}
            {canEdit && (
              <button
                aria-label={`Remove label ${l}`}
                className="text-gray-400 hover:text-red-600"
                disabled={remove.isPending}
                onClick={() => remove.mutate(l)}
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </span>
        ))}
      </div>
      {canEdit && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) add.mutate();
          }}
        >
          <input
            aria-label="Add label"
            className="input h-7 py-0 text-xs"
            placeholder="Add label + Enter"
            list={listId}
            maxLength={30}
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={add.isPending}
          />
          <datalist id={listId}>
            {(suggestions.data ?? [])
              .filter((s) => !task.labels.includes(s))
              .map((s) => (
                <option key={s} value={s} />
              ))}
          </datalist>
        </form>
      )}
    </div>
  );
}

export function WatchButton({ task }: { task: TaskDetail }) {
  const qc = useQueryClient();
  const toast = useToast();
  const toggle = useMutation({
    mutationFn: async () => {
      if (task.watching) await api.delete(`/tasks/${task.key}/watch`);
      else await api.post<TaskDetail>(`/tasks/${task.key}/watch`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["task", task.key] }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const count = task.watchers.length;
  return (
    <Button
      variant="ghost"
      size="sm"
      loading={toggle.isPending}
      onClick={() => toggle.mutate()}
      title={count ? `Watching: ${task.watchers.map((w) => w.full_name).join(", ")}` : "Nobody is watching this task"}
    >
      {task.watching ? <EyeOff className="h-4 w-4" aria-hidden /> : <Eye className="h-4 w-4" aria-hidden />}
      {task.watching ? "Unwatch" : "Watch"}
      {count > 0 && <span className="rounded bg-gray-100 px-1 text-gray-600">{count}</span>}
    </Button>
  );
}
