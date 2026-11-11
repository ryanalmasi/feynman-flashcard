const BLANK = /\{\{([\s\S]*?)\}\}/;

/** Splits a cloze front around its `{{answer}}`. Mirrors the server's
 * `knowledge/cloze.cloze_parts`; the server is the validator, this only renders. */
export function parseCloze(
  front: string,
): { before: string; answer: string; after: string } | null {
  const m = BLANK.exec(front);
  if (!m) return null;
  return {
    before: front.slice(0, m.index),
    answer: m[1],
    after: front.slice(m.index + m[0].length),
  };
}
