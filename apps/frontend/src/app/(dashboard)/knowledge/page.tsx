"use client"

import { useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { Upload, FileText, Trash2, Search, CheckCircle2, Loader2 } from "lucide-react"
import { useApiClient } from "@/hooks/useApiClient"
import { useSelectedClient } from "@/hooks/useSelectedClient"
import { ClientPicker } from "@/components/ui/ClientPicker"
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/StateViews"
import type { DocumentSummary } from "@/lib/api"

export default function KnowledgeBasePage() {
  const api = useApiClient()
  const queryClient = useQueryClient()
  const { clientId, setClientId, clients, isLoading: clientLoading } = useSelectedClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState("")
  const [queryResult, setQueryResult] = useState<{ content: string; sources: string[]; grounded: boolean } | null>(null)

  const documentsQuery = useQuery({
    queryKey: ["documents", clientId],
    queryFn: () => api.documents.list(clientId as string),
    enabled: !!clientId,
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.documents.upload(clientId as string, file),
    onSuccess: (data) => {
      toast.success(`${data.status === "completed" ? "Uploaded and processed" : "Uploaded"} - ready for retrieval.`)
      queryClient.invalidateQueries({ queryKey: ["documents", clientId] })
    },
    onError: (err: Error) => toast.error(`Upload failed: ${err.message}`),
  })

  const deleteMutation = useMutation({
    mutationFn: (documentId: string) => api.documents.remove(documentId),
    onSuccess: () => {
      toast.success("Document removed.")
      queryClient.invalidateQueries({ queryKey: ["documents", clientId] })
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const queryMutation = useMutation({
    mutationFn: (q: string) => api.knowledge.query(clientId as string, q),
    onSuccess: (data) => setQueryResult(data),
    onError: (err: Error) => toast.error(`Query failed: ${err.message}`),
  })

  function handleFilePicked(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) uploadMutation.mutate(file)
    e.target.value = ""
  }

  if (clientLoading) return <LoadingState label="Loading clients..." />
  if (clients.length === 0) {
    return (
      <div className="p-8">
        <EmptyState title="No clients yet" description="Create a client first from the Client Portals page." />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full space-y-8 p-8 max-w-6xl mx-auto font-body">
      <div className="flex justify-between items-end border-b border-border pb-6">
        <div>
          <h1 className="text-4xl font-heading font-medium tracking-tight text-foreground">Knowledge Base</h1>
          <p className="text-muted-foreground mt-2 text-sm max-w-xl">
            Brand documents, campaign notes, and business context that ground every report and content draft.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ClientPicker clients={clients} clientId={clientId} onChange={setClientId} />
          <input ref={fileInputRef} type="file" accept=".txt,.md,.markdown,.pdf" className="hidden" onChange={handleFilePicked} />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadMutation.isPending}
            className="bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 px-6 py-2.5 rounded-md transition-colors font-medium shadow-sm flex items-center gap-2 text-sm"
          >
            {uploadMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            <span>Upload Document</span>
          </button>
        </div>
      </div>

      <div className="bg-card border border-border rounded-lg p-6 space-y-4">
        <h2 className="font-heading font-medium text-lg flex items-center gap-2">
          <Search className="w-4 h-4 text-muted-foreground" />
          Search the knowledge base
        </h2>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (query.trim() && clientId) queryMutation.mutate(query)
          }}
          className="flex gap-2"
        >
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. What is the brand voice?"
            className="flex-1 bg-background border border-border rounded-md p-3 text-sm outline-none focus:ring-1 focus:ring-ring"
          />
          <button
            type="submit"
            disabled={queryMutation.isPending || !query.trim()}
            className="px-6 py-2.5 bg-muted hover:bg-muted/70 disabled:opacity-50 rounded-md text-sm font-medium"
          >
            {queryMutation.isPending ? "Searching..." : "Search"}
          </button>
        </form>
        {queryResult && (
          <div className="rounded-md border border-border bg-muted/40 p-4 space-y-2">
            <div className="flex items-center gap-2 text-xs font-medium">
              {queryResult.grounded ? (
                <span className="flex items-center gap-1 text-secondary">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Grounded - {queryResult.sources.length} source{queryResult.sources.length === 1 ? "" : "s"}
                </span>
              ) : (
                <span className="text-muted-foreground">Not grounded - no relevant content found</span>
              )}
            </div>
            <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">{queryResult.content}</p>
          </div>
        )}
      </div>

      {documentsQuery.isLoading && <LoadingState label="Loading documents..." />}
      {documentsQuery.isError && (
        <ErrorState message={(documentsQuery.error as Error).message} onRetry={() => documentsQuery.refetch()} />
      )}
      {documentsQuery.data && documentsQuery.data.documents.length === 0 && (
        <EmptyState
          title="No documents yet"
          description="Upload brand voice guides, campaign notes, or positioning docs to ground reports and content in this client's real context."
        />
      )}
      {documentsQuery.data && documentsQuery.data.documents.length > 0 && (
        <div className="space-y-3">
          {documentsQuery.data.documents.map((doc: DocumentSummary) => (
            <div
              key={doc.id}
              className="p-5 bg-card border border-border rounded-lg shadow-sm flex items-center justify-between"
            >
              <div className="flex items-center gap-4">
                <div className="p-2.5 bg-muted text-muted-foreground rounded-md">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <p className="font-medium text-foreground">{doc.title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {doc.mime_type} &middot; {(doc.file_size / 1024).toFixed(1)} KB &middot;{" "}
                    {new Date(doc.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <StatusPill status={doc.status} />
                <button
                  onClick={() => deleteMutation.mutate(doc.id)}
                  disabled={deleteMutation.isPending}
                  className="text-muted-foreground hover:text-destructive transition-colors p-2"
                  aria-label="Delete document"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function StatusPill({ status }: { status: string }) {
  const color =
    status === "completed" ? "text-secondary bg-secondary/10" : status === "processing" ? "text-accent bg-accent/10" : "text-muted-foreground bg-muted"
  return <span className={`text-xs font-medium px-2.5 py-1 rounded-full capitalize ${color}`}>{status}</span>
}
