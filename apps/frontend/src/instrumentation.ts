import { isClerkConfigured, CLERK_MISSING_CONFIG_MESSAGE } from '@/lib/clerk-config'

/**
 * Runs once when a new Next.js server instance starts, before any request is
 * handled (see node_modules/next/dist/docs/.../instrumentation.md). This is
 * the correct place to fail fast on missing required configuration instead
 * of letting every individual request rediscover the same problem as an
 * opaque mid-render crash (confirmed live: without this, every route -
 * including /sign-in - returned a bare HTTP 500 from deep inside Clerk's
 * compiled code, with no indication at the process level of what was wrong).
 */
export async function register() {
  if (process.env.NEXT_RUNTIME !== 'nodejs') return
  if (isClerkConfigured()) return

  if (process.env.NODE_ENV === 'production') {
    // A production deployment with no auth provider configured must never start.
    // Throwing alone isn't enough here - confirmed live that Next.js logs the
    // instrumentation error clearly but still leaves the HTTP server listening,
    // 500ing every request from then on (the exact broken-but-alive state this
    // check exists to prevent). Exiting explicitly is what actually stops that.
    console.error(`\n${CLERK_MISSING_CONFIG_MESSAGE}\n`)
    // Accessed dynamically, not as `process.exit(1)` directly - this function body is
    // unreachable in the Edge runtime (guarded above), but Next's bundler can't prove
    // that statically and otherwise flags process.exit as an Edge-incompatible Node
    // API at build time even though it never actually runs there.
    process['exit'](1)
  }

  // Development: don't block `next dev` from starting so the rest of the app stays
  // hackable without Clerk keys - but make the gap loud and impossible to miss.
  // src/proxy.ts and src/app/layout.tsx independently check the same condition to
  // render a clear "not configured" state instead of a raw crash.
  console.error(`\n${CLERK_MISSING_CONFIG_MESSAGE}\n`)
}
