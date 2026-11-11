import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import ReviewPage from "./ReviewPage";
import { json, renderAt, session, stubFetch } from "@/test/pageUtils";

const routes = (
  <Routes>
    <Route path="/sets/:setId/review" element={<ReviewPage />} />
    <Route path="/sets/:setId" element={<h1>Detail</h1>} />
  </Routes>
);
const ts = "2026-01-01T00:00:00Z";
const card = (n: number) => ({
  id: `c${n}`,
  study_set_id: "s1",
  kind: "qa",
  front: `F${n}`,
  back: `B${n}`,
  origin: "manual",
  created_at: ts,
  updated_at: ts,
});
const stubCards = (cards: unknown[]) =>
  stubFetch({
    "GET /auth/session": () => json(session, 200),
    "GET /study-sets/s1/flashcards": () => json(cards, 200),
  });

afterEach(() => vi.unstubAllGlobals());

describe("ReviewPage", () => {
  it("shows Card 1 of 3 and the front; Space flips to back; ArrowRight goes to card 2 front", async () => {
    const user = userEvent.setup();
    stubCards([card(1), card(2), card(3)]);
    renderAt("/sets/s1/review", routes);
    expect(await screen.findByText("Card 1 of 3")).toBeInTheDocument();
    expect(screen.getByText("F1")).toBeInTheDocument();
    await user.keyboard(" ");
    expect(screen.getByText("B1")).toBeInTheDocument();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByText("Card 2 of 3")).toBeInTheDocument();
    expect(screen.getByText("F2")).toBeInTheDocument();
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByText("F1")).toBeInTheDocument();
  });

  it("flips on click", async () => {
    const user = userEvent.setup();
    stubCards([card(1)]);
    renderAt("/sets/s1/review", routes);
    await user.click(await screen.findByText("F1"));
    expect(screen.getByText("B1")).toBeInTheDocument();
  });

  it("Previous disabled on first card, Next disabled on last", async () => {
    const user = userEvent.setup();
    stubCards([card(1), card(2)]);
    renderAt("/sets/s1/review", routes);
    await screen.findByText("Card 1 of 2");
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Card 2 of 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByText("Card 2 of 2")).toBeInTheDocument();
  });

  it("shuffle with a seeded random reorders and restarts at Card 1", async () => {
    const user = userEvent.setup();
    stubCards([card(1), card(2), card(3)]);
    vi.spyOn(Math, "random").mockReturnValue(0);
    renderAt("/sets/s1/review", routes);
    await screen.findByText("Card 1 of 3");
    await user.keyboard("{ArrowRight}");
    const toggle = screen.getByRole("button", { name: "Shuffle" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Card 1 of 3")).toBeInTheDocument();
    expect(screen.getByText("F2")).toBeInTheDocument();
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByText("Card 1 of 3")).toBeInTheDocument();
    expect(screen.getByText("F1")).toBeInTheDocument();
    vi.restoreAllMocks();
  });

  it("empty set shows message and link back", async () => {
    stubCards([]);
    renderAt("/sets/s1/review", routes);
    expect(
      await screen.findByText("This set has no cards yet."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back/i })).toHaveAttribute(
      "href",
      "/sets/s1",
    );
  });

  it("requests only accepted cards", async () => {
    const m = stubCards([card(1)]);
    renderAt("/sets/s1/review", routes);
    await screen.findByText("Card 1 of 1");
    const urls = m.mock.calls.map((c) => (c[0] as Request).url);
    const list = urls.filter((u) => u.includes("/flashcards"));
    expect(list).toHaveLength(1);
    expect(list[0]).not.toContain("status=suggested");
    expect(list[0]).not.toContain("status=all");
  });

  it("ArrowRight advances while the card button has focus", async () => {
    const user = userEvent.setup();
    stubCards([card(1), card(2)]);
    renderAt("/sets/s1/review", routes);
    const flip = await screen.findByRole("button", { name: "Show answer" });
    await user.click(flip);
    expect(flip).toHaveFocus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByText("Card 2 of 2")).toBeInTheDocument();
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByText("Card 1 of 2")).toBeInTheDocument();
  });

  it("renders cloze cards hidden then revealed with the note", async () => {
    const user = userEvent.setup();
    stubCards([
      {
        ...card(1),
        kind: "cloze",
        front: "Capital is {{Paris}}.",
        back: "A note",
      },
    ]);
    renderAt("/sets/s1/review", routes);
    const flip = await screen.findByRole("button", { name: "Show answer" });
    expect(flip).toHaveTextContent("Capital is _____.");
    await user.click(flip);
    const back = screen.getByRole("button", { name: "Show question" });
    expect(back).toHaveTextContent("Capital is Paris.");
    expect(back).toHaveTextContent("A note");
    expect(screen.getByText("Paris").tagName).toBe("STRONG");
  });

  it("the flip control is a real button whose name and aria-pressed track the side", async () => {
    const user = userEvent.setup();
    stubCards([card(1)]);
    renderAt("/sets/s1/review", routes);
    const flip = await screen.findByRole("button", { name: "Show answer" });
    expect(flip.tagName).toBe("BUTTON");
    expect(flip).toHaveAttribute("type", "button");
    expect(flip).toHaveAttribute("aria-pressed", "false");
    await user.click(flip);
    const again = screen.getByRole("button", { name: "Show question" });
    expect(again).toHaveAttribute("aria-pressed", "true");
  });

  it("Enter on the focused card button flips exactly once", async () => {
    const user = userEvent.setup();
    stubCards([card(1)]);
    renderAt("/sets/s1/review", routes);
    const flip = await screen.findByRole("button", { name: "Show answer" });
    flip.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByText("B1")).toBeInTheDocument();
  });

  it("Space flips exactly once, on the button and off it", async () => {
    const user = userEvent.setup();
    stubCards([card(1)]);
    renderAt("/sets/s1/review", routes);
    const flip = await screen.findByRole("button", { name: "Show answer" });
    flip.focus();
    await user.keyboard(" ");
    expect(screen.getByText("B1")).toBeInTheDocument();
    (document.activeElement as HTMLElement).blur();
    await user.keyboard(" ");
    expect(screen.getByText("F1")).toBeInTheDocument();
  });

  it("Ctrl+ArrowRight does not advance", async () => {
    const user = userEvent.setup();
    stubCards([card(1), card(2)]);
    renderAt("/sets/s1/review", routes);
    await screen.findByText("Card 1 of 2");
    await user.keyboard("{Control>}{ArrowRight}{/Control}");
    expect(screen.getByText("Card 1 of 2")).toBeInTheDocument();
  });
});
