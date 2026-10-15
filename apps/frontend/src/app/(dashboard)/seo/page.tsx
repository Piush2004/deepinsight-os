"use client"

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  TrendingUp, TrendingDown, Zap, Sparkles, X, CheckCircle, XCircle,
  Info, ArrowUpRight, ArrowDownRight, ArrowRight, Play,
} from 'lucide-react'
import { useApiClient } from '@/hooks/useApiClient'
import { useSelectedClient } from '@/hooks/useSelectedClient'
import { ClientPicker } from '@/components/ui/ClientPicker'
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/StateViews'
import type { SEOOpportunitySummary } from '@/lib/api'

type Category = 'QUICK_WIN' | 'GROWTH_OPPORTUNITY' | 'PERFORMANCE_RISK' | 'EMERGING_MOMENTUM'

const CATEGORY_META: Record<Category, { label: string; description: string; icon: typeof Zap; accent: string }> = {
  QUICK_WIN: {
    label: 'Quick Wins',
    description: 'Low-effort fixes with strong existing visibility.',
    icon: Zap,
    accent: 'text-secondary bg-secondary/10',
  },
  GROWTH_OPPORTUNITY: {
    label: 'Growth Opportunities',
    description: 'Positions worth pushing toward page one.',
    icon: TrendingUp,
    accent: 'text-primary bg-primary/10',
  },
  PERFORMANCE_RISK: {
    label: 'Performance Risks',
    description: 'Real declines worth investigating now.',
    icon: TrendingDown,
    accent: 'text-destructive bg-destructive/10',
  },
  EMERGING_MOMENTUM: {
    label: 'Emerging Momentum',
    description: 'Keywords already trending the right direction.',
    icon: Sparkles,
    accent: 'text-accent bg-accent/10',
  },
}

const CATEGORY_ORDER: Category[] = ['QUICK_WIN', 'GROWTH_OPPORTUNITY', 'PERFORMANCE_RISK', 'EMERGING_MOMENTUM']

function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setUTCDate(d.getUTCDate() - days)
  return d.toISOString().slice(0, 10)
}

