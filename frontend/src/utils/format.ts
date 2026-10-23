const dateFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" });
const dateYearFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" });
const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
});

/** Parses a backend date ("2026-10-22") as a local calendar date, not UTC midnight. */
export function parseDate(value: string): Date {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = value.length === 10 ? parseDate(value) : new Date(value);
  return date.getFullYear() === new Date().getFullYear() ? dateFormat.format(date) : dateYearFormat.format(date);
}

export function formatDateTime(value: string): string {
  return dateTimeFormat.format(new Date(value));
}

export function timeAgo(value: string): string {
  const seconds = Math.round((Date.now() - new Date(value).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  return formatDate(value);
}

/** "Due in 3 days", "Due today", "2 days overdue". */
export function dueLabel(due: string | null, done = false): string | null {
  if (!due) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((parseDate(due).getTime() - today.getTime()) / 86_400_000);
  if (done) return formatDate(due);
  if (days === 0) return "Due today";
  if (days === 1) return "Due tomorrow";
  if (days > 1) return days <= 7 ? `Due in ${days} days` : formatDate(due);
  return days === -1 ? "1 day overdue" : `${-days} days overdue`;
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}
