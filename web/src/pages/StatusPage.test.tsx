import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import StatusPage from "./StatusPage";

function jsonResponse(body: unknown, status: number) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("StatusPage", () => {
  it("shows loading, then ok for API and database", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ status: "ok", db: "ok", version: "0.1.0" }, 200),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<StatusPage />);
    expect(
      screen.getByRole("heading", { name: "Feynman Flashcard" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Checking API…")).toBeInTheDocument();

    expect(await screen.findByText("API: ok")).toBeInTheDocument();
    expect(screen.getByText("Database: ok")).toBeInTheDocument();
    expect(screen.getByText(/0\.1\.0/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const request = fetchMock.mock.calls[0][0] as Request;
    expect(request.url).toBe("http://api.test/health");
  });

  it("shows database error on 503 with a body", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(
            { status: "degraded", db: "error", version: "0.1.0" },
            503,
          ),
        ),
    );

    render(<StatusPage />);
    expect(await screen.findByText("API: ok")).toBeInTheDocument();
    expect(screen.getByText("Database: error")).toBeInTheDocument();
  });

  it("shows an API error, not API: ok, on a 500 error body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "internal_error",
              message: "Internal server error",
              details: null,
            },
          },
          500,
        ),
      ),
    );

    render(<StatusPage />);
    expect(await screen.findByText("API error (HTTP 500)")).toBeInTheDocument();
    expect(screen.queryByText("API: ok")).not.toBeInTheDocument();
    expect(screen.queryByText(/Database:/)).not.toBeInTheDocument();
  });

  it("shows unreachable on network failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );

    render(<StatusPage />);
    expect(await screen.findByText("API unreachable")).toBeInTheDocument();
    expect(screen.queryByText("API: ok")).not.toBeInTheDocument();
  });
});
