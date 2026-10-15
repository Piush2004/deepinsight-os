"use client"

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { FileText, Eye, CheckCircle, Clock, Plus, X, XCircle } from 'lucide-react'
import { useApiClient } from '@/hooks/useApiClient'
import { useSelectedClient } from '@/hooks/useSelectedClient'
import { ClientPicker } from '@/components/ui/ClientPicker'
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/StateViews'
import type { ReportSummary } from '@/lib/api'

const STATUS_META: Record<string, { label: string; icon: typeof Clock; color: string }> = {
  pending_approval: { label: 'Pending Approval', icon: Clock, color: 'text-accent' },
  approved: { label: 'Approved', icon: CheckCircle, color: 'text-secondary' },
  rejected: { label: 'Rejected', icon: XCircle, color: 'text-destructive' },
  draft: { label: 'Draft', icon: FileText, color: 'text-muted-foreground' },
}

function statusMeta(status: string) {
  return STATUS_META[status] ?? { label: status, icon: FileText, color: 'text-muted-foreground' }
}

export default function ReportsDashboard() {
  const api = useApiClient()
  const queryClient = useQueryClient()
  const { clientId, setClientId, clients, isLoading: clientLoading } = useSelectedClient()
  const [showGenerateForm, setShowGenerateForm] = useState(false)
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null)

  const reportsQuery = useQuery({
    queryKey: ['reports', clientId],
    queryFn: () => api.reports.list(clientId as string),
    enabled: !!clientId,
  })

  const generateMutation = useMutation({
    mutationFn: (vars: { reportingPeriod: string; metrics: Record<string, number> }) =>
      api.reports.generate(clientId as string, vars.reportingPeriod, vars.metrics),
    onSuccess: (data) => {
      // In dev/demo mode (CELERY_EAGER=true) the agent already ran synchronously by
      // the time this resolves - reflect the real outcome instead of a blanket
      // "started" message. Against a real Celery worker, status stays "processing"
      // and this falls through to the generic message, which is still correct there.
      if (data.status === 'failed') {
        toast.error(`Report generation did not pass validation: ${data.error ?? 'unknown error'}`)
      } else if (data.status === 'completed') {
        toast.success('Report generated and is pending approval.')
      } else {
        toast.success('Report generation started - it will appear here once the agent finishes.')
      }
      setShowGenerateForm(false)
      queryClient.invalidateQueries({ queryKey: ['reports', clientId] })
    },
    onError: (err: Error) => toast.error(`Failed to start report generation: ${err.message}`),
  })

  if (clientLoading) return <LoadingState label="Loading clients..." />
  if (clients.length === 0) {
    return (
      <div className="p-8">
        <EmptyState
          title="No clients yet"
          description="Create a client first from the Client Portals page before generating reports."
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full space-y-8 p-8 max-w-7xl mx-auto font-body">
      <div className="flex justify-between items-end border-b border-border pb-6">
        <div>
          <h1 className="text-4xl font-heading font-medium tracking-tight text-foreground">Reporting Engine</h1>
          <p className="text-muted-foreground mt-2 text-sm max-w-xl">
            Narrative-first executive reporting. Powered by DeepInsight OS.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ClientPicker clients={clients} clientId={clientId} onChange={setClientId} />
          <button
            onClick={() => setShowGenerateForm(true)}
            className="bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-2.5 rounded-md transition-colors font-medium shadow-sm flex items-center space-x-2 text-sm"
          >
            <Plus className="w-4 h-4" />
            <span>New Report</span>
          </button>
        </div>
      </div>

      {showGenerateForm && clientId && (
        <GenerateReportForm
          onCancel={() => setShowGenerateForm(false)}
          onSubmit={(vars) => generateMutation.mutate(vars)}
          isPending={generateMutation.isPending}
        />
      )}

      {reportsQuery.isLoading && <LoadingState label="Loading reports..." />}
      {reportsQuery.isError && (
        <ErrorState message={(reportsQuery.error as Error).message} onRetry={() => reportsQuery.refetch()} />
      )}
      {reportsQuery.data && reportsQuery.data.reports.length === 0 && (
        <EmptyState title="No reports yet" description="Generate your first report for this client above." />
      )}

      {reportsQuery.data && reportsQuery.data.reports.length > 0 && (
        <div className="space-y-4">
          {reportsQuery.data.reports.map((report: ReportSummary) => {
            const meta = statusMeta(report.status)
            return (
              <div
                key={report.id}
                className="p-6 bg-card border border-border rounded-lg shadow-sm hover:border-primary/50 transition-colors flex items-center justify-between group cursor-pointer"
                onClick={() => setSelectedReportId(report.id)}
              >
                <div className="flex items-center space-x-6">
                  <div className="p-3 bg-muted text-muted-foreground rounded-md group-hover:text-primary transition-colors">
                    <meta.icon className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="font-heading font-medium text-lg text-foreground group-hover:text-primary transition-colors">
                      {report.title}
                    </h3>
                    <div className="flex flex-wrap text-sm text-muted-foreground mt-1.5 space-x-4">
                      <span>Period: <strong>{report.reporting_period}</strong></span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center space-x-8">
                  <div className={`flex items-center space-x-1.5 text-sm font-medium ${meta.color}`}>
                    <span>{meta.label}</span>
                  </div>
                  <button className="text-muted-foreground hover:text-foreground transition-colors p-2 flex items-center">
                    <span className="sr-only">View</span>
                    <Eye className="w-5 h-5" />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {selectedReportId && (
        <ReportDetailModal reportId={selectedReportId} onClose={() => setSelectedReportId(null)} />
      )}
    </div>
  )
}

function GenerateReportForm({
  onCancel,
  onSubmit,
  isPending,
}: {
  onCancel: () => void
  onSubmit: (vars: { reportingPeriod: string; metrics: Record<string, number> }) => void
  isPending: boolean
}) {
  const [reportingPeriod, setReportingPeriod] = useState('')
  const [metricsText, setMetricsText] = useState('{\n  "ctr": 0.04,\n  "sessions": 1200\n}')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!reportingPeriod.trim()) {
      setError('Reporting period is required.')
      return
    }
    let metrics: Record<string, number>
    try {
      metrics = JSON.parse(metricsText)
    } catch {
      setError('Metrics must be valid JSON, e.g. {"ctr": 0.04}')
      return
    }
    setError(null)
    onSubmit({ reportingPeriod, metrics })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 bg-card border border-border rounded-lg p-6">
      <div className="flex items-center justify-between">
        <h2 className="font-heading font-medium text-lg">Generate a new report</h2>
        <button type="button" onClick={onCancel} className="text-muted-foreground hover:text-foreground">
          <X className="w-5 h-5" />
        </button>
      </div>
      <div className="space-y-2">
        <label className="block text-sm font-medium text-foreground">Reporting Period</label>
        <input
          type="text"
          value={reportingPeriod}
          onChange={(e) => setReportingPeriod(e.target.value)}
          placeholder="e.g. August 2026"
          className="w-full bg-background border border-border rounded-md p-3 text-foreground outline-none focus:ring-1 focus:ring-ring"
        />
      </div>
      <div className="space-y-2">
        <label className="block text-sm font-medium text-foreground">Metrics (JSON)</label>
        <textarea
          rows={5}
          value={metricsText}
          onChange={(e) => setMetricsText(e.target.value)}
          className="w-full bg-background border border-border rounded-md p-3 text-foreground outline-none focus:ring-1 focus:ring-ring font-mono text-sm"
        />
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <button
        type="submit"
        disabled={isPending}
        className="w-full bg-primary hover:bg-primary/90 disabled:opacity-50 text-primary-foreground font-medium py-3 rounded-md transition-colors shadow-sm"
      >
        {isPending ? 'Starting generation...' : 'Generate Report'}
      </button>
    </form>
  )
}

function ReportDetailModal({ reportId, onClose }: { reportId: string; onClose: () => void }) {
  const api = useApiClient()
  const queryClient = useQueryClient()
  const [comment, setComment] = useState('')
  const [rejectReason, setRejectReason] = useState('')
  const [showRejectForm, setShowRejectForm] = useState(false)

  const detailQuery = useQuery({
    queryKey: ['report', reportId],
    queryFn: () => api.reports.get(reportId),
  })

  const approveMutation = useMutation({
    mutationFn: () => api.reports.approve(reportId),
    onSuccess: () => {
      toast.success('Report approved')
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      onClose()
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const rejectMutation = useMutation({
    mutationFn: (reason: string) => api.reports.reject(reportId, reason),
    onSuccess: () => {
      toast.success('Report sent back for revision')
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      onClose()
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const commentMutation = useMutation({
    mutationFn: (text: string) => api.reports.comment(reportId, text),
    onSuccess: () => {
      toast.success('Comment added')
      setComment('')
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const data = detailQuery.data as { title?: string; status?: string; versions?: Array<{ content_text?: string }> } | undefined
  const latestVersion = data?.versions?.[0]

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-lg shadow-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-8 space-y-6"
        onClick={(e) => e.stopPropagation()}
      >
        {detailQuery.isLoading && <LoadingState label="Loading report..." />}
        {detailQuery.isError && <ErrorState message={(detailQuery.error as Error).message} />}
        {data && (
          <>
            <div className="flex justify-between items-start border-b border-border pb-4">
              <h2 className="text-xl font-heading font-medium">{data.title}</h2>
              <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="prose prose-slate dark:prose-invert max-w-none whitespace-pre-wrap text-sm text-foreground leading-relaxed">
              {latestVersion?.content_text || 'No content generated yet.'}
            </div>

            {data.status === 'pending_approval' && (
              <div className="flex items-center justify-between pt-4 border-t border-border">
                <button
                  onClick={() => setShowRejectForm((v) => !v)}
                  className="flex items-center px-4 py-2 border border-border hover:bg-muted text-foreground rounded-md text-sm font-medium transition-colors"
                >
                  <XCircle className="w-4 h-4 mr-2" />
                  Request Revisions
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

            {showRejectForm && (
              <div className="space-y-2">
                <textarea
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Why does this need revision?"
                  className="w-full bg-background border border-border rounded-md p-3 text-sm outline-none focus:ring-1 focus:ring-ring"
                  rows={3}
                />
                <button
                  onClick={() => rejectMutation.mutate(rejectReason)}
                  disabled={!rejectReason.trim() || rejectMutation.isPending}
                  className="text-sm font-medium text-destructive disabled:opacity-50"
                >
                  Submit revision request
                </button>
              </div>
            )}

            <div className="space-y-2 pt-4 border-t border-border">
              <label className="block text-sm font-medium text-foreground">Add comment</label>
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
