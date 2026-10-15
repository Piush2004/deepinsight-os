"use client"

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Calendar, Edit3, CheckCircle, XCircle, MessageSquare, X } from 'lucide-react'
import { useApiClient } from '@/hooks/useApiClient'
import { useSelectedClient } from '@/hooks/useSelectedClient'
import { ClientPicker } from '@/components/ui/ClientPicker'
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/StateViews'
import type { ContentSummary } from '@/lib/api'

// Values must match a real prompts/content/{value}.md file (see
// api/core/agent/content_agent.py's content_type.lower().replace(" ", "_") mapping) -
// only expose a type here once its prompt template genuinely exists, per this
// project's own rule against pretending unsupported content types work.
const CONTENT_TYPES: Array<{ value: string; label: string }> = [
  { value: 'blog', label: 'Blog Post' },
  { value: 'linkedin', label: 'LinkedIn Post' },
  { value: 'email', label: 'Email' },
  { value: 'social', label: 'Social Post' },
]

export default function ContentPlatform() {
  const api = useApiClient()
  const queryClient = useQueryClient()
  const { clientId, setClientId, clients, isLoading: clientLoading } = useSelectedClient()
  const [activeTab, setActiveTab] = useState('library') // library, generator, calendar, approval
  const [selectedContentId, setSelectedContentId] = useState<string | null>(null)

  const contentQuery = useQuery({
    queryKey: ['content', clientId],
    queryFn: () => api.content.list(clientId as string),
    enabled: !!clientId,
  })

  const pendingQuery = useQuery({
    queryKey: ['content', clientId, 'pending_review'],
    queryFn: () => api.content.list(clientId as string, { status: 'pending_review' }),
    enabled: !!clientId && activeTab === 'approval',
  })

  const generateMutation = useMutation({
    mutationFn: (vars: { contentType: string; targetAudience: string; goal: string }) =>
      api.content.generate(clientId as string, vars.contentType, vars.targetAudience, vars.goal),
    onSuccess: (data) => {
      // See reports/page.tsx's identical branch - dev/demo mode (CELERY_EAGER=true)
      // already ran the agent synchronously by the time this resolves.
      if (data.status === 'failed') {
        toast.error(`Content generation did not pass validation: ${data.error ?? 'unknown error'}`)
      } else if (data.status === 'completed') {
        toast.success('Content generated and is pending review.')
      } else {
        toast.success('Content generation started - it will appear in the Library once ready.')
      }
      setActiveTab('library')
      queryClient.invalidateQueries({ queryKey: ['content', clientId] })
    },
    onError: (err: Error) => toast.error(`Failed to start content generation: ${err.message}`),
  })

  if (clientLoading) return <LoadingState label="Loading clients..." />
  if (clients.length === 0) {
    return (
      <div className="p-10">
        <EmptyState
          title="No clients yet"
          description="Create a client first from the Client Portals page before generating content."
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full space-y-8 p-10 bg-background min-h-screen text-foreground font-body">
      <div className="flex justify-between items-end border-b border-border pb-6">
        <div>
          <h1 className="text-4xl font-heading font-medium tracking-tight text-foreground">Content Intelligence</h1>
          <p className="text-muted-foreground mt-2 text-sm max-w-xl">
            Manage your brand narrative. Generate, review, and schedule premium marketing assets.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ClientPicker clients={clients} clientId={clientId} onChange={setClientId} />
          <button
            onClick={() => setActiveTab('generator')}
            className="bg-primary text-primary-foreground hover:bg-primary/90 px-6 py-2.5 rounded-md transition-colors font-medium shadow-sm flex items-center space-x-2 text-sm"
          >
            <Edit3 className="w-4 h-4" />
            <span>New Draft</span>
          </button>
        </div>
      </div>

      <div className="flex space-x-8">
        {[
          { id: 'library', label: 'Library' },
          { id: 'calendar', label: 'Calendar' },
          { id: 'generator', label: 'Generator' },
          { id: 'approval', label: 'Approval Queue' },
        ].map((tab) => (
          <button
            key={tab.id}
            className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === tab.id
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 bg-card rounded-xl border border-border p-8 shadow-sm">
        {activeTab === 'library' && (
          <div className="space-y-6">
            <h2 className="text-xl font-heading font-medium">Recent Assets</h2>
            {contentQuery.isLoading && <LoadingState label="Loading content..." />}
            {contentQuery.isError && (
              <ErrorState message={(contentQuery.error as Error).message} onRetry={() => contentQuery.refetch()} />
            )}
            {contentQuery.data && contentQuery.data.content.length === 0 && (
              <EmptyState title="No content yet" description="Generate your first draft from the Generator tab." />
            )}
            {contentQuery.data && contentQuery.data.content.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-6">
                {contentQuery.data.content.map((item: ContentSummary) => (
                  <div
                    key={item.id}
                    onClick={() => setSelectedContentId(item.id)}
                    className="p-6 border border-border rounded-lg hover:border-primary/30 transition-colors bg-background flex flex-col group cursor-pointer"
                  >
                    <div className="flex justify-between items-start mb-4">
                      <span className="text-xs bg-muted text-muted-foreground px-2.5 py-1 rounded-sm font-medium uppercase tracking-wider">
                        {item.content_type}
                      </span>
                      <StatusBadge status={item.status} />
                    </div>
                    <h3 className="font-medium text-lg leading-snug group-hover:text-primary transition-colors">
                      {item.title}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-auto pt-6">
                      Created {new Date(item.created_at).toLocaleDateString()}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'calendar' && (
          <ContentCalendarTab
            content={contentQuery.data?.content ?? []}
            isLoading={contentQuery.isLoading}
            onSelect={setSelectedContentId}
          />
        )}

        {activeTab === 'generator' && clientId && (
          <GeneratorForm
            onSubmit={(vars) => generateMutation.mutate(vars)}
            isPending={generateMutation.isPending}
          />
        )}

        {activeTab === 'approval' && (
          <div className="max-w-4xl mx-auto space-y-8">
            {pendingQuery.isLoading && <LoadingState label="Loading approval queue..." />}
            {pendingQuery.data && pendingQuery.data.content.length === 0 && (
              <EmptyState title="Nothing pending review" description="New drafts will show up here for approval." />
            )}
            {pendingQuery.data && pendingQuery.data.content.length > 0 && (
              <div className="space-y-4">
                {pendingQuery.data.content.map((item: ContentSummary) => (
                  <div
                    key={item.id}
                    onClick={() => setSelectedContentId(item.id)}
                    className="p-4 border border-border rounded-lg hover:border-primary/50 cursor-pointer flex items-center justify-between"
                  >
                    <span className="font-medium">{item.title}</span>
                    <StatusBadge status={item.status} />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {selectedContentId && (
        <ContentDetailModal contentId={selectedContentId} onClose={() => setSelectedContentId(null)} />
      )}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const isApproved = status === 'approved'
  return (
    <span className={`text-xs font-medium flex items-center ${isApproved ? 'text-secondary' : 'text-muted-foreground'}`}>
      {isApproved ? <CheckCircle className="w-3 h-3 mr-1" /> : null}
      {status.replace('_', ' ')}
    </span>
  )
}

function ContentCalendarTab({
  content,
  isLoading,
  onSelect,
}: {
  content: ContentSummary[]
  isLoading: boolean
  onSelect: (id: string) => void
}) {
  const scheduled = content
    .filter((c) => c.scheduled_date)
    .sort((a, b) => new Date(a.scheduled_date as string).getTime() - new Date(b.scheduled_date as string).getTime())

  // Grouped by calendar date rather than a full month grid - real, interactive, and
  // scales to however many items exist without building/depending on a calendar
  // library for what's currently a straightforward scheduling need.
  const groups = new Map<string, ContentSummary[]>()
  scheduled.forEach((c) => {
    const key = new Date(c.scheduled_date as string).toLocaleDateString(undefined, {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
    })
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(c)
  })

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-heading font-medium">Content Calendar</h2>
      {isLoading && <LoadingState label="Loading calendar..." />}
      {!isLoading && scheduled.length === 0 && (
        <EmptyState
          title="Nothing scheduled yet"
          description="Approve a draft, then set a publication date from its detail view to see it appear here."
        />
      )}
      {!isLoading && scheduled.length > 0 && (
        <div className="space-y-6">
          {Array.from(groups.entries()).map(([date, items]) => (
            <div key={date} className="space-y-2">
              <h3 className="text-sm font-medium text-muted-foreground">{date}</h3>
              <div className="space-y-2">
                {items.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => onSelect(item.id)}
                    className="w-full text-left flex items-center justify-between p-4 bg-background border border-border rounded-lg hover:border-primary/50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <Calendar className="w-4 h-4 text-muted-foreground" />
                      <div>
                        <p className="text-sm font-medium text-foreground">{item.title}</p>
                        <p className="text-xs text-muted-foreground uppercase tracking-wider">{item.content_type}</p>
                      </div>
                    </div>
                    <StatusBadge status={item.status} />
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function GeneratorForm({
  onSubmit,
  isPending,
}: {
  onSubmit: (vars: { contentType: string; targetAudience: string; goal: string }) => void
  isPending: boolean
}) {
  const [contentType, setContentType] = useState(CONTENT_TYPES[0].value)
  const [targetAudience, setTargetAudience] = useState('')
  const [goal, setGoal] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!targetAudience.trim() || !goal.trim()) return
    onSubmit({ contentType, targetAudience, goal })
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-3xl mx-auto space-y-8 py-4">
      <div className="text-center space-y-2">
        <h2 className="text-2xl font-heading font-medium">Create a New Draft</h2>
        <p className="text-muted-foreground">Our AI will generate a strong starting point aligned with your brand voice.</p>
      </div>

      <div className="space-y-6 bg-background p-8 rounded-lg border border-border">
        <div className="space-y-2">
          <label className="block text-sm font-medium text-foreground">Content Type</label>
          <select
            value={contentType}
            onChange={(e) => setContentType(e.target.value)}
            className="w-full bg-background border border-border rounded-md p-3 text-foreground outline-none focus:ring-1 focus:ring-ring"
          >
            {CONTENT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <label className="block text-sm font-medium text-foreground">Target Audience</label>
          <input
            type="text"
            value={targetAudience}
            onChange={(e) => setTargetAudience(e.target.value)}
            placeholder="e.g., Enterprise CTOs looking for efficiency"
            className="w-full bg-background border border-border rounded-md p-3 text-foreground outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div className="space-y-2">
          <label className="block text-sm font-medium text-foreground">Strategic Goal</label>
          <textarea
            rows={4}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="Drive awareness for our new analytics feature..."
            className="w-full bg-background border border-border rounded-md p-3 text-foreground outline-none focus:ring-1 focus:ring-ring resize-none"
          />
        </div>
        <div className="pt-4">
          <button
            type="submit"
            disabled={isPending || !targetAudience.trim() || !goal.trim()}
            className="w-full bg-primary hover:bg-primary/90 disabled:opacity-50 text-primary-foreground font-medium py-3 rounded-md transition-colors shadow-sm"
          >
            {isPending ? 'Starting generation...' : 'Generate Draft'}
          </button>
        </div>
      </div>
    </form>
  )
}

function ContentDetailModal({ contentId, onClose }: { contentId: string; onClose: () => void }) {
  const api = useApiClient()
  const queryClient = useQueryClient()
  const [comment, setComment] = useState('')
  const [rejectReason, setRejectReason] = useState('')
  const [showRejectForm, setShowRejectForm] = useState(false)

  const detailQuery = useQuery({
    queryKey: ['content-detail', contentId],
    queryFn: () => api.content.get(contentId),
  })

  const approveMutation = useMutation({
    mutationFn: () => api.content.approve(contentId),
    onSuccess: () => {
      toast.success('Content approved')
      queryClient.invalidateQueries({ queryKey: ['content'] })
      onClose()
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const rejectMutation = useMutation({
    mutationFn: (reason: string) => api.content.reject(contentId, reason),
    onSuccess: () => {
      toast.success('Sent back for revision')
      queryClient.invalidateQueries({ queryKey: ['content'] })
      onClose()
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const commentMutation = useMutation({
    mutationFn: (text: string) => api.content.comment(contentId, text),
    onSuccess: () => {
      toast.success('Comment added')
      setComment('')
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const scheduleMutation = useMutation({
    mutationFn: (date: string | null) => api.content.schedule(contentId, date),
    onSuccess: () => {
      toast.success('Schedule updated')
      queryClient.invalidateQueries({ queryKey: ['content-detail', contentId] })
      queryClient.invalidateQueries({ queryKey: ['content'] })
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const data = detailQuery.data as
    | { title?: string; status?: string; body?: string; scheduled_date?: string | null }
    | undefined
  const [scheduleDraft, setScheduleDraft] = useState('')

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-lg shadow-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-8 space-y-6"
        onClick={(e) => e.stopPropagation()}
      >
        {detailQuery.isLoading && <LoadingState label="Loading content..." />}
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
              {data.body || 'No content generated yet.'}
            </div>

            {data.status === 'pending_review' && (
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
                  Approve Draft
                </button>
              </div>
            )}

            {showRejectForm && (
              <div className="space-y-2">
                <textarea
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="What needs to change?"
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

            {data.status === 'approved' && (
              <div className="space-y-2 pt-4 border-t border-border">
                <label className="flex items-center text-sm font-medium text-foreground">
                  <Calendar className="w-4 h-4 mr-2" /> Schedule for publication
                </label>
                <div className="flex gap-2">
                  <input
                    type="date"
                    defaultValue={data.scheduled_date ? data.scheduled_date.slice(0, 10) : ''}
                    onChange={(e) => setScheduleDraft(e.target.value)}
                    className="flex-1 bg-background border border-border rounded-md p-2 text-sm outline-none focus:ring-1 focus:ring-ring"
                  />
                  <button
                    onClick={() => scheduleMutation.mutate(scheduleDraft ? `${scheduleDraft}T09:00:00` : null)}
                    disabled={scheduleMutation.isPending}
                    className="px-4 py-2 bg-muted hover:bg-muted/70 disabled:opacity-50 rounded-md text-sm font-medium"
                  >
                    {data.scheduled_date ? 'Update' : 'Set date'}
                  </button>
                  {data.scheduled_date && (
                    <button
                      onClick={() => scheduleMutation.mutate(null)}
                      disabled={scheduleMutation.isPending}
                      className="px-3 py-2 text-muted-foreground hover:text-destructive text-sm"
                    >
                      Clear
                    </button>
                  )}
                </div>
                {data.scheduled_date && (
                  <p className="text-xs text-muted-foreground">
                    Currently scheduled for {new Date(data.scheduled_date).toLocaleDateString()}
                  </p>
                )}
              </div>
            )}

            <div className="space-y-2 pt-4 border-t border-border">
              <label className="flex items-center text-sm font-medium text-foreground">
                <MessageSquare className="w-4 h-4 mr-2" /> Add Comment
              </label>
              <div className="flex gap-2">
                <input
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Leave editorial feedback..."
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
