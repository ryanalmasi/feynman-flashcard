import { describe, expect, it } from "vitest";
import { getApiBaseUrl } from "./client";

describe("getApiBaseUrl", () => {
  it("strips trailing slashes", () => {
    expect(getApiBaseUrl({ VITE_API_BASE_URL: "http://x/" })).toBe("http://x");
  });

  it("throws naming the variable when missing", () => {
    expect(() => getApiBaseUrl({})).toThrow(/VITE_API_BASE_URL/);
  });

  it("throws naming the variable when blank", () => {
    expect(() => getApiBaseUrl({ VITE_API_BASE_URL: "  " })).toThrow(
      /VITE_API_BASE_URL/,
    );
  });
});
