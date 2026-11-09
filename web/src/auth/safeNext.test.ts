import { describe, expect, it } from "vitest";
import { safeNext } from "./safeNext";

describe("safeNext", () => {
  it("keeps same-origin paths", () => {
    expect(safeNext("/sets/1?x=2")).toBe("/sets/1?x=2");
  });
  it.each([
    "//evil.com",
    "https://evil.com",
    "/\\evil",
    "/\t/evil",
    "/\n/evil",
    "/\r/evil",
    "javascript:alert(1)",
    " /sets",
    null,
  ])("rejects %s", (v) => {
    expect(safeNext(v)).toBe("/sets");
  });
  it("keeps an encoded slash path as-is", () => {
    expect(safeNext("/%2F/evil")).toBe("/%2F/evil");
  });
});
