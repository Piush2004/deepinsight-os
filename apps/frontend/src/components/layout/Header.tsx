"use client";

import { UserButton } from "@clerk/nextjs";
import { isDemoMode } from "@/lib/demo-auth";

export function Header() {
  return (
    <header className="flex h-16 items-center justify-between border-b border-zinc-200 bg-white px-6 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center">
        {/* Mobile menu button could go here */}
      </div>
      <div className="flex items-center gap-4">
        {/* UserButton requires a real ClerkProvider, which demo mode deliberately
         * doesn't mount (see src/app/layout.tsx) - the DemoBanner already shows who
         * you're viewing as. */}
        {!isDemoMode() && <UserButton />}
      </div>
    </header>
  );
}
