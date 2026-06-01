import { useState, useCallback, useRef } from "react"
import { Brain, Loader2, Sparkles, RotateCcw } from "lucide-react"
import { cn } from "@/lib/utils"
import { streamMultiAgentAnalysis, type QuoteData, type MultiAgentEvent, type Market } from "@/lib/api"
import AgentCard from "./AgentCard"
import DecisionCard from "./DecisionCard"
import FollowUpChat from "./FollowUpChat"

interface AgentState {
  agentId: string
  agentName: string
  icon: string
  status: "pending" | "running" | "done"
  content: string
  summary: string
  index: number
  total: number
  startedAt?: number
}

interface DecisionState {
  rating: string
  confidence: number
  targetPrice: string
  stopLoss: string
  timeHorizon: string
  coreLogic: string
  operationPlan?: {
    entryStrategy: string
    positionSizing: string
    takeProfit: string
    timeStop: string
  }
  totalTime?: string
}

interface MultiAgentPanelProps {
  quote: QuoteData
  market?: Market
  className?: string
}

const INITIAL_AGENTS: Omit<AgentState, "content" | "summary" | "status">[] = [
  { agentId: "fundamental", agentName: "基本面分析", icon: "📊", index: 1, total: 6 },
  { agentId: "technical_analysis", agentName: "技术面分析", icon: "📈", index: 2, total: 6 },
  { agentId: "sentiment", agentName: "消息面分析", icon: "📰", index: 3, total: 6 },
  { agentId: "flow", agentName: "资金面分析", icon: "💰", index: 4, total: 6 },
  { agentId: "risk", agentName: "风险评估", icon: "⚠️", index: 5, total: 6 },
  { agentId: "decision", agentName: "综合决策", icon: "🎯", index: 6, total: 6 },
]

