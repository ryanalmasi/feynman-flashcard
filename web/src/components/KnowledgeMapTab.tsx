import { useState } from "react";
import { toast } from "sonner";
import { api, errorMessage } from "@/api/client";
import type { components } from "@/api/schema.gen";
import ConceptFormDialog from "@/components/ConceptFormDialog";
import type { ConceptValues } from "@/components/ConceptFormDialog";
import ConfirmDialog from "@/components/ConfirmDialog";
import { TIMEOUT_COPY } from "@/components/DocumentStatus";
import type { DocumentStatusValue } from "@/components/DocumentStatus";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type {
  KnowledgeMapOut,
  KnowledgeMapState,
} from "@/hooks/useKnowledgeMap";
import { IMPORTANCE_LABELS, formatPages } from "@/lib/conceptForm";

type Concept = components["schemas"]["ConceptOut"];

type Props = {
  setId: string;
  map: KnowledgeMapOut | null;
  state: KnowledgeMapState;
  timedOut: boolean;
  /** The set's document status; null when the set has no document. */
  documentStatus: DocumentStatusValue | null;
  /** After a successful mutation: the page reloads the map and the set. */
  onChanged: () => void;
  /** Swap in a map the server just returned (restarts polling if processing). */
  onReplace: (m: KnowledgeMapOut) => void;
};

type ConceptDialog =
  { mode: "add" } | { mode: "edit"; concept: Concept } | null;

const REBUILD_CONFIRM =
  "Rebuilding replaces all concepts, including your edits. Your flashcards are kept.";
const MAP_FAILED_FALLBACK = "The Knowledge Map couldn't be built.";

const IMPORTANCE_VARIANT = {
  core: "default",
  supporting: "secondary",
  detail: "outline",
} as const;

/** A 422's first detail message when present, else the error's message. */
function validationMessage(error: unknown): string {
  const details = (error as { error?: { details?: unknown } } | null)?.error
    ?.details;
  if (Array.isArray(details)) {
    const msg = (details[0] as { msg?: unknown } | undefined)?.msg;
    if (typeof msg === "string" && msg) return msg;
  }
  return errorMessage(error);
}

function NoMap({
  documentStatus,
  timedOut,
  building,
  onBuild,
}: {
  documentStatus: DocumentStatusValue | null;
  timedOut: boolean;
  building: boolean;
  onBuild: () => void;
}) {
  if (documentStatus === "processing") {
    return (
      <div className="grid gap-1">
        <p className="text-muted-foreground">
          The Knowledge Map will be built when the PDF is ready.
        </p>
        {timedOut && (
          <p className="text-sm text-muted-foreground">{TIMEOUT_COPY}</p>
        )}
      </div>
    );
  }
  if (documentStatus === "failed") {
    return (
      <p className="text-muted-foreground">
        No Knowledge Map: the PDF couldn't be processed.
      </p>
    );
  }
  if (documentStatus === null) {
    return (
      <p className="text-muted-foreground">
        Knowledge Maps are built from an uploaded PDF. This set has none.
      </p>
    );
  }
  return (
    <div className="grid justify-items-start gap-3">
      <p className="text-muted-foreground">
        This set has no Knowledge Map yet.
      </p>
      <Button onClick={onBuild} disabled={building}>
        Build Knowledge Map
      </Button>
    </div>
  );
}

