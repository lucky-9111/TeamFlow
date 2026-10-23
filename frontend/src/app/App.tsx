import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ConfirmProvider } from "../components/ui/Confirm";
import { ToastProvider } from "../components/ui/Toast";
import { AuthProvider, RequireAuth } from "../features/auth/AuthContext";
import { AppShell } from "../layouts/AppShell";
import { ApiError } from "../services/api";
import { ActivityPage } from "../pages/ActivityPage";
import { BoardIndexPage, BoardPage } from "../pages/BoardPage";
import { ChangePasswordPage } from "../pages/ChangePasswordPage";
import { LoginPage } from "../pages/LoginPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { OverviewPage } from "../pages/OverviewPage";
import { ProjectDetailPage } from "../pages/ProjectDetailPage";
import { ProjectsPage } from "../pages/ProjectsPage";
import { SettingsPage } from "../pages/SettingsPage";
import { TaskDetailPage } from "../pages/TaskDetailPage";
import { TasksPage } from "../pages/TasksPage";
import { TeamPage } from "../pages/TeamPage";

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        refetchOnWindowFocus: true,
        // Client errors (403/404/422) won't fix themselves; only retry network and server errors.
        retry: (count, error) => count < 2 && !(error instanceof ApiError && error.status >= 400 && error.status < 500),
      },
    },
  });
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/change-password"
        element={
          <RequireAuth>
            <ChangePasswordPage />
          </RequireAuth>
        }
      />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route index element={<OverviewPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="tasks/:key" element={<TaskDetailPage />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="projects/:key" element={<ProjectDetailPage />} />
        <Route path="board" element={<BoardIndexPage />} />
        <Route path="board/:key" element={<BoardPage />} />
        <Route path="team" element={<TeamPage />} />
        <Route path="activity" element={<ActivityPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

const queryClient = createQueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ToastProvider>
          <ConfirmProvider>
            <AuthProvider>
              <AppRoutes />
            </AuthProvider>
          </ConfirmProvider>
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
