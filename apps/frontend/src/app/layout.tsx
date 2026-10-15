import { ClerkProvider } from '@clerk/nextjs'
import { CommandPalette } from '@/components/ui/CommandPalette'
import { QueryProvider } from '@/lib/query-provider'
import { Inter } from 'next/font/google'
import { isClerkConfigured } from '@/lib/clerk-config'
import { isDemoMode } from '@/lib/demo-auth'
import { DemoBanner } from '@/components/ui/DemoBanner'
import './globals.css'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })

// Only reachable in development - src/instrumentation.ts fails the server at startup
// in production before any request is handled, so this component never renders there
// with a missing key. This replaces what used to be a raw, unlabeled HTTP 500 from
// deep inside Clerk's compiled code (confirmed live during infra-closure verification)
// with an explicit, actionable state - not a bypass of authentication, since nothing
// auth-gated is reachable either way until Clerk is actually configured.
function MissingClerkConfigScreen() {
  return (
    <html lang="en">
      <body className={inter.variable}>
        <main style={{ maxWidth: 640, margin: '4rem auto', padding: '0 1.5rem', fontFamily: 'system-ui, sans-serif', lineHeight: 1.6 }}>
          <h1 style={{ fontSize: '1.5rem', marginBottom: '1rem' }}>Clerk authentication is not configured</h1>
          <p>
            DeepInsight OS requires Clerk credentials to run, even in development. Set{' '}
            <code>NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code> and <code>CLERK_SECRET_KEY</code> in{' '}
            <code>apps/frontend/.env.local</code>, then restart the dev server.
          </p>
          <p>
            Get development keys at{' '}
            <a href="https://dashboard.clerk.com/last-active?path=api-keys">dashboard.clerk.com</a>.
          </p>
        </main>
      </body>
    </html>
  )
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // Demo mode is a deliberate opt-in (NEXT_PUBLIC_AUTH_MODE=demo, see
  // src/lib/demo-auth.ts) for running the real app end-to-end without Clerk
  // credentials, mirroring api/core/security.py's AUTH_MODE=demo backend bypass.
  // Distinct from just "Clerk isn't configured yet" below, which still shows the
  // informative screen for a developer who hasn't deliberately chosen this.
  if (isDemoMode()) {
    return (
      <html lang="en">
        <body className={inter.variable}>
          <QueryProvider>
            <DemoBanner />
            <CommandPalette />
            {children}
          </QueryProvider>
        </body>
      </html>
    )
  }

  if (!isClerkConfigured()) {
    return <MissingClerkConfigScreen />
  }

  return (
    <ClerkProvider afterSignOutUrl="/sign-in">
      <html lang="en">
        <body className={inter.variable}>
          <QueryProvider>
            <CommandPalette />
            {children}
          </QueryProvider>
        </body>
      </html>
    </ClerkProvider>
  )
}
