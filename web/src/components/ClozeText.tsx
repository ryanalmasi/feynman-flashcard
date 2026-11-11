import { parseCloze } from "@/lib/cloze";

/** A cloze front as plain text: the blank hidden, or the answer revealed. */
export default function ClozeText({
  front,
  reveal,
}: {
  front: string;
  reveal: boolean;
}) {
  const parts = parseCloze(front);
  if (!parts) return <>{front}</>;
  return (
    <>
      {parts.before}
      {reveal ? (
        <strong className="font-semibold text-primary">{parts.answer}</strong>
      ) : (
        "_____"
      )}
      {parts.after}
    </>
  );
}