export default function MultiAgentPanel({ quote, market = "us", className }: MultiAgentPanelProps) {
  const [agents, setAgents] = useState<AgentState[]>([])
  const [decision, setDecision] = useState<DecisionState | null>(null)
  const [running, setRunning] = useState(false)
  const [statusMsg, setStatusMsg] = useState("")
  const [error, setError] = useState("")
  const abortRef = useRef(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  // 构建分析上下文给追问使用
  const buildAnalysisContext = useCallback(() => {
    const parts: string[] = []
    for (const agent of agents) {
      if (agent.summary) {
        parts.push(`[${agent.agentName}] ${agent.summary}`)
      }
    }
    if (decision) {
      parts.push(`[决策] 评级:${decision.rating} 信心:${decision.confidence}/10`)
      if (decision.coreLogic) parts.push(`核心逻辑: ${decision.coreLogic}`)
      if (decision.targetPrice) parts.push(`目标价: ${decision.targetPrice}`)
      if (decision.stopLoss) parts.push(`止损: ${decision.stopLoss}`)
    }
    return parts.join("\n")
  }, [agents, decision])

  const startAnalysis = useCallback(async () => {
    if (running) return
    abortRef.current = false
    setError("")
    setDecision(null)
    setStatusMsg("正在初始化...")
    setRunning(true)

    const initialStates: AgentState[] = INITIAL_AGENTS.map(a => ({
      ...a,
      status: "pending" as const,
      content: "",
      summary: "",
    }))
    setAgents(initialStates)

    try {
      const gen = streamMultiAgentAnalysis(
        quote.symbol, quote.name, quote.price,
        quote.change_pct, quote.industry, quote.market_cap, market
      )

      for await (const event of gen) {
        if (abortRef.current) break
        handleEvent(event)
      }
    } catch (e) {
      setError(`分析失败: ${String(e)}`)
    } finally {
      setRunning(false)
      setStatusMsg("")
    }
  }, [quote, running, market])

  const handleEvent = (event: MultiAgentEvent) => {
    switch (event.type) {
      case "status":
        setStatusMsg(event.message || "")
        break

      case "agent_start":
        setAgents(prev => prev.map(a =>
          a.agentId === event.agent_id
            ? { ...a, status: "running" as const, startedAt: Date.now() }
            : a
        ))
        setStatusMsg(`${event.icon} ${event.agent_name} 分析中... (${event.index}/${event.total})`)
        break

      case "text":
        setAgents(prev => prev.map(a =>
          a.agentId === event.agent_id
            ? { ...a, content: a.content + (event.text || "") }
            : a
        ))
        if (scrollRef.current) {
          setTimeout(() => {
            scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
          }, 50)
        }
        break

      case "agent_done":
        setAgents(prev => prev.map(a =>
          a.agentId === event.agent_id
            ? { ...a, status: "done" as const, summary: event.summary || "" }
            : a
        ))
        break

      case "decision":
        setDecision({
          rating: event.rating || "持有",
          confidence: event.confidence || 5,
          targetPrice: event.target_price || "",
          stopLoss: event.stop_loss || "",
          timeHorizon: event.time_horizon || "",
          coreLogic: event.core_logic || "",
          operationPlan: event.operation_plan ? {
            entryStrategy: event.operation_plan.entry_strategy || "",
            positionSizing: event.operation_plan.position_sizing || "",
            takeProfit: event.operation_plan.take_profit || "",
            timeStop: event.operation_plan.time_stop || "",
          } : undefined,
          totalTime: event.total_time || "",
        })
        break

      case "error":
        setError(event.message || "未知错误")
        break
    }
  }

  const hasStarted = agents.length > 0

  return (
    <div className={cn("card-base", className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <Brain className="w-4.5 h-4.5 text-primary" />
          <span className="font-semibold text-sm text-foreground">Multi-Agent 深度分析</span>
          <span className="text-[10px] text-muted-foreground px-1.5 py-0.5 bg-surface-2 rounded mono">
            6 Agents
          </span>
        </div>
        {running && statusMsg && (
          <div className="flex items-center gap-1.5 text-xs text-primary">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>{statusMsg}</span>
          </div>
        )}
      </div>

      {/* Content */}
      <div ref={scrollRef} className="p-4 max-h-[600px] overflow-y-auto">
        {!hasStarted && !running && (
          <div className="flex flex-col items-center justify-center py-8 gap-4">
            <div className="w-14 h-14 rounded-full bg-accent/50 flex items-center justify-center">
              <Brain className="w-7 h-7 text-primary" />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-foreground mb-1">
                对 <span className="text-primary mono">{quote.symbol}</span> 进行多维度AI分析
              </p>
              <p className="text-xs text-muted-foreground max-w-md">
                6个专业Agent将分别从基本面、技术面、消息面、资金面、风险评估进行分析，最终给出综合决策建议
              </p>
            </div>
            <button
              onClick={startAnalysis}
              className="mt-2 px-6 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium
                         hover:opacity-90 active:scale-[0.98] transition-all glow-sm flex items-center gap-2"
            >
              <Sparkles className="w-4 h-4" />
              开始多Agent分析
            </button>
          </div>
        )}

        {hasStarted && (
          <div className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
              {agents.filter(a => a.agentId !== "decision").map(agent => (
                <AgentCard
                  key={agent.agentId}
                  agentId={agent.agentId}
                  agentName={agent.agentName}
                  icon={agent.icon}
                  status={agent.status}
                  content={agent.content}
                  summary={agent.summary}
                  index={agent.index}
                  total={agent.total}
                  startedAt={agent.startedAt}
                />
              ))}
            </div>

            {agents.find(a => a.agentId === "decision" && a.status !== "pending") && (
              <div className="mt-3">
                <AgentCard
                  {...agents.find(a => a.agentId === "decision")!}
                />
              </div>
            )}

            {decision && (
              <DecisionCard
                rating={decision.rating}
                confidence={decision.confidence}
                targetPrice={decision.targetPrice}
                stopLoss={decision.stopLoss}
                timeHorizon={decision.timeHorizon}
                coreLogic={decision.coreLogic}
                operationPlan={decision.operationPlan}
                totalTime={decision.totalTime}
                className="mt-3"
              />
            )}

            {/* Follow-up Chat - 分析完成后显示 */}
            {decision && !running && (
              <FollowUpChat
                symbol={quote.symbol}
                market={market || "us"}
                analysisContext={buildAnalysisContext()}
                className="mt-3"
              />
            )}

            {error && (
              <div className="p-3 rounded-lg border border-bear/30 bg-bear/8 text-xs text-bear">
                {error}
              </div>
            )}

            {!running && hasStarted && (
              <div className="flex justify-center pt-2">
                <button
                  onClick={startAnalysis}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs text-muted-foreground
                             hover:text-foreground hover:bg-surface-2 transition-colors border border-border"
                >
                  <RotateCcw className="w-3 h-3" />
                  重新分析
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
