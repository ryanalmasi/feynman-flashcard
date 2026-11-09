import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import RequireAuth from "@/components/RequireAuth";
import { AuthProvider } from "./AuthProvider";

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
});
