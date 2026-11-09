import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DocumentStatus, { POLL_LIMIT_MS, POLL_MS } from "./DocumentStatus";
import { json, stubFetch } from "@/test/pageUtils";

const base = {
  id: "d1",
  original_filename: "a.pdf",
  page_count: null,
  error_message: null,
};
const out = (status: string, extra: object = {}) =>
  json({ ...base, study_set_id: "s1", status, ...extra }, 200);

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("DocumentStatus", () => {
  it("exports the polling constants", () => {
    expect(POLL_MS).toBe(2000);
    expect(POLL_LIMIT_MS).toBe(600_000);
  });

  it("polls every 2 s and stops on ready", async () => {
    const replies = [
      out("processing"),
      out("processing"),
      out("ready", { page_count: 3 }),
    ];
    const fetchMock = stubFetch({
      "GET /documents/d1": () => replies.shift()!,
    });
    render(<DocumentStatus document={{ ...base, status: "processing" }} />);
    expect(screen.getByText("Processing…")).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(screen.getByText("Ready · 3 pages")).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("shows singular page", () => {
    render(
      <DocumentStatus document={{ ...base, status: "ready", page_count: 1 }} />,
    );
    expect(screen.getByText("Ready · 1 page")).toBeInTheDocument();
  });

  it("shows the server failure message and stops", async () => {
    const fetchMock = stubFetch({
      "GET /documents/d1": () =>
        out("failed", { error_message: "Scanned PDF, no text." }),
    });
    render(<DocumentStatus document={{ ...base, status: "processing" }} />);
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    expect(screen.getByText("Scanned PDF, no text.")).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("falls back to generic copy when failed without a message", () => {
    render(<DocumentStatus document={{ ...base, status: "failed" }} />);
    expect(
      screen.getByText(
        "Something went wrong while processing this PDF. Try uploading it again.",
      ),
    ).toBeInTheDocument();
  });

  it("stops after 10 minutes and shows the timeout copy", async () => {
    const fetchMock = stubFetch({
      "GET /documents/d1": () => out("processing"),
    });
    render(<DocumentStatus document={{ ...base, status: "processing" }} />);
    await act(() => vi.advanceTimersByTimeAsync(POLL_LIMIT_MS));
    expect(
      screen.getByText(
        "This is taking longer than expected. Check back later.",
      ),
    ).toBeInTheDocument();
    const n = fetchMock.mock.calls.length;
    await act(() => vi.advanceTimersByTimeAsync(20_000));
    expect(fetchMock).toHaveBeenCalledTimes(n);
  });

  it("keeps polling after an erroring poll", async () => {
    let n = 0;
    const fetchMock = stubFetch({
      "GET /documents/d1": () => {
        n += 1;
        if (n === 1) throw new Error("network");
        if (n === 2) return json({ error: { code: "x", message: "m" } }, 500);
        return out("ready", { page_count: 2 });
      },
    });
    render(<DocumentStatus document={{ ...base, status: "processing" }} />);
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 3));
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(screen.getByText("Ready · 2 pages")).toBeInTheDocument();
  });

  it("clears the interval on unmount", async () => {
    const fetchMock = stubFetch({
      "GET /documents/d1": () => out("processing"),
    });
    const { unmount } = render(
      <DocumentStatus document={{ ...base, status: "processing" }} />,
    );
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    unmount();
    await act(() => vi.advanceTimersByTimeAsync(POLL_LIMIT_MS + 10_000));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });
});
