import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FolderKanban, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { DueDate, PriorityIcon, TypeIcon } from "../components/tasks/TaskBits";
import { CreateTaskDialog } from "../components/tasks/TaskForm";
import { Avatar } from "../components/ui/Avatar";
import { Button } from "../components/ui/Button";
import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState, ErrorState, Spinner } from "../components/ui/States";
import { useToast } from "../components/ui/Toast";
import { invalidateTaskViews, useBoard, useProject, useProjects } from "../hooks/queries";
import { ApiError, api, errorMessage } from "../services/api";
import type { Board, Task, TaskStatus } from "../types/api";
import { PRIORITIES, PRIORITY_LABEL, STATUS_LABEL } from "../utils/labels";
import { NotFoundPage } from "./NotFoundPage";

const LAST_BOARD = "teamflow:last-board";

function rememberBoard(key: string) {
  try {
    localStorage.setItem(LAST_BOARD, key);
  } catch {
    // Storage can be unavailable (private mode); remembering the board is only a convenience.
  }
}

/** /board without a project: open the last board used, or the first project. */
export function BoardIndexPage() {
  const projects = useProjects();
  if (projects.isPending) return <Spinner />;
  if (projects.isError) return <ErrorState error={projects.error} onRetry={() => projects.refetch()} />;
  let last: string | null = null;
  try {
    last = localStorage.getItem(LAST_BOARD);
  } catch {
    last = null;
  }
  const target = projects.data.find((p) => p.key === last) ?? projects.data[0];
  if (target) return <Navigate to={`/board/${target.key}`} replace />;
  return (
    <>
      <PageHeader title="Board" />
      <div className="card">
        <EmptyState icon={FolderKanban} title="No projects yet" description="Boards appear once you're a member of a project." />
      </div>
    </>
  );
}

const columnTone: Record<TaskStatus, string> = {
  todo: "bg-gray-400",
  in_progress: "bg-blue-500",
  in_review: "bg-amber-500",
  done: "bg-green-500",
};

export function BoardPage() {
  const { key } = useParams();
  const navigate = useNavigate();
  const projects = useProjects();
  const project = useProject(key);
  const [assignee, setAssignee] = useState("");
  const [priority, setPriority] = useState("");
  const [q, setQ] = useState("");
  const filters = { assignee: assignee || undefined, priority: priority ? [priority] : undefined, q: q || undefined };
  const board = useBoard(key, filters);
  const [dragging, setDragging] = useState<Task | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const qc = useQueryClient();
  const toast = useToast();

  useEffect(() => {
    if (key) rememberBoard(key.toUpperCase());
  }, [key]);

  const sensors = useSensors(
    // A small distance lets a plain click open the task instead of starting a drag.
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  );

  const boardKey = ["board", key, filters];
  const move = useMutation({
    mutationFn: ({ task, to }: { task: Task; to: TaskStatus }) =>
      api.post<Task>(`/tasks/${task.key}/transitions`, { to_status: to, version: task.version }),
    onMutate: async ({ task, to }) => {
      // Optimistic: move the card now, roll back if the server says no.
      await qc.cancelQueries({ queryKey: boardKey });
      const previous = qc.getQueryData<Board>(boardKey);
      if (previous) {
        qc.setQueryData<Board>(boardKey, {
          ...previous,
          columns: previous.columns.map((c) => ({
            ...c,
            tasks:
              c.status === to
                ? [{ ...task, status: to, allowed_transitions: [] }, ...c.tasks]
                : c.tasks.filter((t) => t.id !== task.id),
          })),
        });
      }
      return { previous };
    },
    onError: (err, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(boardKey, ctx.previous);
      toast.error(
        err instanceof ApiError && err.code === "stale_version"
          ? "Someone else just changed this task. The board has been refreshed."
          : errorMessage(err),
      );
    },
    onSuccess: (task) => toast.success(`${task.key} moved to ${STATUS_LABEL[task.status]}`),
    onSettled: (_data, _err, vars) => invalidateTaskViews(qc, vars.task.key),
  });

  function onDragStart(e: DragStartEvent) {
    setDragging((e.active.data.current as { task: Task }).task);
  }

  function onDragEnd(e: DragEndEvent) {
    setDragging(null);
    const task = (e.active.data.current as { task: Task } | undefined)?.task;
    const to = e.over?.id as TaskStatus | undefined;
    if (!task || !to || to === task.status) return;
    if (!task.allowed_transitions.includes(to)) {
      const options = task.allowed_transitions.map((s) => STATUS_LABEL[s]).join(" or ");
      toast.error(
        options
          ? `${task.key} can move from ${STATUS_LABEL[task.status]} to ${options} only.`
          : `You can't move ${task.key} from ${STATUS_LABEL[task.status]}. Only its assignee, a tester or a manager can.`,
      );
      return;
    }
    move.mutate({ task, to });
  }

  if (project.isError && project.error instanceof ApiError && project.error.status === 404) {
    return <NotFoundPage what="board" />;
  }

  const total = board.data?.columns.reduce((n, c) => n + c.tasks.length, 0) ?? 0;
  const filtered = !!(assignee || priority || q);

  return (
    <>
      <PageHeader
        breadcrumb={project.data ? [{ label: project.data.name, to: `/projects/${project.data.key}` }] : undefined}
        title="Board"
        actions={
          <>
            <select
              aria-label="Project"
              className="input h-9 w-48"
              value={key?.toUpperCase()}
              onChange={(e) => navigate(`/board/${e.target.value}`)}
            >
              {(projects.data ?? []).map((p) => (
                <option key={p.key} value={p.key}>
                  {p.name}
                </option>
              ))}
            </select>
            {project.data?.permissions.can_create_task && (
              <Button variant="primary" onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4" aria-hidden /> Task
              </Button>
            )}
          </>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          aria-label="Filter cards"
          className="input h-8 w-48 py-1"
          placeholder="Filter cards"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select aria-label="Assignee" className="input h-8 w-40 py-0" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
          <option value="">All assignees</option>
          <option value="me">Only my tasks</option>
          <option value="none">Unassigned</option>
          {(project.data?.members ?? []).map((m) => (
            <option key={m.user.id} value={m.user.id}>
              {m.user.full_name}
            </option>
          ))}
        </select>
        <select aria-label="Priority" className="input h-8 w-36 py-0" value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="">All priorities</option>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {PRIORITY_LABEL[p]}
            </option>
          ))}
        </select>
        {filtered && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setAssignee("");
              setPriority("");
              setQ("");
            }}
          >
            Clear
          </Button>
        )}
        <p className="ml-auto hidden text-xs text-gray-500 md:block">
          Drag cards between columns, or open a task to change its status.
        </p>
      </div>

      {board.isPending ? (
        <Spinner />
      ) : board.isError ? (
        <ErrorState error={board.error} onRetry={() => board.refetch()} />
      ) : (
        <>
          {project.data?.archived_at && (
            <div className="mb-3 rounded-md bg-gray-100 px-4 py-2 text-sm text-gray-700">This project is archived; the board is read-only.</div>
          )}
          <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setDragging(null)}>
            <div className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-4 sm:mx-0 sm:px-0">
              {board.data.columns.map((col) => (
                <Column key={col.status} status={col.status} tasks={col.tasks} dragging={dragging} />
              ))}
            </div>
            <DragOverlay>{dragging ? <Card task={dragging} overlay /> : null}</DragOverlay>
          </DndContext>
          {total === 0 && !filtered && (
            <p className="mt-2 text-center text-sm text-gray-500">
              No tasks on this board yet. Use <span className="font-medium">Create</span> to add the first one.
            </p>
          )}
        </>
      )}

      <CreateTaskDialog open={createOpen} onClose={() => setCreateOpen(false)} defaultProject={key?.toUpperCase()} />
    </>
  );
}

