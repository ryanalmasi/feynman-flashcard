import { useEffect, useRef, useState } from "react";
import { api } from "@/api/client";
import type { components } from "@/api/schema.gen";

type DocumentSummary = components["schemas"]["DocumentSummary"];
export type DocumentStatusValue = DocumentSummary["status"];

export const POLL_MS = 2000;
export const POLL_LIMIT_MS = 600_000;

const FAILED_FALLBACK =
  "Something went wrong while processing this PDF. Try uploading it again.";
export const TIMEOUT_COPY =
  "This is taking longer than expected. Check back later.";

function documentStatusText(doc: DocumentSummary, timedOut: boolean): string {
  if (doc.status === "ready") {
    const n = doc.page_count;
    return n === null ? "Ready" : `Ready · ${n} ${n === 1 ? "page" : "pages"}`;
  }
  if (doc.status === "failed") return doc.error_message || FAILED_FALLBACK;
  return timedOut ? TIMEOUT_COPY : "Processing…";
}

export default function DocumentStatus({
  document,
  onStatusChange,
}: {
  document: DocumentSummary;
  /** Called whenever the polled status changes (not on mount). */
  onStatusChange?: (status: DocumentStatusValue) => void;
}) {
  const [doc, setDoc] = useState(document);
  const [timedOut, setTimedOut] = useState(false);
  const inFlight = useRef(false);
  const reported = useRef(document.status);

  useEffect(() => {
    if (doc.status === reported.current) return;
    reported.current = doc.status;
    onStatusChange?.(doc.status);
  }, [doc.status, onStatusChange]);

  const id = document.id;
  const polling = doc.status === "processing" && !timedOut;

  useEffect(() => {
    if (!polling) return;
    let active = true;

    const interval = setInterval(() => {
      if (inFlight.current) return;
      inFlight.current = true;
      api
        .GET("/documents/{document_id}", {
          params: { path: { document_id: id } },
        })
        .then(({ data }) => {
          if (active && data) {
            setDoc({
              id: data.id,
              original_filename: data.original_filename,
              status: data.status,
              page_count: data.page_count,
              error_message: data.error_message,
            });
          }
        })
        .catch(() => {
          // Keep polling; the time limit still applies.
        })
        .finally(() => {
          inFlight.current = false;
        });
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
  }, [polling, id]);

  return (
    <div className="grid gap-1 rounded-lg border p-3">
      <p className="text-sm font-medium">{doc.original_filename}</p>
      <p
        className={
          doc.status === "failed"
            ? "text-sm text-destructive"
            : "text-sm text-muted-foreground"
        }
      >
        {documentStatusText(doc, timedOut)}
      </p>
    </div>
  );
}
