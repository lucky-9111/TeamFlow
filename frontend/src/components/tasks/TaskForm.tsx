import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { invalidateTaskViews, useProject, useProjects } from "../../hooks/queries";
import { ApiError, api, errorMessage } from "../../services/api";
import type { TaskDetail, TaskPriority, TaskType } from "../../types/api";
import { PRIORITIES, PRIORITY_LABEL, TYPES, TYPE_LABEL } from "../../utils/labels";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { Field, FormError } from "../ui/Field";
import { useToast } from "../ui/Toast";

interface Props {
  open: boolean;
  onClose: () => void;
  defaultProject?: string;
}

/** The "Create" dialog. Only the essentials up front; details can be added on the task page. */
export function CreateTaskDialog({ open, onClose, defaultProject }: Props) {
  const { data: projects } = useProjects();
  const creatable = (projects ?? []).filter((p) => p.archived_at === null);
  const [projectKey, setProjectKey] = useState(defaultProject ?? "");
  const [title, setTitle] = useState("");
  const [type, setType] = useState<TaskType>("task");
  const [priority, setPriority] = useState<TaskPriority>("medium");
  const [assignee, setAssignee] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [description, setDescription] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  // Until the user picks one, default to their first active project.
  const effectiveKey = projectKey || creatable[0]?.key || "";
  const project = useProject(effectiveKey || undefined);
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    setProjectKey(defaultProject ?? "");
    setTitle("");
    setType("task");
    setPriority("medium");
    setAssignee("");
    setDueDate("");
    setDescription("");
    setErrors({});
    setFormError(null);
  }, [open, defaultProject]);

  const create = useMutation({
    mutationFn: () =>
      api.post<TaskDetail>(`/projects/${effectiveKey}/tasks`, {
        title: title.trim(),
        type,
        priority,
        description,
        assignee_id: assignee ? Number(assignee) : null,
        due_date: dueDate || null,
      }),
    onSuccess: (task) => {
      invalidateTaskViews(qc);
      toast.success(`Created ${task.key}`);
      onClose();
      navigate(`/tasks/${task.key}`);
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 422) setErrors(err.fieldErrors());
      setFormError(errorMessage(err));
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!effectiveKey) next.project = "Choose a project";
    if (!title.trim()) next.title = "Give the task a short title";
    setErrors(next);
    setFormError(null);
    if (Object.keys(next).length === 0) create.mutate();
  }

  const cannotCreate = project.data && !project.data.permissions.can_create_task;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Create task"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" form="create-task" loading={create.isPending} disabled={!!cannotCreate}>
            Create
          </Button>
        </>
      }
    >
      {creatable.length === 0 ? (
        <p className="text-sm text-gray-600">
          You're not a member of any active project yet. Ask an admin to add you to one.
        </p>
      ) : (
        <form id="create-task" onSubmit={submit} className="space-y-4" noValidate>
          <FormError message={formError} />
          {cannotCreate && (
            <FormError message="Only project managers can create tasks in this project." />
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Project" error={errors.project}>
              {(p) => (
                <select {...p} className="input" value={effectiveKey} onChange={(e) => setProjectKey(e.target.value)}>
                  {creatable.map((pr) => (
                    <option key={pr.key} value={pr.key}>
                      {pr.name} ({pr.key})
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label="Type">
              {(p) => (
                <select {...p} className="input" value={type} onChange={(e) => setType(e.target.value as TaskType)}>
                  {TYPES.map((t) => (
                    <option key={t} value={t}>
                      {TYPE_LABEL[t]}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          </div>
          <Field label="Title" error={errors.title}>
            {(p) => (
              <input
                {...p}
                className={`input ${errors.title ? "input-invalid" : ""}`}
                value={title}
                maxLength={200}
                placeholder="What needs to be done?"
                onChange={(e) => setTitle(e.target.value)}
              />
            )}
          </Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Priority">
              {(p) => (
                <select
                  {...p}
                  className="input"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value as TaskPriority)}
                >
                  {PRIORITIES.map((pr) => (
                    <option key={pr} value={pr}>
                      {PRIORITY_LABEL[pr]}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label="Assignee" error={errors.assignee_id}>
              {(p) => (
                <select {...p} className="input" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
                  <option value="">Unassigned</option>
                  {project.data?.members
                    .filter((m) => m.is_active)
                    .map((m) => (
                      <option key={m.user.id} value={m.user.id}>
                        {m.user.full_name}
                      </option>
                    ))}
                </select>
              )}
            </Field>
            <Field label="Due date" error={errors.due_date}>
              {(p) => (
                <input {...p} type="date" className="input" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
              )}
            </Field>
          </div>
          <Field label="Description" hint="Optional. You can add more detail later.">
            {(p) => (
              <textarea
                {...p}
                className="input min-h-[80px]"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            )}
          </Field>
        </form>
      )}
    </Dialog>
  );
}
