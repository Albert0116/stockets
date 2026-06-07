import { useState } from "react"
import { Brain, Bot } from "lucide-react"
import { cn } from "@/lib/utils"
import type { QuoteData, Market } from "@/lib/api"
import MultiAgentPanel from "./MultiAgentPanel"
import AIPanel from "./AIPanel"

interface AnalysisTabsProps {
  quote: QuoteData
  market?: Market
  className?: string
}

type TabId = "multi" | "single"

const TABS: { id: TabId; label: string; icon: typeof Brain; desc: string }[] = [
  { id: "multi", label: "Multi-Agent 深度分析", icon: Brain, desc: "6个专业Agent综合研判" },
  { id: "single", label: "单模型 AI 分析", icon: Bot, desc: "DeepSeek 快速分析" },
]

export default function AnalysisTabs({ quote, market = "us", className }: AnalysisTabsProps) {
  const [activeTab, setActiveTab] = useState<TabId>("multi")

  return (
    <div className={cn("card-base", className)}>
      {/* Tab 切换栏 */}
      <div className="flex items-center border-b border-border">
        {TABS.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 text-xs font-medium transition-all duration-150",
                "border-b-2 -mb-px",
                isActive
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">{tab.label}</span>
              <span className="sm:hidden">{tab.id === "multi" ? "多Agent" : "单模型"}</span>
            </button>
          )
        })}
        <div className="flex-1" />
        <span className="text-[10px] text-muted-foreground px-3 hidden sm:block">
          {TABS.find((t) => t.id === activeTab)?.desc}
        </span>
      </div>

      {/* 面板内容 */}
      <div className="animate-fade-up">
        {activeTab === "multi" ? (
          <MultiAgentPanel quote={quote} market={market} className="border-0 rounded-none shadow-none bg-transparent" />
        ) : (
          <AIPanel quote={quote} market={market} className="border-0 rounded-none shadow-none bg-transparent" />
        )}
      </div>
    </div>
  )
}
