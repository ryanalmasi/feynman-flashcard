import pytest

from feynman_api.knowledge.cloze import cloze_error, cloze_parts


@pytest.mark.parametrize(
    "front",
    [
        "The capital of France is {{Paris}}.",
        "{{ATP}} stores energy",
        "Water boils at {{100 °C}} at sea level",
        "x {{" + "a" * 100 + "}}",
    ],
)
def test_valid_cloze(front: str) -> None:
    assert cloze_error(front) is None


@pytest.mark.parametrize(
    "front, msg",
    [
        ("No blank here", "Cloze cards need exactly one {{answer}}."),
        ("{{a}} and {{b}}", "Cloze cards need exactly one {{answer}}."),
        ("{{}} empty", "The hidden answer must be 1-100 characters."),
        ("x {{" + "a" * 101 + "}}", "The hidden answer must be 1-100 characters."),
        ("x {{a\nb}}", "The hidden answer can't contain braces or line breaks."),
        ("x {{a\rb}}", "The hidden answer can't contain braces or line breaks."),
        ("x {{a{b}}", "The hidden answer can't contain braces or line breaks."),
        ("x {{a}b}}", "The hidden answer can't contain braces or line breaks."),
        ("x {{{a}}}", "Unbalanced or nested braces."),
        ("x {{a}} }", "Unbalanced or nested braces."),
        ("x {a} {{b}}", "Unbalanced or nested braces."),
        ("  {{only}}  ", "Add some text around the hidden answer."),
    ],
)
def test_invalid_cloze(front: str, msg: str) -> None:
    assert cloze_error(front) == msg


def test_cloze_parts() -> None:
    assert cloze_parts("The capital of France is {{Paris}}.") == (
        "The capital of France is ",
        "Paris",
        ".",
    )
    assert cloze_parts("{{ATP}} stores energy") == ("", "ATP", " stores energy")
