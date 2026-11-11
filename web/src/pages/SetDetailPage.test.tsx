import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import SetDetailPage from "./SetDetailPage";
import { apiError, json, renderAt, session, stubFetch } from "@/test/pageUtils";

const routes = (
  <Routes>
    <Route path="/sets" element={<h1>Sets list</h1>} />
    <Route path="/sets/:setId" element={<SetDetailPage />} />
    <Route path="/sets/:setId/review" element={<h1>Review page</h1>} />
  </Routes>
);

const ts = "2026-01-01T00:00:00Z";
const setOut = (card_count: number, document: unknown = null) => ({
  id: "s1",
  title: "Biology",
  description: "Cells and such",
  card_count,
  document,
  created_at: ts,
  updated_at: ts,
});
const card = (id: string, front: string, back: string) => ({
  id,
  study_set_id: "s1",
  front,
  back,
  origin: "manual",
  created_at: ts,
  updated_at: ts,
});
const bodies = (m: ReturnType<typeof stubFetch>, method: string) =>
  Promise.all(
    m.mock.calls
      .map((c) => c[0] as Request)
      .filter((r) => r.method === method)
      .map(async (r) => ({
        path: new URL(r.url).pathname,
        body: await r.clone().text(),
      })),
  );

afterEach(() => vi.unstubAllGlobals());

describe("SetDetailPage", () => {
  it("add, edit, delete card call the right endpoints by id", async () => {
    const user = userEvent.setup();
    const cards = [card("c1", "Q1", "A1")];
    const m = stubFetch({
      "GET /auth/session": () => json(session, 200),
      "GET /study-sets/s1": () => json(setOut(cards.length), 200),
      "GET /study-sets/s1/flashcards": () => json(cards, 200),
      "POST /study-sets/s1/flashcards": () => json(card("c2", "Q2", "A2"), 201),
      "PATCH /flashcards/c1": () => json(card("c1", "Q1b", "A1"), 200),
      "DELETE /flashcards/c1": () => new Response(null, { status: 204 }),
    });
    renderAt("/sets/s1", routes);
    await screen.findByText("Q1");

    await user.click(screen.getByRole("button", { name: "Add card" }));
    await user.type(screen.getByLabelText("Front"), "Q2");
    await user.type(screen.getByLabelText("Back"), "A2");
    await user.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(async () => expect(await bodies(m, "POST")).toHaveLength(1));
    expect((await bodies(m, "POST"))[0]).toEqual({
      path: "/study-sets/s1/flashcards",
      body: JSON.stringify({ kind: "qa", front: "Q2", back: "A2" }),
    });

    await user.click(screen.getByRole("button", { name: "Edit card" }));
    const front = screen.getByLabelText("Front");
    await user.clear(front);
    await user.type(front, "Q1b");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(async () => expect(await bodies(m, "PATCH")).toHaveLength(1));
    expect((await bodies(m, "PATCH"))[0].path).toBe("/flashcards/c1");
    expect(JSON.parse((await bodies(m, "PATCH"))[0].body)).toEqual({
      front: "Q1b",
      back: "A1",
    });

    await user.click(screen.getByRole("button", { name: "Delete card" }));
    expect(screen.getByText("Delete this card?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(async () =>
      expect(await bodies(m, "DELETE")).toEqual([
        { path: "/flashcards/c1", body: "" },
      ]),
    );
  });

  it("review disabled with no cards", async () => {
    stubFetch({
      "GET /auth/session": () => json(session, 200),
      "GET /study-sets/s1": () => json(setOut(0), 200),
      "GET /study-sets/s1/flashcards": () => json([], 200),
    });
    renderAt("/sets/s1", routes);
    await screen.findByRole("heading", { name: "Biology" });
    expect(screen.getByText("Cells and such")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review" })).toBeDisabled();
  });

  it("links Review to the review page when cards exist", async () => {
    stubFetch({
      "GET /auth/session": () => json(session, 200),
      "GET /study-sets/s1": () => json(setOut(1), 200),
      "GET /study-sets/s1/flashcards": () => json([card("c1", "Q", "A")], 200),
    });
    renderAt("/sets/s1", routes);
    const link = await screen.findByRole("link", { name: "Review" });
    expect(link).toHaveAttribute("href", "/sets/s1/review");
  });

  it("shows document status", async () => {
    stubFetch({
      "GET /auth/session": () => json(session, 200),
      "GET /study-sets/s1": () =>
        json(
          setOut(0, {
            id: "d1",
            original_filename: "a.pdf",
            status: "ready",
            page_count: 1,
            error_message: null,
          }),
          200,
        ),
      "GET /study-sets/s1/flashcards": () => json([], 200),
    });
    renderAt("/sets/s1", routes);
    expect(await screen.findByText("Ready · 1 page")).toBeInTheDocument();
  });

  it("edits the set title and description", async () => {
    const user = userEvent.setup();
    const m = stubFetch({
      "GET /auth/session": () => json(session, 200),
      "GET /study-sets/s1": () => json(setOut(0), 200),
      "GET /study-sets/s1/flashcards": () => json([], 200),
      "PATCH /study-sets/s1": () => json(setOut(0), 200),
    });
    renderAt("/sets/s1", routes);
    await screen.findByRole("heading", { name: "Biology" });
    await user.click(screen.getByRole("button", { name: "Edit" }));
    expect(screen.getByLabelText("Title")).toHaveValue("Biology");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(async () => expect(await bodies(m, "PATCH")).toHaveLength(1));
  });

  it("delete set confirms then navigates to /sets", async () => {
    const user = userEvent.setup();
    const m = stubFetch({
      "GET /auth/session": () => json(session, 200),
      "GET /study-sets/s1": () => json(setOut(0), 200),
      "GET /study-sets/s1/flashcards": () => json([], 200),
      "DELETE /study-sets/s1": () => new Response(null, { status: 204 }),
    });
    renderAt("/sets/s1", routes);
    await screen.findByRole("heading", { name: "Biology" });
    await user.click(screen.getByRole("button", { name: "Delete set" }));
    expect(
      screen.getByText(
        "Delete this study set? Its cards and PDF will be deleted too.",
      ),
    ).toBeInTheDocument();
    const dialog = screen.getByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));
    expect(
      await screen.findByRole("heading", { name: "Sets list" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/sets");
    expect(await bodies(m, "DELETE")).toHaveLength(1);
  });

  it("404 shows Study set not found.", async () => {
    stubFetch({
      "GET /auth/session": () => json(session, 200),
      "GET /study-sets/s1": () => json(apiError("not_found", "nope"), 404),
      "GET /study-sets/s1/flashcards": () =>
        json(apiError("not_found", "nope"), 404),
    });
    renderAt("/sets/s1", routes);
    expect(await screen.findByText("Study set not found.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /sets/i })).toHaveAttribute(
      "href",
      "/sets",
    );
  });

  it("preserves line breaks in card text", async () => {
    stubFetch({
      "GET /auth/session": () => json(session, 200),
      "GET /study-sets/s1": () => json(setOut(1), 200),
      "GET /study-sets/s1/flashcards": () =>
        json([card("c1", "line1\nline2", "<b>x</b>")], 200),
    });
    renderAt("/sets/s1", routes);
    const el = await screen.findByText(
      (_, n) => n?.textContent === "line1\nline2" && n.tagName === "P",
    );
    expect(el).toHaveClass("whitespace-pre-wrap");
    expect(screen.getByText("<b>x</b>")).toBeInTheDocument();
  });
});
