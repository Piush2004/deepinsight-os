"use client"

import { useState } from "react"
import { useQueries } from "@tanstack/react-query"
import Link from "next/link"
import { ChevronDown, Sparkles, BookOpen, RefreshCw } from "lucide-react"
import { useApiClient } from "@/hooks/useApiClient"
import { LoadingState } from "@/components/ui/StateViews"

interface ProfileField {
  key: string
  label: string
  question: string
}

// The exact same questions ReportingAgent.gather_context() / ContentAgent.gather_context()
// ask the real RAG knowledge service internally (api/core/agent/reporting_agent.py,
// api/core/agent/content_agent.py) - this profile shows the operator precisely what
// context those agents will actually see, not a separately-fabricated summary.
const PROFILE_FIELDS: ProfileField[] = [
  { key: "brand_voice", label: "Brand Voice", question: "What is the brand voice and tone?" },
  { key: "audience", label: "Target Audience", question: "Who is the target audience?" },
  { key: "goals", label: "Business Goals", question: "What are the business goals and objectives?" },
  { key: "campaigns", label: "Active Campaigns", question: "What were the active campaigns and objectives recently?" },
]

interface KnowledgeQueryResult {
  content: string
  sources: string[]
  grounded: boolean
}

/** The central intelligence summary for a client - real RAG queries against the real
 * knowledge base (no fabricated profile data), shown per-field with an honest "not yet
 * defined" state when nothing's been uploaded to ground that field. This is exactly
 * what every real report/content generation call sees as context, surfaced for a human
 * to inspect before trusting AI output grounded in it. */
export function DeepInsightProfile({ clientId, documentCount }: { clientId: string; documentCount: number }) {
  const api = useApiClient()
  const [expanded, setExpanded] = useState<string | null>(PROFILE_FIELDS[0].key)

  const queries = useQueries({
    queries: PROFILE_FIELDS.map((field) => ({
      queryKey: ["deep-insight-profile", clientId, field.key],
      queryFn: () => api.knowledge.query(clientId, field.question) as Promise<KnowledgeQueryResult>,
      enabled: !!clientId && documentCount > 0,
      staleTime: 60_000,
    })),
  })

  const isLoading = documentCount > 0 && queries.some((q) => q.isLoading)
  const groundedCount = queries.filter((q) => q.data?.grounded).length

  return (
    // shrink-0 is required, not cosmetic: this card is a flex item inside the parent
    // page's `flex flex-col h-full` layout. When the column's total content exceeds
    // the container height, flexbox's default flex-shrink:1 squashes every child
    // proportionally - siblings without overflow-hidden just visually escape their
    // shrunk box, but this card's overflow-hidden (needed to clip children to the
    // rounded corners) faithfully clips to that shrunk height instead, collapsing the
    // whole profile to a ~17px sliver despite its real content being ~1400px tall
    // (confirmed live: scrollHeight vs. getBoundingClientRect().height diverged
    // exactly this much). shrink-0 opts this card out of that shrink calculation.
    <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden shrink-0">
      <div className="flex items-center justify-between px-8 py-6 border-b border-border/50">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 text-primary rounded-md">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-heading font-medium text-foreground">Deep Insight Profile</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              What the AI team actually knows about this client, grounded in real uploaded documents.
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm font-medium text-foreground">
            {documentCount === 0 ? "No knowledge yet" : `${groundedCount}/${PROFILE_FIELDS.length} defined`}
          </p>
          <p className="text-xs text-muted-foreground">{documentCount} source document{documentCount === 1 ? "" : "s"}</p>
        </div>
      </div>

      {documentCount === 0 ? (
        <div className="px-8 py-10 text-center space-y-3">
          <BookOpen className="w-6 h-6 text-muted-foreground mx-auto" />
          <p className="text-sm text-foreground font-medium">This client&apos;s intelligence hub is ready for its first source.</p>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            Upload brand guidelines, campaign notes, or positioning docs and this profile will populate automatically -
            grounded in what you actually give it, never invented.
          </p>
          <Link
            href="/knowledge"
            className="inline-block mt-2 text-sm font-medium text-primary-foreground bg-primary hover:bg-primary/90 px-5 py-2.5 rounded-md transition-colors"
          >
            Upload Knowledge
          </Link>
        </div>
      ) : (
        <div className="divide-y divide-border/50">
          {PROFILE_FIELDS.map((field, i) => {
            const result = queries[i]?.data
            const loading = queries[i]?.isLoading
            const isOpen = expanded === field.key
            return (
              <div key={field.key}>
                <button
                  onClick={() => setExpanded(isOpen ? null : field.key)}
                  className="w-full flex items-center justify-between px-8 py-4 text-left hover:bg-muted/30 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-medium text-foreground">{field.label}</span>
                    {!loading && result && (
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          result.grounded ? "bg-secondary/10 text-secondary" : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {result.grounded ? `${result.sources.length} source${result.sources.length === 1 ? "" : "s"}` : "Not yet defined"}
                      </span>
                    )}
                  </div>
                  <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${isOpen ? "rotate-180" : ""}`} />
                </button>
                {isOpen && (
                  <div className="px-8 pb-5 -mt-1">
                    {loading && <LoadingState label="Querying knowledge base..." />}
                    {!loading && result?.grounded && (
                      <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap bg-muted/30 rounded-md p-4">
                        {result.content}
                      </p>
                    )}
                    {!loading && result && !result.grounded && (
                      <p className="text-sm text-muted-foreground italic">
                        Not yet defined - no uploaded document answers &ldquo;{field.question}&rdquo; yet.
                      </p>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {isLoading && documentCount > 0 && (
        <div className="px-8 py-2 border-t border-border/50 flex items-center gap-2 text-xs text-muted-foreground">
          <RefreshCw className="w-3 h-3 animate-spin" /> Refreshing profile from the knowledge base...
        </div>
      )}
    </div>
  )
}
