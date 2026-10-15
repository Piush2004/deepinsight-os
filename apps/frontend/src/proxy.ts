import { NextResponse } from 'next/server';
import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server';
import { isClerkConfigured, CLERK_MISSING_CONFIG_MESSAGE } from '@/lib/clerk-config';

const isPublicRoute = createRouteMatcher(['/sign-in(.*)', '/sign-up(.*)']);

// Guarded rather than calling clerkMiddleware() unconditionally: without real Clerk
// keys, clerkMiddleware() itself throws deep inside its compiled code before any
// route/layout ever renders - every request, including /sign-in, previously surfaced
// as a bare HTTP 500 with no indication of the actual cause (confirmed live during
// infra-closure verification). See src/instrumentation.ts for the equivalent
// production-startup check and src/app/layout.tsx for the dev-mode fallback screen.
const handler = isClerkConfigured()
  ? clerkMiddleware(async (auth, request) => {
      if (!isPublicRoute(request)) {
        await auth.protect();
      }
    })
  : () => {
      if (process.env.NODE_ENV === 'production') {
        // Defense in depth: instrumentation.ts should already have failed the server
        // at startup in production. If some deployment topology reaches this branch
        // anyway (e.g. an edge-only runtime that skipped Node instrumentation), never
        // silently let a protected route through unauthenticated - fail loudly instead.
        throw new Error(CLERK_MISSING_CONFIG_MESSAGE);
      }
      // Development only: let the request through so layout.tsx can render a clear
      // "Clerk not configured" screen instead of a raw crash. There is no real
      // authentication to bypass in this state - Clerk cannot function at all
      // without these keys, in either direction.
      return NextResponse.next();
    };

export default handler;

export const config = {
  matcher: ['/((?!.*\\..*|_next).*)', '/', '/(api|trpc)(.*)'],
};
