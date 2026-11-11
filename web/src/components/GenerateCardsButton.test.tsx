import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { afterEach, describe, expect, it, vi } from "vitest";
import GenerateCardsButton from "./GenerateCardsButton";
import { apiError, json, stubFetch } from "@/test/pageUtils";

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

const ts = "2026-01-01T00:00:00Z";
const card = (id: string, extra: object = {}) => ({
  id,
  study_set_id: "s1",
  concept_id: "k1",
  kind: "qa",
  front: "F",
  back: "B",
  origin: "generated",
  status: "suggested",
  edited: false,
  created_at: ts,
  updated_at: ts,
  ...extra,
});
const mapOut = (extra: object = {}) => ({
  id: "m1",
  status: "ready",
  error_message: null,
  model_id: "model-x",
  revision: 1,
  cards_status: "processing",
  cards_error_message: null,
  source_filename: "bio.pdf",
  concepts: [],
  ...extra,
});
const LIST = "GET /study-sets/s1/flashcards";
const GENERATE = "POST /study-sets/s1/flashcards/generate";

/** Both list calls go to one path; branch on ?status. */
const lists =
  (accepted: object[], suggested: object[]) =>
  (req: Request): Response => {
    const status = new URL(req.url).searchParams.get("status");
    if (status === "accepted") return json(accepted, 200);
    if (status === "suggested") return json(suggested, 200);
    throw new Error(`unexpected status query: ${status}`);
  };

const posts = (m: ReturnType<typeof stubFetch>) =>
  Promise.all(
    m.mock.calls
      .map((c) => c[0] as Request)
      .filter((r) => r.method === "POST")
      .map(async (r) => ({
        path: new URL(r.url).pathname,
        body: await r.clone().text(),
      })),
  );

afterEach(() => {
  vi.unstubAllGlobals();
  vi.mocked(toast.error).mockClear();
});

describe("GenerateCardsButton", () => {
  it("labels: whole set and per concept", () => {
    stubFetch({});
    const { unmount } = render(
      <GenerateCardsButton
        setId="s1"
        conceptId={null}
        disabled={false}
        onStarted={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Generate flashcards" }),
    ).toBeEnabled();
    unmount();
    render(
      <GenerateCardsButton
        setId="s1"
        conceptId="k1"
        disabled
        onStarted={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Regenerate cards/ }),
    ).toBeDisabled();
  });

  it("warns with the exact counts, then posts {concept_id} on confirm", async () => {
    const user = userEvent.setup();
    const onStarted = vi.fn();
    const started = mapOut();
    const m = stubFetch({
      [LIST]: lists(
        [
          card("a1", { status: "accepted" }),
          card("mine", { origin: "manual", status: "accepted" }),
          card("ed", { status: "accepted", edited: true }),
        ],
        [card("s1c"), card("s2c"), card("other", { concept_id: "k2" })],
      ),
      [GENERATE]: () => json(started, 202),
    });
    render(
      <GenerateCardsButton
        setId="s1"
        conceptId="k1"
        disabled={false}
        onStarted={onStarted}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Regenerate cards/ }));
    const dialog = await screen.findByRole("alertdialog");
    expect(
      within(dialog).getByText(
        "This replaces 3 AI-generated cards you haven't edited (1 of them already accepted). Your own cards and cards you've edited are kept.",
      ),
    ).toBeInTheDocument();
    // Both statuses were listed, and nothing was posted before the confirm.
    const listed = m.mock.calls
      .map((c) => new URL((c[0] as Request).url).searchParams.get("status"))
      .sort();
    expect(listed).toEqual(["accepted", "suggested"]);
    expect(await posts(m)).toEqual([]);

    await user.click(within(dialog).getByRole("button", { name: "Generate" }));
    await waitFor(() => expect(onStarted).toHaveBeenCalledWith(started));
    expect(await posts(m)).toEqual([
      {
        path: "/study-sets/s1/flashcards/generate",
        body: JSON.stringify({ concept_id: "k1" }),
      },
    ]);
  });

  it("Cancel in the warning posts nothing", async () => {
    const user = userEvent.setup();
    const onStarted = vi.fn();
    const m = stubFetch({
      [LIST]: lists([], [card("s1c")]),
      [GENERATE]: () => json(mapOut(), 202),
    });
    render(
      <GenerateCardsButton
        setId="s1"
        conceptId={null}
        disabled={false}
        onStarted={onStarted}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: "Generate flashcards" }),
    );
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(await posts(m)).toEqual([]);
    expect(onStarted).not.toHaveBeenCalled();
  });

  it("generates without a dialog when there is nothing to replace", async () => {
    const user = userEvent.setup();
    const onStarted = vi.fn();
    const started = mapOut();
    const m = stubFetch({
      [LIST]: lists(
        [
          card("mine", { origin: "manual", status: "accepted" }),
          card("ed", { edited: true, status: "accepted" }),
        ],
        [],
      ),
      [GENERATE]: () => json(started, 202),
    });
    render(
      <GenerateCardsButton
        setId="s1"
        conceptId={null}
        disabled={false}
        onStarted={onStarted}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: "Generate flashcards" }),
    );
    await waitFor(() => expect(onStarted).toHaveBeenCalledWith(started));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(await posts(m)).toEqual([
      {
        path: "/study-sets/s1/flashcards/generate",
        body: JSON.stringify({ concept_id: null }),
      },
    ]);
  });

  it.each([
    [429, "rate_limited", "Too many card generations. Try again later."],
    [409, "conflict", "Flashcards are already being generated."],
  ])("a %i shows a toast with the error message", async (status, code, msg) => {
    const user = userEvent.setup();
    const onStarted = vi.fn();
    stubFetch({
      [LIST]: lists([], []),
      [GENERATE]: () => json(apiError(code, msg), status),
    });
    render(
      <GenerateCardsButton
        setId="s1"
        conceptId={null}
        disabled={false}
        onStarted={onStarted}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: "Generate flashcards" }),
    );
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(msg));
    expect(onStarted).not.toHaveBeenCalled();
  });

  it("a failed count lookup shows a toast and posts nothing", async () => {
    const user = userEvent.setup();
    const m = stubFetch({
      [LIST]: () => json(apiError("not_found", "Not found."), 404),
      [GENERATE]: () => json(mapOut(), 202),
    });
    render(
      <GenerateCardsButton
        setId="s1"
        conceptId={null}
        disabled={false}
        onStarted={vi.fn()}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: "Generate flashcards" }),
    );
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Not found."));
    expect(await posts(m)).toEqual([]);
  });
});
