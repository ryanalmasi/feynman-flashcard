import { useState } from "react";
import { toast } from "sonner";
import { api, errorMessage } from "@/api/client";
import RegenerateConfirmDialog from "@/components/RegenerateConfirmDialog";
import { Button } from "@/components/ui/button";
import type { KnowledgeMapOut } from "@/hooks/useKnowledgeMap";
import { regenerationCounts } from "@/lib/regenerate";
import type { RegenerationCounts } from "@/lib/regenerate";

type Props = {
  setId: string;
  /** null: the whole set ("Generate flashcards"); else one concept. */
  conceptId: string | null;
  /** The concept's title, for the row button's accessible name. */
  conceptTitle?: string;
  disabled: boolean;
  /** The 202 map (cards_status "processing"): swap it in to start polling. */
  onStarted: (map: KnowledgeMapOut) => void;
};

/**
 * Starts a card run. It first counts what the run would replace from both
 * lists (accepted and suggested) and warns when that is more than zero.
 */
export default function GenerateCardsButton({
  setId,
  conceptId,
  conceptTitle,
  disabled,
  onStarted,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  // Kept after closing so the dialog's text doesn't change while it animates out.
  const [counts, setCounts] = useState<RegenerationCounts>({
    replace: 0,
    accepted: 0,
  });

  async function generate() {
    const { data, error } = await api.POST(
      "/study-sets/{set_id}/flashcards/generate",
      {
        params: { path: { set_id: setId } },
        body: { concept_id: conceptId },
      },
    );
    if (data) onStarted(data);
    else toast.error(errorMessage(error));
  }

  async function run(step: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    try {
      await step();
    } catch {
      toast.error(errorMessage(null));
    } finally {
      setBusy(false);
    }
  }

  const start = () =>
    run(async () => {
      const path = { set_id: setId };
      const [accepted, suggested] = await Promise.all([
        api.GET("/study-sets/{set_id}/flashcards", {
          params: { path, query: { status: "accepted" } },
        }),
        api.GET("/study-sets/{set_id}/flashcards", {
          params: { path, query: { status: "suggested" } },
        }),
      ]);
      if (!accepted.data || !suggested.data) {
        toast.error(errorMessage(accepted.error ?? suggested.error));
        return;
      }
      const c = regenerationCounts(
        [...accepted.data, ...suggested.data],
        conceptId,
      );
      if (c.replace > 0) {
        setCounts(c);
        setConfirming(true);
      } else {
        await generate();
      }
    });

  const label = conceptId === null ? "Generate flashcards" : "Regenerate cards";
  return (
    <>
      <Button
        variant={conceptId === null ? "default" : "outline"}
        size={conceptId === null ? "default" : "sm"}
        aria-label={
          conceptId !== null && conceptTitle
            ? `Regenerate cards for ${conceptTitle}`
            : undefined
        }
        disabled={disabled || busy}
        onClick={() => void start()}
      >
        {label}
      </Button>
      <RegenerateConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        counts={counts}
        onConfirm={() => {
          setConfirming(false);
          void run(generate);
        }}
      />
    </>
  );
}
