import { ArrowDownWideNarrow, ArrowUpNarrowWide, ListChecks, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { BulkBar } from "../components/tasks/BulkBar";
import { DueDate, PriorityIcon, StatusBadge, TypeIcon } from "../components/tasks/TaskBits";
import { CreateTaskDialog } from "../components/tasks/TaskForm";
import { Avatar } from "../components/ui/Avatar";
import { Button } from "../components/ui/Button";
import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState, ErrorState, Spinner } from "../components/ui/States";
import { useProjects, useTasks, useTeam, type TaskFilters } from "../hooks/queries";
import { timeAgo } from "../utils/format";
import { PRIORITIES, PRIORITY_LABEL, STATUSES, STATUS_LABEL, TYPES, TYPE_LABEL } from "../utils/labels";

const OPEN = ["todo", "in_progress", "in_review"];
const PAGE_SIZE = 25;
const SORTS = [
  { value: "updated", label: "Last updated" },
  { value: "created", label: "Created" },
  { value: "due", label: "Due date" },
  { value: "priority", label: "Priority" },
  { value: "status", label: "Status" },
  { value: "key", label: "Key" },
];

export function TasksPage() {
  const [params, setParams] = useSearchParams();
  const [createOpen, setCreateOpen] = useState(false);
  const projects = useProjects();
  const team = useTeam();

  const statuses = params.getAll("status");
  const filters: TaskFilters = {
    project: params.get("project") ?? undefined,
    status: statuses.length ? statuses : undefined,
    priority: params.getAll("priority").length ? params.getAll("priority") : undefined,
    type: params.getAll("type").length ? params.getAll("type") : undefined,
    assignee: params.get("assignee") ?? undefined,
    q: params.get("q") ?? undefined,
    overdue: params.get("overdue") === "true" || undefined,
    label: params.get("label") ?? undefined,
    sort: params.get("sort") ?? "updated",
    order: (params.get("order") as "asc" | "desc") ?? (params.get("sort") === "due" ? "asc" : "desc"),
    page: Number(params.get("page") ?? 1),
    page_size: PAGE_SIZE,
  };
  const { data, isPending, isError, error, refetch, isFetching } = useTasks(filters);

  // Selection for bulk actions; it only ever covers the rows on screen, so any filter change resets it.
  const [selected, setSelected] = useState<string[]>([]);
  useEffect(() => setSelected([]), [params]);
  const pageKeys = data?.items.map((t) => t.key) ?? [];
  const allSelected = pageKeys.length > 0 && pageKeys.every((k) => selected.includes(k));
  const toggle = (key: string) => setSelected((s) => (s.includes(key) ? s.filter((k) => k !== key) : [...s, key]));

  // The search box updates the URL after a pause, so typing doesn't fire a request per key.
  const [q, setQ] = useState(filters.q ?? "");
  useEffect(() => setQ(params.get("q") ?? ""), [params]);
  useEffect(() => {
    const t = setTimeout(() => {
      if ((params.get("q") ?? "") !== q) update({ q: q || null });
    }, 300);
    return () => clearTimeout(t);
  }, [q]); // only the typed text should trigger this, not every URL change

  function update(changes: Record<string, string | string[] | null>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      next.delete(key);
      if (Array.isArray(value)) value.forEach((v) => next.append(key, v));
      else if (value) next.set(key, value);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next, { replace: true });
  }

  const statusValue =
    statuses.length === 0 ? "" : statuses.length === 3 && OPEN.every((s) => statuses.includes(s)) ? "open" : statuses[0];
  const onlyMine = filters.assignee === "me";
  const activeFilters = ["project", "status", "priority", "type", "assignee", "q", "overdue", "label"].some((k) => params.has(k));
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <>
      <PageHeader
        title={onlyMine && !filters.q ? "My Tasks" : "Tasks"}
        description={onlyMine ? "Everything assigned to you across projects." : "Search and filter tasks across your projects."}
        actions={
          <Button variant="primary" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" aria-hidden /> Create task
          </Button>
        }
      />

      <div className="card mb-4 flex flex-wrap items-end gap-3 p-3">
        <div className="min-w-[180px] flex-1">
          <label className="label" htmlFor="task-search">
            Search
          </label>
          <input
            id="task-search"
            className="input"
            placeholder="Title or key, e.g. TF-12"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <FilterSelect
          label="Project"
          value={filters.project ?? ""}
          onChange={(v) => update({ project: v })}
          options={(projects.data ?? []).map((p) => ({ value: p.key, label: p.name }))}
        />
        <FilterSelect
          label="Status"
          value={statusValue}
          onChange={(v) => update({ status: v === "open" ? OPEN : v || null })}
          options={[{ value: "open", label: "Open (not done)" }, ...STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] }))]}
        />
        <FilterSelect
          label="Priority"
          value={filters.priority?.[0] ?? ""}
          onChange={(v) => update({ priority: v })}
          options={PRIORITIES.map((p) => ({ value: p, label: PRIORITY_LABEL[p] }))}
        />
        <FilterSelect
          label="Type"
          value={filters.type?.[0] ?? ""}
          onChange={(v) => update({ type: v })}
          options={TYPES.map((t) => ({ value: t, label: TYPE_LABEL[t] }))}
        />
        <FilterSelect
          label="Assignee"
          value={filters.assignee ?? ""}
          onChange={(v) => update({ assignee: v })}
          options={[
            { value: "me", label: "Me" },
            { value: "none", label: "Unassigned" },
            ...(team.data ?? []).map((u) => ({ value: String(u.id), label: u.full_name })),
          ]}
        />
        <LabelFilter value={filters.label ?? ""} onChange={(v) => update({ label: v || null })} />
        <label className="flex h-9 items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-gray-300 text-brand-600"
            checked={!!filters.overdue}
            onChange={(e) => update({ overdue: e.target.checked ? "true" : null })}
          />
          Overdue
        </label>
        <div className="flex items-end gap-1">
          <FilterSelect
            label="Sort by"
            value={filters.sort!}
            onChange={(v) => update({ sort: v || "updated", order: null })}
            options={SORTS}
            allowEmpty={false}
          />
          <Button
            variant="ghost"
            className="h-9 w-9 !px-0"
            onClick={() => update({ order: filters.order === "asc" ? "desc" : "asc" })}
            aria-label={filters.order === "asc" ? "Sort descending" : "Sort ascending"}
            title={filters.order === "asc" ? "Ascending" : "Descending"}
          >
            {filters.order === "asc" ? <ArrowUpNarrowWide className="h-4 w-4" /> : <ArrowDownWideNarrow className="h-4 w-4" />}
          </Button>
        </div>
        {activeFilters && (
          <Button variant="ghost" onClick={() => setParams({}, { replace: true })}>
            Clear filters
          </Button>
        )}
      </div>

      {selected.length > 0 && <BulkBar keys={selected} onDone={setSelected} />}

      <div className={`card overflow-hidden transition-opacity ${isFetching && !isPending ? "opacity-70" : ""}`}>
        {isPending ? (
          <Spinner />
        ) : isError ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : data.items.length === 0 ? (
          <EmptyState
            icon={ListChecks}
            title={activeFilters ? "No tasks match these filters" : "No tasks yet"}
            description={activeFilters ? "Try removing a filter or searching for something else." : "Create the first task to get started."}
            action={
              activeFilters ? (
                <Button size="sm" onClick={() => setParams({}, { replace: true })}>
                  Clear filters
                </Button>
              ) : undefined
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px]">
              <thead className="border-b border-gray-200 bg-gray-50">
                <tr>
                  <th className="table-head w-10">
                    <input
                      type="checkbox"
                      aria-label="Select all tasks on this page"
                      className="h-4 w-4 rounded border-gray-300 text-brand-600"
                      checked={allSelected}
                      onChange={() => setSelected(allSelected ? [] : pageKeys)}
                    />
                  </th>
                  <th className="table-head w-24">Key</th>
                  <th className="table-head">Title</th>
                  <th className="table-head hidden lg:table-cell">Project</th>
                  <th className="table-head">Status</th>
                  <th className="table-head">Priority</th>
                  <th className="table-head">Assignee</th>
                  <th className="table-head">Due</th>
                  <th className="table-head hidden xl:table-cell">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.items.map((t) => (
                  <tr key={t.id} className={`group hover:bg-gray-50 ${selected.includes(t.key) ? "bg-brand-50/40" : ""}`}>
                    <td className="px-4 py-2.5">
                      <input
                        type="checkbox"
                        aria-label={`Select ${t.key}`}
                        className="h-4 w-4 rounded border-gray-300 text-brand-600"
                        checked={selected.includes(t.key)}
                        onChange={() => toggle(t.key)}
                      />
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-2 text-xs font-medium text-gray-500">
                        <TypeIcon type={t.type} />
                        {t.key}
                      </span>
                    </td>
                    <td className="max-w-0 px-4 py-2.5">
                      <Link to={`/tasks/${t.key}`} className="block truncate font-medium text-gray-900 group-hover:text-brand-700">
                        {t.title}
                      </Link>
                      {(t.parent_key || t.labels.length > 0) && (
                        <span className="mt-0.5 flex flex-wrap gap-1 text-xs text-gray-500">
                          {t.parent_key && <span>Subtask of {t.parent_key}</span>}
                          {t.labels.map((l) => (
                            <span key={l} className="rounded bg-gray-100 px-1.5 text-gray-600">
                              {l}
                            </span>
                          ))}
                        </span>
                      )}
                    </td>
                    <td className="hidden px-4 py-2.5 text-gray-600 lg:table-cell">{t.project.name}</td>
                    <td className="px-4 py-2.5">
                      <StatusBadge status={t.status} />
                    </td>
                    <td className="px-4 py-2.5">
                      <PriorityIcon priority={t.priority} withLabel />
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-2 text-gray-700">
                        <Avatar user={t.assignee} />
                        <span className="hidden truncate md:inline">{t.assignee?.full_name ?? "Unassigned"}</span>
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5">
                      <DueDate due={t.due_date} overdue={t.is_overdue} done={t.status === "done"} />
                    </td>
                    <td className="hidden whitespace-nowrap px-4 py-2.5 text-xs text-gray-500 xl:table-cell">
                      {timeAgo(t.updated_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && data.total > PAGE_SIZE && (
          <div className="flex items-center justify-between border-t border-gray-100 px-4 py-2.5 text-sm text-gray-600">
            <span>
              {(filters.page! - 1) * PAGE_SIZE + 1}–{Math.min(filters.page! * PAGE_SIZE, data.total)} of {data.total}
            </span>
            <div className="flex gap-2">
              <Button size="sm" disabled={filters.page! <= 1} onClick={() => update({ page: String(filters.page! - 1) })}>
                Previous
              </Button>
              <Button size="sm" disabled={filters.page! >= pages} onClick={() => update({ page: String(filters.page! + 1) })}>
                Next
              </Button>
            </div>
          </div>
        )}
      </div>

      <CreateTaskDialog open={createOpen} onClose={() => setCreateOpen(false)} defaultProject={filters.project} />
    </>
  );
}

/** Applies on Enter or when the field loses focus, so typing doesn't refetch per key. */
function LabelFilter({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  return (
    <div className="w-36">
      <label className="label" htmlFor="filter-label">
        Label
      </label>
      <input
        id="filter-label"
        className="input"
        placeholder="Any"
        maxLength={30}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => draft.trim() !== value && onChange(draft.trim())}
        onKeyDown={(e) => e.key === "Enter" && onChange(draft.trim())}
      />
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
  allowEmpty = true,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  allowEmpty?: boolean;
}) {
  const id = `filter-${label.toLowerCase().replace(/\s/g, "-")}`;
  return (
    <div className="w-36">
      <label className="label" htmlFor={id}>
        {label}
      </label>
      <select id={id} className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        {allowEmpty && <option value="">Any</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
