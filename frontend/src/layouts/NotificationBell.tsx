import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Spinner } from "../components/ui/States";
import { useNotifications, useUnreadCount } from "../hooks/queries";
import { api } from "../services/api";
import type { Notification } from "../types/api";
import { timeAgo } from "../utils/format";

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const unread = useUnreadCount();
  const list = useNotifications(open);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const count = unread.data?.count ?? 0;

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const refresh = () => qc.invalidateQueries({ queryKey: ["notifications"] });
  const readAll = useMutation({ mutationFn: () => api.post("/notifications/read-all"), onSuccess: refresh });
  const readOne = useMutation({
    mutationFn: (id: number) => api.post(`/notifications/${id}/read`),
    onSuccess: refresh,
  });

  function openNotification(n: Notification) {
    if (!n.read) readOne.mutate(n.id);
    setOpen(false);
    if (n.task_key) navigate(`/tasks/${n.task_key}`);
    else if (n.project_key) navigate(`/projects/${n.project_key}`);
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative rounded-md p-2 text-gray-600 hover:bg-gray-100 hover:text-gray-900"
        aria-label={count ? `Notifications, ${count} unread` : "Notifications"}
        aria-expanded={open}
      >
        <Bell className="h-[18px] w-[18px]" />
        {count > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold text-white">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-lg border border-gray-200 bg-white shadow-pop">
          <div className="flex items-center justify-between border-b border-gray-100 px-4 py-2.5">
            <p className="text-sm font-semibold text-gray-900">Notifications</p>
            {count > 0 && (
              <button className="text-xs font-medium text-brand-600 hover:underline" onClick={() => readAll.mutate()}>
                Mark all as read
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {list.isPending ? (
              <Spinner />
            ) : !list.data?.length ? (
              <p className="px-4 py-8 text-center text-sm text-gray-500">You're all caught up.</p>
            ) : (
              <ul>
                {list.data.map((n) => (
                  <li key={n.id}>
                    <button
                      onClick={() => openNotification(n)}
                      className="flex w-full gap-2.5 px-4 py-2.5 text-left hover:bg-gray-50"
                    >
                      <span
                        className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.read ? "bg-transparent" : "bg-brand-600"}`}
                        aria-hidden
                      />
                      <span className="min-w-0">
                        <span className={`block text-sm ${n.read ? "text-gray-600" : "text-gray-900"}`}>{n.message}</span>
                        <span className="text-xs text-gray-400">{timeAgo(n.created_at)}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
