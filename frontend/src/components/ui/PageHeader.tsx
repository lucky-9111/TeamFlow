import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export function PageHeader({
  title,
  description,
  actions,
  breadcrumb,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  breadcrumb?: { label: string; to: string }[];
}) {
  return (
    <div className="mb-6">
      {breadcrumb && (
        <nav className="mb-1 flex items-center gap-1.5 text-xs text-gray-500" aria-label="Breadcrumb">
          {breadcrumb.map((b, i) => (
            <span key={b.to} className="flex items-center gap-1.5">
              {i > 0 && <span aria-hidden>/</span>}
              <Link to={b.to} className="hover:text-gray-800 hover:underline">
                {b.label}
              </Link>
            </span>
          ))}
        </nav>
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold text-gray-900">{title}</h1>
          {description && <p className="mt-1 text-sm text-gray-500">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}

export function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
        <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}
