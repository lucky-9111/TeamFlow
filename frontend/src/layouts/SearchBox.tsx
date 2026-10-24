import { FolderKanban, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { TypeIcon } from "../components/tasks/TaskBits";
import { useSearch } from "../hooks/queries";

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

export function SearchBox() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const debounced = useDebounced(q, 250);
  const results = useSearch(debounced);
  const navigate = useNavigate();
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const shortcut = (e: KeyboardEvent) => {
      if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement).tagName)) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", shortcut);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", shortcut);
    };
  }, []);

  function go(path: string) {
    setOpen(false);
    setQ("");
    navigate(path);
  }

  const data = results.data;
  const hasResults = !!data && (data.projects.length > 0 || data.tasks.length > 0);

  return (
    <div className="relative w-full max-w-sm" ref={ref}>
      <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" aria-hidden />
      <input
        ref={inputRef}
        type="search"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false);
          if (e.key === "Enter" && q.trim()) go(`/tasks?q=${encodeURIComponent(q.trim())}`);
        }}
        placeholder="Search tasks and projects"
        aria-label="Search tasks and projects"
        className="h-9 w-full rounded-md border border-gray-200 bg-gray-50 pl-8 pr-8 text-sm placeholder:text-gray-400 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
      />
      <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded border border-gray-200 bg-white px-1.5 text-[10px] text-gray-400 sm:block">
        /
      </kbd>
      {open && debounced.trim().length >= 2 && (
        <div className="absolute left-0 right-0 mt-1 max-h-96 overflow-y-auto rounded-lg border border-gray-200 bg-white py-1 shadow-pop">
          {!hasResults ? (
            <p className="px-3 py-3 text-sm text-gray-500">{results.isFetching ? "Searching…" : "No matches."}</p>
          ) : (
            <>
              {data!.projects.map((p) => (
                <button
                  key={p.key}
                  onClick={() => go(`/projects/${p.key}`)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50"
                >
                  <FolderKanban className="h-4 w-4 text-gray-400" aria-hidden />
                  <span className="truncate">{p.name}</span>
                  <span className="ml-auto text-xs text-gray-400">{p.key}</span>
                </button>
              ))}
              {data!.tasks.map((t) => (
                <button
                  key={t.key}
                  onClick={() => go(`/tasks/${t.key}`)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50"
                >
                  <TypeIcon type={t.type} />
                  <span className="w-14 shrink-0 text-xs text-gray-500">{t.key}</span>
                  <span className="truncate">{t.title}</span>
                </button>
              ))}
              <button
                onClick={() => go(`/tasks?q=${encodeURIComponent(debounced.trim())}`)}
                className="w-full border-t border-gray-100 px-3 py-2 text-left text-xs font-medium text-brand-600 hover:bg-gray-50"
              >
                See all matching tasks
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
