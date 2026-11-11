from collections.abc import Sequence
from typing import Any

from feynman_api.knowledge.limits import MERGE_SUMMARY_MAX
from feynman_api.knowledge.merge import (
    local_ids,
    merge_concepts,
    merge_listing,
    truncate_by_importance,
)
from feynman_api.knowledge.schemas import ConceptDraft, MergeGroup, MergeGroups


def _d(
    title: str,
    importance: Any = "core",
    terms: Sequence[tuple[str, list[str]]] = (),
    mis: Sequence[str] = (),
    pages: Sequence[int] = (),
    explanation: str | None = None,
) -> ConceptDraft:
    return ConceptDraft(
        title=title,
        explanation=explanation or f"{title} explained. More.",
        importance=importance,
        key_terms=[{"term": t, "synonyms": list(s)} for t, s in terms],
        misconceptions=list(mis),
        source_pages=list(pages),
    )


def _g(*groups: tuple[str, list[str]]) -> MergeGroups:
    return MergeGroups(groups=[MergeGroup(keep=k, merge=m) for k, m in groups])


def test_merge_groups_union_fields() -> None:
    chunks = [
        [_d("A", "detail", [("ATP", ["x"])], ["m1"], [3, 1])],
        [_d("B", "core", [("atp", ["y"]), ("NADH", [])], ["m1", "m2"], [2, 1])],
    ]
    (out,) = merge_concepts(chunks, _g(("c0-0", ["c1-0"])))
    assert out.title == "A" and out.explanation == "A explained. More."
    assert out.importance == "core"
    assert out.key_terms == [
        {"term": "ATP", "synonyms": ["x", "y"]},
        {"term": "NADH", "synonyms": []},
    ]
    assert out.misconceptions == ["m1", "m2"]
    assert out.source_pages == [1, 2, 3]


def test_merge_unknown_ids_ignored_and_first_group_wins() -> None:
    chunks = [[_d("A"), _d("B"), _d("C")], [_d("D"), _d("E")]]
    groups = _g(
        ("c0-0", ["c0-0", "zzz", "c0-1"]),  # self-ref and unknown ignored
        ("c0-2", ["c0-1", "c1-0"]),  # c0-1 already used: ignored; c1-0 merges
        ("c0-0", ["c1-1"]),  # keep already used: skipped, c1-1 standalone
    )
    out = merge_concepts(chunks, groups)
    assert [c.title for c in out] == ["A", "C", "E"]


def test_merged_concept_sits_at_keep_position() -> None:
    chunks = [[_d("A"), _d("B")], [_d("C")]]
    out = merge_concepts(chunks, _g(("c0-1", ["c0-0", "c1-0"])))
    assert [c.title for c in out] == ["B"]
    out = merge_concepts(chunks, _g(("c1-0", ["c0-0"])))
    assert [c.title for c in out] == ["B", "C"]


def test_merge_order_is_first_appearance() -> None:
    chunks = [[_d("A"), _d("B")], [_d("C"), _d("D")]]
    out = merge_concepts(chunks, _g(("c0-0", ["c1-1"])))
    assert [c.title for c in out] == ["A", "B", "C"]


def test_merge_caps_lists() -> None:
    a = _d("A", terms=[(f"a{i}", []) for i in range(8)], mis=[f"a{i}" for i in range(4)])
    b = _d("B", terms=[(f"b{i}", []) for i in range(8)], mis=[f"b{i}" for i in range(4)])
    (out,) = merge_concepts([[a], [b]], _g(("c0-0", ["c1-0"])))
    assert len(out.key_terms) == 10 and len(out.misconceptions) == 5


def test_truncation_prefers_core_then_supporting_keeps_order() -> None:
    kinds = ["detail", "supporting", "core"]
    concepts = [_d(f"n{i}", kinds[i % 3]) for i in range(120)]
    out = truncate_by_importance(concepts)
    assert len(out) == 100
    assert sum(c.importance == "core" for c in out) == 40
    titles = [int(c.title[1:]) for c in out]
    assert titles == sorted(titles)
    assert sum(c.importance == "supporting" for c in out) == 40
    assert sum(c.importance == "detail" for c in out) == 20


def test_no_merge_fallback_keeps_everything_truncated() -> None:
    chunks = [[_d(f"a{i}") for i in range(60)], [_d(f"b{i}") for i in range(60)]]
    out = merge_concepts(chunks, None)
    assert len(out) == 100
    assert [c.title for c in out[:3]] == ["a0", "a1", "a2"]
    assert len(merge_concepts([[_d("A")], [_d("B")]], None)) == 2


def test_merge_listing_format_and_cap() -> None:
    chunks = [[_d("A", explanation="First one. Second."), _d("B", explanation="x" * 500)]]
    lines = merge_listing(chunks).split("\n")
    assert lines[0] == "c0-0 | A | First one."
    assert len(lines[1]) == MERGE_SUMMARY_MAX
    assert [i for i, _ in local_ids(chunks)] == ["c0-0", "c0-1"]
