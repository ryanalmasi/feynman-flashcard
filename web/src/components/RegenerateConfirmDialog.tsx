import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import type { RegenerationCounts } from "@/lib/regenerate";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  counts: RegenerationCounts;
  onConfirm: () => void;
};

/** The regeneration warning (design §7.8), with N and M filled in. */
export default function RegenerateConfirmDialog({
  open,
  onOpenChange,
  counts,
  onConfirm,
}: Props) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Replace AI-generated cards?</AlertDialogTitle>
          <AlertDialogDescription>
            {`This replaces ${counts.replace} AI-generated cards you haven't edited (${counts.accepted} of them already accepted). Your own cards and cards you've edited are kept.`}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm}>Generate</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
