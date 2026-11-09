import { createContext, useContext } from "react";
import type { components } from "@/api/schema.gen";

export type UserOut = components["schemas"]["UserOut"];
export type SessionOut = components["schemas"]["SessionOut"];

export interface AuthState {
  status: "loading" | "signed_in" | "signed_out";
  user: UserOut | null;
  signedIn(s: SessionOut): void;
  signedOut(): void;
  refresh(): Promise<void>;
}

export const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
