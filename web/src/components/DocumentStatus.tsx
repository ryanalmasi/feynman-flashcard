import type { components } from "@/api/schema.gen";

type DocumentSummary = components["schemas"]["DocumentSummary"];

const FAILED_FALLBACK =
  "Something went wrong while processing this PDF. Try uploading it again.";

function documentStatusText(doc: DocumentSummary): string {
  if (doc.status === "ready") {
    const n = doc.page_count;
    return n === null ? "Ready" : `Ready · ${n} ${n === 1 ? "page" : "pages"}`;
  }
  if (doc.status === "failed") return doc.error_message || FAILED_FALLBACK;
  return "Processing…";
}

export default function DocumentStatus({ doc }: { doc: DocumentSummary }) {
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
        {documentStatusText(doc)}
      </p>
    </div>
  );
}
