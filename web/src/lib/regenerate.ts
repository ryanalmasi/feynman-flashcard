import type { components } from "@/api/schema.gen";

type Flashcard = components["schemas"]["FlashcardOut"];

export type RegenerationCounts = { replace: number; accepted: number };

/**
 * How many cards a (re)generation would replace (design §7.8): the unedited
 * AI-generated cards in scope, suggested or accepted. `cards` holds both
 * statuses; `conceptId` null means the whole set. Manual and edited cards are
 * always kept, so they never count.
 */
export function regenerationCounts(
  cards: Flashcard[],
  conceptId: string | null,
): RegenerationCounts {
  const replaced = cards.filter(
    (c) =>
      c.origin === "generated" &&
      !c.edited &&
      (conceptId === null || c.concept_id === conceptId),
  );
  return {
    replace: replaced.length,
    accepted: replaced.filter((c) => c.status === "accepted").length,
  };
}
