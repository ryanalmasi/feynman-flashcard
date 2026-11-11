from typing import Any

from feynman_api.knowledge.clean import clean_extraction
from feynman_api.knowledge.schemas import (
    ChunkExtraction,
    ConceptDraft,
    ExtractedConcept,
    ExtractedKeyTerm,
)


def _c(**kw: Any) -> ExtractedConcept:
    base: dict[str, Any] = dict(
        title="T",
        explanation="E",
        importance="core",
        key_terms=[],
        misconceptions=[],
        source_pages=[],
    )
    base.update(kw)
    return ExtractedConcept(**base)


def _clean(*concepts: ExtractedConcept, start: int = 1, end: int = 10) -> list[ConceptDraft]:
    return clean_extraction(ChunkExtraction(concepts=list(concepts)), start, end)


def test_clean_clamps_and_drops() -> None:
    out = _clean(
        _c(title="x" * 130, source_pages=[0, 3, 3, 99]),
        _c(explanation="   "),
        _c(title=" "),
        start=2,
        end=5,
    )
    assert len(out) == 1
    assert len(out[0].title) == 120
    assert out[0].source_pages == [3]


def test_clean_dedupes_key_terms_case_insensitively() -> None:
    kts = [
        ExtractedKeyTerm(term="ATP", synonyms=["energy"]),
        ExtractedKeyTerm(term="atp", synonyms=["Energy", "adenosine"]),
        ExtractedKeyTerm(term="  ", synonyms=[]),
        ExtractedKeyTerm(term="NADH", synonyms=[]),
    ]
    (d,) = _clean(_c(key_terms=kts))
    assert d.key_terms == [
        {"term": "ATP", "synonyms": ["energy", "adenosine"]},
        {"term": "NADH", "synonyms": []},
    ]


def test_clean_caps_key_terms_at_ten() -> None:
    kts = [ExtractedKeyTerm(term=f"t{i}", synonyms=[]) for i in range(12)]
    (d,) = _clean(_c(key_terms=kts))
    assert [k["term"] for k in d.key_terms] == [f"t{i}" for i in range(10)]


def test_clean_dedupes_misconceptions_and_drops_empty() -> None:
    (d,) = _clean(_c(misconceptions=["m  1", "m 1", " ", "m2"]))
    assert d.misconceptions == ["m 1", "m2"]


def test_clean_caps_misconceptions_and_strips_nul() -> None:
    (d,) = _clean(
        _c(
            title="a\x00b",
            misconceptions=[f"m{i}" for i in range(8)],
            key_terms=[ExtractedKeyTerm(term="t\x00", synonyms=["s\x00", "", "S", *"abcdefg"])],
        )
    )
    assert d.title == "ab"
    assert d.misconceptions == [f"m{i}" for i in range(5)]
    assert d.key_terms[0]["term"] == "t"
    assert d.key_terms[0]["synonyms"] == ["s", "a", "b", "c", "d"]


def test_clean_sorts_and_caps_source_pages() -> None:
    (d,) = _clean(_c(source_pages=[5, 3]))
    assert d.source_pages == [3, 5]
    (d,) = _clean(_c(source_pages=list(range(200, 0, -1))), start=1, end=200)
    assert d.source_pages == list(range(1, 51))
