import { Badge } from "@/components/ui/badge";

/** Marks AI-generated content (design §7.8, AI disclosure). */
export default function AiBadge() {
  return (
    <Badge variant="secondary" title="AI-generated">
      AI
    </Badge>
  );
}
