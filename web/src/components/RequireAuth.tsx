import { Navigate, Outlet, useLocation } from "react-router";
import { useAuth } from "@/auth/useAuth";
import AppShell from "./AppShell";

export default function RequireAuth() {
  const { status } = useAuth();
  const { pathname, search } = useLocation();
  if (status === "loading") return <p className="p-4">Loading…</p>;
  if (status === "signed_out") {
    return (
      <Navigate
        to={"/login?next=" + encodeURIComponent(pathname + search)}
        replace
      />
    );
  }
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}
