import { useEffect, useState } from "react";
import { api } from "../api/client";

type State =
  | { kind: "loading" }
  | { kind: "unreachable" }
  | { kind: "error"; status: number }
  | { kind: "result"; db: "ok" | "error"; version: string };

function isHealthBody(body: unknown): body is { db: string; version: string } {
  return (
    typeof body === "object" &&
    body !== null &&
    "db" in body &&
    typeof body.db === "string" &&
    "version" in body &&
    typeof body.version === "string"
  );
}

export default function StatusPage() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    api
      .GET("/health")
      .then(({ data, error, response }) => {
        if (cancelled) return;
        if (data) {
          setState({
            kind: "result",
            db: data.db === "ok" ? "ok" : "error",
            version: data.version,
          });
          return;
        }
        if (response.status === 503 && isHealthBody(error)) {
          setState({
            kind: "result",
            db: error.db === "ok" ? "ok" : "error",
            version: error.version,
          });
          return;
        }
        setState({ kind: "error", status: response.status });
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
      {state.kind === "error" && <p>API error (HTTP {state.status})</p>}
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
