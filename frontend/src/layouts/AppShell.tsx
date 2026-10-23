import {
  Activity,
  FolderKanban,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  Plus,
  Settings,
  SquareKanban,
  Users,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { CreateTaskDialog } from "../components/tasks/TaskForm";
import { Avatar } from "../components/ui/Avatar";
import { Button } from "../components/ui/Button";
import { useAuth } from "../features/auth/AuthContext";
import { useWorkspace } from "../hooks/queries";
import { NotificationBell } from "./NotificationBell";
import { SearchBox } from "./SearchBox";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/tasks?assignee=me", match: "/tasks", label: "My Tasks", icon: ListChecks },
  { to: "/projects", label: "Projects", icon: FolderKanban },
  { to: "/board", label: "Board", icon: SquareKanban },
  { to: "/team", label: "Team", icon: Users },
  { to: "/activity", label: "Activity", icon: Activity },
  { to: "/settings", label: "Settings", icon: Settings },
];

/** The project currently in view, so "Create" can preselect it. */
function useCurrentProjectKey(): string | undefined {
  const { pathname } = useLocation();
  const m = pathname.match(/^\/(?:projects|board)\/([A-Za-z0-9]+)/) ?? pathname.match(/^\/tasks\/([A-Za-z0-9]+)-\d+/);
  return m?.[1]?.toUpperCase();
}

export function AppShell() {
  const { user, logout } = useAuth();
  const workspace = useWorkspace();
  const [createOpen, setCreateOpen] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const location = useLocation();
  const currentProject = useCurrentProjectKey();

  useEffect(() => setMobileNav(false), [location.pathname, location.search]);

  const sidebar = (
    <nav className="flex h-full flex-col" aria-label="Main">
      <div className="flex h-14 items-center gap-2 px-4">
        <img src="/favicon.svg" alt="" className="h-7 w-7" />
        <span className="truncate font-semibold text-gray-900">{workspace.data?.name ?? "TeamFlow"}</span>
      </div>
      <ul className="flex-1 space-y-0.5 px-2 py-2">
        {NAV.map(({ to, label, icon: Icon, end, match }) => (
          <li key={label}>
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) => {
                const active = match ? location.pathname === match && location.search.includes("assignee=me") : isActive;
                return `flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors ${
                  active ? "bg-brand-50 text-brand-700" : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                }`;
              }}
            >
              <Icon className="h-4 w-4" aria-hidden />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-56 shrink-0 border-r border-gray-200 bg-white lg:block">
        {sidebar}
      </aside>

      {mobileNav && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-gray-900/30" onClick={() => setMobileNav(false)} aria-hidden />
          <aside className="relative h-full w-64 bg-white shadow-pop">
            <button
              className="absolute right-2 top-3 rounded p-1.5 text-gray-500 hover:bg-gray-100"
              onClick={() => setMobileNav(false)}
              aria-label="Close menu"
            >
              <X className="h-4 w-4" />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-gray-200 bg-white/95 px-4 backdrop-blur sm:px-6">
          <button
            className="-ml-1 rounded p-1.5 text-gray-600 hover:bg-gray-100 lg:hidden"
            onClick={() => setMobileNav(true)}
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <SearchBox />
          <div className="ml-auto flex items-center gap-2">
            <Button variant="primary" size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" aria-hidden />
              <span className="hidden sm:inline">Create</span>
            </Button>
            <NotificationBell />
            <UserMenu name={user!.full_name} id={user!.id} username={user!.username} onLogout={logout} />
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">
          <Outlet />
        </main>
      </div>

      <CreateTaskDialog open={createOpen} onClose={() => setCreateOpen(false)} defaultProject={currentProject} />
    </div>
  );
}

function UserMenu({ name, id, username, onLogout }: { name: string; id: number; username: string; onLogout: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

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

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center rounded-full p-0.5 hover:ring-2 hover:ring-gray-200"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
      >
        <Avatar user={{ id, full_name: name, username }} size="md" />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 mt-2 w-56 rounded-lg border border-gray-200 bg-white py-1 shadow-pop">
          <div className="border-b border-gray-100 px-3 py-2">
            <p className="truncate text-sm font-medium text-gray-900">{name}</p>
            <p className="truncate text-xs text-gray-500">@{username}</p>
          </div>
          <button
            role="menuitem"
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
            onClick={() => {
              setOpen(false);
              navigate("/settings");
            }}
          >
            <Settings className="h-4 w-4" aria-hidden /> Settings
          </button>
          <button
            role="menuitem"
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
            onClick={async () => {
              await onLogout();
              navigate("/login");
            }}
          >
            <LogOut className="h-4 w-4" aria-hidden /> Log out
          </button>
        </div>
      )}
    </div>
  );
}