function ConceptRow({
  concept,
  disabled,
  onEdit,
  onDelete,
}: {
  concept: Concept;
  disabled: boolean;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const pages = formatPages(concept.source_pages);
  const hasDetails =
    concept.key_terms.length > 0 || concept.misconceptions.length > 0;
  return (
    <Card>
      <CardContent className="grid gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-semibold">{concept.title}</h3>
          <Badge variant={IMPORTANCE_VARIANT[concept.importance]}>
            {IMPORTANCE_LABELS[concept.importance]}
          </Badge>
          {pages && (
            <span className="text-sm text-muted-foreground">{pages}</span>
          )}
        </div>
        <p className="whitespace-pre-wrap">{concept.explanation}</p>
        {hasDetails && (
          <details className="grid gap-2 text-sm">
            <summary className="cursor-pointer font-medium">
              Key terms and misconceptions
            </summary>
            {concept.key_terms.length > 0 && (
              <div className="mt-2 grid gap-1">
                <h4 className="font-medium">Key terms</h4>
                <ul className="list-disc pl-5">
                  {concept.key_terms.map((kt) => (
                    <li key={kt.term}>
                      <span>{kt.term}</span>
                      {kt.synonyms.length > 0 && (
                        <span className="text-muted-foreground">
                          {` (${kt.synonyms.join(", ")})`}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {concept.misconceptions.length > 0 && (
              <div className="mt-2 grid gap-1">
                <h4 className="font-medium">Misconceptions</h4>
                <ul className="list-disc pl-5">
                  {concept.misconceptions.map((m, i) => (
                    <li key={i} className="whitespace-pre-wrap">
                      {m}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </details>
        )}
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            aria-label={`Edit ${concept.title}`}
            disabled={disabled}
            onClick={onEdit}
          >
            Edit
          </Button>
          <Button
            size="sm"
            variant="outline"
            aria-label={`Delete ${concept.title}`}
            disabled={disabled}
            onClick={onDelete}
          >
            Delete
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function KnowledgeMapTab({
  setId,
  map,
  state,
  timedOut,
  documentStatus,
  onChanged,
  onReplace,
}: Props) {
  const [building, setBuilding] = useState(false);
  const [confirmRebuild, setConfirmRebuild] = useState(false);
  const [conceptDialog, setConceptDialog] = useState<ConceptDialog>(null);
  const [deleting, setDeleting] = useState<Concept | null>(null);

  async function rebuild() {
    setBuilding(true);
    try {
      const { data, error } = await api.POST(
        "/study-sets/{set_id}/knowledge-map/rebuild",
        { params: { path: { set_id: setId } } },
      );
      if (data) onReplace(data);
      else toast.error(errorMessage(error));
    } catch {
      toast.error(errorMessage(null));
    } finally {
      setBuilding(false);
    }
  }

  async function saveConcept(values: ConceptValues): Promise<string | null> {
    const dialog = conceptDialog;
    if (!dialog) return null;
    try {
      const res =
        dialog.mode === "add"
          ? await api.POST("/study-sets/{set_id}/concepts", {
              params: { path: { set_id: setId } },
              body: values,
            })
          : await api.PATCH("/concepts/{concept_id}", {
              params: { path: { concept_id: dialog.concept.id } },
              body: values,
            });
      if (res.data) {
        onChanged();
        return null;
      }
      if (res.response.status === 422) return validationMessage(res.error);
      // 409 (the map started processing) or 404: the form can't succeed now.
      toast.error(errorMessage(res.error));
      onChanged();
      return null;
    } catch {
      return errorMessage(null);
    }
  }

  async function removeConcept() {
    const concept = deleting;
    setDeleting(null);
    if (!concept) return;
    try {
      const { response, error } = await api.DELETE("/concepts/{concept_id}", {
        params: { path: { concept_id: concept.id } },
      });
      if (!response.ok) toast.error(errorMessage(error));
      onChanged();
    } catch {
      toast.error(errorMessage(null));
    }
  }

  if (state === "loading") {
    return <p className="text-muted-foreground">Loading…</p>;
  }
  if (state === "error") {
    return (
      <p role="alert" className="text-destructive">
        {errorMessage(null)}
      </p>
    );
  }
  if (!map) {
    return (
      <NoMap
        documentStatus={documentStatus}
        timedOut={timedOut}
        building={building}
        onBuild={() => void rebuild()}
      />
    );
  }

  const mapProcessing = map.status === "processing";
  const cardsProcessing = map.cards_status === "processing";
  const locked = mapProcessing || cardsProcessing || building;
  const editable = map.status === "ready" && !locked;
  const n = map.concepts.length;

  return (
    <section className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          {`AI-generated from ${map.source_filename} · ${n} ${n === 1 ? "concept" : "concepts"}`}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={!editable}
            onClick={() => setConceptDialog({ mode: "add" })}
          >
            Add concept
          </Button>
          {map.status !== "failed" && (
            <Button
              variant="outline"
              disabled={locked}
              onClick={() => setConfirmRebuild(true)}
            >
              Rebuild
            </Button>
          )}
        </div>
      </div>

      {(mapProcessing || cardsProcessing) && (
        <p role="status" className="text-sm text-muted-foreground">
          {timedOut
            ? TIMEOUT_COPY
            : mapProcessing
              ? "Building the Knowledge Map…"
              : "Generating flashcards…"}
        </p>
      )}
      {map.status === "failed" && (
        <div className="grid justify-items-start gap-2 rounded-lg border p-3">
          <p className="text-sm text-destructive">
            {map.error_message || MAP_FAILED_FALLBACK}
          </p>
          <Button
            variant="outline"
            disabled={locked}
            onClick={() => setConfirmRebuild(true)}
          >
            Rebuild
          </Button>
        </div>
      )}
      {map.cards_status === "failed" && map.cards_error_message && (
        <p className="text-sm text-destructive">{map.cards_error_message}</p>
      )}

      {n === 0 && map.status === "ready" && (
        <p className="text-muted-foreground">No concepts yet.</p>
      )}
      <ul className="grid gap-3">
        {map.concepts.map((c) => (
          <li key={c.id}>
            <ConceptRow
              concept={c}
              disabled={!editable}
              onEdit={() => setConceptDialog({ mode: "edit", concept: c })}
              onDelete={() => setDeleting(c)}
            />
          </li>
        ))}
      </ul>

      <ConceptFormDialog
        open={conceptDialog !== null}
        onOpenChange={(o) => {
          if (!o) setConceptDialog(null);
        }}
        heading={
          conceptDialog?.mode === "edit" ? "Edit concept" : "Add concept"
        }
        submitLabel={conceptDialog?.mode === "edit" ? "Save" : "Add"}
        initial={
          conceptDialog?.mode === "edit"
            ? {
                title: conceptDialog.concept.title,
                explanation: conceptDialog.concept.explanation,
                importance: conceptDialog.concept.importance,
                key_terms: conceptDialog.concept.key_terms,
                misconceptions: conceptDialog.concept.misconceptions,
                source_pages: conceptDialog.concept.source_pages,
              }
            : undefined
        }
        onSubmit={saveConcept}
      />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => {
          if (!o) setDeleting(null);
        }}
        title="Delete this concept? Its flashcards are kept."
        confirmLabel="Delete"
        onConfirm={removeConcept}
      />
      <ConfirmDialog
        open={confirmRebuild}
        onOpenChange={setConfirmRebuild}
        title={REBUILD_CONFIRM}
        confirmLabel="Rebuild"
        onConfirm={() => {
          setConfirmRebuild(false);
          void rebuild();
        }}
      />
    </section>
  );
}
