import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import SetDetailPage from "./SetDetailPage";
import { POLL_MS } from "@/components/DocumentStatus";
import { apiError, json, renderAt, session, stubFetch } from "@/test/pageUtils";

const routes = (
  <Routes>
    <Route path="/sets" element={<h1>Sets list</h1>} />
    <Route path="/sets/:setId" element={<SetDetailPage />} />
    <Route path="/sets/:setId/review" element={<h1>Review page</h1>} />
  </Routes>
);

const ts = "2026-01-01T00:00:00Z";
const setOut = (
  card_count: number,
  document: unknown = null,
  extra: object = {},
) => ({
  id: "s1",
  title: "Biology",
  description: "Cells and such",
  card_count,
  suggested_count: 0,
  document,
  knowledge_map: null,
  created_at: ts,
  updated_at: ts,
  ...extra,
});
const card = (id: string, front: string, back: string, extra: object = {}) => ({
  id,
  study_set_id: "s1",
  concept_id: null,
  kind: "qa",
  front,
  back,
  origin: "manual",
  status: "accepted",
  edited: false,
  created_at: ts,
  updated_at: ts,
  ...extra,
});
const KM = "GET /study-sets/s1/knowledge-map";
const FC = "GET /study-sets/s1/flashcards";
const statusOf = (req: Request) => new URL(req.url).searchParams.get("status");
/**
 * stubFetch keys on the pathname only, so the accepted list (no query or
 * ?status=accepted) and ?status=suggested share one stub: branch on the query.
 */
const flashcards =
  (accepted: unknown[], suggested: unknown[] = []) =>
  (req: Request) => {
    const status = statusOf(req);
    if (status === null || status === "accepted") return json(accepted, 200);
    if (status === "suggested") return json(suggested, 200);
    throw new Error(`unexpected flashcards status: ${status}`);
  };
