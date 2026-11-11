import { useState } from "react";
import { toast } from "sonner";
import { api, errorMessage, validationMessage } from "@/api/client";
import type { components } from "@/api/schema.gen";
import AiBadge from "@/components/AiBadge";
import CardFormDialog from "@/components/CardFormDialog";
import type { CardValues } from "@/components/CardFormDialog";
import ConfirmDialog from "@/components/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type Flashcard = components["schemas"]["FlashcardOut"];
type Concept = components["schemas"]["ConceptOut"];

type Props = {
  setId: string;
  /** The set's suggested cards. */
  cards: Flashcard[];
  /** The map's concepts, in map order (for the group titles and their order). */
  concepts: Concept[];
  /** After any change (or a failed one): the page reloads the set and lists. */
  onChanged: () => void;
};

type Group = { key: string; title: string; cards: Flashcard[] };

const EMPTY =
  "No suggested cards. Generate flashcards from the Knowledge Map tab.";

/** Concept groups in map order, then "Other" for unlinked or unknown ones. */
function groupCards(cards: Flashcard[], concepts: Concept[]): Group[] {
  const known = new Set(concepts.map((c) => c.id));
  const groups: Group[] = concepts
    .map((c) => ({
      key: c.id,
      title: c.title,
      cards: cards.filter((card) => card.concept_id === c.id),
    }))
    .filter((g) => g.cards.length > 0);
  const other = cards.filter(
    (card) => card.concept_id === null || !known.has(card.concept_id),
  );
  if (other.length > 0)
    groups.push({ key: "other", title: "Other", cards: other });
  return groups;
}

export default function SuggestedTab({
  setId,
  cards,
  concepts,
  onChanged,
}: Props) {
  // One request at a time: every action is disabled while one runs.
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Flashcard | null>(null);
  const [confirmAll, setConfirmAll] = useState<"accept" | "reject" | null>(
    null,
  );
  // Kept after closing so the dialog's title doesn't change while it animates out.
  const [lastAll, setLastAll] = useState<"accept" | "reject">("accept");

  async function perform(
    send: () => Promise<{ response: Response; error?: unknown }>,
  ) {
    if (busy) return;
    setBusy(true);
    try {
      const { response, error } = await send();
      if (!response.ok) toast.error(errorMessage(error));
    } catch {
      toast.error(errorMessage(null));
    } finally {
      setBusy(false);
    }
    // Reload on failure too: a 404 usually means the card is already gone.
    onChanged();
  }

  const accept = (card: Flashcard) =>
    perform(() =>
      api.PATCH("/flashcards/{card_id}", {
        params: { path: { card_id: card.id } },
        body: { status: "accepted" },
      }),
    );

  const reject = (cardIds: string[] | null) =>
    perform(() =>
      api.POST("/study-sets/{set_id}/suggested-cards/reject", {
        params: { path: { set_id: setId } },
        body: { card_ids: cardIds },
      }),
    );

  const acceptAll = () =>
    perform(() =>
      api.POST("/study-sets/{set_id}/suggested-cards/accept", {
        params: { path: { set_id: setId } },
        body: { card_ids: null },
      }),
    );

  async function saveEdit(values: CardValues): Promise<string | null> {
    const card = editing;
    if (!card) return null;
    try {
      const res = await api.PATCH("/flashcards/{card_id}", {
        params: { path: { card_id: card.id } },
        body: values,
      });
      if (res.data) {
        onChanged();
        return null;
      }
      return res.response.status === 422
        ? validationMessage(res.error)
        : errorMessage(res.error);
    } catch {
      return errorMessage(null);
    }
  }

  function openAll(which: "accept" | "reject") {
    setLastAll(which);
    setConfirmAll(which);
  }

  if (cards.length === 0) {
    return <p className="text-muted-foreground">{EMPTY}</p>;
  }

  return (
    <section className="grid gap-4">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button disabled={busy} onClick={() => openAll("accept")}>
          Accept all
        </Button>
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => openAll("reject")}
        >
          Reject all
        </Button>
      </div>
      {groupCards(cards, concepts).map((g) => (
        <section key={g.key} className="grid gap-3">
          <h3 className="font-semibold">{g.title}</h3>
          <ul className="grid gap-3">
            {g.cards.map((c) => (
              <li key={c.id}>
                <Card>
                  <CardContent className="grid gap-3">
                    {c.origin === "generated" && <AiBadge />}
                    <div className="grid gap-2 sm:grid-cols-2">
                      <p className="whitespace-pre-wrap">{c.front}</p>
                      <p className="whitespace-pre-wrap text-muted-foreground">
                        {c.back}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        disabled={busy}
                        onClick={() => void accept(c)}
                      >
                        Accept
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy}
                        onClick={() => void reject([c.id])}
                      >
                        Reject
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy}
                        onClick={() => setEditing(c)}
                      >
                        Edit
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
        </section>
      ))}

      <CardFormDialog
        open={editing !== null}
        onOpenChange={(o) => {
          if (!o) setEditing(null);
        }}
        heading="Edit card"
        submitLabel="Save"
        initial={
          editing ? { front: editing.front, back: editing.back } : undefined
        }
        onSubmit={saveEdit}
      />
      <ConfirmDialog
        open={confirmAll !== null}
        onOpenChange={(o) => {
          if (!o) setConfirmAll(null);
        }}
        title={
          lastAll === "accept"
            ? "Accept all suggested cards?"
            : "Reject all suggested cards?"
        }
        confirmLabel={lastAll === "accept" ? "Accept all" : "Reject all"}
        onConfirm={() => {
          const which = confirmAll;
          setConfirmAll(null);
          if (which === "accept") void acceptAll();
          else if (which === "reject") void reject(null);
        }}
      />
    </section>
  );
}
