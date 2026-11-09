import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";
import { Where } from "@/test/Where";
import { AuthProvider } from "@/auth/AuthProvider";

export function json(body: unknown, status: number) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export const session = {
  csrf_token: "t",
  user: {
    id: "11111111-1111-1111-1111-111111111111",
    email: "a@b.co",
    created_at: "2026-01-01T00:00:00Z",
  },
};

export const apiError = (code: string, message: string) => ({
  error: { code, message, details: null },
});

type Handler = (req: Request) => Response | Promise<Response>;

/** Stubs fetch per "METHOD /path". Unmatched requests fail the test loudly. */
export function stubFetch(routes: Record<string, Handler>) {
  const mock = vi.fn().mockImplementation(async (req: Request) => {
    const key = `${req.method} ${new URL(req.url).pathname}`;
    const h = routes[key];
    if (!h) throw new Error(`unstubbed request: ${key}`);
    return h(req);
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

export function renderAt(path: string, routes: ReactNode) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Where />
        {routes}
      </AuthProvider>
    </MemoryRouter>,
  );
}
