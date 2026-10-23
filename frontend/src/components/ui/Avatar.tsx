import { UserRound } from "lucide-react";
import type { UserBrief } from "../../types/api";
import { initials } from "../../utils/format";

// Muted, readable backgrounds; picked deterministically so a person keeps their colour.
const palette = [
  "bg-sky-100 text-sky-800",
  "bg-amber-100 text-amber-800",
  "bg-emerald-100 text-emerald-800",
  "bg-rose-100 text-rose-800",
  "bg-violet-100 text-violet-800",
  "bg-teal-100 text-teal-800",
  "bg-orange-100 text-orange-800",
];

const sizes = { xs: "h-5 w-5 text-[9px]", sm: "h-6 w-6 text-[10px]", md: "h-8 w-8 text-xs" };

export function Avatar({ user, size = "sm" }: { user: UserBrief | null | undefined; size?: keyof typeof sizes }) {
  if (!user) {
    return (
      <span
        className={`inline-flex shrink-0 items-center justify-center rounded-full border border-dashed border-gray-300 text-gray-400 ${sizes[size]}`}
        title="Unassigned"
      >
        <UserRound className="h-3/5 w-3/5" aria-hidden />
      </span>
    );
  }
  return (
    <span
      className={`inline-flex shrink-0 select-none items-center justify-center rounded-full font-semibold ${palette[user.id % palette.length]} ${sizes[size]}`}
      title={user.full_name}
    >
      {initials(user.full_name)}
    </span>
  );
}
