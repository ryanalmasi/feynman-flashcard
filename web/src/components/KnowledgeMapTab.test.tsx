import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { afterEach, describe, expect, it, vi } from "vitest";
import KnowledgeMapTab from "./KnowledgeMapTab";
import { POLL_LIMIT_MS, POLL_MS, TIMEOUT_COPY } from "./DocumentStatus";
import { useKnowledgeMap } from "@/hooks/useKnowledgeMap";
import { apiError, json, stubFetch } from "@/test/pageUtils";

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

type DocStatus = "processing" | "ready" | "failed" | null;

function Harness({ documentStatus }: { documentStatus: DocStatus }) {
  const km = useKnowledgeMap("s1", documentStatus === "processing");
  return (
    <KnowledgeMapTab
      setId="s1"
      map={km.map}
      state={km.state}
      timedOut={km.timedOut}
      documentStatus={documentStatus}
      onChanged={km.refresh}
      onReplace={km.replace}
    />
  );
}

const concept = (id: string, title: string, extra: object = {}) => ({
  id,
  position: 0,
  title,
  explanation: `About ${title}.`,
  importance: "core",
  key_terms: [],
  misconceptions: [],
  source_pages: [],
  ...extra,
});
const c1 = concept("c1", "Cell division", {
  importance: "core",
  source_pages: [4, 5, 6, 7],
  key_terms: [{ term: "mitosis", synonyms: ["karyokinesis"] }],
  misconceptions: ["Cells grow during mitosis."],
});
const c2 = concept("c2", "Respiration", {
  position: 1,
  importance: "detail",
  source_pages: [4, 9],
});
const mapOut = (extra: object = {}) => ({
  id: "m1",
  status: "ready",
  error_message: null,
  model_id: "model-x",
  revision: 1,
  cards_status: "idle",
  cards_error_message: null,
  source_filename: "bio.pdf",
  concepts: [c1, c2],
  ...extra,
});
const KM = "GET /study-sets/s1/knowledge-map";
const REBUILD = "POST /study-sets/s1/knowledge-map/rebuild";
const notFound = () => json(apiError("not_found", "Not found."), 404);

const requests = (m: ReturnType<typeof stubFetch>, method: string) =>
  Promise.all(
    m.mock.calls
      .map((c) => c[0] as Request)
      .filter((r) => r.method === method)
      .map(async (r) => ({
        path: new URL(r.url).pathname,
        body: await r.clone().text(),
      })),
  );
const gets = (m: ReturnType<typeof stubFetch>) =>
  m.mock.calls.filter((c) => (c[0] as Request).method === "GET").length;

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.mocked(toast.error).mockClear();
});

