import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Spinner } from "../../components/ui/States";
import { ApiError, UNAUTHORIZED_EVENT, api } from "../../services/api";
import type { CurrentUser } from "../../types/api";

interface AuthApi {
  user: CurrentUser | null;
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<CurrentUser>;
  logout: () => Promise<void>;
  setUser: (user: CurrentUser) => void;
}

const AuthContext = createContext<AuthApi | null>(null);
const ME = ["me"];

/** Drop everything cached for the previous user, but keep the "me" query mounted. */
function resetCache(qc: QueryClient, user: CurrentUser | null) {
  qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
  qc.setQueryData(ME, user);
}

async function fetchMe(): Promise<CurrentUser | null> {
  try {
    return await api.get<CurrentUser>("/auth/me");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const me = useQuery({ queryKey: ME, queryFn: fetchMe, staleTime: Infinity, retry: 1 });

  // Any 401 (expired or revoked session) signs the user out locally.
  useEffect(() => {
    const onUnauthorized = () => {
      if (qc.getQueryData(ME)) resetCache(qc, null);
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, [qc]);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await api.post<{ user: CurrentUser }>("/auth/login", { email, password });
      resetCache(qc, res.user);
      return res.user;
    },
    [qc],
  );

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      resetCache(qc, null);
    }
  }, [qc]);

  const setUser = useCallback((user: CurrentUser) => qc.setQueryData(ME, user), [qc]);

  const value = useMemo<AuthApi>(
    () => ({
      user: me.data ?? null,
      isAdmin: me.data?.workspace_role === "admin",
      login,
      logout,
      setUser,
    }),
    [me.data, login, logout, setUser],
  );

  if (me.isPending) return <Spinner label="Loading TeamFlow…" />;
  if (me.isError) {
    return (
      <div className="p-8 text-center text-sm text-gray-600">
        Cannot reach the TeamFlow server. Check that the backend is running, then reload the page.
      </div>
    );
  }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthApi {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

/** Signed-in users only; users with a temporary password are sent to change it first. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (user.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }
  return <>{children}</>;
}
