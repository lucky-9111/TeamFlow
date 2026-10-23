import { CalendarClock, CheckCircle2, FolderKanban, Inbox } from "lucide-react";
import { Link } from "react-router-dom";
import { ActivityItem } from "../components/ActivityItem";
import { TaskRow } from "../components/tasks/TaskRow";
import { PageHeader, Section } from "../components/ui/PageHeader";
import { EmptyState, ErrorState, Skeleton } from "../components/ui/States";
import { useAuth } from "../features/auth/AuthContext";
import { useDashboard } from "../hooks/queries";

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

function Stat({ label, value, to, tone }: { label: string; value: number; to: string; tone?: "danger" }) {
  return (
    <Link to={to} className="card block px-4 py-3 transition-colors hover:border-gray-300">
      <p className="text-xs font-medium text-gray-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${tone === "danger" && value > 0 ? "text-red-600" : "text-gray-900"}`}>
        {value}
      </p>
    </Link>
  );
}

export function OverviewPage() {
  const { user } = useAuth();
  const { data, isPending, isError, error, refetch } = useDashboard();
  const firstName = user!.full_name.split(" ")[0];

  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />;

  return (
    <>
      <PageHeader title={`${greeting()}, ${firstName}`} description="Here's what's happening across your projects." />

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-5">
        {isPending ? (
          Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-[74px]" />)
        ) : (
          <>
            <Stat label="My open tasks" value={data.stats.my_open_tasks} to="/tasks?assignee=me" />
            <Stat label="Overdue" value={data.stats.overdue_tasks} to="/tasks?overdue=true" tone="danger" />
            <Stat label="Open tasks" value={data.stats.open_tasks} to="/tasks?status=todo&status=in_progress&status=in_review" />
            <Stat label="Done this week" value={data.stats.completed_last_7_days} to="/tasks?status=done&sort=updated" />
            <Stat label="Active projects" value={data.stats.active_projects} to="/projects" />
          </>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Section
            title="Assigned to me"
            action={
              <Link to="/tasks?assignee=me" className="text-xs font-medium text-brand-600 hover:underline">
                View all
              </Link>
            }
          >
            {isPending ? (
              <div className="space-y-2 p-4">
                <Skeleton className="h-5" />
                <Skeleton className="h-5" />
                <Skeleton className="h-5" />
              </div>
            ) : data.my_tasks.length === 0 ? (
              <EmptyState icon={Inbox} title="Nothing assigned to you" description="Tasks assigned to you will show up here." />
            ) : (
              <div className="divide-y divide-gray-100">
                {data.my_tasks.map((t) => (
                  <TaskRow key={t.id} task={t} />
                ))}
              </div>
            )}
          </Section>

          <Section title="Upcoming deadlines">
            {isPending ? (
              <div className="p-4">
                <Skeleton className="h-5" />
              </div>
            ) : data.upcoming.length === 0 ? (
              <EmptyState icon={CalendarClock} title="No deadlines in the next two weeks" />
            ) : (
              <div className="divide-y divide-gray-100">
                {data.upcoming.map((t) => (
                  <TaskRow key={t.id} task={t} />
                ))}
              </div>
            )}
          </Section>

          {!isPending && data.recently_completed.length > 0 && (
            <Section title="Recently completed">
              <div className="divide-y divide-gray-100">
                {data.recently_completed.map((t) => (
                  <TaskRow key={t.id} task={t} />
                ))}
              </div>
            </Section>
          )}
        </div>

        <div className="space-y-6">
          <Section title="Projects">
            {isPending ? (
              <div className="p-4">
                <Skeleton className="h-10" />
              </div>
            ) : data.projects.length === 0 ? (
              <EmptyState icon={FolderKanban} title="No projects yet" />
            ) : (
              <ul className="divide-y divide-gray-100">
                {data.projects.map((p) => {
                  const pct = p.total ? Math.round((p.done / p.total) * 100) : 0;
                  return (
                    <li key={p.key}>
                      <Link to={`/projects/${p.key}`} className="block px-4 py-3 hover:bg-gray-50">
                        <div className="flex items-center justify-between text-sm">
                          <span className="truncate font-medium text-gray-900">{p.name}</span>
                          <span className="text-xs text-gray-500">
                            {p.done}/{p.total} done
                          </span>
                        </div>
                        <div
                          className="mt-2 h-1.5 overflow-hidden rounded-full bg-gray-100"
                          role="progressbar"
                          aria-valuenow={pct}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label={`${p.name} progress`}
                        >
                          <div className="h-full rounded-full bg-brand-600" style={{ width: `${pct}%` }} />
                        </div>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </Section>

          <Section
            title="Recent activity"
            action={
              <Link to="/activity" className="text-xs font-medium text-brand-600 hover:underline">
                View all
              </Link>
            }
          >
            {isPending ? (
              <div className="p-4">
                <Skeleton className="h-10" />
              </div>
            ) : data.recent_activity.length === 0 ? (
              <EmptyState icon={CheckCircle2} title="No activity yet" />
            ) : (
              <ul className="divide-y divide-gray-100">
                {data.recent_activity.map((e) => (
                  <ActivityItem key={e.id} event={e} />
                ))}
              </ul>
            )}
          </Section>
        </div>
      </div>
    </>
  );
}
