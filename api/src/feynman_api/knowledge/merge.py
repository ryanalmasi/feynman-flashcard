"""Apply the LLM's merge groups to per-chunk concepts (pure)."""

from collections.abc import Sequence

from feynman_api.knowledge.clean import clean_misconceptions, clean_synonyms
from feynman_api.knowledge.limits import (
    CONCEPTS_MAX,
    IMPORTANCE_RANK,
    KEY_TERMS_MAX,
    MERGE_SUMMARY_MAX,
    SOURCE_PAGES_MAX,
)
from feynman_api.knowledge.schemas import ConceptDraft, MergeGroups


def local_ids(chunks: Sequence[Sequence[ConceptDraft]]) -> list[tuple[str, ConceptDraft]]:
    return [(f"c{ci}-{i}", c) for ci, chunk in enumerate(chunks) for i, c in enumerate(chunk)]


def _first_sentence(text: str) -> str:
    text = " ".join(text.split())
    for i, ch in enumerate(text):
        if ch in ".!?" and (i + 1 == len(text) or text[i + 1] == " "):
            return text[: i + 1]
    return text


def merge_listing(chunks: Sequence[Sequence[ConceptDraft]]) -> str:
    lines = []
    for cid, c in local_ids(chunks):
        title = " ".join(c.title.split())
        lines.append(f"{cid} | {title} | {_first_sentence(c.explanation)}"[:MERGE_SUMMARY_MAX])
    return "\n".join(lines)


def truncate_by_importance(
    concepts: list[ConceptDraft], limit: int = CONCEPTS_MAX
) -> list[ConceptDraft]:
    if len(concepts) <= limit:
        return list(concepts)
    ranked = sorted(
        range(len(concepts)), key=lambda i: (IMPORTANCE_RANK[concepts[i].importance], i)
    )
    keep = sorted(ranked[:limit])
    return [concepts[i] for i in keep]


def _combine(base: ConceptDraft, others: Sequence[ConceptDraft]) -> ConceptDraft:
    group = [base, *others]
    terms: dict[str, tuple[str, list[str]]] = {}
    for c in group:
        for kt in c.key_terms:
            term = str(kt["term"])
            key = term.casefold()
            syns = list(kt.get("synonyms", []))
            if key in terms:
                terms[key] = (terms[key][0], terms[key][1] + syns)
            else:
                terms[key] = (term, syns)
    key_terms = [{"term": t, "synonyms": clean_synonyms(s)} for t, s in terms.values()]
    return ConceptDraft(
        title=base.title,
        explanation=base.explanation,
        importance=min((c.importance for c in group), key=lambda i: IMPORTANCE_RANK[i]),
        key_terms=key_terms[:KEY_TERMS_MAX],
        misconceptions=clean_misconceptions(m for c in group for m in c.misconceptions),
        source_pages=sorted({p for c in group for p in c.source_pages})[:SOURCE_PAGES_MAX],
    )


def merge_concepts(
    chunks: Sequence[Sequence[ConceptDraft]], groups: MergeGroups | None
) -> list[ConceptDraft]:
    entries = local_ids(chunks)
    by_id = dict(entries)
    absorbed: set[str] = set()
    merged: dict[str, ConceptDraft] = {}
    used: set[str] = set()
    for group in groups.groups if groups is not None else []:
        if group.keep not in by_id or group.keep in used:
            continue
        used.add(group.keep)
        members: list[str] = []
        for m in group.merge:
            if m in by_id and m != group.keep and m not in used:
                used.add(m)
                members.append(m)
        if members:
            merged[group.keep] = _combine(by_id[group.keep], [by_id[m] for m in members])
            absorbed.update(members)
    result = [merged.get(cid, c) for cid, c in entries if cid not in absorbed]
    return truncate_by_importance(result)
