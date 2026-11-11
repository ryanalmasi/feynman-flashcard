import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { POLL_LIMIT_MS, POLL_MS } from "@/components/DocumentStatus";

export type KnowledgeMapOut = components["schemas"]["KnowledgeMapOut"];
export type KnowledgeMapState = "loading" | "none" | "ready" | "error";

type Loaded = {
  setId: string;
  map: KnowledgeMapOut | null;
  state: KnowledgeMapState;
};

export type UseKnowledgeMap = {
  map: KnowledgeMapOut | null;
  state: KnowledgeMapState;
  timedOut: boolean;
  refresh: () => void;
  replace: (m: KnowledgeMapOut) => void;
};

/**
 * Loads a set's Knowledge Map and polls it every POLL_MS while the map or its
 * card job is processing, or while there is no map yet but the document is
 * still processing. Polling stops on a terminal state and after POLL_LIMIT_MS.
 * Requests never overlap: a poll tick is skipped while one is in flight, and an
 * explicit reload is queued behind it.
 */
export function useKnowledgeMap(
  setId: string,
  documentProcessing: boolean,
): UseKnowledgeMap {
  const [loaded, setLoaded] = useState<Loaded>({
    setId,
    map: null,
    state: "loading",
  });
  const [timedOut, setTimedOut] = useState(false);
  const inFlight = useRef(false);
  const queued = useRef(false);
  const mounted = useRef(true);
  // Bumped by replace(): a response to a request sent before it is stale.
  const generation = useRef(0);

  // A result for another set (after a setId change) reads as still loading.
  const current = loaded.setId === setId;
  const map = current ? loaded.map : null;
  const state: KnowledgeMapState = current ? loaded.state : "loading";

  const load = useCallback(
    async (explicit: boolean) => {
      if (inFlight.current) {
        if (explicit) queued.current = true;
        return;
      }
      inFlight.current = true;
      const failed = (l: Loaded): Loaded =>
        // A failed poll keeps what we have; only a failed first load is an error.
        l.setId === setId && l.state !== "loading"
          ? l
          : { setId, map: null, state: "error" };
      try {
        // An explicit load requested meanwhile runs right after, never alongside.
        do {
          queued.current = false;
          const gen = generation.current;
          try {
            const { data, response } = await api.GET(
              "/study-sets/{set_id}/knowledge-map",
              { params: { path: { set_id: setId } } },
            );
            if (!mounted.current || gen !== generation.current) continue;
            if (data) setLoaded({ setId, map: data, state: "ready" });
            else if (response.status === 404)
              setLoaded({ setId, map: null, state: "none" });
            else setLoaded(failed);
          } catch {
            if (mounted.current && gen === generation.current) {
              setLoaded(failed);
            }
          }
        } while (queued.current && mounted.current);
      } finally {
        inFlight.current = false;
      }
    },
    [setId],
  );

  useEffect(() => {
    mounted.current = true;
    void load(true);
    return () => {
      mounted.current = false;
    };
  }, [load]);

  // When the document stops processing, fetch once more: extract_pdf creates
  // the map at the very end, and a poll may not have seen it yet.
  const wasProcessing = useRef(documentProcessing);
  useEffect(() => {
    if (wasProcessing.current && !documentProcessing) void load(true);
    wasProcessing.current = documentProcessing;
  }, [documentProcessing, load]);

  const processing =
    map !== null
      ? map.status === "processing" || map.cards_status === "processing"
      : documentProcessing;
  const polling = processing && !timedOut;

  useEffect(() => {
    if (!polling) return;
    let active = true;
    const interval = setInterval(() => {
      void load(false);
    }, POLL_MS);
    const limit = setTimeout(() => {
      clearInterval(interval);
      if (active) setTimedOut(true);
    }, POLL_LIMIT_MS);
    return () => {
      active = false;
      clearInterval(interval);
      clearTimeout(limit);
    };
  }, [polling, load]);

  const refresh = useCallback(() => {
    setTimedOut(false);
    void load(true);
  }, [load]);

  const replace = useCallback(
    (m: KnowledgeMapOut) => {
      generation.current += 1;
      setTimedOut(false);
      setLoaded({ setId, map: m, state: "ready" });
    },
    [setId],
  );

  return { map, state, timedOut, refresh, replace };
}
