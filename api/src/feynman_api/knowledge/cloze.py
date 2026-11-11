"""Cloze front rules: exactly one `{{answer}}` and no other braces."""

import re

from feynman_api.knowledge.limits import CLOZE_ANSWER_MAX

_BLANK = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)
_LINE_BREAKS = "\n\r\x85\x0b\x0c\x1c\x1d\x1e" + chr(0x2028) + chr(0x2029)


def cloze_error(front: str) -> str | None:
    """None when the front is a valid cloze, else a fixed user-facing message."""
    matches = list(_BLANK.finditer(front))
    if len(matches) != 1:
        return "Cloze cards need exactly one {{answer}}."
    match = matches[0]
    outside = front[: match.start()] + front[match.end() :]
    if "{" in outside or "}" in outside:
        return "Unbalanced or nested braces."
    answer = match.group(1)
    if not answer.strip() or len(answer) > CLOZE_ANSWER_MAX:
        return "The hidden answer must be 1-100 characters."
    if "{" in answer or "}" in answer or any(c in answer for c in _LINE_BREAKS):
        return "The hidden answer can't contain braces or line breaks."
    if not outside.strip():
        return "Add some text around the hidden answer."
    return None


def cloze_parts(front: str) -> tuple[str, str, str]:
    """(before, answer, after) of a front that passed `cloze_error`."""
    match = _BLANK.search(front)
    if match is None:
        raise ValueError("not a cloze front")
    return front[: match.start()], match.group(1), front[match.end() :]
