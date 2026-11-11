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
    ] + [ExtractedKeyTerm(term=f"t{i}", synonyms=[]) for i in range(11)]
    (d,) = _clean(_c(key_terms=kts))
    assert len(d.key_terms) == 10
    assert d.key_terms[0] == {"term": "ATP", "synonyms": ["energy", "adenosine"]}


def test_clean_caps_misconceptions_and_strips_nul() -> None:
    (d,) = _clean(
        _c(
            title="a\x00b",
            misconceptions=["m  1", "m 1", " ", *[f"m{i}" for i in range(2, 9)]],
            key_terms=[ExtractedKeyTerm(term="t\x00", synonyms=["s\x00", "", "S", *"abcdefg"])],
        )
    )
    assert d.title == "ab"
    assert len(d.misconceptions) == 5 and d.misconceptions[0] == "m 1"
    assert d.key_terms[0]["term"] == "t"
    assert d.key_terms[0]["synonyms"][0] == "s" and len(d.key_terms[0]["synonyms"]) == 5
