"""Pure validation of model-generated cards (design 7.7 step 4)."""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from feynman_api.knowledge.cloze import cloze_error
from feynman_api.knowledge.limits import BACK_MAX, FRONT_MAX
from feynman_api.knowledge.schemas import CardBatch, GeneratedCard


@dataclass(frozen=True)
class CardDraft:
    concept_id: UUID
    kind: str
    front: str
    back: str


def _valid(card: GeneratedCard) -> bool:
    if "\x00" in card.front or "\x00" in card.back:
        return False
    if not card.front.strip() or len(card.front) > FRONT_MAX or len(card.back) > BACK_MAX:
        return False
    if card.kind == "cloze":
        return cloze_error(card.front) is None
    return bool(card.back.strip())


def validate_cards(
    raw: CardBatch, scope: Mapping[str, tuple[UUID, int]]
) -> tuple[list[CardDraft], int]:
    """Keep valid cards for in-scope concepts, grouped in scope order.

    Returns the kept cards and the number dropped (invalid, unknown concept,
    extra cloze, or beyond the concept's required count).
    """
    total = 0
    by_local: dict[str, list[GeneratedCard]] = {}
    for group in raw.concepts:
        total += len(group.cards)
        if group.concept_id in scope:
            by_local.setdefault(group.concept_id, []).extend(group.cards)

    kept: list[CardDraft] = []
    for local_id, (concept_id, required) in scope.items():
        has_cloze = False
        chosen: list[CardDraft] = []
        for card in by_local.get(local_id, []):
            if not _valid(card):
                continue
            if card.kind == "cloze":
                if has_cloze:
                    continue
                has_cloze = True
            chosen.append(CardDraft(concept_id, card.kind, card.front, card.back))
        kept.extend(chosen[: max(required, 0)])
    return kept, total - len(kept)


def cap_cards(drafts: list[CardDraft], room: int) -> list[CardDraft]:
    """The first `room` cards; the caller orders them by concept position."""
    return drafts[: max(room, 0)]
