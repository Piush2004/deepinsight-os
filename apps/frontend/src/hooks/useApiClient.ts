"use client";

import { useMemo, useSyncExternalStore } from "react";
import { useAuth } from "@clerk/nextjs";
import { createApiClient } from "@/lib/api";
import { isDemoMode, getDemoUser } from "@/lib/demo-auth";

const noopToken = async () => null;

function subscribeToDemoUser(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("deepinsight-demo-user-changed", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("deepinsight-demo-user-changed", callback);
  };
}

function useDemoApiClient() {
  const demoUser = useSyncExternalStore(subscribeToDemoUser, getDemoUser, () => getDemoUser());
  return useMemo(() => createApiClient(noopToken, demoUser), [demoUser]);
}

function useClerkApiClient() {
  const { getToken } = useAuth();
  return useMemo(() => createApiClient(getToken), [getToken]);
}

// Resolved once at module scope (NEXT_PUBLIC_AUTH_MODE is a build-time constant, never
// changes at runtime), not inside a component - so every caller of useApiClient()
// consistently calls exactly one of these two hooks on every render, satisfying the
// Rules of Hooks. useAuth() is only ever actually invoked in the Clerk branch; in demo
// mode there is no <ClerkProvider> in the tree at all (see src/app/layout.tsx), and
// calling useAuth() without one would throw.
export const useApiClient = isDemoMode() ? useDemoApiClient : useClerkApiClient;
