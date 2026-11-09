import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import LoginPage from "./LoginPage";
import { apiError, json, renderAt, session, stubFetch } from "@/test/pageUtils";

const routes = (
  <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/register" element={<h1>Register</h1>} />
    <Route path="/sets" element={<h1>Sets</h1>} />
    <Route path="/sets/:id" element={<h1>Set detail</h1>} />
    <Route path="//evil.com" element={<h1>Evil</h1>} />
  </Routes>
);

const notAuth = () => json(apiError("not_authenticated", "x"), 401);

async function fill(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText("Email"), "a@b.co");
  await user.type(screen.getByLabelText("Password"), "hunter2hunter2");
}

afterEach(() => vi.unstubAllGlobals());

describe("LoginPage", () => {
  it("submits email and password and navigates to next", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch({
      "GET /auth/session": notAuth,
      "POST /auth/login": () => json(session, 200),
    });
    renderAt("/login?next=%2Fsets%2F42", routes);
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(
      await screen.findByRole("heading", { name: "Set detail" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/sets/42");
    const req = fetchMock.mock.calls
      .map((c) => c[0] as Request)
      .find((r) => r.method === "POST")!;
    expect(await req.clone().json()).toEqual({
      email: "a@b.co",
      password: "hunter2hunter2",
    });
  });

  it("ignores an unsafe next", async () => {
    const user = userEvent.setup();
    stubFetch({
      "GET /auth/session": notAuth,
      "POST /auth/login": () => json(session, 200),
    });
    renderAt("/login?next=%2F%2Fevil.com", routes);
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(
      await screen.findByRole("heading", { name: "Sets" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/sets");
  });

  it("shows Invalid email or password. on 401 and stays on /login", async () => {
    const user = userEvent.setup();
    stubFetch({
      "GET /auth/session": notAuth,
      "POST /auth/login": () =>
        json(
          apiError("invalid_credentials", "Invalid email or password."),
          401,
        ),
    });
    renderAt("/login", routes);
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid email or password.",
    );
    expect(screen.getByTestId("where")).toHaveTextContent(/^\/login$/);
    expect(screen.getByRole("button", { name: "Log in" })).toBeEnabled();
  });

  it("shows the rate-limit message on 429", async () => {
    const user = userEvent.setup();
    stubFetch({
      "GET /auth/session": notAuth,
      "POST /auth/login": () =>
        json(
          apiError("rate_limited", "Too many attempts. Try again later."),
          429,
        ),
    });
    renderAt("/login", routes);
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Too many attempts. Try again later.",
    );
  });

  it("a network failure shows a generic error and re-enables the button", async () => {
    const user = userEvent.setup();
    stubFetch({
      "GET /auth/session": notAuth,
      "POST /auth/login": () => {
        throw new TypeError("down");
      },
    });
    renderAt("/login", routes);
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong. Try again.",
    );
    expect(screen.getByRole("button", { name: "Log in" })).toBeEnabled();
  });

  it("disables the button while submitting", async () => {
    const user = userEvent.setup();
    let release!: () => void;
    stubFetch({
      "GET /auth/session": notAuth,
      "POST /auth/login": () =>
        new Promise<Response>((res) => {
          release = () => res(json(session, 200));
        }),
    });
    renderAt("/login", routes);
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Log in" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Log in" })).toBeDisabled(),
    );
    release();
    await screen.findByRole("heading", { name: "Sets" });
  });

  it("redirects a signed-in user to /sets", async () => {
    stubFetch({ "GET /auth/session": () => json(session, 200) });
    renderAt("/login", routes);
    expect(
      await screen.findByRole("heading", { name: "Sets" }),
    ).toBeInTheDocument();
  });

  it("links to register", async () => {
    stubFetch({ "GET /auth/session": notAuth });
    renderAt("/login", routes);
    expect(
      await screen.findByRole("link", { name: "Create an account" }),
    ).toHaveAttribute("href", "/register");
  });
});