export default function SEOIntelligencePage() {
  const api = useApiClient()
  const queryClient = useQueryClient()
  const { clientId, setClientId, clients, isLoading: clientLoading } = useSelectedClient()
  const [activeCategory, setActiveCategory] = useState<Category | null>(null)
  const [selectedOpportunityId, setSelectedOpportunityId] = useState<string | null>(null)
  const [showAnalyzeForm, setShowAnalyzeForm] = useState(false)

  const summaryQuery = useQuery({
    queryKey: ['seo-summary', clientId],
    queryFn: () => api.seo.summary(clientId as string),
    enabled: !!clientId,
  })

  const opportunitiesQuery = useQuery({
    queryKey: ['seo-opportunities', clientId, activeCategory],
    queryFn: () => api.seo.listOpportunities(clientId as string, { category: activeCategory ?? undefined }),
    enabled: !!clientId,
  })

  const analyzeMutation = useMutation({
    mutationFn: (vars: { periodStart: string; periodEnd: string }) =>
      api.seo.analyze(clientId as string, vars.periodStart, vars.periodEnd),
    onSuccess: (data) => {
      if (data.status === 'failed') {
        toast.error(`SEO analysis did not pass validation: ${data.error ?? 'unknown error'}`)
      } else if (data.status === 'completed') {
        toast.success('SEO analysis complete - opportunities are ready for review.')
      } else {
        toast.success('SEO analysis started - opportunities will appear here once the agent finishes.')
      }
      setShowAnalyzeForm(false)
      queryClient.invalidateQueries({ queryKey: ['seo-summary', clientId] })
      queryClient.invalidateQueries({ queryKey: ['seo-opportunities', clientId] })
    },
    onError: (err: Error) => toast.error(`Failed to start SEO analysis: ${err.message}`),
  })

  if (clientLoading) return <LoadingState label="Loading clients..." />
  if (clients.length === 0) {
    return (
      <div className="p-8">
        <EmptyState
          title="No clients yet"
          description="Create a client first from the Client Portals page before running SEO analysis."
        />
      </div>
    )
  }

  const summary = summaryQuery.data
  const opportunities = opportunitiesQuery.data?.opportunities ?? []

  return (
    <div className="flex flex-col h-full space-y-8 p-8 max-w-7xl mx-auto font-body">
      <div className="flex justify-between items-end border-b border-border pb-6">
        <div>
          <h1 className="text-4xl font-heading font-medium tracking-tight text-foreground">SEO Intelligence</h1>
          <p className="text-muted-foreground mt-2 text-sm max-w-xl">
            Deterministic rules detect the opportunity; the strategist explains why it matters. Every number here traces back to real search performance data.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ClientPicker clients={clients} clientId={clientId} onChange={setClientId} />
          <button
            onClick={() => setShowAnalyzeForm(true)}
            className="bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-2.5 rounded-md transition-colors font-medium shadow-sm flex items-center space-x-2 text-sm"
          >
            <Play className="w-4 h-4" />
            <span>Run Analysis</span>
          </button>
        </div>
      </div>

      <div className="flex items-start gap-3 rounded-lg border border-accent/30 bg-accent/5 p-4 text-sm text-foreground/80">
        <Info className="w-4 h-4 mt-0.5 flex-shrink-0 text-accent" />
        <p>
          Google Search Console is not connected yet. Development data is currently available for testing - every
          opportunity below is produced by the same deterministic rule engine and LLM strategist that will run
          against live GSC data once that connector ships.
        </p>
      </div>

      {showAnalyzeForm && clientId && (
        <AnalyzeForm
          onCancel={() => setShowAnalyzeForm(false)}
          onSubmit={(vars) => analyzeMutation.mutate(vars)}
          isPending={analyzeMutation.isPending}
        />
      )}

      {summaryQuery.isLoading && <LoadingState label="Loading SEO summary..." />}
      {summaryQuery.isError && (
        <ErrorState message={(summaryQuery.error as Error).message} onRetry={() => summaryQuery.refetch()} />
      )}

      {summary && !summary.has_analysis && (
        <EmptyState
          title="No SEO analysis yet"
          description="Run your first analysis above to detect ranking, CTR, and traffic opportunities for this client."
        />
      )}

      {summary?.latest_analysis?.executive_summary && (
        <div className="p-6 bg-card border border-border rounded-lg shadow-sm space-y-2">
          <h2 className="font-heading font-medium text-lg text-foreground">Executive Summary</h2>
          <p className="text-sm text-foreground/80 leading-relaxed">{summary.latest_analysis.executive_summary}</p>
          <p className="text-xs text-muted-foreground pt-2">
            Period: {summary.latest_analysis.period_start} to {summary.latest_analysis.period_end} · Source: {summary.latest_analysis.data_provider}
          </p>
        </div>
      )}

      {summary && summary.has_analysis && (
        <div className="grid gap-6 md:grid-cols-4">
          {CATEGORY_ORDER.map((category) => {
            const meta = CATEGORY_META[category]
            const count = summary.category_counts[category]
            const isActive = activeCategory === category
            return (
              <button
                key={category}
                onClick={() => setActiveCategory(isActive ? null : category)}
                className={`text-left p-6 rounded-xl border bg-card shadow-sm transition-colors ${
                  isActive ? 'border-primary ring-1 ring-primary' : 'border-border hover:border-primary/50'
                }`}
              >
                <div className={`inline-flex p-2.5 rounded-md ${meta.accent}`}>
                  <meta.icon className="w-5 h-5" />
                </div>
                <p className="text-3xl font-heading font-medium text-foreground mt-4">{count}</p>
                <p className="text-sm font-medium text-foreground mt-1">{meta.label}</p>
                <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{meta.description}</p>
              </button>
            )
          })}
        </div>
      )}

      {summary?.has_analysis && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-heading font-medium text-lg text-foreground">
              {activeCategory ? CATEGORY_META[activeCategory].label : 'All Opportunities'}
            </h2>
            {activeCategory && (
              <button onClick={() => setActiveCategory(null)} className="text-sm text-muted-foreground hover:text-foreground">
                Clear filter
              </button>
            )}
          </div>

          {opportunitiesQuery.isLoading && <LoadingState label="Loading opportunities..." />}
          {opportunitiesQuery.isError && (
            <ErrorState message={(opportunitiesQuery.error as Error).message} onRetry={() => opportunitiesQuery.refetch()} />
          )}
          {opportunitiesQuery.data && opportunities.length === 0 && (
            <EmptyState title="No opportunities in this category" description="Try a different category or run a new analysis." />
          )}

          {opportunities.length > 0 && (
            <div className="space-y-3">
              {opportunities.map((opp: SEOOpportunitySummary) => (
                <OpportunityRow key={opp.id} opportunity={opp} onClick={() => setSelectedOpportunityId(opp.id)} />
              ))}
            </div>
          )}
        </div>
      )}

      {selectedOpportunityId && (
        <OpportunityDetailModal opportunityId={selectedOpportunityId} onClose={() => setSelectedOpportunityId(null)} />
      )}
    </div>
  )
}

