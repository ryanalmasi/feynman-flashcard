import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import RegisterPage from "./RegisterPage";
import { apiError, json, renderAt, session, stubFetch } from "@/test/pageUtils";

const routes = (
  <Routes>
    <Route path="/register" element={<RegisterPage />} />
    <Route path="/login" element={<h1>Login</h1>} />
    <Route path="/sets" element={<h1>Sets</h1>} />
  </Routes>
);
const notAuth = () => json(apiError("not_authenticated", "x"), 401);

afterEach(() => vi.unstubAllGlobals());

const BRIEF_RE = /\b13\b|\bage\b|old enough/i;
const WIDE_RE =
  /\b(1[3-9]|2[01])\b|\bage\b|\bold(er)?\b|young|minimum|eligible|must be|adult|minor|teen|under\s*\d|years?\s+old/i;

/** Text content plus placeholder/aria-label/title/alt/aria-describedby copy. */
function visibleCopy(root: HTMLElement): string[] {
  const out = [root.textContent ?? ""];
  root.querySelectorAll("*").forEach((el) => {
    for (const a of ["placeholder", "aria-label", "title", "alt"]) {
      const v = el.getAttribute(a);
      if (v) out.push(v);
    }
    el.getAttribute("aria-describedby")
      ?.split(/\s+/)
      .forEach((id) => {
        const t = root.querySelector("#" + id)?.textContent;
        if (t) out.push(t);
      });
  });
  return out;
}

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

  it("no visible text or attribute outside the year <option>s mentions an age limit", async () => {
    stubFetch({ "GET /auth/session": notAuth });
    const { container } = renderAt("/register", routes);
    await screen.findByLabelText("Email");
    container.querySelectorAll("#birth-year option").forEach((n) => n.remove());
    const texts = visibleCopy(container);
    expect(texts.join("\n")).not.toMatch(BRIEF_RE);
    expect(texts.join("\n")).not.toMatch(WIDE_RE);
  });

  it("the wide age-copy check catches typical age-gate wording", async () => {
    stubFetch({ "GET /auth/session": notAuth });
    const { container } = renderAt("/register", routes);
    await screen.findByLabelText("Email");
    for (const copy of ["You must be 18 or older", "Adults only"]) {
      const p = document.createElement("p");
      p.textContent = copy;
      container.appendChild(p);
      expect(visibleCopy(container).join("\n")).toMatch(WIDE_RE);
      p.remove();
    }
    const input = container.querySelector("input")!;
    input.setAttribute("placeholder", "Must be an adult");
    expect(visibleCopy(container).join("\n")).toMatch(WIDE_RE);
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

  it("short password shows the hint as an error (aria-invalid) and sends nothing", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch({ "GET /auth/session": notAuth });
    renderAt("/register", routes);
    await user.type(await screen.findByLabelText("Email"), "a@b.co");
    await user.type(screen.getByLabelText("Password"), "short");
    await user.selectOptions(screen.getByLabelText("Birth month"), "3");
    await user.selectOptions(screen.getByLabelText("Birth year"), "1999");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "At least 12 characters",
    );
    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1); // only the session check
  });

  it("missing fields block submission", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch({ "GET /auth/session": notAuth });
    renderAt("/register", routes);
    await user.type(await screen.findByLabelText("Email"), "a@b.co");
    await user.type(screen.getByLabelText("Password"), "correct-horse-battery");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("a network failure shows a generic error and re-enables the button", async () => {
    const user = userEvent.setup();
    stubFetch({
      "GET /auth/session": notAuth,
      "POST /auth/register": () => {
        throw new TypeError("down");
      },
    });
    renderAt("/register", routes);
    await fillAndSubmit(user);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong. Try again.",
    );
    expect(
      screen.getByRole("button", { name: "Create account" }),
    ).toBeEnabled();
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
