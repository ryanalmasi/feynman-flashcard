import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { api, errorMessage } from "@/api/client";
import type { components } from "@/api/schema.gen";
import ClozeText from "@/components/ClozeText";
import { Button } from "@/components/ui/button";
import { shuffle } from "@/lib/shuffle";

type Flashcard = components["schemas"]["FlashcardOut"];

export default function ReviewPage() {
  const { setId = "" } = useParams();
  const [cards, setCards] = useState<Flashcard[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [order, setOrder] = useState<Flashcard[]>([]);
  const [shuffled, setShuffled] = useState(false);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .GET("/study-sets/{set_id}/flashcards", {
        params: { path: { set_id: setId } },
      })
      .then(({ data, error }) => {
        if (cancelled) return;
        if (data) {
          setCards(data);
          setOrder(data);
        } else {
          setLoadError(errorMessage(error));
        }
      })
      .catch(() => {
        if (!cancelled) setLoadError(errorMessage(null));
      });
    return () => {
      cancelled = true;
    };
  }, [setId]);

  const total = order.length;

  function go(delta: number) {
    const next = index + delta;
    if (next < 0 || next >= total) return;
    setIndex(next);
    setFlipped(false);
  }

  function toggleShuffle() {
    const on = !shuffled;
    setShuffled(on);
    setOrder(on ? shuffle(cards ?? []) : (cards ?? []));
    setIndex(0);
    setFlipped(false);
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
      const t = e.target;
      if (t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement) {
        return;
      }
      if (e.key === " " || e.key === "Enter") {
        // A focused button handles Space and Enter itself (one press, one flip).
        if (t instanceof HTMLButtonElement || t instanceof HTMLAnchorElement) {
          return;
        }
        if (e.key === "Enter") return;
        e.preventDefault();
        setFlipped((f) => !f);
      } else if (e.key === "ArrowRight") {
        const next = index + 1;
        if (next < total) {
          setIndex(next);
          setFlipped(false);
        }
      } else if (e.key === "ArrowLeft") {
        if (index > 0) {
          setIndex(index - 1);
          setFlipped(false);
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, total]);

  const back = (
    <Link to={`/sets/${setId}`} className="text-primary underline">
      Back to study set
    </Link>
  );

  if (loadError) {
    return (
      <div className="grid gap-3">
        <p role="alert" className="text-destructive">
          {loadError}
        </p>
        {back}
      </div>
    );
  }
  if (cards === null) return <p className="text-muted-foreground">Loading…</p>;
  if (total === 0) {
    return (
      <div className="grid gap-3">
        <p>This set has no cards yet.</p>
        {back}
      </div>
    );
  }

  const card = order[index];
  return (
    <div className="grid max-w-2xl gap-4">
      <div className="flex items-center justify-between">
        {back}
        <Button
          variant={shuffled ? "default" : "outline"}
          aria-pressed={shuffled}
          onClick={toggleShuffle}
        >
          Shuffle
        </Button>
      </div>
      <p className="text-sm text-muted-foreground">
        Card {index + 1} of {total}
      </p>
      <button
        type="button"
        aria-label={flipped ? "Show question" : "Show answer"}
        aria-pressed={flipped}
        onClick={() => setFlipped((f) => !f)}
        className="flex min-h-48 w-full cursor-pointer items-center justify-center rounded-xl border bg-card p-6 text-center text-card-foreground shadow-sm focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        <span className="grid gap-3 whitespace-pre-wrap text-lg">
          {card.kind === "cloze" ? (
            <>
              <span>
                <ClozeText front={card.front} reveal={flipped} />
              </span>
              {flipped && card.back && (
                <span className="text-base text-muted-foreground">
                  {card.back}
                </span>
              )}
            </>
          ) : (
            <span>{flipped ? card.back : card.front}</span>
          )}
        </span>
      </button>
      <div className="flex justify-between">
        <Button variant="outline" disabled={index === 0} onClick={() => go(-1)}>
          Previous
        </Button>
        <Button
          variant="outline"
          disabled={index === total - 1}
          onClick={() => go(1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
