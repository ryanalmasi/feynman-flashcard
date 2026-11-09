import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useLocation, useNavigate } from "react-router";
import { api, setCsrfToken, setUnauthenticatedHandler } from "@/api/client";
import {
  AuthContext,
  type AuthState,
  type SessionOut,
  type UserOut,
} from "./useAuth";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthState["status"]>("loading");
  const [user, setUser] = useState<UserOut | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const locationRef = useRef(location);
  useEffect(() => {
    locationRef.current = location;
  }, [location]);

  const signedIn = useCallback((s: SessionOut) => {
    setCsrfToken(s.csrf_token);
    setUser(s.user);
    setStatus("signed_in");
  }, []);

  const signedOut = useCallback(() => {
    setCsrfToken(null);
    setUser(null);
    setStatus("signed_out");
  }, []);

  const refresh = useCallback(async () => {
    try {
      const { data, response } = await api.GET("/auth/session");
      if (data) signedIn(data);
      else if (response.status === 401) signedOut();
    } catch {
      signedOut();
    }
  }, [signedIn, signedOut]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  useEffect(() => {
    setUnauthenticatedHandler(() => {
      signedOut();
      const { pathname, search } = locationRef.current;
      navigate("/login?next=" + encodeURIComponent(pathname + search));
    });
    return () => setUnauthenticatedHandler(null);
  }, [navigate, signedOut]);

  const value = useMemo<AuthState>(
    () => ({ status, user, signedIn, signedOut, refresh }),
    [status, user, signedIn, signedOut, refresh],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
