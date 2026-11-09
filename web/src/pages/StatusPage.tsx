import { useEffect, useState } from "react";
import { api } from "../api/client";

type State =
  | { kind: "loading" }
  | { kind: "unreachable" }
  | { kind: "result"; db: "ok" | "error"; version: string };

export default function StatusPage() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    api
      .GET("/health")
      .then(({ data, error }) => {
        if (cancelled) return;
        const body = data ?? error;
        if (!body) {
          setState({ kind: "unreachable" });
          return;
        }
        setState({
          kind: "result",
          db: body.db === "ok" ? "ok" : "error",
          version: body.version,
        });
      })
      .catch(() => {
        if (!cancelled) setState({ kind: "unreachable" });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main>
      <h1>Feynman Flashcard</h1>
      {state.kind === "loading" && <p>Checking API…</p>}
      {state.kind === "unreachable" && <p>API unreachable</p>}
      {state.kind === "result" && (
        <>
          <p>API: ok</p>
          <p>Database: {state.db}</p>
          {state.version && <p>Version: {state.version}</p>}
        </>
      )}
    </main>
  );
}
