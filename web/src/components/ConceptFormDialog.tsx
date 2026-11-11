import { useState } from "react";
import type { FormEvent } from "react";
import type { components } from "@/api/schema.gen";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import type { Importance } from "@/lib/conceptForm";
import {
  IMPORTANCE_LABELS,
  formatKeyTerms,
  parseKeyTerms,
  parseLines,
  parsePages,
} from "@/lib/conceptForm";

export type ConceptValues = components["schemas"]["ConceptCreate"];

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  heading: string;
  submitLabel: string;
  initial?: ConceptValues;
  /** Resolves to an error message to show inline, or null on success. */
  onSubmit: (values: ConceptValues) => Promise<string | null>;
};

function ConceptForm({
  submitLabel,
  initial,
  onSubmit,
  onDone,
}: Omit<Props, "open" | "onOpenChange" | "heading"> & { onDone: () => void }) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [explanation, setExplanation] = useState(initial?.explanation ?? "");
  const [importance, setImportance] = useState<Importance>(
    initial?.importance ?? "core",
  );
  const [keyTerms, setKeyTerms] = useState(
    formatKeyTerms(initial?.key_terms ?? []),
  );
  const [misconceptions, setMisconceptions] = useState(
    (initial?.misconceptions ?? []).join("\n"),
  );
  const [pages, setPages] = useState((initial?.source_pages ?? []).join(", "));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!title.trim() || !explanation.trim()) {
      setError("Title and explanation are both required.");
      return;
    }
    const sourcePages = parsePages(pages);
    if (sourcePages === null) {
      setError("Pages must be page numbers separated by commas.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const msg = await onSubmit({
        title: title.trim(),
        explanation: explanation.trim(),
        importance,
        key_terms: parseKeyTerms(keyTerms),
        misconceptions: parseLines(misconceptions),
        source_pages: sourcePages,
      });
      if (msg) setError(msg);
      else onDone();
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <div className="grid gap-2">
        <Label htmlFor="concept-title">Title</Label>
        <Input
          id="concept-title"
          maxLength={120}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="concept-explanation">Explanation</Label>
        <Textarea
          id="concept-explanation"
          maxLength={2000}
          value={explanation}
          onChange={(e) => setExplanation(e.target.value)}
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="concept-importance">Importance</Label>
        <NativeSelect
          id="concept-importance"
          value={importance}
          onChange={(e) => setImportance(e.target.value as Importance)}
        >
          {(Object.keys(IMPORTANCE_LABELS) as Importance[]).map((k) => (
            <NativeSelectOption key={k} value={k}>
              {IMPORTANCE_LABELS[k]}
            </NativeSelectOption>
          ))}
        </NativeSelect>
      </div>
      <div className="grid gap-2">
        <Label htmlFor="concept-key-terms">Key terms</Label>
        <Textarea
          id="concept-key-terms"
          aria-describedby="concept-key-terms-hint"
          value={keyTerms}
          onChange={(e) => setKeyTerms(e.target.value)}
        />
        <p
          id="concept-key-terms-hint"
          className="text-xs text-muted-foreground"
        >
          One per line: term: synonym, synonym
        </p>
      </div>
      <div className="grid gap-2">
        <Label htmlFor="concept-misconceptions">Misconceptions</Label>
        <Textarea
          id="concept-misconceptions"
          aria-describedby="concept-misconceptions-hint"
          value={misconceptions}
          onChange={(e) => setMisconceptions(e.target.value)}
        />
        <p
          id="concept-misconceptions-hint"
          className="text-xs text-muted-foreground"
        >
          One per line
        </p>
      </div>
      <div className="grid gap-2">
        <Label htmlFor="concept-pages">Pages</Label>
        <Input
          id="concept-pages"
          aria-describedby="concept-pages-hint"
          inputMode="numeric"
          value={pages}
          onChange={(e) => setPages(e.target.value)}
        />
        <p id="concept-pages-hint" className="text-xs text-muted-foreground">
          Comma-separated, e.g. 3, 4, 7
        </p>
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <DialogFooter>
        <Button type="submit" disabled={busy}>
          {submitLabel}
        </Button>
      </DialogFooter>
    </form>
  );
}

export default function ConceptFormDialog({
  open,
  onOpenChange,
  heading,
  ...rest
}: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{heading}</DialogTitle>
          <DialogDescription className="sr-only">
            A concept in this set's Knowledge Map.
          </DialogDescription>
        </DialogHeader>
        <ConceptForm {...rest} onDone={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}