const noMap = () => json(apiError("not_found", "Not found."), 404);
const mapOut = (extra: object = {}) => ({
  id: "m1",
  status: "ready",
  error_message: null,
  model_id: "model-x",
  revision: 1,
  cards_status: "idle",
  cards_error_message: null,
  source_filename: "bio.pdf",
  concepts: [],
  ...extra,
});
const doc = (status: string) => ({
  id: "d1",
  original_filename: "a.pdf",
  status,
  page_count: status === "ready" ? 1 : null,
  error_message: null,
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
      [KM]: noMap,
      [FC]: flashcards(cards),
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
      [KM]: noMap,
      [FC]: flashcards([]),
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
      [KM]: noMap,
      [FC]: flashcards([card("c1", "Q", "A")]),
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
      [KM]: noMap,
      [FC]: flashcards([]),
    });
    renderAt("/sets/s1", routes);
    expect(await screen.findByText("Ready · 1 page")).toBeInTheDocument();
  });

  it("edits the set title and description", async () => {
    const user = userEvent.setup();
    const m = stubFetch({
      "GET /auth/session": () => json(session, 200),
      "GET /study-sets/s1": () => json(setOut(0), 200),
      [KM]: noMap,
      [FC]: flashcards([]),
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
      [KM]: noMap,
      [FC]: flashcards([]),
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
      [KM]: noMap,
      [FC]: (req) =>
        json(apiError("not_found", `nope ${statusOf(req) ?? "accepted"}`), 404),
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
      [KM]: noMap,
      [FC]: flashcards([card("c1", "line1\nline2", "<b>x</b>")]),
    });
    renderAt("/sets/s1", routes);
    const el = await screen.findByText(
      (_, n) => n?.textContent === "line1\nline2" && n.tagName === "P",
    );
    expect(el).toHaveClass("whitespace-pre-wrap");
    expect(screen.getByText("<b>x</b>")).toBeInTheDocument();
  });
  describe("tabs", () => {
    const stubs = (extra: Parameters<typeof stubFetch>[0] = {}) =>
      stubFetch({
        "GET /auth/session": () => json(session, 200),
        "GET /study-sets/s1": () =>
          json(setOut(2, doc("ready"), { suggested_count: 3 }), 200),
        [KM]: () => json(mapOut(), 200),
        [FC]: flashcards(
          [
            card("c1", "Mine", "A"),
            card("c2", "Generated", "B", { origin: "generated" }),
          ],
          [
            card("c8", "Suggested Q", "S", {
              origin: "generated",
              status: "suggested",
            }),
          ],
        ),
        ...extra,
      });

    it("renders three tabs with the suggested count, Cards by default", async () => {
      stubs();
      renderAt("/sets/s1", routes);
      await screen.findByRole("heading", { name: "Biology" });
      const tabs = screen.getAllByRole("tab").map((t) => t.textContent);
      expect(tabs).toEqual(["Cards", "Knowledge Map", "Suggested (3)"]);
      expect(screen.getByRole("tab", { name: "Cards" })).toHaveAttribute(
        "aria-selected",
        "true",
      );
      expect(screen.getByText("Mine")).toBeVisible();
      // The header and document status stay above the tabs.
      expect(screen.getByText("Ready · 1 page")).toBeInTheDocument();
    });

    it("?tab=map opens the Knowledge Map tab", async () => {
      stubs();
      renderAt("/sets/s1?tab=map", routes);
      expect(
        await screen.findByText("AI-generated from bio.pdf · 0 concepts"),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("tab", { name: "Knowledge Map" }),
      ).toHaveAttribute("aria-selected", "true");
      expect(screen.queryByText("Mine")).toBeNull();
    });

    it("?tab=suggested opens the Suggested tab with the suggested list", async () => {
      const m = stubs();
      renderAt("/sets/s1?tab=suggested", routes);
      await screen.findByRole("heading", { name: "Biology" });
      expect(
        screen.getByRole("tab", { name: "Suggested (3)" }),
      ).toHaveAttribute("aria-selected", "true");
      const panel = screen.getByRole("tabpanel");
      expect(within(panel).getByText("Suggested Q")).toBeInTheDocument();
      expect(within(panel).queryByText("Mine")).toBeNull();
      const queries = m.mock.calls
        .map((c) => new URL((c[0] as Request).url))
        .filter((u) => u.pathname === "/study-sets/s1/flashcards")
        .map((u) => u.searchParams.get("status"));
      expect(queries.sort()).toEqual([null, "suggested"].sort());
    });

    it("suggested cards never appear in the Cards tab", async () => {
      stubs();
      renderAt("/sets/s1", routes);
      await screen.findByText("Mine");
      expect(screen.queryByText("Suggested Q")).toBeNull();
      expect(
        within(screen.getByRole("tabpanel")).getAllByRole("listitem"),
      ).toHaveLength(2);
    });

    it("accepting a suggested card reloads the set, cards and suggested list", async () => {
      const user = userEvent.setup();
      let accepted = false;
      const m = stubs({
        "GET /study-sets/s1": () =>
          json(
            setOut(accepted ? 3 : 2, doc("ready"), {
              suggested_count: accepted ? 0 : 1,
            }),
            200,
          ),
        [FC]: (req) =>
          flashcards(
            accepted
              ? [
                  card("c1", "Mine", "A"),
                  card("c8", "Suggested Q", "S", { origin: "generated" }),
                ]
              : [card("c1", "Mine", "A")],
            accepted
              ? []
              : [
                  card("c8", "Suggested Q", "S", {
                    origin: "generated",
                    status: "suggested",
                  }),
                ],
          )(req),
        "PATCH /flashcards/c8": () => {
          accepted = true;
          return json(card("c8", "Suggested Q", "S"), 200);
        },
      });
      renderAt("/sets/s1?tab=suggested", routes);
      const panel = await screen.findByRole("tabpanel");
      await within(panel).findByText("Suggested Q");
      expect(screen.getByRole("tab", { name: "Suggested (1)" })).toBeVisible();
      await user.click(within(panel).getByRole("button", { name: "Accept" }));
      expect(
        await screen.findByRole("tab", { name: "Suggested (0)" }),
      ).toBeInTheDocument();
      expect(
        await screen.findByText(
          "No suggested cards. Generate flashcards from the Knowledge Map tab.",
        ),
      ).toBeInTheDocument();
      const gets = (status: string | null) =>
        m.mock.calls
          .map((c) => c[0] as Request)
          .filter(
            (r) =>
              r.method === "GET" &&
              new URL(r.url).pathname === "/study-sets/s1/flashcards" &&
              statusOf(r) === status,
          ).length;
      expect(gets(null)).toBe(2);
      expect(gets("suggested")).toBe(2);
      await user.click(screen.getByRole("tab", { name: "Cards" }));
      expect(screen.getByText("Suggested Q")).toBeVisible();
    });

    it("Generate flashcards on the map tab starts the card job", async () => {
      const user = userEvent.setup();
      const k = {
        id: "k1",
        position: 0,
        title: "Cells",
        explanation: "E",
        importance: "core",
        key_terms: [],
        misconceptions: [],
        source_pages: [],
      };
      const m = stubs({
        [KM]: () => json(mapOut({ concepts: [k] }), 200),
        [FC]: flashcards([card("c1", "Mine", "A")]),
        "POST /study-sets/s1/flashcards/generate": () =>
          json(mapOut({ concepts: [k], cards_status: "processing" }), 202),
      });
      renderAt("/sets/s1?tab=map", routes);
      await user.click(
        await screen.findByRole("button", { name: "Generate flashcards" }),
      );
      expect(
        await screen.findByText("Generating flashcards…"),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Generate flashcards" }),
      ).toBeDisabled();
      const posts = m.mock.calls.filter(
        (c) => (c[0] as Request).method === "POST",
      );
      expect(posts).toHaveLength(1);
    });

    it("clicking a tab updates the URL", async () => {
      const user = userEvent.setup();
      stubs();
      renderAt("/sets/s1", routes);
      await screen.findByRole("heading", { name: "Biology" });
      await user.click(screen.getByRole("tab", { name: "Knowledge Map" }));
      expect(screen.getByTestId("where")).toHaveTextContent("/sets/s1?tab=map");
      expect(
        await screen.findByText("AI-generated from bio.pdf · 0 concepts"),
      ).toBeInTheDocument();
      await user.click(screen.getByRole("tab", { name: "Cards" }));
      expect(screen.getByTestId("where")).toHaveTextContent(
        "/sets/s1?tab=cards",
      );
      expect(screen.getByText("Mine")).toBeVisible();
    });

    it("an invalid tab falls back to Cards", async () => {
      stubs();
      renderAt("/sets/s1?tab=bogus", routes);
      await screen.findByRole("heading", { name: "Biology" });
      expect(screen.getByRole("tab", { name: "Cards" })).toHaveAttribute(
        "aria-selected",
        "true",
      );
      expect(screen.getByText("Mine")).toBeVisible();
    });

    it("shows the AI badge on generated cards only", async () => {
      stubs();
      renderAt("/sets/s1", routes);
      await screen.findByText("Mine");
      const items = screen.getAllByRole("listitem");
      const mine = items.find((li) => within(li).queryByText("Mine"))!;
      const gen = items.find((li) => within(li).queryByText("Generated"))!;
      expect(within(gen).getByText("AI")).toBeInTheDocument();
      expect(within(mine).queryByText("AI")).toBeNull();
      expect(screen.getAllByText("AI")).toHaveLength(1);
    });

    it("a concept edit reloads the map and the set", async () => {
      const user = userEvent.setup();
      const c = {
        id: "k1",
        position: 0,
        title: "Cells",
        explanation: "E",
        importance: "core",
        key_terms: [],
        misconceptions: [],
        source_pages: [],
      };
      const m = stubs({
        [KM]: () => json(mapOut({ concepts: [c] }), 200),
        "DELETE /concepts/k1": () => new Response(null, { status: 204 }),
      });
      renderAt("/sets/s1?tab=map", routes);
      await user.click(
        await screen.findByRole("button", { name: "Delete Cells" }),
      );
      await user.click(
        within(screen.getByRole("alertdialog")).getByRole("button", {
          name: "Delete",
        }),
      );
      const count = (path: string) =>
        m.mock.calls.filter(
          (x) =>
            (x[0] as Request).method === "GET" &&
            new URL((x[0] as Request).url).pathname === path,
        ).length;
      await waitFor(() => {
        expect(count("/study-sets/s1/knowledge-map")).toBe(2);
        expect(count("/study-sets/s1")).toBe(2);
      });
    });
  });

  describe("document processing", () => {
    afterEach(() => vi.useRealTimers());

    it("refreshes the suggested count when cards_status returns to idle", async () => {
      vi.useFakeTimers();
      let done = false;
      const m = stubFetch({
        "GET /auth/session": () => json(session, 200),
        "GET /study-sets/s1": () =>
          json(
            setOut(0, doc("ready"), {
              suggested_count: done ? 2 : 0,
              knowledge_map: {
                status: "ready",
                cards_status: done ? "idle" : "processing",
              },
            }),
            200,
          ),
        [FC]: (req) =>
          flashcards(
            [],
            done
              ? [
                  card("g1", "G1", "B", {
                    origin: "generated",
                    status: "suggested",
                  }),
                  card("g2", "G2", "B", {
                    origin: "generated",
                    status: "suggested",
                  }),
                ]
              : [],
          )(req),
        [KM]: () =>
          json(mapOut({ cards_status: done ? "idle" : "processing" }), 200),
      });
      renderAt("/sets/s1?tab=suggested", routes);
      await act(() => vi.advanceTimersByTimeAsync(0));
      expect(screen.getByRole("tab", { name: "Suggested (0)" })).toBeVisible();
      const setGets = () =>
        m.mock.calls.filter(
          (x) => new URL((x[0] as Request).url).pathname === "/study-sets/s1",
        ).length;
      expect(setGets()).toBe(1);

      // A poll while still processing does not reload the set.
      await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
      expect(setGets()).toBe(1);

      done = true;
      await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
      await act(() => vi.advanceTimersByTimeAsync(0));
      expect(screen.getByRole("tab", { name: "Suggested (2)" })).toBeVisible();
      expect(screen.getByText("G1")).toBeInTheDocument();
      expect(setGets()).toBe(2);

      // Polling has stopped; nothing reloads again.
      await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 3));
      expect(setGets()).toBe(2);
    });

    it("fetches the map again when the document finishes processing", async () => {
      vi.useFakeTimers();
      // The map exists only once extraction has finished.
      let extracted = false;
      const m = stubFetch({
        "GET /auth/session": () => json(session, 200),
        "GET /study-sets/s1": () => json(setOut(0, doc("processing")), 200),
        [FC]: flashcards([]),
        [KM]: () =>
          extracted ? json(mapOut({ status: "processing" }), 200) : noMap(),
        "GET /documents/d1": () => {
          extracted = true;
          return json({ ...doc("ready"), study_set_id: "s1" }, 200);
        },
      });
      renderAt("/sets/s1?tab=map", routes);
      await act(() => vi.advanceTimersByTimeAsync(0));
      expect(
        screen.getByText(
          "The Knowledge Map will be built when the PDF is ready.",
        ),
      ).toBeInTheDocument();
      // One poll tick: the document poll returns ready; the map poll (if any) runs too.
      await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
      await act(() => vi.advanceTimersByTimeAsync(0));
      expect(screen.getByText("Ready · 1 page")).toBeInTheDocument();
      expect(screen.getByText("Building the Knowledge Map…")).toBeVisible();
      const kmCalls = m.mock.calls.filter(
        (x) =>
          new URL((x[0] as Request).url).pathname ===
          "/study-sets/s1/knowledge-map",
      ).length;
      expect(kmCalls).toBeGreaterThanOrEqual(2);
    });
  });
});