function OpportunityRow({ opportunity, onClick }: { opportunity: SEOOpportunitySummary; onClick: () => void }) {
  const meta = CATEGORY_META[opportunity.category]
  const statusLabel =
    opportunity.status === 'approved' ? 'Approved' : opportunity.status === 'rejected' ? 'Rejected' : 'Pending Review'
  const statusColor =
    opportunity.status === 'approved'
      ? 'text-secondary'
      : opportunity.status === 'rejected'
        ? 'text-destructive'
        : 'text-accent'

  return (
    <div
      onClick={onClick}
      className="p-6 bg-card border border-border rounded-lg shadow-sm hover:border-primary/50 transition-colors flex items-center justify-between group cursor-pointer"
    >
      <div className="flex items-center space-x-6">
        <div className={`p-3 rounded-md ${meta.accent}`}>
          <meta.icon className="w-6 h-6" />
        </div>
        <div>
          <h3 className="font-heading font-medium text-lg text-foreground group-hover:text-primary transition-colors">
            {opportunity.title}
          </h3>
          <div className="flex flex-wrap text-sm text-muted-foreground mt-1.5 gap-x-4">
            <span>{opportunity.source_type === 'page' ? 'Page' : 'Keyword'}: <strong>{opportunity.source_entity}</strong></span>
            <span>Effort: <strong>{opportunity.effort_estimate}</strong></span>
            <span>Priority: <strong>{opportunity.priority_score.toFixed(0)}</strong></span>
          </div>
        </div>
      </div>
      <div className="flex items-center space-x-8">
        <div className={`flex items-center space-x-1.5 text-sm font-medium ${statusColor}`}>
          <span>{statusLabel}</span>
        </div>
        <ArrowRight className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
      </div>
    </div>
  )
}

