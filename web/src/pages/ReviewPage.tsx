import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { api, errorMessage } from "@/api/client";
import type { components } from "@/api/schema.gen";
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
      const t = e.target;
      if (
        t instanceof HTMLElement &&
        (t instanceof HTMLInputElement ||
          t instanceof HTMLTextAreaElement ||
          t instanceof HTMLButtonElement)
      ) {
        return;
      }
      if (e.key === " ") {
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
      <div
        role="button"
        tabIndex={0}
        onClick={() => setFlipped((f) => !f)}
        className="flex min-h-48 cursor-pointer items-center justify-center rounded-xl border bg-card p-6 text-center text-card-foreground shadow-sm"
      >
        <p className="whitespace-pre-wrap text-lg">
          {flipped ? card.back : card.front}
        </p>
      </div>
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
