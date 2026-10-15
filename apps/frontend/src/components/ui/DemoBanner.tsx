"use client"

import { useSyncExternalStore } from "react"
import { DEMO_USERS, getDemoUser, setDemoUser } from "@/lib/demo-auth"

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback)
  window.addEventListener("deepinsight-demo-user-changed", callback)
  return () => {
    window.removeEventListener("storage", callback)
    window.removeEventListener("deepinsight-demo-user-changed", callback)
  }
}

/** Always visible in dev/demo mode (NEXT_PUBLIC_AUTH_MODE=demo) - clearly labels the
 * app as running without real authentication, and lets a demo presenter switch between
 * seeded demo users live to show tenant-isolation behavior (Admin sees every client;
 * Manager only sees the one client it has membership on). Never rendered otherwise. */
export function DemoBanner() {
  const current = useSyncExternalStore(subscribe, getDemoUser, () => DEMO_USERS[0].clerkId)
  const activeUser = DEMO_USERS.find((u) => u.clerkId === current) ?? DEMO_USERS[0]

  function handleChange(clerkId: string) {
    setDemoUser(clerkId)
    window.dispatchEvent(new Event("deepinsight-demo-user-changed"))
  }

  return (
    <div className="flex items-center justify-center gap-3 bg-accent px-4 py-2 text-xs font-medium text-accent-foreground">
      <span>Demo mode - no real authentication. Viewing as:</span>
      <select
        value={activeUser.clerkId}
        onChange={(e) => handleChange(e.target.value)}
        className="rounded border border-accent-foreground/20 bg-white/70 px-2 py-1 text-xs font-medium text-accent-foreground"
      >
        {DEMO_USERS.map((u) => (
          <option key={u.clerkId} value={u.clerkId}>
            {u.label} - {u.description}
          </option>
        ))}
      </select>
    </div>
  )
}
