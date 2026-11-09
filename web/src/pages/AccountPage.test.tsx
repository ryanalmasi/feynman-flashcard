import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import RequireAuth from "@/components/RequireAuth";
import AccountPage from "./AccountPage";
import { apiError, json, renderAt, session, stubFetch } from "@/test/pageUtils";

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", async (orig) => ({
  ...(await orig<typeof import("sonner")>()),
  toast,
}));

const routes = (
  <Routes>
    <Route path="/login" element={<h1>Login</h1>} />
    <Route path="/register" element={<h1>Register</h1>} />
    <Route element={<RequireAuth />}>
      <Route path="/account" element={<AccountPage />} />
    </Route>
  </Routes>
);

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

async function openDialog(user: ReturnType<typeof userEvent.setup>) {
  await user.click(
    await screen.findByRole("button", { name: "Delete account" }),
  );
  return screen.findByRole("alertdialog");
}

describe("AccountPage", () => {
  it("shows heading, email and the dialog copy", async () => {
    const user = userEvent.setup();
    stubFetch({ "GET /auth/session": () => json(session, 200) });
    renderAt("/account", routes);
    expect(
      await screen.findByRole("heading", { name: "Account" }),
    ).toBeInTheDocument();
    expect(screen.getByText("a@b.co")).toBeInTheDocument();
    const dlg = await openDialog(user);
    expect(dlg).toHaveTextContent("Delete your account?");
    expect(dlg).toHaveTextContent(
      "This permanently deletes your account, all your study sets, cards and uploaded PDFs. This can't be undone.",
    );
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Delete my account" }),
    ).toBeInTheDocument();
  });

  it("wrong password shows an error and keeps the user signed in", async () => {
    const user = userEvent.setup();
    stubFetch({
      "GET /auth/session": () => json(session, 200),
      "DELETE /auth/account": () =>
        json(apiError("invalid_credentials", "Incorrect password."), 401),
    });
    renderAt("/account", routes);
    await openDialog(user);
    await user.type(screen.getByLabelText("Password"), "wrong-password-123");
    await user.click(screen.getByRole("button", { name: "Delete my account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Incorrect password.",
    );
    expect(
      screen.getByRole("link", { name: "Study sets", hidden: true }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/account");
  });

  it("429 shows the rate-limit message and keeps the user signed in", async () => {
    const user = userEvent.setup();
    stubFetch({
      "GET /auth/session": () => json(session, 200),
      "DELETE /auth/account": () =>
        json(
          apiError("rate_limited", "Too many attempts. Try again later."),
          429,
        ),
    });
    renderAt("/account", routes);
    await openDialog(user);
    await user.type(screen.getByLabelText("Password"), "wrong-password-123");
    await user.click(screen.getByRole("button", { name: "Delete my account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Too many attempts. Try again later.",
    );
    expect(
      screen.getByRole("link", { name: "Study sets", hidden: true }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/account");
  });

  it("successful delete signs out and goes to /register", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch({
      "GET /auth/session": () => json(session, 200),
      "DELETE /auth/account": () => new Response(null, { status: 204 }),
    });
    renderAt("/account", routes);
    await openDialog(user);
    await user.type(screen.getByLabelText("Password"), "right-password-123");
    await user.click(screen.getByRole("button", { name: "Delete my account" }));
    expect(
      await screen.findByRole("heading", { name: "Register" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent(/^\/register$/);
    expect(toast.success).toHaveBeenCalledWith(
      "Your account has been deleted.",
    );
    const req = fetchMock.mock.calls
      .map((c) => c[0] as Request)
      .find((r) => r.method === "DELETE")!;
    expect(await req.clone().json()).toEqual({
      password: "right-password-123",
    });
  });

  it("log out calls /auth/logout then shows the login page", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch({
      "GET /auth/session": () => json(session, 200),
      "POST /auth/logout": () => new Response(null, { status: 204 }),
    });
    renderAt("/account", routes);
    await user.click(await screen.findByRole("button", { name: "Log out" }));
    expect(
      await screen.findByRole("heading", { name: "Login" }),
    ).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(
        (c) => new URL((c[0] as Request).url).pathname === "/auth/logout",
      ),
    ).toBe(true);
    expect(screen.getByTestId("where")).toHaveTextContent(/^\/login$/);
  });

  it("a network failure shows a generic error and re-enables the button", async () => {
    const user = userEvent.setup();
    stubFetch({
      "GET /auth/session": () => json(session, 200),
      "DELETE /auth/account": () => {
        throw new TypeError("down");
      },
    });
    renderAt("/account", routes);
    await openDialog(user);
    await user.type(screen.getByLabelText("Password"), "right-password-123");
    await user.click(screen.getByRole("button", { name: "Delete my account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong. Try again.",
    );
    expect(
      screen.getByRole("button", { name: "Delete my account" }),
    ).toBeEnabled();
  });

  it("a not_authenticated 401 mid-delete signs out and lands on /login?next=%2Faccount", async () => {
    const user = userEvent.setup();
    stubFetch({
      "GET /auth/session": () => json(session, 200),
      "DELETE /auth/account": () =>
        json(apiError("not_authenticated", "Not authenticated."), 401),
    });
    renderAt("/account", routes);
    await openDialog(user);
    await user.type(screen.getByLabelText("Password"), "right-password-123");
    await user.click(screen.getByRole("button", { name: "Delete my account" }));
    expect(
      await screen.findByRole("heading", { name: "Login" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent(
      "/login?next=%2Faccount",
    );
  });
});
