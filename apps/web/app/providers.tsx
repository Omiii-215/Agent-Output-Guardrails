"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { loadSession, saveSession, type DevSession } from "@/lib/session";

const SessionContext = createContext<{
  session: DevSession | null;
  setSession: (s: DevSession | null) => void;
  ready: boolean;
}>({ session: null, setSession: () => {}, ready: false });

export function useSession() {
  return useContext(SessionContext);
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 2_000 } } }),
  );
  const [session, setState] = useState<DevSession | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setState(loadSession());
    setReady(true);
  }, []);

  // Stable identity: effects that depend on setSession must not re-run on every render.
  const setSession = useCallback(
    (s: DevSession | null) => {
      saveSession(s);
      setState(s);
      client.clear(); // never reuse cached data across identities or tenants
    },
    [client],
  );
  const value = useMemo(() => ({ session, setSession, ready }), [session, setSession, ready]);

  return (
    <SessionContext.Provider value={value}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </SessionContext.Provider>
  );
}
