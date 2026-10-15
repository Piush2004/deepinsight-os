"use client";

import { useCallback, useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import { useApiClient } from "@/hooks/useApiClient";

const STORAGE_KEY = "deepinsight:selected-client-id";
const CHANGE_EVENT = "deepinsight:selected-client-changed";

function subscribe(callback: () => void) {
  window.addEventListener(CHANGE_EVENT, callback);
  return () => window.removeEventListener(CHANGE_EVENT, callback);
}

function getSnapshot() {
  return window.localStorage.getItem(STORAGE_KEY);
}

function getServerSnapshot() {
  return null;
}

/** Every report/content/integration is client-scoped on the backend, but there's no
 * per-page client param in the nav - this persists the operator's last-picked client
 * across pages/reloads (localStorage via useSyncExternalStore, so it's hydration-safe
 * and doesn't need a setState-in-effect to sync from an external source), and hands
 * back the full client list so pages can render a picker + the resolved Client object. */
export function useSelectedClient() {
  const api = useApiClient();
  const storedClientId = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const setClientId = useCallback((id: string) => {
    window.localStorage.setItem(STORAGE_KEY, id);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }, []);

  const clientsQuery = useQuery({
    queryKey: ["clients", "list"],
    queryFn: () => api.clients.list({ limit: 100 }),
  });

  const clients = clientsQuery.data ?? [];
  // Fall back to the first available client when nothing's been picked yet, or the
  // stored id no longer matches a real client - computed, not stored, so there's
  // nothing to synchronize via an effect.
  const effectiveClientId =
    storedClientId && clients.some((c) => c.id === storedClientId) ? storedClientId : (clients[0]?.id ?? null);

  const selectedClient = clients.find((c) => c.id === effectiveClientId) ?? null;

  return {
    clientId: effectiveClientId,
    setClientId,
    selectedClient,
    clients,
    isLoading: clientsQuery.isLoading,
    error: clientsQuery.error,
  };
}
