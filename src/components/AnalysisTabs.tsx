import { Brain } from "lucide-react"
import { cn } from "@/lib/utils"
import type { QuoteData, Market } from "@/lib/api"
import MultiAgentPanel from "./MultiAgentPanel"

interface AnalysisTabsProps {
  quote: QuoteData
  market?: Market
  className?: string
}

export default function AnalysisTabs({ quote, market = "us", className }: AnalysisTabsProps) {
  return (
    <div className={cn("card-base", className)}>
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
        <Brain className="w-4 h-4 text-primary" />
        <span className="font-semibold text-sm text-foreground">Multi-Agent 深度分析</span>
        <span className="text-[10px] text-muted-foreground ml-auto hidden sm:block">6个专业Agent综合研判</span>
      </div>

      <MultiAgentPanel
        quote={quote}
        market={market}
        className="border-0 rounded-none shadow-none bg-transparent"
      />
    </div>
  )
}
