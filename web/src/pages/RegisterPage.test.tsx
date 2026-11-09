import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import RegisterPage from "./RegisterPage";
import { apiError, json, renderAt, session, stubFetch } from "./testUtils";

const routes = (
  <Routes>
    <Route path="/register" element={<RegisterPage />} />
    <Route path="/login" element={<h1>Login</h1>} />
    <Route path="/sets" element={<h1>Sets</h1>} />
  </Routes>
);
const notAuth = () => json(apiError("not_authenticated", "x"), 401);

afterEach(() => vi.unstubAllGlobals());

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText("Email"), "a@b.co");
  await user.type(screen.getByLabelText("Password"), "correct-horse-battery");
  await user.selectOptions(screen.getByLabelText("Birth month"), "3");
  await user.selectOptions(screen.getByLabelText("Birth year"), "1999");
  await user.click(screen.getByRole("button", { name: "Create account" }));
}

describe("RegisterPage", () => {
  it("shows the password hint 'At least 12 characters'", async () => {
    stubFetch({ "GET /auth/session": notAuth });
    renderAt("/register", routes);
    expect(await screen.findByText("At least 12 characters")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Create your account" }),
    ).toBeInTheDocument();
  });

  it("month select has 12 options plus placeholder; year select has 101 years and no default value", async () => {
    stubFetch({ "GET /auth/session": notAuth });
    renderAt("/register", routes);
    const month = (await screen.findByLabelText(
      "Birth month",
    )) as HTMLSelectElement;
    const year = screen.getByLabelText("Birth year") as HTMLSelectElement;
    expect(month.tagName).toBe("SELECT");
    expect(month.options).toHaveLength(13);
    expect(month.options[0]).toHaveTextContent("Month");
    expect(month.options[0].value).toBe("");
    expect(month.options[1]).toHaveTextContent("January");
    expect(month.options[12]).toHaveTextContent("December");
    expect(month.options[12].value).toBe("12");
    expect(month.value).toBe("");
    const now = new Date().getFullYear();
    expect(year.options).toHaveLength(102);
    expect(year.options[0]).toHaveTextContent("Year");
    expect(year.options[1].value).toBe(String(now));
    expect(year.options[101].value).toBe(String(now - 100));
    expect(year.value).toBe("");
  });

  it("no visible text outside the year <option>s matches the age regex", async () => {
    stubFetch({ "GET /auth/session": notAuth });
    const { container } = renderAt("/register", routes);
    await screen.findByLabelText("Email");
    container.querySelectorAll("#birth-year option").forEach((n) => n.remove());
    expect(container.textContent).not.toMatch(/\b13\b|\bage\b|old enough/i);
  });

  it.each([
    ["email_taken", "That email is already registered."],
    ["password_breached", "That password appeared in a data breach."],
    [
      "registration_not_allowed",
      "We couldn't create an account with those details.",
    ],
  ])("shows server error message for %s", async (code, message) => {
    const user = userEvent.setup();
    stubFetch({
      "GET /auth/session": notAuth,
      "POST /auth/register": () => json(apiError(code, message), 400),
    });
    renderAt("/register", routes);
    await fillAndSubmit(user);
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  it("posts birth_month and birth_year as numbers", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch({
      "GET /auth/session": notAuth,
      "POST /auth/register": () => json(session, 201),
    });
    renderAt("/register", routes);
    await fillAndSubmit(user);
    expect(
      await screen.findByRole("heading", { name: "Sets" }),
    ).toBeInTheDocument();
    const req = fetchMock.mock.calls
      .map((c) => c[0] as Request)
      .find((r) => r.method === "POST")!;
    expect(await req.clone().json()).toEqual({
      email: "a@b.co",
      password: "correct-horse-battery",
      birth_month: 3,
      birth_year: 1999,
    });
  });

  it("validates client-side: short password and missing fields send nothing", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch({ "GET /auth/session": notAuth });
    renderAt("/register", routes);
    await user.type(await screen.findByLabelText("Email"), "a@b.co");
    await user.type(screen.getByLabelText("Password"), "short");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some((c) => (c[0] as Request).method === "POST"),
    ).toBe(false);
  });

  it("links to login", async () => {
    stubFetch({ "GET /auth/session": notAuth });
    renderAt("/register", routes);
    expect(
      await screen.findByRole("link", {
        name: "Already have an account? Log in",
      }),
    ).toHaveAttribute("href", "/login");
  });
});
