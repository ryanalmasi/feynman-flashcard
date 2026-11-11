import { describe, expect, it } from "vitest";
import {
  formatKeyTerms,
  formatPages,
  parseKeyTerms,
  parseLines,
  parsePages,
} from "./conceptForm";

describe("formatPages", () => {
  it("formats ranges and lists", () => {
    expect(formatPages([4, 5, 6, 7])).toBe("p. 4–7");
    expect(formatPages([4, 9])).toBe("p. 4, 9");
    expect(formatPages([3, 5, 6])).toBe("p. 3, 5–6");
    expect(formatPages([2])).toBe("p. 2");
    expect(formatPages([])).toBe("");
  });

  it("sorts and de-duplicates its input", () => {
    expect(formatPages([7, 4, 5, 5, 6])).toBe("p. 4–7");
  });
});

describe("parsePages", () => {
  it("parses a comma list of positive integers", () => {
    expect(parsePages("3, 4, 7")).toEqual([3, 4, 7]);
    expect(parsePages(" 12 ")).toEqual([12]);
    expect(parsePages("7,3,3")).toEqual([3, 7]);
  });

  it("treats empty input as no pages", () => {
    expect(parsePages("")).toEqual([]);
    expect(parsePages("   ")).toEqual([]);
  });

  it("returns null when invalid", () => {
    expect(parsePages("0")).toBeNull();
    expect(parsePages("-1")).toBeNull();
    expect(parsePages("a")).toBeNull();
    expect(parsePages("3,,4")).toBeNull();
    expect(parsePages("3.5")).toBeNull();
    expect(parsePages("4-7")).toBeNull();
    expect(parsePages("1e3")).toBeNull();
  });
});

describe("parseKeyTerms", () => {
  it("parses one term per line with synonyms", () => {
    expect(
      parseKeyTerms("mitosis: cell division, karyokinesis\n\n  ATP  \nDNA:"),
    ).toEqual([
      { term: "mitosis", synonyms: ["cell division", "karyokinesis"] },
      { term: "ATP", synonyms: [] },
      { term: "DNA", synonyms: [] },
    ]);
  });

  it("splits on the first colon only and drops empty synonyms", () => {
    expect(parseKeyTerms("ratio: a:b, , c")).toEqual([
      { term: "ratio", synonyms: ["a:b", "c"] },
    ]);
  });

  it("skips blank lines and lines with no term", () => {
    expect(parseKeyTerms("\n  \n: orphan\n")).toEqual([]);
  });

  it("round-trips with formatKeyTerms", () => {
    const terms = [
      { term: "mitosis", synonyms: ["cell division", "karyokinesis"] },
      { term: "ATP", synonyms: [] },
    ];
    expect(formatKeyTerms(terms)).toBe(
      "mitosis: cell division, karyokinesis\nATP",
    );
    expect(parseKeyTerms(formatKeyTerms(terms))).toEqual(terms);
  });
});

describe("parseLines", () => {
  it("returns trimmed non-blank lines", () => {
    expect(parseLines(" one \n\n two\n   \n")).toEqual(["one", "two"]);
    expect(parseLines("")).toEqual([]);
  });
});
