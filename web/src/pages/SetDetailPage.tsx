import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { api, errorMessage } from "@/api/client";
import type { components } from "@/api/schema.gen";
import CardFormDialog from "@/components/CardFormDialog";
import ConfirmDialog from "@/components/ConfirmDialog";
import DocumentStatus from "@/components/DocumentStatus";
import SetFormDialog from "@/components/SetFormDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type StudySet = components["schemas"]["StudySetOut"];
type Flashcard = components["schemas"]["FlashcardOut"];

type CardDialog = { mode: "add" } | { mode: "edit"; card: Flashcard } | null;

export default function SetDetailPage() {
  const { setId = "" } = useParams();
  const navigate = useNavigate();
  const [studySet, setStudySet] = useState<StudySet | null>(null);
  const [cards, setCards] = useState<Flashcard[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "missing" | "error">(
    "loading",
  );
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editingSet, setEditingSet] = useState(false);
  const [cardDialog, setCardDialog] = useState<CardDialog>(null);
  const [deletingCard, setDeletingCard] = useState<Flashcard | null>(null);
  const [deletingSet, setDeletingSet] = useState(false);

  const [version, setVersion] = useState(0);
  const reload = () => setVersion((v) => v + 1);

  useEffect(() => {
    let cancelled = false;
    const path = { set_id: setId };
    Promise.all([
      api.GET("/study-sets/{set_id}", { params: { path } }),
      api.GET("/study-sets/{set_id}/flashcards", { params: { path } }),
    ])
      .then(([s, c]) => {
        if (cancelled) return;
        if (s.response.status === 404) {
          setState("missing");
        } else if (s.data && c.data) {
          setStudySet(s.data);
          setCards(c.data);
          setState("ready");
        } else {
          setLoadError(errorMessage(s.error ?? c.error));
          setState("error");
        }
      })
      .catch(() => {
        if (cancelled) return;
        setLoadError(errorMessage(null));
        setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [setId, version]);

  async function saveSet(values: {
    title: string;
    description: string | null;
  }): Promise<string | null> {
    try {
      const { data, error } = await api.PATCH("/study-sets/{set_id}", {
        params: { path: { set_id: setId } },
        body: values,
      });
      if (!data) return errorMessage(error);
      setStudySet(data);
      return null;
    } catch {
      return errorMessage(null);
    }
  }

  async function saveCard(values: {
    front: string;
    back: string;
  }): Promise<string | null> {
    const dialog = cardDialog;
    if (!dialog) return null;
    try {
      const res =
        dialog.mode === "add"
          ? await api.POST("/study-sets/{set_id}/flashcards", {
              params: { path: { set_id: setId } },
              body: { kind: "qa", ...values },
            })
          : await api.PATCH("/flashcards/{card_id}", {
              params: { path: { card_id: dialog.card.id } },
              body: values,
            });
      if (!res.data) return errorMessage(res.error);
      reload();
      return null;
    } catch {
      return errorMessage(null);
    }
  }

  async function removeCard() {
    const card = deletingCard;
    setDeletingCard(null);
    if (!card) return;
    try {
      const { response, error } = await api.DELETE("/flashcards/{card_id}", {
        params: { path: { card_id: card.id } },
      });
      if (response.ok) reload();
      else toast.error(errorMessage(error));
    } catch {
      toast.error(errorMessage(null));
    }
  }

  async function removeSet() {
    setDeletingSet(false);
    try {
      const { response, error } = await api.DELETE("/study-sets/{set_id}", {
        params: { path: { set_id: setId } },
      });
      if (response.ok) {
        toast.success("Study set deleted.");
        navigate("/sets");
      } else {
        toast.error(errorMessage(error));
      }
    } catch {
      toast.error(errorMessage(null));
    }
  }

  if (state === "loading")
    return <p className="text-muted-foreground">Loading…</p>;
  if (state === "missing") {
    return (
      <div className="grid gap-3">
        <p>Study set not found.</p>
        <Link to="/sets" className="text-primary underline">
          Back to your study sets
        </Link>
      </div>
    );
  }
  if (state === "error" || !studySet) {
    return (
      <p role="alert" className="text-destructive">
        {loadError ?? errorMessage(null)}
      </p>
    );
  }

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <h1 className="text-2xl font-semibold">{studySet.title}</h1>
          {studySet.description && (
            <p className="whitespace-pre-wrap text-muted-foreground">
              {studySet.description}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setEditingSet(true)}>
            Edit
          </Button>
          {cards.length === 0 ? (
            <Button disabled>Review</Button>
          ) : (
            <Button asChild>
              <Link to={`/sets/${setId}/review`}>Review</Link>
            </Button>
          )}
          <Button variant="destructive" onClick={() => setDeletingSet(true)}>
            Delete set
          </Button>
        </div>
      </div>

      {studySet.document && (
        <DocumentStatus
          key={studySet.document.id}
          document={studySet.document}
        />
      )}

      <section className="grid gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Cards</h2>
          <Button onClick={() => setCardDialog({ mode: "add" })}>
            Add card
          </Button>
        </div>
        {cards.length === 0 && (
          <p className="text-muted-foreground">No cards yet.</p>
        )}
        <ul className="grid gap-3">
          {cards.map((c) => (
            <li key={c.id}>
              <Card>
                <CardContent className="grid gap-3">
                  <div className="grid gap-2 sm:grid-cols-2">
                    <p className="whitespace-pre-wrap">{c.front}</p>
                    <p className="whitespace-pre-wrap text-muted-foreground">
                      {c.back}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      aria-label="Edit card"
                      onClick={() => setCardDialog({ mode: "edit", card: c })}
                    >
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      aria-label="Delete card"
                      onClick={() => setDeletingCard(c)}
                    >
                      Delete
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      </section>

      <SetFormDialog
        open={editingSet}
        onOpenChange={setEditingSet}
        heading="Edit study set"
        submitLabel="Save"
        initial={{ title: studySet.title, description: studySet.description }}
        onSubmit={saveSet}
      />
      <CardFormDialog
        open={cardDialog !== null}
        onOpenChange={(o) => {
          if (!o) setCardDialog(null);
        }}
        heading={cardDialog?.mode === "edit" ? "Edit card" : "Add card"}
        submitLabel={cardDialog?.mode === "edit" ? "Save" : "Add"}
        initial={
          cardDialog?.mode === "edit"
            ? { front: cardDialog.card.front, back: cardDialog.card.back }
            : undefined
        }
        onSubmit={saveCard}
      />
      <ConfirmDialog
        open={deletingCard !== null}
        onOpenChange={(o) => {
          if (!o) setDeletingCard(null);
        }}
        title="Delete this card?"
        confirmLabel="Delete"
        onConfirm={removeCard}
      />
      <ConfirmDialog
        open={deletingSet}
        onOpenChange={setDeletingSet}
        title="Delete this study set? Its cards and PDF will be deleted too."
        confirmLabel="Delete"
        onConfirm={removeSet}
      />
    </div>
  );
}
