import { useState } from "react";
import type { FormEvent } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export type CardValues = { front: string; back: string };

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  heading: string;
  submitLabel: string;
  initial?: CardValues;
  /** Resolves to an error message to show inline, or null on success. */
  onSubmit: (values: CardValues) => Promise<string | null>;
};

function CardForm({
  submitLabel,
  initial,
  onSubmit,
  onDone,
}: Omit<Props, "open" | "onOpenChange" | "heading"> & { onDone: () => void }) {
  const [front, setFront] = useState(initial?.front ?? "");
  const [back, setBack] = useState(initial?.back ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!front.trim() || !back.trim()) {
      setError("Front and back are both required.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const msg = await onSubmit({ front, back });
      if (msg) setError(msg);
      else onDone();
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <div className="grid gap-2">
        <Label htmlFor="card-front">Front</Label>
        <Textarea
          id="card-front"
          maxLength={500}
          value={front}
          onChange={(e) => setFront(e.target.value)}
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="card-back">Back</Label>
        <Textarea
          id="card-back"
          maxLength={2000}
          value={back}
          onChange={(e) => setBack(e.target.value)}
        />
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

export default function CardFormDialog({
  open,
  onOpenChange,
  heading,
  ...rest
}: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{heading}</DialogTitle>
        </DialogHeader>
        <CardForm {...rest} onDone={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}
