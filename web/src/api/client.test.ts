import { afterEach, describe, expect, it, vi } from "vitest";
import {
  api,
  errorMessage,
  getApiBaseUrl,
  setCsrfToken,
  setUnauthenticatedHandler,
} from "./client";

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

describe("client middleware", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setCsrfToken(null);
    setUnauthenticatedHandler(null);
  });

  function stub(status: number, body: unknown) {
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify(body), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  it("adds X-CSRF-Token on POST/PATCH/DELETE when set, never on GET", async () => {
    const fetchMock = stub(200, {});
    setCsrfToken("tok");
    await api.GET("/health");
    await api.POST("/auth/logout");
    await api.PATCH("/study-sets/{set_id}", {
      params: { path: { set_id: "x" } },
      body: {},
    });
    await api.DELETE("/study-sets/{set_id}", {
      params: { path: { set_id: "x" } },
    });
    const headers = fetchMock.mock.calls.map((c) =>
      (c[0] as Request).headers.get("X-CSRF-Token"),
    );
    expect(headers).toEqual([null, "tok", "tok", "tok"]);
  });

  it("does not add the header when no token is set", async () => {
    const fetchMock = stub(200, {});
    await api.POST("/auth/logout");
    expect(
      (fetchMock.mock.calls[0][0] as Request).headers.has("X-CSRF-Token"),
    ).toBe(false);
  });

  it("calls the unauthenticated handler on 401 not_authenticated", async () => {
    stub(401, {
      error: { code: "not_authenticated", message: "x", details: null },
    });
    const handler = vi.fn();
    setUnauthenticatedHandler(handler);
    await api.GET("/study-sets");
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("does not call it on 401 invalid_credentials", async () => {
    stub(401, {
      error: { code: "invalid_credentials", message: "x", details: null },
    });
    const handler = vi.fn();
    setUnauthenticatedHandler(handler);
    await api.POST("/auth/login", {
      body: { email: "a@b.co", password: "pw" },
    });
    expect(handler).not.toHaveBeenCalled();
  });

  it("does not call it on 401 from /auth/session", async () => {
    stub(401, {
      error: { code: "not_authenticated", message: "x", details: null },
    });
    const handler = vi.fn();
    setUnauthenticatedHandler(handler);
    await api.GET("/auth/session");
    expect(handler).not.toHaveBeenCalled();
  });
});

describe("errorMessage", () => {
  it("returns the API message when present", () => {
    expect(errorMessage({ error: { code: "c", message: "Nope" } })).toBe(
      "Nope",
    );
  });
  it("falls back otherwise", () => {
    expect(errorMessage(undefined)).toBe("Something went wrong. Try again.");
    expect(errorMessage({}, "custom")).toBe("custom");
  });
});