function AnalyzeForm({
  onCancel,
  onSubmit,
  isPending,
}: {
  onCancel: () => void
  onSubmit: (vars: { periodStart: string; periodEnd: string }) => void
  isPending: boolean
}) {
  const [periodStart, setPeriodStart] = useState(isoDaysAgo(28))
  const [periodEnd, setPeriodEnd] = useState(isoDaysAgo(0))
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!periodStart || !periodEnd) {
      setError('Both a start and end date are required.')
      return
    }
    if (periodStart > periodEnd) {
      setError('Start date must be before end date.')
      return
    }
    setError(null)
    onSubmit({ periodStart, periodEnd })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 bg-card border border-border rounded-lg p-6">
      <div className="flex items-center justify-between">
        <h2 className="font-heading font-medium text-lg">Run a new SEO analysis</h2>
        <button type="button" onClick={onCancel} className="text-muted-foreground hover:text-foreground">
          <X className="w-5 h-5" />
        </button>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="block text-sm font-medium text-foreground">Period Start</label>
          <input
            type="date"
            value={periodStart}
            onChange={(e) => setPeriodStart(e.target.value)}
            className="w-full bg-background border border-border rounded-md p-3 text-foreground outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div className="space-y-2">
          <label className="block text-sm font-medium text-foreground">Period End</label>
          <input
            type="date"
            value={periodEnd}
            onChange={(e) => setPeriodEnd(e.target.value)}
            className="w-full bg-background border border-border rounded-md p-3 text-foreground outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <button
        type="submit"
        disabled={isPending}
        className="w-full bg-primary hover:bg-primary/90 disabled:opacity-50 text-primary-foreground font-medium py-3 rounded-md transition-colors shadow-sm"
      >
        {isPending ? 'Running analysis...' : 'Run Analysis'}
      </button>
    </form>
  )
}

