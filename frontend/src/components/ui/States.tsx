import { AlertTriangle, Loader2, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { errorMessage } from "../../services/api";
import { Button } from "./Button";

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-gray-500" role="status">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {label}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-gray-200/70 ${className}`} aria-hidden />;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-3 rounded-full bg-gray-100 p-3">
        <Icon className="h-5 w-5 text-gray-500" aria-hidden />
      </div>
      <p className="font-medium text-gray-900">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-gray-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center" role="alert">
      <div className="mb-3 rounded-full bg-red-50 p-3">
        <AlertTriangle className="h-5 w-5 text-red-600" aria-hidden />
      </div>
      <p className="font-medium text-gray-900">Couldn't load this</p>
      <p className="mt-1 max-w-sm text-sm text-gray-500">{errorMessage(error)}</p>
      {onRetry && (
        <Button className="mt-4" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