function Column({ status, tasks, dragging }: { status: TaskStatus; tasks: Task[]; dragging: Task | null }) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  const canDrop = dragging ? dragging.allowed_transitions.includes(status) : false;
  const isSource = dragging?.status === status;
  return (
    <section
      ref={setNodeRef}
      aria-label={`${STATUS_LABEL[status]} column`}
      className={`flex w-72 shrink-0 flex-col rounded-lg border bg-gray-100/70 transition-colors lg:w-auto lg:flex-1 ${
        dragging && !isSource
          ? canDrop
            ? isOver
              ? "border-brand-500 bg-brand-50"
              : "border-dashed border-brand-200"
            : "border-transparent opacity-60"
          : "border-transparent"
      }`}
    >
      <header className="flex items-center gap-2 px-3 py-2.5">
        <span className={`h-2 w-2 rounded-full ${columnTone[status]}`} aria-hidden />
        <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-600">{STATUS_LABEL[status]}</h2>
        <span className="text-xs text-gray-400">{tasks.length}</span>
      </header>
      <div className="flex min-h-[120px] flex-1 flex-col gap-2 px-2 pb-2">
        {tasks.map((t) => (
          <DraggableCard key={t.id} task={t} />
        ))}
        {tasks.length === 0 && <p className="px-2 py-6 text-center text-xs text-gray-400">No tasks</p>}
      </div>
    </section>
  );
}

function DraggableCard({ task }: { task: Task }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: task.id,
    data: { task },
    disabled: task.allowed_transitions.length === 0,
  });
  return (
    <div ref={setNodeRef} {...listeners} {...attributes} className={isDragging ? "opacity-30" : ""}>
      <Card task={task} />
    </div>
  );
}

function Card({ task, overlay = false }: { task: Task; overlay?: boolean }) {
  const movable = task.allowed_transitions.length > 0;
  const body = (
    <>
      <p className="line-clamp-3 text-sm text-gray-900">{task.title}</p>
      <div className="mt-2.5 flex items-center gap-2">
        <TypeIcon type={task.type} />
        <span className={`text-xs font-medium ${task.status === "done" ? "text-gray-400 line-through" : "text-gray-500"}`}>
          {task.key}
        </span>
        <PriorityIcon priority={task.priority} />
        <span className="ml-auto flex items-center gap-2">
          <DueDate due={task.due_date} overdue={task.is_overdue} done={task.status === "done"} />
          <Avatar user={task.assignee} />
        </span>
      </div>
    </>
  );
  const cls = `block rounded-md border bg-white p-3 shadow-card ${
    overlay ? "rotate-1 border-brand-200 shadow-pop" : "border-gray-200 hover:border-gray-300"
  } ${task.is_overdue ? "border-l-2 border-l-red-500" : ""} ${movable ? "cursor-grab active:cursor-grabbing" : ""}`;
  if (overlay) return <div className={cls}>{body}</div>;
  return (
    <Link to={`/tasks/${task.key}`} className={cls} draggable={false}>
      {body}
    </Link>
  );
}
