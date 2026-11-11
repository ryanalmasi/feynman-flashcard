import { describe, expect, it } from "vitest";
import type { components } from "@/api/schema.gen";
import { regenerationCounts } from "./regenerate";

type Flashcard = components["schemas"]["FlashcardOut"];

const ts = "2026-01-01T00:00:00Z";
const card = (id: string, extra: Partial<Flashcard> = {}): Flashcard => ({
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

const cards: Flashcard[] = [
  card("g1"), // generated, suggested, k1
  card("g2", { status: "accepted" }), // generated, accepted, k1
  card("g3", { concept_id: "k2" }), // generated, suggested, other concept
  card("g4", { concept_id: "k2", status: "accepted" }), // accepted, other concept
  card("g5", { concept_id: null }), // generated, unlinked
  card("e1", { edited: true }), // edited: kept
  card("e2", { edited: true, status: "accepted" }), // edited, accepted: kept
  card("m1", { origin: "manual", status: "accepted" }), // manual: kept
  card("m2", { origin: "manual", status: "accepted", concept_id: null }),
];

describe("regenerationCounts", () => {
  it("counts unedited generated cards of every concept for the whole set", () => {
    expect(regenerationCounts(cards, null)).toEqual({
      replace: 5,
      accepted: 2,
    });
  });

  it("counts only the concept's unedited generated cards for a concept", () => {
    expect(regenerationCounts(cards, "k1")).toEqual({
      replace: 2,
      accepted: 1,
    });
    expect(regenerationCounts(cards, "k2")).toEqual({
      replace: 2,
      accepted: 1,
    });
  });

  it("never counts manual or edited cards", () => {
    const kept = cards.filter(
      (c) => c.origin === "manual" || c.edited === true,
    );
    expect(regenerationCounts(kept, null)).toEqual({ replace: 0, accepted: 0 });
    expect(regenerationCounts(kept, "k1")).toEqual({ replace: 0, accepted: 0 });
  });

  it("is zero for a concept with no cards and for an empty list", () => {
    expect(regenerationCounts(cards, "k9")).toEqual({
      replace: 0,
      accepted: 0,
    });
    expect(regenerationCounts([], null)).toEqual({ replace: 0, accepted: 0 });
  });
});