describe("KnowledgeMapTab", () => {
  it("shows the header with its concept count and the concept rows", async () => {
    stubFetch({ [KM]: () => json(mapOut(), 200) });
    render(<Harness documentStatus="ready" />);
    expect(
      await screen.findByText("AI-generated from bio.pdf · 2 concepts"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Cell division" }),
    ).toBeVisible();
    expect(screen.getByText("Core")).toBeInTheDocument();
    expect(screen.getByText("Detail")).toBeInTheDocument();
    expect(screen.getByText("p. 4–7")).toBeInTheDocument();
    expect(screen.getByText("p. 4, 9")).toBeInTheDocument();
    expect(screen.getByText("About Cell division.")).toBeInTheDocument();
    const summary = screen.getByText("Key terms and misconceptions");
    expect(summary.tagName).toBe("SUMMARY");
    const details = summary.closest("details")!;
    expect(within(details).getByText("mitosis")).toBeInTheDocument();
    expect(within(details).getByText(/karyokinesis/)).toBeInTheDocument();
    expect(
      within(details).getByText("Cells grow during mitosis."),
    ).toBeInTheDocument();
  });

  it("uses the singular for one concept", async () => {
    stubFetch({ [KM]: () => json(mapOut({ concepts: [c1] }), 200) });
    render(<Harness documentStatus="ready" />);
    expect(
      await screen.findByText("AI-generated from bio.pdf · 1 concept"),
    ).toBeInTheDocument();
  });

  it("renders model text as plain text", async () => {
    stubFetch({
      [KM]: () =>
        json(
          mapOut({
            concepts: [concept("c9", "<i>T</i>", { explanation: "<b>x</b>" })],
          }),
          200,
        ),
    });
    render(<Harness documentStatus="ready" />);
    expect(await screen.findByText("<b>x</b>")).toBeInTheDocument();
    expect(screen.getByText("<i>T</i>")).toBeInTheDocument();
  });

  it("add concept POSTs the parsed body and reloads the map", async () => {
    const user = userEvent.setup();
    const m = stubFetch({
      [KM]: () => json(mapOut(), 200),
      "POST /study-sets/s1/concepts": () => json(concept("c3", "New"), 201),
    });
    render(<Harness documentStatus="ready" />);
    await screen.findByText("AI-generated from bio.pdf · 2 concepts");

    await user.click(screen.getByRole("button", { name: "Add concept" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Title"), "Osmosis");
    await user.type(within(dialog).getByLabelText("Explanation"), "Water.");
    await user.selectOptions(
      within(dialog).getByLabelText("Importance"),
      "Supporting",
    );
    await user.type(
      within(dialog).getByLabelText("Key terms"),
      "osmosis: diffusion of water, water flow{Enter}{Enter}membrane",
    );
    await user.type(
      within(dialog).getByLabelText("Misconceptions"),
      "Salt moves.{Enter}It needs energy.",
    );
    await user.type(within(dialog).getByLabelText("Pages"), "7, 3");
    await user.click(within(dialog).getByRole("button", { name: "Add" }));

    await waitFor(async () =>
      expect(await requests(m, "POST")).toHaveLength(1),
    );
    const [post] = await requests(m, "POST");
    expect(post.path).toBe("/study-sets/s1/concepts");
    expect(JSON.parse(post.body)).toEqual({
      title: "Osmosis",
      explanation: "Water.",
      importance: "supporting",
      key_terms: [
        { term: "osmosis", synonyms: ["diffusion of water", "water flow"] },
        { term: "membrane", synonyms: [] },
      ],
      misconceptions: ["Salt moves.", "It needs energy."],
      source_pages: [3, 7],
    });
    await waitFor(() => expect(gets(m)).toBe(2));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("edit concept is pre-filled and PATCHes the concept", async () => {
    const user = userEvent.setup();
    const m = stubFetch({
      [KM]: () => json(mapOut(), 200),
      "PATCH /concepts/c1": () => json(c1, 200),
    });
    render(<Harness documentStatus="ready" />);
    await screen.findByText("AI-generated from bio.pdf · 2 concepts");

    await user.click(
      screen.getByRole("button", { name: "Edit Cell division" }),
    );
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByLabelText("Title")).toHaveValue("Cell division");
    expect(within(dialog).getByLabelText("Importance")).toHaveValue("core");
    expect(within(dialog).getByLabelText("Key terms")).toHaveValue(
      "mitosis: karyokinesis",
    );
    expect(within(dialog).getByLabelText("Misconceptions")).toHaveValue(
      "Cells grow during mitosis.",
    );
    expect(within(dialog).getByLabelText("Pages")).toHaveValue("4, 5, 6, 7");

    const title = within(dialog).getByLabelText("Title");
    await user.clear(title);
    await user.type(title, "Mitosis");
    const pages = within(dialog).getByLabelText("Pages");
    await user.clear(pages);
    await user.type(pages, "5,4");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));

    await waitFor(async () =>
      expect(await requests(m, "PATCH")).toHaveLength(1),
    );
    const [patch] = await requests(m, "PATCH");
    expect(patch.path).toBe("/concepts/c1");
    expect(JSON.parse(patch.body)).toEqual({
      title: "Mitosis",
      explanation: "About Cell division.",
      importance: "core",
      key_terms: [{ term: "mitosis", synonyms: ["karyokinesis"] }],
      misconceptions: ["Cells grow during mitosis."],
      source_pages: [4, 5],
    });
    await waitFor(() => expect(gets(m)).toBe(2));
  });

  it("delete concept confirms, then DELETEs it", async () => {
    const user = userEvent.setup();
    const m = stubFetch({
      [KM]: () => json(mapOut(), 200),
      "DELETE /concepts/c2": () => new Response(null, { status: 204 }),
    });
    render(<Harness documentStatus="ready" />);
    await screen.findByText("AI-generated from bio.pdf · 2 concepts");

    await user.click(
      screen.getByRole("button", { name: "Delete Respiration" }),
    );
    const dialog = screen.getByRole("alertdialog");
    expect(
      within(dialog).getByText("Delete this concept? Its flashcards are kept."),
    ).toBeInTheDocument();
    expect(await requests(m, "DELETE")).toHaveLength(0);
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));
    await waitFor(async () =>
      expect(await requests(m, "DELETE")).toEqual([
        { path: "/concepts/c2", body: "" },
      ]),
    );
    await waitFor(() => expect(gets(m)).toBe(2));
  });

  it("shows the server's 422 message inline", async () => {
    const user = userEvent.setup();
    stubFetch({
      [KM]: () => json(mapOut(), 200),
      "POST /study-sets/s1/concepts": () =>
        json(
          {
            error: {
              code: "validation_error",
              message: "Request validation failed.",
              details: [
                {
                  loc: ["body", "source_pages"],
                  msg: "page numbers must be within the document",
                },
              ],
            },
          },
          422,
        ),
    });
    render(<Harness documentStatus="ready" />);
    await screen.findByText("AI-generated from bio.pdf · 2 concepts");
    await user.click(screen.getByRole("button", { name: "Add concept" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Title"), "T");
    await user.type(within(dialog).getByLabelText("Explanation"), "E");
    await user.type(within(dialog).getByLabelText("Pages"), "99");
    await user.click(within(dialog).getByRole("button", { name: "Add" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "page numbers must be within the document",
    );
  });

  it("falls back to the error message when a 422 has no details", async () => {
    const user = userEvent.setup();
    stubFetch({
      [KM]: () => json(mapOut(), 200),
      "POST /study-sets/s1/concepts": () =>
        json(apiError("validation_error", "Bad concept."), 422),
    });
    render(<Harness documentStatus="ready" />);
    await screen.findByText("AI-generated from bio.pdf · 2 concepts");
    await user.click(screen.getByRole("button", { name: "Add concept" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Title"), "T");
    await user.type(within(dialog).getByLabelText("Explanation"), "E");
    await user.click(within(dialog).getByRole("button", { name: "Add" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Bad concept.",
    );
  });

  it("rejects invalid pages before sending", async () => {
    const user = userEvent.setup();
    const m = stubFetch({ [KM]: () => json(mapOut(), 200) });
    render(<Harness documentStatus="ready" />);
    await screen.findByText("AI-generated from bio.pdf · 2 concepts");
    await user.click(screen.getByRole("button", { name: "Add concept" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Title"), "T");
    await user.type(within(dialog).getByLabelText("Explanation"), "E");
    await user.type(within(dialog).getByLabelText("Pages"), "4-7");
    await user.click(within(dialog).getByRole("button", { name: "Add" }));
    expect(within(dialog).getByRole("alert")).toBeInTheDocument();
    expect(await requests(m, "POST")).toHaveLength(0);
  });

  it("rebuild asks first, then POSTs /rebuild and shows the building status", async () => {
    const user = userEvent.setup();
    const m = stubFetch({
      [KM]: () => json(mapOut(), 200),
      [REBUILD]: () => json(mapOut({ status: "processing" }), 202),
    });
    render(<Harness documentStatus="ready" />);
    await screen.findByText("AI-generated from bio.pdf · 2 concepts");

    await user.click(screen.getByRole("button", { name: "Rebuild" }));
    const dialog = screen.getByRole("alertdialog");
    expect(
      within(dialog).getByText(
        "Rebuilding replaces all concepts, including your edits. Your flashcards are kept.",
      ),
    ).toBeInTheDocument();
    expect(await requests(m, "POST")).toHaveLength(0);
    await user.click(within(dialog).getByRole("button", { name: "Rebuild" }));
    await waitFor(async () =>
      expect(await requests(m, "POST")).toEqual([
        { path: "/study-sets/s1/knowledge-map/rebuild", body: "" },
      ]),
    );
    expect(
      await screen.findByText("Building the Knowledge Map…"),
    ).toBeInTheDocument();
  });

  it.each([
    [429, "rate_limited", "Too many rebuilds. Try again later."],
    [409, "conflict", "The Knowledge Map is being built."],
  ])("a %i on rebuild shows a toast", async (status, code, message) => {
    const user = userEvent.setup();
    stubFetch({
      [KM]: () => json(mapOut(), 200),
      [REBUILD]: () => json(apiError(code, message), status),
    });
    render(<Harness documentStatus="ready" />);
    await screen.findByText("AI-generated from bio.pdf · 2 concepts");
    await user.click(screen.getByRole("button", { name: "Rebuild" }));
    await user.click(
      within(screen.getByRole("alertdialog")).getByRole("button", {
        name: "Rebuild",
      }),
    );
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(message));
  });

  it("a 409 on a concept edit shows a toast and reloads the map", async () => {
    const user = userEvent.setup();
    const m = stubFetch({
      [KM]: () => json(mapOut(), 200),
      "DELETE /concepts/c1": () =>
        json(apiError("conflict", "Flashcards are being generated."), 409),
    });
    render(<Harness documentStatus="ready" />);
    await screen.findByText("AI-generated from bio.pdf · 2 concepts");
    await user.click(
      screen.getByRole("button", { name: "Delete Cell division" }),
    );
    await user.click(
      within(screen.getByRole("alertdialog")).getByRole("button", {
        name: "Delete",
      }),
    );
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        "Flashcards are being generated.",
      ),
    );
    await waitFor(() => expect(gets(m)).toBe(2));
  });

  it("disables every mutating control while cards are processing", async () => {
    stubFetch({
      [KM]: () => json(mapOut({ cards_status: "processing" }), 200),
    });
    render(<Harness documentStatus="ready" />);
    expect(await screen.findByText("Generating flashcards…")).toBeVisible();
    expect(screen.getByRole("button", { name: "Add concept" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Rebuild" })).toBeDisabled();
    for (const name of [
      "Edit Cell division",
      "Delete Cell division",
      "Edit Respiration",
      "Delete Respiration",
    ]) {
      expect(screen.getByRole("button", { name })).toBeDisabled();
    }
  });

  it("disables every mutating control while the map is processing", async () => {
    stubFetch({ [KM]: () => json(mapOut({ status: "processing" }), 200) });
    render(<Harness documentStatus="ready" />);
    expect(
      await screen.findByText("Building the Knowledge Map…"),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Add concept" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Rebuild" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Edit Cell division" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Delete Cell division" }),
    ).toBeDisabled();
  });

  it("a failed map shows its message and a Rebuild button", async () => {
    const user = userEvent.setup();
    const m = stubFetch({
      [KM]: () =>
        json(
          mapOut({
            status: "failed",
            error_message: "We couldn't build the Knowledge Map.",
            concepts: [],
          }),
          200,
        ),
      [REBUILD]: () => json(mapOut({ status: "processing" }), 202),
    });
    render(<Harness documentStatus="ready" />);
    expect(
      await screen.findByText("We couldn't build the Knowledge Map."),
    ).toBeInTheDocument();
    const rebuild = screen.getByRole("button", { name: "Rebuild" });
    expect(rebuild).toBeEnabled();
    expect(screen.getByRole("button", { name: "Add concept" })).toBeDisabled();
    await user.click(rebuild);
    await user.click(
      within(screen.getByRole("alertdialog")).getByRole("button", {
        name: "Rebuild",
      }),
    );
    await waitFor(async () =>
      expect(await requests(m, "POST")).toHaveLength(1),
    );
    expect(
      await screen.findByText("Building the Knowledge Map…"),
    ).toBeInTheDocument();
  });

  describe("no map", () => {
    it.each([
      ["processing", "The Knowledge Map will be built when the PDF is ready."],
      ["failed", "No Knowledge Map: the PDF couldn't be processed."],
      [
        null,
        "Knowledge Maps are built from an uploaded PDF. This set has none.",
      ],
      ["ready", "This set has no Knowledge Map yet."],
    ] as const)("document %s", async (documentStatus, copy) => {
      stubFetch({ [KM]: notFound });
      render(<Harness documentStatus={documentStatus} />);
      expect(await screen.findByText(copy)).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Build Knowledge Map" }) !== null,
      ).toBe(documentStatus === "ready");
    });

    it("Build Knowledge Map POSTs /rebuild without a confirmation, then shows the building status", async () => {
      const user = userEvent.setup();
      let release: (r: Response) => void = () => {};
      const m = stubFetch({
        [KM]: notFound,
        [REBUILD]: () => new Promise<Response>((r) => (release = r)),
      });
      render(<Harness documentStatus="ready" />);
      const build = await screen.findByRole("button", {
        name: "Build Knowledge Map",
      });
      await user.click(build);
      expect(screen.queryByRole("alertdialog")).toBeNull();
      await waitFor(async () =>
        expect(await requests(m, "POST")).toEqual([
          { path: "/study-sets/s1/knowledge-map/rebuild", body: "" },
        ]),
      );
      expect(build).toBeDisabled();
      await act(async () => {
        release(json(mapOut({ status: "processing", concepts: [] }), 202));
      });
      expect(
        await screen.findByText("Building the Knowledge Map…"),
      ).toBeInTheDocument();
    });

    it("a 429 on Build Knowledge Map shows a toast and re-enables the button", async () => {
      const user = userEvent.setup();
      stubFetch({
        [KM]: notFound,
        [REBUILD]: () =>
          json(apiError("rate_limited", "Too many requests."), 429),
      });
      render(<Harness documentStatus="ready" />);
      const build = await screen.findByRole("button", {
        name: "Build Knowledge Map",
      });
      await user.click(build);
      await waitFor(() =>
        expect(toast.error).toHaveBeenCalledWith("Too many requests."),
      );
      expect(build).toBeEnabled();
    });
  });

  describe("polling", () => {
    it("polls while processing and shows the concepts once ready", async () => {
      vi.useFakeTimers();
      const replies = [
        mapOut({ status: "processing", concepts: [] }),
        mapOut({ status: "processing", concepts: [] }),
        mapOut(),
      ];
      const m = stubFetch({ [KM]: () => json(replies.shift(), 200) });
      render(<Harness documentStatus="ready" />);
      await act(() => vi.advanceTimersByTimeAsync(0));
      expect(screen.getByText("Building the Knowledge Map…")).toBeVisible();
      await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 2));
      expect(screen.queryByText("Building the Knowledge Map…")).toBeNull();
      expect(screen.getByText("AI-generated from bio.pdf · 2 concepts"));
      await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 5));
      expect(m).toHaveBeenCalledTimes(3);
    });

    it("stops at the 10-minute cap with the timeout copy", async () => {
      vi.useFakeTimers();
      const m = stubFetch({
        [KM]: () => json(mapOut({ status: "processing" }), 200),
      });
      render(<Harness documentStatus="ready" />);
      await act(() => vi.advanceTimersByTimeAsync(0));
      await act(() => vi.advanceTimersByTimeAsync(POLL_LIMIT_MS));
      expect(TIMEOUT_COPY).toBe(
        "This is taking longer than expected. Check back later.",
      );
      expect(screen.getByText(TIMEOUT_COPY)).toBeInTheDocument();
      const n = m.mock.calls.length;
      await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 10));
      expect(m).toHaveBeenCalledTimes(n);
    });
  });
});
