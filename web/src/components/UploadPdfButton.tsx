import { useRef, useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { api, errorMessage } from "@/api/client";
import { Button } from "@/components/ui/button";

const MAX_BYTES = 20 * 1024 * 1024;

export default function UploadPdfButton() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const input = e.target;
    const file = input.files?.[0];
    // Reset so picking the same file twice still fires onChange.
    input.value = "";
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Choose a PDF file.");
      return;
    }
    if (file.size > MAX_BYTES) {
      toast.error("This file is larger than 20 MB.");
      return;
    }
    setBusy(true);
    try {
      const { data, error } = await api.POST("/documents", {
        // The body is built as FormData; the browser sets the multipart boundary.
        body: { file: "" },
        bodySerializer: () => {
          const form = new FormData();
          form.append("file", file);
          return form;
        },
      });
      if (!data) {
        toast.error(errorMessage(error));
        return;
      }
      toast.success("Upload received. Processing…");
      navigate(`/sets/${data.study_set.id}`);
    } catch {
      toast.error(errorMessage(null));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="hidden"
        data-testid="pdf-input"
        onChange={onPick}
        tabIndex={-1}
        aria-hidden="true"
      />
      <Button
        variant="outline"
        disabled={busy}
        onClick={() => inputRef.current?.click()}
      >
        {busy ? "Uploading…" : "Upload PDF"}
      </Button>
    </>
  );
}
