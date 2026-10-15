"use client"

import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { Building, FileText, PenTool, BookOpen, Plug, Search } from 'lucide-react'
import Link from 'next/link'
import { useApiClient } from '@/hooks/useApiClient'
import { LoadingState, ErrorState } from '@/components/ui/StateViews'
import { DeepInsightProfile } from '@/components/knowledge/DeepInsightProfile'

export default function ClientWorkspace() {
  const { clientId } = useParams<{ clientId: string }>()
  const api = useApiClient()

  const clientQuery = useQuery({
    queryKey: ['client', clientId],
    queryFn: () => api.clients.get(clientId),
    enabled: !!clientId,
  })

  const reportsQuery = useQuery({
    queryKey: ['reports', clientId],
    queryFn: () => api.reports.list(clientId),
    enabled: !!clientId,
  })

  const contentQuery = useQuery({
    queryKey: ['content', clientId],
    queryFn: () => api.content.list(clientId),
    enabled: !!clientId,
  })

  const documentsQuery = useQuery({
    queryKey: ['documents', clientId],
    queryFn: () => api.documents.list(clientId),
    enabled: !!clientId,
  })

  const seoSummaryQuery = useQuery({
    queryKey: ['seo-summary', clientId],
    queryFn: () => api.seo.summary(clientId),
    enabled: !!clientId,
  })

  if (clientQuery.isLoading) return <LoadingState label="Loading client..." />
  if (clientQuery.isError) {
    return <ErrorState message={(clientQuery.error as Error).message} onRetry={() => clientQuery.refetch()} />
  }
  const client = clientQuery.data
  if (!client) return null

  return (
    <div className="flex flex-col h-full space-y-12 p-8 max-w-7xl mx-auto font-body">
      <div className="flex justify-between items-start border-b border-border pb-10">
        <div className="flex items-center space-x-6">
          <div className="w-20 h-20 bg-primary/10 rounded-xl flex items-center justify-center border border-primary/20">
            <Building className="w-10 h-10 text-primary" />
          </div>
          <div>
            <h1 className="text-4xl font-heading font-medium tracking-tight text-foreground">{client.name}</h1>
            <p className="text-muted-foreground mt-2 text-sm max-w-2xl leading-relaxed">
              {client.description || client.industry || 'No description set for this client yet.'}
            </p>
            <span className="inline-block mt-2 text-xs uppercase tracking-wider text-muted-foreground">
              {client.status}
            </span>
          </div>
        </div>
      </div>

      <DeepInsightProfile clientId={clientId} documentCount={documentsQuery.data?.documents.length ?? 0} />

      <div className="grid gap-6 md:grid-cols-4">
        <StatCard
          icon={BookOpen}
          label="Knowledge Documents"
          value={documentsQuery.data?.documents.length ?? (documentsQuery.isLoading ? '...' : 0)}
          href="/knowledge"
        />
        <StatCard
          icon={FileText}
          label="Reports"
          value={reportsQuery.data?.reports.length ?? (reportsQuery.isLoading ? '...' : 0)}
          href="/reports"
        />
        <StatCard
          icon={PenTool}
          label="Content Drafts"
          value={contentQuery.data?.content.length ?? (contentQuery.isLoading ? '...' : 0)}
          href="/content"
        />
        <StatCard
          icon={Search}
          label="SEO Opportunities"
          value={seoSummaryQuery.data?.total_open_opportunities ?? (seoSummaryQuery.isLoading ? '...' : 0)}
          href="/seo"
        />
      </div>

      <div className="grid gap-8 md:grid-cols-2">
        <div className="p-8 rounded-xl bg-card border border-border shadow-sm flex flex-col space-y-4">
          <div className="flex items-center space-x-3 border-b border-border/50 pb-4">
            <div className="p-2 bg-blue-500/10 text-blue-600 rounded-md">
              <Building className="w-5 h-5" />
            </div>
            <h2 className="text-xl font-heading font-medium">Client Details</h2>
          </div>
          <dl className="text-sm space-y-3">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Industry</dt>
              <dd className="text-foreground font-medium">{client.industry || '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Website</dt>
              <dd className="text-foreground font-medium">{client.website || '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Client since</dt>
              <dd className="text-foreground font-medium">{new Date(client.created_at).toLocaleDateString()}</dd>
            </div>
          </dl>
        </div>

        <div className="p-8 rounded-xl bg-card border border-border shadow-sm flex flex-col space-y-4">
          <div className="flex items-center space-x-3 border-b border-border/50 pb-4">
            <div className="p-2 bg-purple-500/10 text-purple-600 rounded-md">
              <Plug className="w-5 h-5" />
            </div>
            <h2 className="text-xl font-heading font-medium">Get started</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Upload brand documents to the Knowledge Base, connect analytics integrations, then generate a report or content draft grounded in this client&apos;s real data.
          </p>
          <Link href="/settings/integrations" className="text-sm font-medium text-primary hover:underline">
            Manage integrations &rarr;
          </Link>
        </div>
      </div>
    </div>
  )
}

function StatCard({
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
    <Link href={href} className="p-6 bg-card border border-border rounded-xl shadow-sm hover:border-primary/50 transition-colors flex items-center gap-4">
      <div className="p-3 bg-muted rounded-md text-muted-foreground">
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-2xl font-heading font-medium text-foreground">{value}</p>
        <p className="text-sm text-muted-foreground">{label}</p>
      </div>
    </Link>
  )
}
