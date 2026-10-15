"use client"

import { useQueries, useQuery } from '@tanstack/react-query'
import { Building, CheckCircle2, FileText, PenTool, Plug, ChevronRight } from 'lucide-react'
import Link from 'next/link'
import { useApiClient } from '@/hooks/useApiClient'
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/StateViews'
import type { ReportSummary, ContentSummary } from '@/lib/api'

export default function ExecutiveCommandCenter() {
  const api = useApiClient()

  const clientsQuery = useQuery({
    queryKey: ['clients', 'list'],
    queryFn: () => api.clients.list({ limit: 100 }),
  })

  const clients = clientsQuery.data ?? []

  // No agency-wide aggregate endpoint exists on the backend yet (every report/content
  // endpoint is client-scoped by design - see Rule 2 in docs/PROJECT_RULES.md), so this
  // fans out per-client and sums real results client-side rather than faking a number.
  const reportsQueries = useQueries({
    queries: clients.map((c) => ({
      queryKey: ['reports', c.id],
      queryFn: () => api.reports.list(c.id),
      enabled: clients.length > 0,
    })),
  })
  const contentQueries = useQueries({
    queries: clients.map((c) => ({
      queryKey: ['content', c.id],
      queryFn: () => api.content.list(c.id),
      enabled: clients.length > 0,
    })),
  })

  const pendingReports: Array<ReportSummary & { clientName: string }> = []
  reportsQueries.forEach((q, i) => {
    q.data?.reports.forEach((r) => {
      if (r.status === 'pending_approval') pendingReports.push({ ...r, clientName: clients[i]?.name ?? '' })
    })
  })

  const pendingContent: Array<ContentSummary & { clientName: string }> = []
  contentQueries.forEach((q, i) => {
    q.data?.content.forEach((c) => {
      if (c.status === 'pending_review') pendingContent.push({ ...c, clientName: clients[i]?.name ?? '' })
    })
  })

  const isAggregating = reportsQueries.some((q) => q.isLoading) || contentQueries.some((q) => q.isLoading)

  if (clientsQuery.isLoading) return <LoadingState label="Loading portfolio..." />
  if (clientsQuery.isError) {
    return <ErrorState message={(clientsQuery.error as Error).message} onRetry={() => clientsQuery.refetch()} />
  }

  return (
    <div className="flex flex-col h-full space-y-12 p-8 max-w-[1400px] mx-auto font-body">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end border-b border-border pb-6 gap-4">
        <div>
          <h1 className="text-4xl font-heading font-medium tracking-tight text-foreground">Executive Command Center</h1>
          <p className="text-muted-foreground mt-2 text-sm max-w-xl">
            Agency-wide intelligence and portfolio health.
          </p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <MetricCard icon={Building} label="Active Clients" value={clients.length} href="/clients" />
        <MetricCard
          icon={FileText}
          label="Reports Awaiting Approval"
          value={isAggregating ? '...' : pendingReports.length}
          href="/reports"
        />
        <MetricCard
          icon={PenTool}
          label="Content Drafts Pending Review"
          value={isAggregating ? '...' : pendingContent.length}
          href="/content"
        />
      </div>

      {clients.length === 0 && (
        <EmptyState
          title="No clients yet"
          description="Add your first client to start generating reports and content."
          action={
            <Link href="/clients" className="text-sm font-medium text-primary hover:underline">
              Go to Client Portals &rarr;
            </Link>
          }
        />
      )}

      {clients.length > 0 && (
        <div className="grid gap-8 lg:grid-cols-2">
          <div className="space-y-4">
            <h2 className="text-xl font-heading font-medium flex items-center">
              <CheckCircle2 className="w-5 h-5 mr-2 text-primary" />
              Reports Awaiting Approval
            </h2>
            {isAggregating && <LoadingState label="Aggregating across clients..." />}
            {!isAggregating && pendingReports.length === 0 && (
              <EmptyState title="Nothing pending" description="All reports are up to date across your portfolio." />
            )}
            {!isAggregating && pendingReports.length > 0 && (
              <div className="space-y-3">
                {pendingReports.slice(0, 5).map((r) => (
                  <Link
                    key={r.id}
                    href="/reports"
                    className="block p-4 bg-card border border-border rounded-lg shadow-sm hover:border-primary/50 transition-colors group"
                  >
                    <div className="flex items-start space-x-3">
                      <FileText className="w-4 h-4 text-secondary mt-0.5" />
                      <div>
                        <h4 className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">{r.title}</h4>
                        <p className="text-xs text-muted-foreground mt-1">{r.clientName}</p>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-4">
            <h2 className="text-xl font-heading font-medium flex items-center">
              <PenTool className="w-5 h-5 mr-2 text-purple-500" />
              Content Drafts Pending Review
            </h2>
            {isAggregating && <LoadingState label="Aggregating across clients..." />}
            {!isAggregating && pendingContent.length === 0 && (
              <EmptyState title="Nothing pending" description="All content is up to date across your portfolio." />
            )}
            {!isAggregating && pendingContent.length > 0 && (
              <div className="space-y-3">
                {pendingContent.slice(0, 5).map((c) => (
                  <Link
                    key={c.id}
                    href="/content"
                    className="block p-4 bg-card border border-border rounded-lg shadow-sm hover:border-primary/50 transition-colors group"
                  >
                    <div className="flex items-start space-x-3">
                      <PenTool className="w-4 h-4 text-purple-500 mt-0.5" />
                      <div>
                        <h4 className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">{c.title}</h4>
                        <p className="text-xs text-muted-foreground mt-1">{c.clientName}</p>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <Link
        href="/settings/integrations"
        className="flex items-center justify-between p-5 bg-card border border-border rounded-lg shadow-sm hover:border-primary/50 transition-colors"
      >
        <div className="flex items-center space-x-3">
          <Plug className="w-5 h-5 text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">Manage data integrations</span>
        </div>
        <ChevronRight className="w-4 h-4 text-muted-foreground" />
      </Link>
    </div>
  )
}

function MetricCard({
  icon: Icon,
  label,
  value,
  href,
}: {
  icon: typeof Building
  label: string
  value: number | string
  href: string
}) {
  return (
    <Link href={href} className="p-6 rounded-xl bg-card border border-border shadow-sm flex flex-col hover:border-primary/30 transition-colors">
      <Icon className="w-5 h-5 text-primary mb-4" />
      <p className="text-3xl font-heading font-medium text-foreground mb-1">{value}</p>
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
    </Link>
  )
}
