import { describe, expect, it } from "vitest";
import { shuffle } from "./shuffle";

describe("shuffle", () => {
  it("returns a permutation and does not mutate input", () => {
    const input = [1, 2, 3, 4, 5, 6];
    const copy = [...input];
    const out = shuffle(input, () => 0.3);
    expect(input).toEqual(copy);
    expect(out).not.toBe(input);
    expect([...out].sort()).toEqual(copy);
  });

  it("is deterministic for a given random source", () => {
    expect(shuffle([1, 2, 3], () => 0)).toEqual([2, 3, 1]);
  });
});
