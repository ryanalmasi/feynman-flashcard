export type KeyTermValue = { term: string; synonyms: string[] };
export type Importance = "core" | "supporting" | "detail";

export const IMPORTANCE_LABELS: Record<Importance, string> = {
  core: "Core",
  supporting: "Supporting",
  detail: "Detail",
};

/** "p. 4–7", "p. 4, 9", "p. 3, 5–6"; "" when there are no pages. */
export function formatPages(pages: number[]): string {
  const sorted = [...new Set(pages)].sort((a, b) => a - b);
  if (sorted.length === 0) return "";
  const parts: string[] = [];
  let start = sorted[0];
  let prev = start;
  for (const p of [...sorted.slice(1), Number.NaN]) {
    if (p === prev + 1) {
      prev = p;
      continue;
    }
    parts.push(start === prev ? `${start}` : `${start}–${prev}`);
    start = p;
    prev = p;
  }
  return `p. ${parts.join(", ")}`;
}

/** A comma list of positive integers, sorted and de-duplicated; null when invalid. */
export function parsePages(text: string): number[] | null {
  if (!text.trim()) return [];
  const pages: number[] = [];
  for (const part of text.split(",")) {
    const t = part.trim();
    if (!/^\d+$/.test(t)) return null;
    const n = Number(t);
    if (!Number.isSafeInteger(n) || n < 1) return null;
    pages.push(n);
  }
  return [...new Set(pages)].sort((a, b) => a - b);
}

/** Trimmed, non-blank lines. */
export function parseLines(text: string): string[] {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

/** One term per line, `term: synonym, synonym`; blank lines are skipped. */
export function parseKeyTerms(text: string): KeyTermValue[] {
  return parseLines(text).flatMap((line) => {
    const colon = line.indexOf(":");
    const term = (colon === -1 ? line : line.slice(0, colon)).trim();
    if (!term) return [];
    const synonyms =
      colon === -1
        ? []
        : line
            .slice(colon + 1)
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
    return [{ term, synonyms }];
  });
}

export function formatKeyTerms(terms: KeyTermValue[]): string {
  return terms
    .map((t) =>
      t.synonyms.length ? `${t.term}: ${t.synonyms.join(", ")}` : t.term,
    )
    .join("\n");
}
