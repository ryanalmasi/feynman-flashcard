"""Split document pages into prompt-sized chunks without splitting a page."""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    index: int
    page_start: int
    page_end: int
    text: str


def escape_page_text(text: str) -> str:
    return text.replace("<", "&lt;").replace(">", "&gt;")


def render_pages(pages: Sequence[tuple[int, str]]) -> str:
    return "\n".join(
        f'<page number="{number}">\n{escape_page_text(text)}\n</page>' for number, text in pages
    )


def chunk_pages(pages: Sequence[tuple[int, str]], budget: int) -> list[Chunk]:
    groups: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    size = 0
    for page in pages:
        length = len(page[1])
        if current and size + length > budget:
            groups.append(current)
            current, size = [], 0
        current.append(page)
        size += length
    if current:
        groups.append(current)
    return [
        Chunk(index=i, page_start=g[0][0], page_end=g[-1][0], text=render_pages(g))
        for i, g in enumerate(groups)
    ]
