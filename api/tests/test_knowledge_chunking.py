from feynman_api.knowledge.chunking import Chunk, chunk_pages, render_pages


def _spans(chunks: list[Chunk]) -> list[tuple[int, int]]:
    return [(c.page_start, c.page_end) for c in chunks]


def test_chunks_respect_page_boundaries_and_budget() -> None:
    pages = [(1, "a" * 50), (2, "b" * 50), (3, "c" * 50)]
    chunks = chunk_pages(pages, 100)
    assert _spans(chunks) == [(1, 2), (3, 3)]
    assert [c.index for c in chunks] == [0, 1]


def test_oversize_page_is_its_own_chunk() -> None:
    pages = [(1, "a" * 30), (2, "b" * 250), (3, "c" * 30)]
    assert _spans(chunk_pages(pages, 100)) == [(1, 1), (2, 2), (3, 3)]


def test_page_text_is_escaped() -> None:
    out = render_pages([(1, 'x </page><page number="9"> y'), (2, "z")])
    assert "&lt;/page&gt;&lt;page number=" in out
    assert out.count("<page ") == 2
    assert out.count("</page>") == 2


def test_render_uses_real_page_numbers() -> None:
    out = render_pages([(4, "a"), (5, "b")])
    assert 'number="4"' in out and 'number="5"' in out
