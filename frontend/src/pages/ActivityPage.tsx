import { Activity } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { ActivityItem } from "../components/ActivityItem";
import { Button } from "../components/ui/Button";
import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState, ErrorState, Spinner } from "../components/ui/States";
import { useActivity, useProjects } from "../hooks/queries";

export function ActivityPage() {
  const [params, setParams] = useSearchParams();
  const project = params.get("project") ?? undefined;
  const page = Number(params.get("page") ?? 1);
  const projects = useProjects();
  const { data, isPending, isError, error, refetch } = useActivity(project, page);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  function set(next: Record<string, string | undefined>) {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) (v ? p.set(k, v) : p.delete(k));
    setParams(p, { replace: true });
  }

  return (
    <>
      <PageHeader
        title="Activity"
        description="Who changed what, most recent first."
        actions={
          <select
            aria-label="Project"
            className="input h-9 w-52"
            value={project ?? ""}
            onChange={(e) => set({ project: e.target.value || undefined, page: undefined })}
          >
            <option value="">All projects</option>
            {(projects.data ?? []).map((p) => (
              <option key={p.key} value={p.key}>
                {p.name}
              </option>
            ))}
          </select>
        }
      />
      <div className="card">
        {isPending ? (
          <Spinner />
        ) : isError ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : data.items.length === 0 ? (
          <EmptyState icon={Activity} title="No activity yet" description="Changes to projects and tasks will appear here." />
        ) : (
          <>
            <ul className="divide-y divide-gray-100">
              {data.items.map((e) => (
                <ActivityItem key={e.id} event={e} />
              ))}
            </ul>
            {pages > 1 && (
              <div className="flex items-center justify-between border-t border-gray-100 px-4 py-2.5 text-sm text-gray-600">
                <span>
                  Page {page} of {pages}
                </span>
                <div className="flex gap-2">
                  <Button size="sm" disabled={page <= 1} onClick={() => set({ page: String(page - 1) })}>
                    Newer
                  </Button>
                  <Button size="sm" disabled={page >= pages} onClick={() => set({ page: String(page + 1) })}>
                    Older
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
