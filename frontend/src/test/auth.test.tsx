import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes, createQueryClient } from "../app/App";
import { ConfirmProvider } from "../components/ui/Confirm";
import { ToastProvider } from "../components/ui/Toast";
import { AuthProvider } from "../features/auth/AuthContext";

const user = {
  id: 1,
  email: "priya@example.com",
  username: "priya",
  full_name: "Priya Verma",
  workspace_role: "member",
  must_change_password: false,
  timezone: "UTC",
  due_reminders: true,
  last_login_at: null,
};

const json = (status: number, body: unknown) =>
  Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));

/** Routes fetch calls by path; anything unexpected fails the test loudly. */
function mockBackend(routes: Record<string, () => Promise<Response>>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const path = String(input).replace(/^\/api\/v1/, "").split("?")[0];
    const handler = routes[path];
    if (!handler) throw new Error(`Unexpected request: ${path}`);
    return handler();
  });
}

function renderApp(path: string) {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ToastProvider>
          <ConfirmProvider>
            <AuthProvider>
              <AppRoutes />
            </AuthProvider>
          </ConfirmProvider>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const dashboard = {
  stats: { active_projects: 1, open_tasks: 4, my_open_tasks: 2, overdue_tasks: 1, completed_last_7_days: 3 },
  my_tasks: [],
  upcoming: [],
  recently_completed: [],
  recent_activity: [],
  projects: [{ key: "TF", name: "TeamFlow Web", done: 3, total: 7 }],
};

afterEach(() => vi.restoreAllMocks());

describe("authentication flow", () => {
  it("sends signed-out visitors to the login page", async () => {
    mockBackend({ "/auth/me": () => json(401, { error: { code: "not_authenticated", message: "Authentication required" } }) });
    renderApp("/projects");
    expect(await screen.findByRole("heading", { name: "Sign in to TeamFlow" })).toBeInTheDocument();
  });

  it("shows the server's message when login fails", async () => {
    mockBackend({
      "/auth/me": () => json(401, { error: { code: "not_authenticated", message: "Authentication required" } }),
      "/auth/login": () => json(401, { error: { code: "invalid_credentials", message: "Invalid email or password" } }),
    });
    renderApp("/login");
    await userEvent.type(await screen.findByLabelText("Email"), "priya@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
  });

  it("validates the form before calling the server", async () => {
    const fetchMock = mockBackend({
      "/auth/me": () => json(401, { error: { code: "not_authenticated", message: "Authentication required" } }),
    });
    renderApp("/login");
    await userEvent.click(await screen.findByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter your email and password.");
    expect(fetchMock).toHaveBeenCalledTimes(1); // only the initial /auth/me
  });

  it("logs in and lands on the overview with real dashboard numbers", async () => {
    mockBackend({
      "/auth/me": () => json(401, { error: { code: "not_authenticated", message: "Authentication required" } }),
      "/auth/login": () => json(200, { user, csrf_token: "t" }),
      "/dashboard": () => json(200, dashboard),
      "/workspace": () => json(200, { name: "Acme" }),
      "/notifications/unread-count": () => json(200, { count: 2 }),
      "/projects": () => json(200, []),
    });
    renderApp("/login");
    await userEvent.type(await screen.findByLabelText("Email"), "priya@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "correct-horse-battery");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: /Priya$/ })).toBeInTheDocument();
    expect(await screen.findByText("TeamFlow Web")).toBeInTheDocument();
    expect(screen.getByText("3/7 done")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Notifications, 2 unread" })).toBeInTheDocument();
  });

  it("forces a password change for temporary passwords", async () => {
    mockBackend({ "/auth/me": () => json(200, { ...user, must_change_password: true }) });
    renderApp("/");
    expect(await screen.findByRole("heading", { name: "Choose a new password" })).toBeInTheDocument();
  });
});
