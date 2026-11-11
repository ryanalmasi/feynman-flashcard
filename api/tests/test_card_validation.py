from uuid import UUID, uuid4

from feynman_api.knowledge.cards import CardDraft, cap_cards, validate_cards
from feynman_api.knowledge.schemas import CardBatch, ConceptCards, GeneratedCard


def qa(front: str = "Q?", back: str = "A.") -> GeneratedCard:
    return GeneratedCard(kind="qa", front=front, back=back)


def cloze(front: str = "It is {{x}} here", back: str = "") -> GeneratedCard:
    return GeneratedCard(kind="cloze", front=front, back=back)


def batch(**groups: list[GeneratedCard]) -> CardBatch:
    return CardBatch(concepts=[ConceptCards(concept_id=k, cards=v) for k, v in groups.items()])


def test_validate_cards_counts_by_importance() -> None:
    c1, c2 = uuid4(), uuid4()
    scope = {"k1": (c1, 3), "k2": (c2, 1)}
    raw = batch(
        k1=[qa(f"q{i}") for i in range(5)],
        k2=[qa("a"), qa("b")],
    )
    kept, dropped = validate_cards(raw, scope)
    assert [(d.concept_id, d.front) for d in kept] == [
        (c1, "q0"),
        (c1, "q1"),
        (c1, "q2"),
        (c2, "a"),
    ]
    assert dropped == 3


def test_validate_cards_groups_in_scope_order() -> None:
    c1, c2 = uuid4(), uuid4()
    scope = {"k1": (c1, 2), "k2": (c2, 2)}
    raw = batch(k2=[qa("b")], k1=[qa("a")])
    kept, dropped = validate_cards(raw, scope)
    assert [d.concept_id for d in kept] == [c1, c2]
    assert dropped == 0


def test_validate_cards_one_cloze_per_concept() -> None:
    c1 = uuid4()
    raw = batch(k1=[cloze("A {{one}} x"), cloze("B {{two}} x"), qa("q1"), qa("q2"), qa("q3")])
    kept, dropped = validate_cards(raw, {"k1": (c1, 3)})
    # the extra cloze is dropped before trimming, so it does not use a slot
    assert [(d.kind, d.front) for d in kept] == [
        ("cloze", "A {{one}} x"),
        ("qa", "q1"),
        ("qa", "q2"),
    ]
    assert dropped == 2  # the extra cloze and the third qa
    assert all(isinstance(d, CardDraft) for d in kept)


def test_cloze_limit_is_per_concept() -> None:
    c1, c2 = uuid4(), uuid4()
    raw = batch(k1=[cloze()], k2=[cloze()])
    kept, dropped = validate_cards(raw, {"k1": (c1, 3), "k2": (c2, 3)})
    assert len(kept) == 2
    assert dropped == 0


def test_validate_cards_drops_invalid_and_unknown() -> None:
    c1 = uuid4()
    raw = batch(
        k1=[
            qa("ok1", "fine"),
            qa("blank back", "   "),
            cloze("no blank here"),
            qa("x" * 501, "a"),
            qa("nul\x00 front", "a"),
            qa("q", "nul\x00 back"),
            qa("   ", "a"),
            qa("ok2", "fine"),
        ],
        k9=[qa("unknown")],
    )
    kept, dropped = validate_cards(raw, {"k1": (c1, 5)})
    assert [d.front for d in kept] == ["ok1", "ok2"]
    assert dropped == 7  # 9 raw cards, 2 kept


def test_validate_cards_length_boundaries() -> None:
    c1 = uuid4()
    raw = batch(k1=[qa("x" * 500, "y" * 2000), qa("x" * 500, "y" * 2001)])
    kept, dropped = validate_cards(raw, {"k1": (c1, 5)})
    assert len(kept) == 1
    assert dropped == 1


def test_cloze_back_may_be_empty_but_nul_is_invalid() -> None:
    c1, c2 = uuid4(), uuid4()
    raw = batch(
        k1=[cloze("A {{x}} b", "")],
        k2=[cloze("A {{x}} b", "n\x00")],
    )
    kept, dropped = validate_cards(raw, {"k1": (c1, 1), "k2": (c2, 1)})
    assert [d.concept_id for d in kept] == [c1]
    assert dropped == 1


def test_invalid_cloze_does_not_use_the_cloze_slot() -> None:
    c1 = uuid4()
    raw = batch(k1=[cloze("broken"), cloze("Good {{one}} here")])
    kept, dropped = validate_cards(raw, {"k1": (c1, 3)})
    assert [d.front for d in kept] == ["Good {{one}} here"]
    assert dropped == 1


def test_cap_cards() -> None:
    c: UUID = uuid4()
    drafts = [CardDraft(concept_id=c, kind="qa", front=f"q{i}", back="a") for i in range(5)]
    assert [d.front for d in cap_cards(drafts, 3)] == ["q0", "q1", "q2"]
    assert cap_cards(drafts, 10) == drafts
    assert cap_cards(drafts, 0) == []
    assert cap_cards(drafts, -2) == []
