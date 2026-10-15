/**
 * Whether Clerk has the credentials it needs to actually function. Both the
 * publishable key (client-side) and secret key (server-side/middleware) are
 * required - having only one still leaves the app unable to authenticate.
 *
 * Centralized here because both src/proxy.ts (middleware) and
 * src/app/layout.tsx (ClerkProvider) need the identical check, and they must
 * never disagree about whether Clerk is configured.
 */
export function isClerkConfigured(): boolean {
  return Boolean(
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY
  )
}

export const CLERK_MISSING_CONFIG_MESSAGE =
  'DeepInsight OS: Clerk is not configured. ' +
  'Set NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY and CLERK_SECRET_KEY ' +
  '(apps/frontend/.env.local) before starting the app. ' +
  'Get development keys at https://dashboard.clerk.com/last-active?path=api-keys.'
