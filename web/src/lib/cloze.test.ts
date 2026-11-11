import { describe, expect, it } from "vitest";
import { parseCloze } from "./cloze";

describe("parseCloze", () => {
  it("splits before, answer and after", () => {
    expect(parseCloze("The capital of France is {{Paris}}.")).toEqual({
      before: "The capital of France is ",
      answer: "Paris",
      after: ".",
    });
  });
  it("handles a blank at the start or end", () => {
    expect(parseCloze("{{Paris}} is big")).toEqual({
      before: "",
      answer: "Paris",
      after: " is big",
    });
    expect(parseCloze("Big: {{Paris}}")?.after).toBe("");
  });
  it("returns null when there is no blank", () => {
    expect(parseCloze("No blank here")).toBeNull();
    expect(parseCloze("{{unclosed")).toBeNull();
  });
});