function OpportunityDetailModal({ opportunityId, onClose }: { opportunityId: string; onClose: () => void }) {
  const api = useApiClient()
  const queryClient = useQueryClient()
  const [comment, setComment] = useState('')
  const [rejectReason, setRejectReason] = useState('')
  const [showRejectForm, setShowRejectForm] = useState(false)
  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [editedTitle, setEditedTitle] = useState('')

  const detailQuery = useQuery({
    queryKey: ['seo-opportunity', opportunityId],
    queryFn: () => api.seo.getOpportunity(opportunityId),
  })

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['seo-opportunity', opportunityId] })
    queryClient.invalidateQueries({ queryKey: ['seo-opportunities'] })
    queryClient.invalidateQueries({ queryKey: ['seo-summary'] })
  }

  const approveMutation = useMutation({
    mutationFn: () => api.seo.approve(opportunityId),
    onSuccess: () => {
      toast.success('Opportunity approved')
      invalidateAll()
      onClose()
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const rejectMutation = useMutation({
    mutationFn: (reason: string) => api.seo.reject(opportunityId, reason),
    onSuccess: () => {
      toast.success('Opportunity rejected')
      invalidateAll()
      onClose()
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const commentMutation = useMutation({
    mutationFn: (text: string) => api.seo.comment(opportunityId, text),
    onSuccess: () => {
      toast.success('Comment added')
      setComment('')
      queryClient.invalidateQueries({ queryKey: ['seo-opportunity', opportunityId] })
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const editMutation = useMutation({
    mutationFn: (title: string) => api.seo.update(opportunityId, { title }),
    onSuccess: () => {
      toast.success('Opportunity updated')
      setIsEditingTitle(false)
      invalidateAll()
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const data = detailQuery.data

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-lg shadow-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-8 space-y-6"
        onClick={(e) => e.stopPropagation()}
      >
        {detailQuery.isLoading && <LoadingState label="Loading opportunity..." />}
        {detailQuery.isError && <ErrorState message={(detailQuery.error as Error).message} />}
        {data && (
          <>
            <div className="flex justify-between items-start border-b border-border pb-4">
              <div className="flex-1 pr-4">
                {isEditingTitle ? (
                  <div className="flex items-center gap-2">
                    <input
                      value={editedTitle}
                      onChange={(e) => setEditedTitle(e.target.value)}
                      className="flex-1 bg-background border border-border rounded-md p-2 text-lg font-heading font-medium outline-none focus:ring-1 focus:ring-ring"
                    />
                    <button
                      onClick={() => editedTitle.trim() && editMutation.mutate(editedTitle)}
                      disabled={editMutation.isPending}
                      className="text-sm font-medium text-primary"
                    >
                      Save
                    </button>
                    <button onClick={() => setIsEditingTitle(false)} className="text-sm text-muted-foreground">
                      Cancel
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <h2 className="text-xl font-heading font-medium">{data.title}</h2>
                    <button
                      onClick={() => {
                        setEditedTitle(data.title)
                        setIsEditingTitle(true)
                      }}
                      className="text-xs font-medium text-muted-foreground hover:text-primary"
                    >
                      Edit
                    </button>
                  </div>
                )}
                <p className="text-sm text-muted-foreground mt-1">
                  {data.source_type === 'page' ? 'Page' : 'Keyword'}: <strong>{data.source_entity}</strong> · {CATEGORY_META[data.category].label}
                </p>
              </div>
              <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
                <X className="w-5 h-5" />
              </button>
            </div>

            <ScoreRow data={data} />

            <Section title="Evidence">
              <ul className="space-y-1.5">
                {data.evidence.map((line, i) => (
                  <li key={i} className="text-sm text-foreground/80 flex items-start gap-2">
                    <span className="mt-1.5 h-1 w-1 rounded-full bg-muted-foreground flex-shrink-0" />
                    {line}
                  </li>
                ))}
              </ul>
            </Section>

            {data.strategic_explanation && (
              <Section title="Why It Matters">
                <p className="text-sm text-foreground/80 leading-relaxed">{data.strategic_explanation}</p>
              </Section>
            )}

            <Section title="Recommended Action">
              <ul className="space-y-1.5">
                {data.recommended_actions.map((action, i) => (
                  <li key={i} className="text-sm text-foreground/80 flex items-start gap-2">
                    <CheckCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-secondary" />
                    {action}
                  </li>
                ))}
              </ul>
            </Section>

            <MetricsSection metrics={data.metrics} />

            {data.evaluation_scores && (
              <Section title="Quality Evaluation">
                <div className="grid grid-cols-3 gap-3">
                  {Object.entries(data.evaluation_scores).map(([key, value]) => (
                    <div key={key} className="p-2.5 rounded-md bg-muted text-center">
                      <p className="text-lg font-heading font-medium text-foreground">
                        {typeof value === 'number' ? value.toFixed(0) : String(value)}
                      </p>
                      <p className="text-[11px] text-muted-foreground capitalize">{key.replace(/_/g, ' ')}</p>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {data.status === 'pending_review' && (
              <div className="flex items-center justify-between pt-4 border-t border-border">
                <button
                  onClick={() => setShowRejectForm((v) => !v)}
                  className="flex items-center px-4 py-2 border border-border hover:bg-muted text-foreground rounded-md text-sm font-medium transition-colors"
                >
                  <XCircle className="w-4 h-4 mr-2" />
                  Reject
                </button>
                <button
                  onClick={() => approveMutation.mutate()}
                  disabled={approveMutation.isPending}
                  className="flex items-center px-6 py-2 bg-primary hover:bg-primary/90 disabled:opacity-50 text-primary-foreground rounded-md text-sm font-medium transition-colors shadow-sm"
                >
                  <CheckCircle className="w-4 h-4 mr-2" />
                  Approve
                </button>
              </div>
            )}
            {data.status !== 'pending_review' && (
              <p className="text-sm text-muted-foreground pt-4 border-t border-border">
                This opportunity is <strong>{data.status}</strong>{data.approval?.comments ? `: ${data.approval.comments}` : '.'}
              </p>
            )}

            {showRejectForm && (
              <div className="space-y-2">
                <textarea
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Why isn't this a priority?"
                  className="w-full bg-background border border-border rounded-md p-3 text-sm outline-none focus:ring-1 focus:ring-ring"
                  rows={3}
                />
                <button
                  onClick={() => rejectMutation.mutate(rejectReason)}
                  disabled={!rejectReason.trim() || rejectMutation.isPending}
                  className="text-sm font-medium text-destructive disabled:opacity-50"
                >
                  Submit rejection
                </button>
              </div>
            )}

            <div className="space-y-3 pt-4 border-t border-border">
              <label className="block text-sm font-medium text-foreground">Comments</label>
              {data.comments.length > 0 && (
                <ul className="space-y-2">
                  {data.comments.map((c) => (
                    <li key={c.id} className="text-sm text-foreground/80 bg-muted rounded-md p-3">
                      {c.comment}
                    </li>
                  ))}
                </ul>
              )}
              <div className="flex gap-2">
                <input
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Leave a note for the team..."
                  className="flex-1 bg-background border border-border rounded-md p-2 text-sm outline-none focus:ring-1 focus:ring-ring"
                />
                <button
                  onClick={() => comment.trim() && commentMutation.mutate(comment)}
                  disabled={!comment.trim() || commentMutation.isPending}
                  className="px-4 py-2 bg-muted hover:bg-muted/70 disabled:opacity-50 rounded-md text-sm font-medium"
                >
                  Post
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-foreground uppercase tracking-wide text-xs">{title}</h3>
      {children}
    </div>
  )
}

function ScoreRow({ data }: { data: { priority_score: number; confidence_score: number; impact_score: number; effort_estimate: string } }) {
  return (
    <div className="grid grid-cols-4 gap-3">
      <div className="p-3 rounded-md bg-muted text-center">
        <p className="text-lg font-heading font-medium text-foreground">{data.priority_score.toFixed(0)}</p>
        <p className="text-[11px] text-muted-foreground">Priority</p>
      </div>
      <div className="p-3 rounded-md bg-muted text-center">
        <p className="text-lg font-heading font-medium text-foreground">{data.confidence_score.toFixed(0)}</p>
        <p className="text-[11px] text-muted-foreground">Confidence</p>
      </div>
      <div className="p-3 rounded-md bg-muted text-center">
        <p className="text-lg font-heading font-medium text-foreground">{data.impact_score.toFixed(0)}</p>
        <p className="text-[11px] text-muted-foreground">Impact</p>
      </div>
      <div className="p-3 rounded-md bg-muted text-center">
        <p className="text-lg font-heading font-medium text-foreground">{data.effort_estimate}</p>
        <p className="text-[11px] text-muted-foreground">Effort</p>
      </div>
    </div>
  )
}

const METRIC_LABELS: Record<string, string> = {
  impressions: 'Impressions',
  clicks: 'Clicks',
  ctr: 'CTR',
  position: 'Position',
  impressions_previous: 'Impressions (prior)',
  clicks_previous: 'Clicks (prior)',
  ctr_previous: 'CTR (prior)',
  position_previous: 'Position (prior)',
  page: 'Page',
}

function formatMetricValue(key: string, value: number | string | null): string {
  if (value === null || value === undefined) return '—'
  if (key === 'ctr' || key === 'ctr_previous') return `${(Number(value) * 100).toFixed(2)}%`
  if (key === 'position' || key === 'position_previous') return Number(value).toFixed(1)
  return String(value)
}

function MetricsSection({ metrics }: { metrics: Record<string, number | string | null> }) {
  const entries = Object.entries(metrics).filter(([key]) => key in METRIC_LABELS)
  if (entries.length === 0) return null

  const positionDelta =
    typeof metrics.position === 'number' && typeof metrics.position_previous === 'number'
      ? metrics.position_previous - metrics.position
      : null

  return (
    <Section title="Strategic Context: Search Performance">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {entries.map(([key, value]) => (
          <div key={key} className="p-3 rounded-md border border-border">
            <p className="text-sm font-medium text-foreground">{formatMetricValue(key, value)}</p>
            <p className="text-[11px] text-muted-foreground">{METRIC_LABELS[key]}</p>
          </div>
        ))}
      </div>
      {positionDelta !== null && positionDelta !== 0 && (
        <p className="text-xs text-muted-foreground flex items-center gap-1.5 pt-1">
          {positionDelta > 0 ? (
            <ArrowUpRight className="w-3.5 h-3.5 text-secondary" />
          ) : (
            <ArrowDownRight className="w-3.5 h-3.5 text-destructive" />
          )}
          Position {positionDelta > 0 ? 'improved' : 'worsened'} by {Math.abs(positionDelta).toFixed(1)} over the period.
        </p>
      )}
    </Section>
  )
}
