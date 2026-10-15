/**
 * Dev/demo-only auth bypass for the frontend, mirroring api/core/security.py's
 * AUTH_MODE=demo bypass on the backend. Deliberate, explicit opt-in
 * (NEXT_PUBLIC_AUTH_MODE=demo) - distinct from just "Clerk isn't configured yet",
 * which still shows the informative screen in src/app/layout.tsx. Never used in
 * production: this file only matters when isDemoMode() is true, which requires the
 * env var to be explicitly set.
 */

export interface DemoUser {
  clerkId: string;
  label: string;
  description: string;
}

export const DEMO_USERS: DemoUser[] = [
  { clerkId: "demo-admin", label: "Demo Admin", description: "Full access to every client" },
  { clerkId: "demo-manager", label: "Demo Manager", description: "Member of Aurora Wellness Collective only" },
];

const STORAGE_KEY = "deepinsight-demo-user";

export function isDemoMode(): boolean {
  return process.env.NEXT_PUBLIC_AUTH_MODE === "demo";
}

export function getDemoUser(): string {
  if (typeof window === "undefined") return DEMO_USERS[0].clerkId;
  try {
    return window.localStorage.getItem(STORAGE_KEY) || DEMO_USERS[0].clerkId;
  } catch {
    return DEMO_USERS[0].clerkId;
  }
}

export function setDemoUser(clerkId: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, clerkId);
  } catch {
    // ignore - non-fatal, just won't persist across reloads
  }
}
