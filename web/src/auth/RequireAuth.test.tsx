import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import RequireAuth from "@/components/RequireAuth";
import { api } from "@/api/client";
import { AuthProvider } from "./AuthProvider";
import { useAuth } from "./useAuth";

function json(body: unknown, status: number) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function Where() {
  const l = useLocation();
  return <p data-testid="where">{l.pathname + l.search}</p>;
}

function setup(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Where />
        <Routes>
          <Route path="/login" element={<h1>Login</h1>} />
          <Route path="/register" element={<h1>Register</h1>} />
          <Route element={<RequireAuth />}>
            <Route path="/sets/:id" element={<h1>Secret</h1>} />
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => vi.unstubAllGlobals());

const unauth = {
  error: { code: "not_authenticated", message: "x", details: null },
};

describe("RequireAuth", () => {
  it("signed-out user at /sets/abc is redirected to /login?next=%2Fsets%2Fabc", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => Promise.resolve(json(unauth, 401))),
    );
    setup("/sets/abc");
    expect(
      await screen.findByRole("heading", { name: "Login" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent(
      "/login?next=%2Fsets%2Fabc",
    );
  });

  it("signed-in user sees the outlet and the nav", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() =>
        Promise.resolve(
          json(
            {
              csrf_token: "t",
              user: {
                id: "11111111-1111-1111-1111-111111111111",
                email: "a@b.co",
                created_at: "2026-01-01T00:00:00Z",
              },
            },
            200,
          ),
        ),
      ),
    );
    setup("/sets/abc");
    expect(
      await screen.findByRole("heading", { name: "Secret" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Study sets" })).toHaveAttribute(
      "href",
      "/sets",
    );
    expect(screen.getByRole("link", { name: "Account" })).toHaveAttribute(
      "href",
      "/account",
    );
  });

  it("on /register a 401 from /auth/session does not redirect", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => Promise.resolve(json(unauth, 401))),
    );
    setup("/register");
    expect(
      await screen.findByRole("heading", { name: "Register" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/register");
  });

  it("treats a 500 from /auth/session as signed out", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() =>
        Promise.resolve(
          json(
            {
              error: { code: "internal_error", message: "x", details: null },
            },
            500,
          ),
        ),
      ),
    );
    setup("/sets/abc");
    expect(
      await screen.findByRole("heading", { name: "Login" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent(
      "/login?next=%2Fsets%2Fabc",
    );
  });

  it("treats a network failure on /auth/session as signed out", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("down")));
    setup("/sets/abc");
    expect(
      await screen.findByRole("heading", { name: "Login" }),
    ).toBeInTheDocument();
  });

  it("signedOut() clears the CSRF token", async () => {
    const fetchMock = vi.fn().mockImplementation((req: Request) =>
      Promise.resolve(
        req.method === "GET"
          ? json(
              {
                csrf_token: "t",
                user: { id: "1", email: "a@b.co", created_at: "x" },
              },
              200,
            )
          : json({}, 200),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    function Out() {
      const { signedOut, status } = useAuth();
      return <button onClick={signedOut}>out-{status}</button>;
    }
    render(
      <MemoryRouter>
        <AuthProvider>
          <Out />
        </AuthProvider>
      </MemoryRouter>,
    );
    const btn = await screen.findByRole("button", { name: "out-signed_in" });
    btn.click();
    await screen.findByRole("button", { name: "out-signed_out" });
    await api.POST("/auth/logout");
    const last = fetchMock.mock.calls.at(-1)![0] as Request;
    expect(last.headers.has("X-CSRF-Token")).toBe(false);
  });
});

describe("useAuth", () => {
  it("throws outside the provider", () => {
    function Bad() {
      useAuth();
      return null;
    }
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Bad />)).toThrow(/AuthProvider/);
    spy.mockRestore();
  });
});

describe("unauthenticated handler on auth pages", () => {
  async function fire(path: string) {
    const fetchMock = vi
      .fn()
      .mockImplementation(() => Promise.resolve(json(unauth, 401)));
    vi.stubGlobal("fetch", fetchMock);
    setup(path);
    await screen.findByTestId("where");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1)); // session check
    await api.POST("/auth/logout"); // resolves after the handler has run
    expect(fetchMock).toHaveBeenCalledTimes(2);
  }

  it("a not_authenticated 401 while on /login does not add a next param", async () => {
    await fire("/login");
    await waitFor(() =>
      expect(screen.getByTestId("where")).toHaveTextContent(/^\/login$/),
    );
    expect(screen.getByRole("heading", { name: "Login" })).toBeInTheDocument();
  });

  it("a not_authenticated 401 while on /register goes to plain /login", async () => {
    await fire("/register");
    expect(
      await screen.findByRole("heading", { name: "Login" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent(/^\/login$/);
  });
});
