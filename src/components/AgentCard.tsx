import { useState, useEffect } from "react"
import { ChevronDown, ChevronUp, Check, Loader2, Clock } from "lucide-react"
import { cn } from "@/lib/utils"

interface AgentCardProps {
  agentId: string
  agentName: string
  icon: string
  status: "pending" | "running" | "done"
  content: string
  summary: string
  index: number
  total: number
  startedAt?: number // timestamp when agent started
}

function formatDuration(ms: number) {
  const sec = Math.floor(ms / 1000)
  if (sec < 60) return `${sec}s`
  const min = Math.floor(sec / 60)
  const remainSec = sec % 60
  return `${min}m ${remainSec}s`
}

export default function AgentCard({
  agentId,
  agentName,
  icon,
  status,
  content,
  summary,
  index,
  total,
  startedAt,
}: AgentCardProps) {
  const [expanded, setExpanded] = useState(status === "running")
  const [elapsed, setElapsed] = useState(0)

  // P0-7: Auto-expand when running - 使用 useEffect 避免 render 中直接 setState
  useEffect(() => {
    if (status === "running") setExpanded(true)
  }, [status])

  // 计时器
  useEffect(() => {
    if (status === "running" && startedAt) {
      setElapsed(0)
      const timer = setInterval(() => {
        setElapsed(Date.now() - startedAt)
      }, 1000)
      return () => clearInterval(timer)
    }
    if (status === "done" && startedAt) {
      setElapsed(Date.now() - startedAt)
    }
  }, [status, startedAt])

  const renderContent = (text: string) => {
    return text.split("\n").map((line, i) => {
      if (line.startsWith("### ")) return <h3 key={i} className="text-xs font-semibold text-accent-foreground mt-2 mb-0.5">{line.slice(4)}</h3>
      if (line.startsWith("## ")) return <h2 key={i} className="text-sm font-semibold text-foreground mt-2 mb-0.5">{line.slice(3)}</h2>
      if (line.startsWith("# ")) return <h2 key={i} className="text-sm font-bold text-foreground mt-2 mb-0.5">{line.slice(2)}</h2>
      if (line.startsWith("- ") || line.startsWith("• ")) {
        return <li key={i} className="ml-3 text-xs text-foreground/85 leading-relaxed list-disc list-inside">{line.slice(2)}</li>
      }
      if (line.trim() === "") return <div key={i} className="h-1" />
      const parts = line.split(/(\*\*[^*]+\*\*)/)
      return (
        <p key={i} className="text-xs text-foreground/85 leading-relaxed">
          {parts.map((part, j) =>
            part.startsWith("**") && part.endsWith("**")
              ? <strong key={j} className="font-semibold text-foreground">{part.slice(2, -2)}</strong>
              : part
          )}
        </p>
      )
    })
  }

  return (
    <div className={cn(
      "rounded-lg border transition-all duration-300",
      status === "running" ? "border-primary/50 bg-accent/30" :
      status === "done" ? "border-border bg-card" :
      "border-border/50 bg-card/50"
    )}>
      {/* Pending skeleton */}
      {status === "pending" && (
        <div className="flex items-center gap-2.5 px-3 py-2.5">
          <span className="text-base shrink-0 opacity-50">{icon}</span>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">{agentName}</span>
              <span className="text-[10px] text-muted-foreground mono">{index}/{total}</span>
            </div>
            <div className="mt-1 h-2 w-24 shimmer-bg rounded" />
          </div>
          <div className="w-4 h-4 rounded-full border border-border/50" />
        </div>
      )}

      {(status === "running" || status === "done") && (
        <>
          {/* Header */}
          <button
            onClick={() => status === "done" && setExpanded(!expanded)}
            className={cn(
              "w-full flex items-center gap-2.5 px-3 py-2.5",
              status === "done" && "cursor-pointer hover:bg-surface-2/50"
            )}
          >
            {/* Icon */}
            <span className="text-base shrink-0">{icon}</span>

            {/* Name + Status */}
            <div className="flex-1 text-left">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-foreground">{agentName}</span>
                <span className="text-[10px] text-muted-foreground mono">
                  {index}/{total}
                </span>
                {elapsed > 0 && (
                  <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
                    <Clock className="w-2.5 h-2.5" />
                    {formatDuration(elapsed)}
                  </span>
                )}
              </div>
              {status === "done" && summary && !expanded && (
                <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">{summary}</p>
              )}
            </div>

            {/* Status indicator */}
            <div className="shrink-0">
              {status === "running" && (
                <Loader2 className="w-4 h-4 text-primary animate-spin" />
              )}
              {status === "done" && (
                <div className="flex items-center gap-1">
                  <Check className="w-3.5 h-3.5 text-bull" />
                  {expanded ? <ChevronUp className="w-3 h-3 text-muted-foreground" /> : <ChevronDown className="w-3 h-3 text-muted-foreground" />}
                </div>
              )}
            </div>
          </button>

          {/* Content */}
          {expanded && content && (
            <div className={cn(
              "px-3 pb-3 max-h-[260px] overflow-y-auto border-t border-border/50",
              status === "running" && "animate-fade-up"
            )}>
              <div className="pt-2 space-y-0.5">
                {renderContent(content)}
                {status === "running" && (
                  <span className="inline-block w-1 h-3 bg-primary ml-0.5 animate-pulse rounded-sm" />
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
