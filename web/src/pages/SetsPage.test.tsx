import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import SetsPage from "./SetsPage";
import { json, renderAt, session, stubFetch } from "@/test/pageUtils";

const routes = (
  <Routes>
    <Route path="/sets" element={<SetsPage />} />
    <Route path="/sets/:id" element={<h1>Set detail</h1>} />
  </Routes>
);

const ts = "2026-01-01T00:00:00Z";
const mk = (
  id: string,
  title: string,
  card_count: number,
  document: unknown,
) => ({
  id,
  title,
  description: null,
  card_count,
  document,
  created_at: ts,
  updated_at: ts,
});
const doc = (status: string) => ({
  id: "d1",
  original_filename: "a.pdf",
  status,
  page_count: null,
  error_message: null,
});

afterEach(() => vi.unstubAllGlobals());

describe("SetsPage", () => {
  it("lists sets with card counts and document badges", async () => {
    stubFetch({
      "GET /auth/session": () => json(session, 200),
      "GET /study-sets": () =>
        json(
          [
            mk("s1", "Biology", 1, doc("processing")),
            mk("s2", "History", 5, doc("ready")),
            mk("s3", "Math", 0, doc("failed")),
            mk("s4", "Plain", 2, null),
          ],
          200,
        ),
    });
    renderAt("/sets", routes);
    expect(
      await screen.findByRole("heading", { name: "Your study sets" }),
    ).toBeInTheDocument();
    const bio = await screen.findByRole("link", { name: /Biology/ });
    expect(bio).toHaveAttribute("href", "/sets/s1");
    expect(within(bio).getByText("1 card")).toBeInTheDocument();
    expect(within(bio).getByText("Processing…")).toBeInTheDocument();
    const hist = screen.getByRole("link", { name: /History/ });
    expect(within(hist).getByText("5 cards")).toBeInTheDocument();
    expect(within(hist).getByText("Ready")).toBeInTheDocument();
    const math = screen.getByRole("link", { name: /Math/ });
    expect(within(math).getByText("0 cards")).toBeInTheDocument();
    expect(within(math).getByText("Failed")).toBeInTheDocument();
    const plain = screen.getByRole("link", { name: /Plain/ });
    expect(within(plain).queryByText(/Ready|Failed|Processing/)).toBeNull();
    expect(screen.getByRole("button", { name: "New set" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Upload PDF" }),
    ).toBeInTheDocument();
  });

  it("empty state text", async () => {
    stubFetch({
      "GET /auth/session": () => json(session, 200),
      "GET /study-sets": () => json([], 200),
    });
    renderAt("/sets", routes);
    expect(
      await screen.findByText("No study sets yet. Create one or upload a PDF."),
    ).toBeInTheDocument();
  });

  it("create set dialog posts and navigates", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch({
      "GET /auth/session": () => json(session, 200),
      "GET /study-sets": () => json([], 200),
      "POST /study-sets": () => json(mk("new1", "Chem", 0, null), 201),
    });
    renderAt("/sets", routes);
    await user.click(await screen.findByRole("button", { name: "New set" }));
    await user.type(screen.getByLabelText("Title"), "Chem");
    await user.type(screen.getByLabelText("Description"), "Atoms");
    await user.click(screen.getByRole("button", { name: "Create" }));
    expect(
      await screen.findByRole("heading", { name: "Set detail" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/sets/new1");
    const req = fetchMock.mock.calls
      .map((c) => c[0] as Request)
      .find((r) => r.method === "POST")!;
    expect(await req.clone().json()).toEqual({
      title: "Chem",
      description: "Atoms",
    });
  });

  it("requires a non-blank title", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch({
      "GET /auth/session": () => json(session, 200),
      "GET /study-sets": () => json([], 200),
    });
    renderAt("/sets", routes);
    await user.click(await screen.findByRole("button", { name: "New set" }));
    await user.type(screen.getByLabelText("Title"), "   ");
    await user.click(screen.getByRole("button", { name: "Create" }));
    expect(
      fetchMock.mock.calls.some((c) => (c[0] as Request).method === "POST"),
    ).toBe(false);
  });
});
