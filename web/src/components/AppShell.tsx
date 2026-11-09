import type { ReactNode } from "react";
import { Link } from "react-router";

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <Link to="/sets" className="text-lg font-semibold">
            Feynman Flashcard
          </Link>
          <nav className="flex gap-4 text-sm">
            <Link
              to="/sets"
              className="text-muted-foreground hover:text-foreground"
            >
              Study sets
            </Link>
            <Link
              to="/account"
              className="text-muted-foreground hover:text-foreground"
            >
              Account
            </Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
    </div>
  );
}
