"use client"

import Link from "next/link"
import { FileText, PenTool, BookOpen, Search, Mail, Share2, Megaphone, ArrowRight } from "lucide-react"

interface AgentDef {
  key: string
  name: string
  icon: typeof FileText
  benefit: string
  description: string
  status: "available" | "coming_soon"
  actionLabel?: string
  actionHref?: string
}

// Only "available" for agents with a real, wired backend pipeline (routers ->
// services -> BaseAgent -> Intelligence Layer -> persistence, per docs/PROJECT_RULES.md).
// The rest are real, planned roadmap items (docs/ROADMAP.md) shown honestly as not yet
// built - never a fake "Generate" button with nothing behind it.
const AGENTS: AgentDef[] = [
  {
    key: "reporting",
    name: "Reporting Intelligence",
    icon: FileText,
    benefit: "Turn performance data into clear strategic decisions.",
    description:
      "Runs raw metrics through the deterministic Rule Engine and Insight Engine before an LLM ever sees them, then grounds the narrative in this client's real knowledge base and gates it through the Evaluation Engine before it reaches you for approval.",
    status: "available",
    actionLabel: "Generate a Report",
    actionHref: "/reports",
  },
  {
    key: "content",
    name: "Content Intelligence",
    icon: PenTool,
    benefit: "Keep every piece of content aligned with the client's voice and goals.",
    description:
      "Generates on-brand drafts grounded in the client's Deep Insight Profile, validates them against brand voice rules, and scores quality before anything reaches the Approval Center.",
    status: "available",
    actionLabel: "Create Content",
    actionHref: "/content",
  },
  {
    key: "knowledge",
    name: "Knowledge Intelligence",
    icon: BookOpen,
    benefit: "Give every AI decision the context it needs.",
    description:
      "The retrieval layer every other agent depends on - real document ingestion, chunking, embedding, and grounded semantic search, so nothing gets generated from thin air.",
    status: "available",
    actionLabel: "Manage Knowledge",
    actionHref: "/knowledge",
  },
  {
    key: "seo",
    name: "SEO Intelligence",
    icon: Search,
    benefit: "Turn search visibility into a repeatable growth channel.",
    description:
      "Runs real search performance data through a deterministic opportunity-detection rule engine (CTR gaps, page-one/page-two positioning, momentum, and risk), then grounds an LLM strategist's explanation in this client's real knowledge base and the Evaluation Engine before it reaches you for approval.",
    status: "available",
    actionLabel: "Review SEO Opportunities",
    actionHref: "/seo",
  },
  {
    key: "email",
    name: "Email Intelligence",
    icon: Mail,
    benefit: "Nurture sequences that sound like your team wrote them.",
    description: "Planned: lifecycle and campaign email generation grounded in the same knowledge base.",
    status: "coming_soon",
  },
  {
    key: "social",
    name: "Social Intelligence",
    icon: Share2,
    benefit: "Consistent presence across every channel, without the manual lift.",
    description: "Planned: multi-platform social content and scheduling intelligence.",
    status: "coming_soon",
  },
  {
    key: "pr",
    name: "PR Intelligence",
    icon: Megaphone,
    benefit: "Spot the story before your competitors do.",
    description: "Planned: media monitoring and narrative/positioning support.",
    status: "coming_soon",
  },
]

export default function AgentCenterPage() {
  return (
    <div className="flex flex-col h-full space-y-8 p-8 max-w-6xl mx-auto font-body">
      <div className="border-b border-border pb-6">
        <h1 className="text-4xl font-heading font-medium tracking-tight text-foreground">Agent Center</h1>
        <p className="text-muted-foreground mt-2 text-sm max-w-2xl">
          The AI team working for your agency - each one grounded in real client knowledge, evaluated before it reaches you.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {AGENTS.map((agent) => (
          <div
            key={agent.key}
            className={`p-6 rounded-xl border bg-card shadow-sm flex flex-col ${
              agent.status === "available" ? "border-border" : "border-dashed border-border opacity-75"
            }`}
          >
            <div className="flex items-start justify-between mb-4">
              <div className={`p-3 rounded-md ${agent.status === "available" ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"}`}>
                <agent.icon className="w-5 h-5" />
              </div>
              <span
                className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                  agent.status === "available" ? "bg-secondary/10 text-secondary" : "bg-muted text-muted-foreground"
                }`}
              >
                {agent.status === "available" ? "Available" : "Coming Soon"}
              </span>
            </div>
            <h2 className="text-lg font-heading font-medium text-foreground">{agent.name}</h2>
            <p className="text-sm font-medium text-foreground/80 mt-1">{agent.benefit}</p>
            <p className="text-sm text-muted-foreground mt-3 leading-relaxed flex-1">{agent.description}</p>
            {agent.status === "available" && agent.actionHref && (
              <Link
                href={agent.actionHref}
                className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
              >
                {agent.actionLabel} <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
