import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, UNAUTHORIZED_EVENT, api, toQuery } from "../services/api";
import { dueLabel, initials } from "../utils/format";

function respond(status: number, body?: unknown) {
  return Promise.resolve(
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  document.cookie = "teamflow_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
});

describe("api client", () => {
  it("builds query strings, repeating list values and skipping empty ones", () => {
    expect(toQuery({ status: ["todo", "done"], q: "", page: 2, project: undefined })).toBe("?status=todo&status=done&page=2");
    expect(toQuery({})).toBe("");
  });

  it("sends the CSRF cookie as a header on writes only", async () => {
    document.cookie = "teamflow_csrf=abc123";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() => respond(200, { ok: true }));
    await api.get("/tasks");
    await api.post("/tasks/TF-1/comments", { body: "hi" });
    const getHeaders = fetchMock.mock.calls[0][1]!.headers as Record<string, string>;
    const postHeaders = fetchMock.mock.calls[1][1]!.headers as Record<string, string>;
    expect(getHeaders["X-CSRF-Token"]).toBeUndefined();
    expect(postHeaders["X-CSRF-Token"]).toBe("abc123");
  });

  it("turns the backend error format into an ApiError with field messages", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      respond(422, {
        error: {
          code: "validation_error",
          message: "Invalid request",
          details: [{ loc: ["body", "title"], msg: "String should have at least 1 character" }],
        },
      }),
    );
    const err = (await api.post("/projects/TF/tasks", { title: "" }).catch((e) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.fieldErrors()).toEqual({ title: "String should have at least 1 character" });
  });

  it("broadcasts unauthorized on 401 so the app can return to login", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      respond(401, { error: { code: "session_expired", message: "Your session has expired." } }),
    );
    const listener = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, listener);
    await expect(api.get("/dashboard")).rejects.toMatchObject({ code: "session_expired" });
    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener(UNAUTHORIZED_EVENT, listener);
  });

  it("refreshes a missing CSRF token once and retries", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementationOnce(() => respond(403, { error: { code: "csrf_failed", message: "Missing CSRF" } }))
      .mockImplementationOnce(() => respond(200, { csrf_token: "new" }))
      .mockImplementationOnce(() => respond(200, { id: 1 }));
    await expect(api.post("/tasks/TF-1/comments", { body: "x" })).resolves.toEqual({ id: 1 });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("reports an unreachable server clearly", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => Promise.reject(new TypeError("Failed to fetch")));
    await expect(api.get("/dashboard")).rejects.toMatchObject({ code: "network_error" });
  });
});

describe("formatting", () => {
  const iso = (offsetDays: number) => {
    const d = new Date();
    d.setDate(d.getDate() + offsetDays);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  };

  it("describes due dates relative to today", () => {
    expect(dueLabel(iso(0))).toBe("Due today");
    expect(dueLabel(iso(1))).toBe("Due tomorrow");
    expect(dueLabel(iso(3))).toBe("Due in 3 days");
    expect(dueLabel(iso(-1))).toBe("1 day overdue");
    expect(dueLabel(iso(-4))).toBe("4 days overdue");
    expect(dueLabel(null)).toBeNull();
  });

  it("makes initials from names", () => {
    expect(initials("Priya Verma")).toBe("PV");
    expect(initials("Rahul")).toBe("R");
    expect(initials("Sneha K Iyer")).toBe("SI");
  });
});
