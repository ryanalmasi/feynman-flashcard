import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";
import { api, errorMessage } from "@/api/client";
import type { components } from "@/api/schema.gen";
import SetFormDialog from "@/components/SetFormDialog";
import UploadPdfButton from "@/components/UploadPdfButton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type StudySet = components["schemas"]["StudySetOut"];

const BADGE: Record<"processing" | "ready" | "failed", string> = {
  processing: "Processing…",
  ready: "Ready",
  failed: "Failed",
};

export default function SetsPage() {
  const navigate = useNavigate();
  const [sets, setSets] = useState<StudySet[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .GET("/study-sets")
      .then(({ data, error }) => {
        if (cancelled) return;
        if (data) setSets(data);
        else setLoadError(errorMessage(error));
      })
      .catch(() => {
        if (!cancelled) setLoadError(errorMessage(null));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function create(values: {
    title: string;
    description: string | null;
  }): Promise<string | null> {
    try {
      const { data, error } = await api.POST("/study-sets", { body: values });
      if (!data) return errorMessage(error);
      toast.success("Study set created.");
      navigate(`/sets/${data.id}`);
      return null;
    } catch {
      return errorMessage(null);
    }
  }

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Your study sets</h1>
        <div className="flex gap-2">
          <Button onClick={() => setCreating(true)}>New set</Button>
          <UploadPdfButton />
        </div>
      </div>
      {loadError && (
        <p role="alert" className="text-destructive">
          {loadError}
        </p>
      )}
      {sets === null && !loadError && (
        <p className="text-muted-foreground">Loading…</p>
      )}
      {sets?.length === 0 && (
        <p className="text-muted-foreground">
          No study sets yet. Create one or upload a PDF.
        </p>
      )}
      <ul className="grid gap-3 sm:grid-cols-2">
        {sets?.map((s) => (
          <li key={s.id}>
            <Link to={`/sets/${s.id}`} className="block">
              <Card className="transition-colors hover:bg-accent">
                <CardHeader>
                  <CardTitle>{s.title}</CardTitle>
                </CardHeader>
                <CardContent className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span>
                    {s.card_count === 1 ? "1 card" : `${s.card_count} cards`}
                  </span>
                  {s.document && (
                    <Badge
                      variant={
                        s.document.status === "failed"
                          ? "destructive"
                          : "secondary"
                      }
                    >
                      {BADGE[s.document.status]}
                    </Badge>
                  )}
                </CardContent>
              </Card>
            </Link>
          </li>
        ))}
      </ul>
      <SetFormDialog
        open={creating}
        onOpenChange={setCreating}
        heading="New study set"
        submitLabel="Create"
        onSubmit={create}
      />
    </div>
  );
}
