import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useKnowledgeMap } from "./useKnowledgeMap";
import { POLL_LIMIT_MS, POLL_MS } from "@/components/DocumentStatus";
import { apiError, json, stubFetch } from "@/test/pageUtils";

const mapOut = (extra: object = {}) => ({
  id: "m1",
  status: "ready",
  error_message: null,
  model_id: "model-x",
  revision: 1,
  cards_status: "idle",
  cards_error_message: null,
  source_filename: "bio.pdf",
  concepts: [],
  ...extra,
});
const notFound = () => json(apiError("not_found", "Not found."), 404);
const KM = "GET /study-sets/s1/knowledge-map";

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const settle = () => act(() => vi.advanceTimersByTimeAsync(0));

describe("useKnowledgeMap", () => {
  it("loads the map", async () => {
    stubFetch({ [KM]: () => json(mapOut(), 200) });
    const { result } = renderHook(() => useKnowledgeMap("s1", false));
    expect(result.current.state).toBe("loading");
    await settle();
    expect(result.current.state).toBe("ready");
    expect(result.current.map?.source_filename).toBe("bio.pdf");
  });

  it("a 404 is state none and does not poll when the document is not processing", async () => {
    const m = stubFetch({ [KM]: notFound });
    const { result } = renderHook(() => useKnowledgeMap("s1", false));
    await settle();
    expect(result.current.state).toBe("none");
    expect(result.current.map).toBeNull();
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 5));
    expect(m).toHaveBeenCalledTimes(1);
  });

  it("a server error is state error", async () => {
    stubFetch({ [KM]: () => json(apiError("internal_error", "x"), 500) });
    const { result } = renderHook(() => useKnowledgeMap("s1", false));
    await settle();
    expect(result.current.state).toBe("error");
  });

  it("polls while the map is processing and stops on ready", async () => {
    const replies = [
      mapOut({ status: "processing" }),
      mapOut({ status: "processing" }),
      mapOut({ status: "processing" }),
      mapOut({ status: "ready" }),
    ];
    const m = stubFetch({ [KM]: () => json(replies.shift(), 200) });
    const { result } = renderHook(() => useKnowledgeMap("s1", false));
    await settle();
    expect(result.current.map?.status).toBe("processing");
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    expect(m).toHaveBeenCalledTimes(4);
    expect(result.current.map?.status).toBe("ready");
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 10));
    expect(m).toHaveBeenCalledTimes(4);
    expect(result.current.timedOut).toBe(false);
  });

  it("polls while cards are processing", async () => {
    const replies = [
      mapOut({ cards_status: "processing" }),
      mapOut({ cards_status: "idle" }),
    ];
    const m = stubFetch({ [KM]: () => json(replies.shift(), 200) });
    const { result } = renderHook(() => useKnowledgeMap("s1", false));
    await settle();
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    expect(result.current.map?.cards_status).toBe("idle");
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 5));
    expect(m).toHaveBeenCalledTimes(2);
  });

  it("stops at the 10-minute cap and reports timedOut", async () => {
    const m = stubFetch({
      [KM]: () => json(mapOut({ status: "processing" }), 200),
    });
    const { result } = renderHook(() => useKnowledgeMap("s1", false));
    await settle();
    await act(() => vi.advanceTimersByTimeAsync(POLL_LIMIT_MS));
    expect(result.current.timedOut).toBe(true);
    const n = m.mock.calls.length;
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 10));
    expect(m).toHaveBeenCalledTimes(n);
  });

  it("a 404 keeps polling only while the document is processing", async () => {
    let n = 0;
    const m = stubFetch({
      [KM]: () => {
        n += 1;
        return n < 3 ? notFound() : json(mapOut({ status: "processing" }), 200);
      },
    });
    const { result } = renderHook(() => useKnowledgeMap("s1", true));
    await settle();
    expect(result.current.state).toBe("none");
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    expect(m).toHaveBeenCalledTimes(2);
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    expect(m).toHaveBeenCalledTimes(3);
    expect(result.current.state).toBe("ready");
    expect(result.current.map?.status).toBe("processing");
  });

  it("stops polling a 404 when the document stops processing, after one more fetch", async () => {
    const m = stubFetch({ [KM]: notFound });
    const { result, rerender } = renderHook(
      ({ processing }) => useKnowledgeMap("s1", processing),
      { initialProps: { processing: true } },
    );
    await settle();
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    expect(m).toHaveBeenCalledTimes(2);
    rerender({ processing: false });
    await settle();
    expect(m).toHaveBeenCalledTimes(3);
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 10));
    expect(m).toHaveBeenCalledTimes(3);
    expect(result.current.state).toBe("none");
  });

  it("fetches once more when documentProcessing goes from true to false", async () => {
    // No polls in between: the refetch alone must find the new map.
    const replies = [notFound(), json(mapOut({ status: "processing" }), 200)];
    const m = stubFetch({ [KM]: () => replies.shift()! });
    const { result, rerender } = renderHook(
      ({ processing }) => useKnowledgeMap("s1", processing),
      { initialProps: { processing: true } },
    );
    await settle();
    expect(result.current.state).toBe("none");
    rerender({ processing: false });
    await settle();
    expect(m).toHaveBeenCalledTimes(2);
    expect(result.current.map?.status).toBe("processing");
  });

  it("queues the true-to-false refetch behind an in-flight poll", async () => {
    let release: (r: Response) => void = () => {};
    let n = 0;
    const m = stubFetch({
      [KM]: () => {
        n += 1;
        if (n === 2) return new Promise<Response>((r) => (release = r));
        if (n === 3) return json(mapOut({ status: "processing" }), 200);
        return notFound();
      },
    });
    const { result, rerender } = renderHook(
      ({ processing }) => useKnowledgeMap("s1", processing),
      { initialProps: { processing: true } },
    );
    await settle();
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS)); // poll 2 hangs
    rerender({ processing: false });
    await settle();
    expect(m).toHaveBeenCalledTimes(2); // no overlap
    await act(async () => {
      release(notFound());
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(m).toHaveBeenCalledTimes(3);
    expect(result.current.map?.status).toBe("processing");
  });

  it("never overlaps poll requests", async () => {
    let release: (r: Response) => void = () => {};
    let n = 0;
    const m = stubFetch({
      [KM]: () => {
        n += 1;
        if (n === 1) return json(mapOut({ status: "processing" }), 200);
        return new Promise<Response>((r) => (release = r));
      },
    });
    renderHook(() => useKnowledgeMap("s1", false));
    await settle();
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 5));
    expect(m).toHaveBeenCalledTimes(2);
    await act(async () => {
      release(json(mapOut({ status: "ready" }), 200));
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 5));
    expect(m).toHaveBeenCalledTimes(2);
  });

  it("replace() with a processing map restarts polling", async () => {
    const replies = [
      mapOut(),
      mapOut({ status: "processing" }),
      mapOut({ status: "ready", revision: 2 }),
    ];
    const m = stubFetch({ [KM]: () => json(replies.shift(), 200) });
    const { result } = renderHook(() => useKnowledgeMap("s1", false));
    await settle();
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 3));
    expect(m).toHaveBeenCalledTimes(1);
    act(() =>
      result.current.replace(
        mapOut({ status: "processing" }) as Parameters<
          typeof result.current.replace
        >[0],
      ),
    );
    expect(result.current.map?.status).toBe("processing");
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    expect(result.current.map?.revision).toBe(2);
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS * 5));
    expect(m).toHaveBeenCalledTimes(3);
  });

  it("replace() after a timeout clears timedOut and polls again", async () => {
    let status = "processing";
    stubFetch({ [KM]: () => json(mapOut({ status }), 200) });
    const { result } = renderHook(() => useKnowledgeMap("s1", false));
    await settle();
    await act(() => vi.advanceTimersByTimeAsync(POLL_LIMIT_MS));
    expect(result.current.timedOut).toBe(true);
    act(() =>
      result.current.replace(
        mapOut({ status: "processing" }) as Parameters<
          typeof result.current.replace
        >[0],
      ),
    );
    expect(result.current.timedOut).toBe(false);
    status = "ready";
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    expect(result.current.map?.status).toBe("ready");
  });

  it("refresh() refetches and restarts polling on a processing state", async () => {
    const replies = [
      mapOut(),
      mapOut({ cards_status: "processing" }),
      mapOut({ cards_status: "idle" }),
    ];
    const m = stubFetch({ [KM]: () => json(replies.shift(), 200) });
    const { result } = renderHook(() => useKnowledgeMap("s1", false));
    await settle();
    act(() => result.current.refresh());
    await settle();
    expect(result.current.map?.cards_status).toBe("processing");
    await act(() => vi.advanceTimersByTimeAsync(POLL_MS));
    expect(result.current.map?.cards_status).toBe("idle");
    expect(m).toHaveBeenCalledTimes(3);
  });

  it("loads the new set's map when setId changes mid-request", async () => {
    let releaseS1: (r: Response) => void = () => {};
    const m = stubFetch({
      [KM]: () => new Promise<Response>((r) => (releaseS1 = r)),
      "GET /study-sets/s2/knowledge-map": () =>
        json(mapOut({ id: "m2", source_filename: "two.pdf" }), 200),
    });
    const { result, rerender } = renderHook(
      ({ id }) => useKnowledgeMap(id, false),
      { initialProps: { id: "s1" } },
    );
    await settle(); // the s1 request is in flight
    rerender({ id: "s2" });
    await settle();
    const paths = () =>
      m.mock.calls.map((c) => new URL((c[0] as Request).url).pathname);
    expect(paths()).toContain("/study-sets/s2/knowledge-map");
    expect(result.current.state).toBe("ready");
    expect(result.current.map?.source_filename).toBe("two.pdf");
    // The late s1 response doesn't overwrite s2's map.
    await act(async () => {
      releaseS1(json(mapOut({ source_filename: "one.pdf" }), 200));
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.map?.source_filename).toBe("two.pdf");
    expect(paths().filter((p) => p.includes("/s1/"))).toHaveLength(1);
  });

  it("resets timedOut when setId changes", async () => {
    stubFetch({
      [KM]: () => json(mapOut({ status: "processing" }), 200),
      "GET /study-sets/s2/knowledge-map": () =>
        json(mapOut({ status: "processing" }), 200),
    });
    const { result, rerender } = renderHook(
      ({ id }) => useKnowledgeMap(id, false),
      { initialProps: { id: "s1" } },
    );
    await settle();
    await act(() => vi.advanceTimersByTimeAsync(POLL_LIMIT_MS));
    expect(result.current.timedOut).toBe(true);
    rerender({ id: "s2" });
    await settle();
    expect(result.current.timedOut).toBe(false);
  });

  it("clears its timers on unmount", async () => {
    const m = stubFetch({
      [KM]: () => json(mapOut({ status: "processing" }), 200),
    });
    const { unmount } = renderHook(() => useKnowledgeMap("s1", false));
    await settle();
    unmount();
    await act(() => vi.advanceTimersByTimeAsync(POLL_LIMIT_MS + 10_000));
    expect(m).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });
});
