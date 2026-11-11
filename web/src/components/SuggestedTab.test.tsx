import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { afterEach, describe, expect, it, vi } from "vitest";
import SuggestedTab from "./SuggestedTab";
import type { components } from "@/api/schema.gen";
import { apiError, json, stubFetch } from "@/test/pageUtils";

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

type Flashcard = components["schemas"]["FlashcardOut"];
type Concept = components["schemas"]["ConceptOut"];

const ts = "2026-01-01T00:00:00Z";
const card = (
  id: string,
  front: string,
  extra: Partial<Flashcard> = {},
): Flashcard => ({
  id,
  study_set_id: "s1",
  concept_id: null,
  kind: "qa",
  front,
  back: `Back of ${front}`,
  origin: "generated",
  status: "suggested",
  edited: false,
  created_at: ts,
  updated_at: ts,
  ...extra,
});
const concept = (id: string, title: string, position: number): Concept => ({
  id,
  position,
  title,
  explanation: "E",
  importance: "core",
  key_terms: [],
  misconceptions: [],
  source_pages: [],
});
const concepts = [concept("k1", "Cells", 0), concept("k2", "Energy", 1)];
const cards = [
  card("c3", "Unlinked card"),
  card("c2", "Energy card", { concept_id: "k2" }),
  card("c1", "Cells card", { concept_id: "k1" }),
  card("c4", "Gone concept card", { concept_id: "k-deleted" }),
];

const requests = (m: ReturnType<typeof stubFetch>) =>
  Promise.all(
    m.mock.calls
      .map((c) => c[0] as Request)
      .filter((r) => r.method !== "GET")
      .map(async (r) => ({
        method: r.method,
        path: new URL(r.url).pathname,
        body: await r.clone().text(),
      })),
  );
const itemOf = (text: string) => screen.getByText(text).closest("li")!;

afterEach(() => {
  vi.unstubAllGlobals();
  vi.mocked(toast.error).mockClear();
});

