# 0021. Generated flashcards: on request, by importance, Q/A plus cloze, draft tray, safe regeneration

- **Status:** Accepted (owner, 2026-11-10)

## Context
Phase 2b, milestone M5 (ADR 0012). Cards are derived from Knowledge Map concepts (ADR 0020) by Haiku 5.5 (ADR 0019). The 2a cards (ADR 0018) are plain-text `front` (1–500) and `back` (1–2000), `origin` `manual|generated`, with no `concept_id` yet.

## Options (each was presented to the owner with a recommendation)
1. **Trigger:** **the student clicks "Generate flashcards" (chosen)** / automatic when the map is ready.
2. **Count and style:** by importance, Q/A / fixed 2, Q/A / **by importance, Q/A plus cloze (chosen; the owner's choice over the recommendation)**.
3. **Regeneration:** **replace unedited generated cards, with a warning popup first (chosen; the owner added the popup)** / append only.
4. **Entry into the set:** straight in with a badge / **a draft tray, then accept (chosen; the owner's choice over the recommendation)**.
5. **Cloze format:** **one `{{blank}}` per card (chosen)** / several blanks.
6. **Cloze mix:** **at most 1 cloze card per concept (chosen)** / the model decides.
7. **Manual cloze:** **yes, through a Q/A | Cloze toggle in the editor (chosen)** / generator only.

## Decision
**Schema changes to `flashcards`**
- `concept_id` (nullable FK to `concepts`, `ON DELETE SET NULL`).
- `kind` `qa|cloze` (default `qa`).
- `status` `suggested|accepted` (default `accepted`; manual cards are always `accepted`).
- `edited` boolean (default false; set true when the student changes `front` or `back` of a generated card).
- **Cloze rules:**
  - `front` contains **exactly one** well-formed `{{answer}}` span; the API validates it and returns a 422 otherwise.
  - `back` is an optional note, so `back` may be empty for cloze cards only.
  - The 2b design states the exact constraints.

**Generation**
- **On request:** "Generate flashcards" for the whole set, and "Regenerate" for one concept. Each is a `generate_flashcards` job (Haiku 5.5) that counts against the 20 runs per 24 h limit (ADR 0020).
- **Count by importance:**
  - core concepts get 3 cards, supporting 2, detail 1
  - **at most 1 cloze card per concept** (targeting a key term); the rest are Q/A with varied question types (definition, why/how, application, common mistake)
  - **at most 150 generated cards per set**
- Cards are grounded in the concept's fields and its source pages' text. PDF text is untrusted input, the same as in ADR 0020.

**Draft tray and acceptance**
- Generated cards arrive as `status = suggested` in a **Suggested** tab.
- The student accepts or rejects each card, or all of them, and can edit before accepting.
- Review, the card list and card counts include **only accepted cards**. Generated cards keep an "AI" badge after acceptance (AI disclosure, ADR 0019).

**Regeneration**
- Scope: one concept or the whole set.
- It **replaces generated cards in that scope with `edited = false`**, whether suggested or accepted. Manual cards and edited generated cards are always kept. New cards arrive as suggested.
- **A confirmation dialog first** states what will happen: "This replaces N AI-generated cards you haven't edited (M of them already accepted). Your own cards and cards you've edited are kept."

**Manual cards:** the card editor gets a **Q/A | Cloze** toggle with a short `{{ }}` hint. Cloze cards created by hand are `origin = manual`, `status = accepted`.

**Review:** for a cloze card, the front shows the sentence with the blank as `_____`. Flipping shows the full sentence with the answer emphasised, plus the note if there is one. Q/A review is unchanged.

**Map changes:** deleting a concept, or rebuilding the map, keeps its cards and sets their `concept_id` to NULL.

## Consequences
- The flashcard schema gains four columns. The review screen and card editor change for cloze.
- The card list API needs a status filter (accepted vs. suggested).
- Card limits and costs are bounded (150 per set; Haiku pricing; per-user limit).
- Multi-blank cloze, other card types, and spaced repetition are later.
