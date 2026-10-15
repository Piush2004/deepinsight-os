"use client"

import { useMemo, useState } from "react"
import { useQueries, useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { FileText, PenTool, CheckCircle, XCircle, Clock, X } from "lucide-react"
import { useApiClient } from "@/hooks/useApiClient"
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/StateViews"
import type { ReportSummary, ContentSummary } from "@/lib/api"

type ApprovalKind = "report" | "content"

interface ApprovalItem {
  kind: ApprovalKind
  id: string
  clientId: string
  clientName: string
  title: string
  status: string
  createdAt: string
}

const TABS = [
  { key: "all", label: "All" },
  { key: "report", label: "Reports" },
  { key: "content", label: "Content" },
] as const

/** Aggregates pending reports + content across every client the current user can see,
 * since neither /reports nor /content exposes a cross-client "everything pending"
 * endpoint - this fetches per-client (bounded by however many real clients exist) and
 * merges client-side. Every item here is real data from real endpoints, not fabricated. */
export default function ApprovalCenterPage() {
  const api = useApiClient()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<(typeof TABS)[number]["key"]>("all")
  const [selected, setSelected] = useState<ApprovalItem | null>(null)

  const clientsQuery = useQuery({ queryKey: ["clients"], queryFn: () => api.clients.list() })
  const clients = useMemo(() => clientsQuery.data ?? [], [clientsQuery.data])

  const reportQueries = useQueries({
    queries: clients.map((c) => ({
      queryKey: ["reports", c.id],
      queryFn: () => api.reports.list(c.id),
      enabled: clients.length > 0,
    })),
  })
  const contentQueries = useQueries({
    queries: clients.map((c) => ({
      queryKey: ["content", c.id],
      queryFn: () => api.content.list(c.id),
      enabled: clients.length > 0,
    })),
  })

  const isLoading =
    clientsQuery.isLoading ||
    reportQueries.some((q) => q.isLoading) ||
    contentQueries.some((q) => q.isLoading)

  const items: ApprovalItem[] = useMemo(() => {
    const out: ApprovalItem[] = []
    clients.forEach((client, i) => {
      const reports = (reportQueries[i]?.data?.reports ?? []) as ReportSummary[]
      reports
        .filter((r) => r.status === "pending_approval")
        .forEach((r) =>
          out.push({ kind: "report", id: r.id, clientId: client.id, clientName: client.name, title: r.title, status: r.status, createdAt: r.created_at })
        )
      const content = (contentQueries[i]?.data?.content ?? []) as ContentSummary[]
      content
        .filter((c) => c.status === "pending_review")
        .forEach((c) =>
          out.push({ kind: "content", id: c.id, clientId: client.id, clientName: client.name, title: c.title, status: c.status, createdAt: c.created_at })
        )
    })
    return out.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  }, [clients, reportQueries, contentQueries])

  const filtered = tab === "all" ? items : items.filter((i) => i.kind === tab)

  function refreshAll() {
    queryClient.invalidateQueries({ queryKey: ["reports"] })
    queryClient.invalidateQueries({ queryKey: ["content"] })
  }

  return (
    <div className="flex flex-col h-full space-y-8 p-8 max-w-6xl mx-auto font-body">
      <div className="border-b border-border pb-6">
        <h1 className="text-4xl font-heading font-medium tracking-tight text-foreground">Approval Center</h1>
        <p className="text-muted-foreground mt-2 text-sm max-w-2xl">
          Every AI-generated report and content draft waits here before it becomes anything client-facing.
        </p>
      </div>

      <div className="flex gap-2 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
            {t.key !== "all" && (
              <span className="ml-2 text-xs text-muted-foreground">
                ({items.filter((i) => i.kind === t.key).length})
              </span>
            )}
          </button>
        ))}
      </div>

      {isLoading && <LoadingState label="Loading pending approvals..." />}
      {!isLoading && clientsQuery.isError && (
        <ErrorState message={(clientsQuery.error as Error).message} onRetry={() => clientsQuery.refetch()} />
      )}
      {!isLoading && !clientsQuery.isError && filtered.length === 0 && (
        <EmptyState
          title="Nothing waiting for review"
          description="There isn't anything waiting for review yet. Generate a report or content draft to see it appear here."
        />
      )}

      {!isLoading && filtered.length > 0 && (
        <div className="space-y-3">
          {filtered.map((item) => (
            <button
              key={`${item.kind}-${item.id}`}
              onClick={() => setSelected(item)}
              className="w-full text-left p-5 bg-card border border-border rounded-lg shadow-sm hover:border-primary/50 transition-colors flex items-center justify-between group"
            >
              <div className="flex items-center gap-4">
                <div className="p-2.5 bg-muted text-muted-foreground rounded-md group-hover:text-primary transition-colors">
                  {item.kind === "report" ? <FileText className="w-5 h-5" /> : <PenTool className="w-5 h-5" />}
                </div>
                <div>
                  <p className="font-medium text-foreground group-hover:text-primary transition-colors">{item.title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {item.clientName} &middot; {item.kind === "report" ? "Report" : "Content"} &middot;{" "}
                    {new Date(item.createdAt).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1.5 text-xs font-medium text-accent">
                <Clock className="w-3.5 h-3.5" />
                Pending
              </div>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <ApprovalDetailPanel
          item={selected}
          onClose={() => setSelected(null)}
          onResolved={() => {
            setSelected(null)
            refreshAll()
          }}
        />
      )}
    </div>
  )
}

function ApprovalDetailPanel({
  item,
  onClose,
  onResolved,
}: {
  item: ApprovalItem
  onClose: () => void
  onResolved: () => void
}) {
  const api = useApiClient()
  const [rejectReason, setRejectReason] = useState("")
  const [showReject, setShowReject] = useState(false)

  const detailQuery = useQuery({
    queryKey: [item.kind, item.id],
    queryFn: () => (item.kind === "report" ? api.reports.get(item.id) : api.content.get(item.id)),
  })

  const approveMutation = useMutation({
    mutationFn: () => (item.kind === "report" ? api.reports.approve(item.id) : api.content.approve(item.id)),
    onSuccess: () => {
      toast.success(`${item.kind === "report" ? "Report" : "Content"} approved.`)
      onResolved()
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const rejectMutation = useMutation({
    mutationFn: (reason: string) => (item.kind === "report" ? api.reports.reject(item.id, reason) : api.content.reject(item.id, reason)),
    onSuccess: () => {
      toast.success("Sent back for revision.")
      onResolved()
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const data = detailQuery.data as
    | { title?: string; status?: string; body?: string; scores?: Record<string, number>; versions?: Array<{ content_text?: string }> }
    | undefined
  const bodyText = item.kind === "report" ? data?.versions?.[0]?.content_text : data?.body

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-lg shadow-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-8 space-y-6"
        onClick={(e) => e.stopPropagation()}
      >
        {detailQuery.isLoading && <LoadingState label="Loading..." />}
        {detailQuery.isError && <ErrorState message={(detailQuery.error as Error).message} />}
        {data && (
          <>
            <div className="flex justify-between items-start border-b border-border pb-4">
              <div>
                <h2 className="text-xl font-heading font-medium">{data.title ?? item.title}</h2>
                <p className="text-sm text-muted-foreground mt-1">{item.clientName}</p>
              </div>
              <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
                <X className="w-5 h-5" />
              </button>
            </div>

            {data.scores && (
              <div className="grid grid-cols-3 gap-3">
                {Object.entries(data.scores).map(([key, value]) => (
                  <div key={key} className="bg-muted rounded-md p-3 text-center">
                    <p className="text-lg font-heading font-medium text-foreground">{typeof value === "number" ? value.toFixed(0) : value}</p>
                    <p className="text-xs text-muted-foreground capitalize">{key.replace(/_/g, " ")}</p>
                  </div>
                ))}
              </div>
            )}

            <div className="prose prose-slate dark:prose-invert max-w-none whitespace-pre-wrap text-sm text-foreground leading-relaxed">
              {bodyText || "No content generated yet."}
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-border">
              <button
                onClick={() => setShowReject((v) => !v)}
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

            {showReject && (
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
          </>
        )}
      </div>
    </div>
  )
}