describe("SuggestedTab", () => {
  it("shows the empty state", () => {
    stubFetch({});
    render(
      <SuggestedTab
        setId="s1"
        cards={[]}
        concepts={concepts}
        onChanged={vi.fn()}
      />,
    );
    expect(
      screen.getByText(
        "No suggested cards. Generate flashcards from the Knowledge Map tab.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accept all" })).toBeNull();
  });

  it("groups cards by concept in map order, unlinked last under Other", () => {
    stubFetch({});
    render(
      <SuggestedTab
        setId="s1"
        cards={cards}
        concepts={concepts}
        onChanged={vi.fn()}
      />,
    );
    const headings = screen
      .getAllByRole("heading", { level: 3 })
      .map((h) => h.textContent);
    expect(headings).toEqual(["Cells", "Energy", "Other"]);
    const other = screen
      .getByRole("heading", { name: "Other" })
      .closest("section")!;
    expect(within(other).getByText("Unlinked card")).toBeInTheDocument();
    expect(within(other).getByText("Gone concept card")).toBeInTheDocument();
    const cells = screen
      .getByRole("heading", { name: "Cells" })
      .closest("section")!;
    expect(within(cells).getByText("Cells card")).toBeInTheDocument();
    expect(within(cells).getByText("Back of Cells card")).toBeInTheDocument();
    expect(within(cells).getByText("AI")).toBeInTheDocument();
  });

  it("renders model text as plain text", () => {
    stubFetch({});
    render(
      <SuggestedTab
        setId="s1"
        cards={[card("c9", "<b>x</b>")]}
        concepts={[]}
        onChanged={vi.fn()}
      />,
    );
    expect(screen.getByText("<b>x</b>")).toBeInTheDocument();
  });

  it("Accept PATCHes status accepted and reloads", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    const m = stubFetch({
      "PATCH /flashcards/c1": () =>
        json(card("c1", "Cells card", { status: "accepted" }), 200),
    });
    render(
      <SuggestedTab
        setId="s1"
        cards={cards}
        concepts={concepts}
        onChanged={onChanged}
      />,
    );
    await user.click(
      within(itemOf("Cells card")).getByRole("button", { name: "Accept" }),
    );
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(await requests(m)).toEqual([
      {
        method: "PATCH",
        path: "/flashcards/c1",
        body: JSON.stringify({ status: "accepted" }),
      },
    ]);
  });

  it("Reject posts the one id and reloads", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    const m = stubFetch({
      "POST /study-sets/s1/suggested-cards/reject": () =>
        json({ rejected: 1 }, 200),
    });
    render(
      <SuggestedTab
        setId="s1"
        cards={cards}
        concepts={concepts}
        onChanged={onChanged}
      />,
    );
    await user.click(
      within(itemOf("Energy card")).getByRole("button", { name: "Reject" }),
    );
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(await requests(m)).toEqual([
      {
        method: "POST",
        path: "/study-sets/s1/suggested-cards/reject",
        body: JSON.stringify({ card_ids: ["c2"] }),
      },
    ]);
  });

  it("Accept all confirms, posts card_ids null and reloads", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    const m = stubFetch({
      "POST /study-sets/s1/suggested-cards/accept": () =>
        json({ accepted: 4 }, 200),
    });
    render(
      <SuggestedTab
        setId="s1"
        cards={cards}
        concepts={concepts}
        onChanged={onChanged}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Accept all" }));
    const dialog = screen.getByRole("alertdialog");
    expect(
      within(dialog).getByText("Accept all suggested cards?"),
    ).toBeInTheDocument();
    expect(await requests(m)).toEqual([]);
    await user.click(
      within(dialog).getByRole("button", { name: "Accept all" }),
    );
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(await requests(m)).toEqual([
      {
        method: "POST",
        path: "/study-sets/s1/suggested-cards/accept",
        body: JSON.stringify({ card_ids: null }),
      },
    ]);
  });

  it("Reject all confirms, posts card_ids null and reloads", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    const m = stubFetch({
      "POST /study-sets/s1/suggested-cards/reject": () =>
        json({ rejected: 4 }, 200),
    });
    render(
      <SuggestedTab
        setId="s1"
        cards={cards}
        concepts={concepts}
        onChanged={onChanged}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Reject all" }));
    const dialog = screen.getByRole("alertdialog");
    expect(
      within(dialog).getByText("Reject all suggested cards?"),
    ).toBeInTheDocument();
    await user.click(
      within(dialog).getByRole("button", { name: "Reject all" }),
    );
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(await requests(m)).toEqual([
      {
        method: "POST",
        path: "/study-sets/s1/suggested-cards/reject",
        body: JSON.stringify({ card_ids: null }),
      },
    ]);
  });

  it("Edit PATCHes front and back and reloads", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    const m = stubFetch({
      "PATCH /flashcards/c1": () => json(card("c1", "New front"), 200),
    });
    render(
      <SuggestedTab
        setId="s1"
        cards={cards}
        concepts={concepts}
        onChanged={onChanged}
      />,
    );
    await user.click(
      within(itemOf("Cells card")).getByRole("button", { name: "Edit" }),
    );
    const front = screen.getByLabelText("Front");
    expect(front).toHaveValue("Cells card");
    await user.clear(front);
    await user.type(front, "New front");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(await requests(m)).toEqual([
      {
        method: "PATCH",
        path: "/flashcards/c1",
        body: JSON.stringify({
          kind: "qa",
          front: "New front",
          back: "Back of Cells card",
        }),
      },
    ]);
  });

  it("Edit shows the server's 422 detail message in the dialog", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    stubFetch({
      "PATCH /flashcards/c1": () =>
        json(
          {
            error: {
              code: "validation_error",
              message: "The request is invalid.",
              details: [
                { loc: ["body", "front"], msg: "Use exactly one blank." },
              ],
            },
          },
          422,
        ),
    });
    render(
      <SuggestedTab
        setId="s1"
        cards={cards}
        concepts={concepts}
        onChanged={onChanged}
      />,
    );
    await user.click(
      within(itemOf("Cells card")).getByRole("button", { name: "Edit" }),
    );
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Use exactly one blank.",
    );
    expect(onChanged).not.toHaveBeenCalled();
  });

  it("a failed Accept shows a toast and still reloads", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    stubFetch({
      "PATCH /flashcards/c1": () =>
        json(apiError("not_found", "Not found."), 404),
    });
    render(
      <SuggestedTab
        setId="s1"
        cards={cards}
        concepts={concepts}
        onChanged={onChanged}
      />,
    );
    await user.click(
      within(itemOf("Cells card")).getByRole("button", { name: "Accept" }),
    );
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Not found."));
    expect(onChanged).toHaveBeenCalledTimes(1);
  });
});
