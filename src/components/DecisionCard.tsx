import { useState } from "react"
import { cn } from "@/lib/utils"
import { Target, Shield, TrendingUp, TrendingDown, Minus, Copy, Check, Clock, Crosshair, PieChart, ArrowUpRight } from "lucide-react"

interface OperationPlan {
  entryStrategy: string
  positionSizing: string
  takeProfit: string
  timeStop: string
}

interface DecisionCardProps {
  rating: string
  confidence: number
  targetPrice: string
  stopLoss: string
  timeHorizon: string
  coreLogic: string
  operationPlan?: OperationPlan
  totalTime?: string
  className?: string
}

const RATING_CONFIG: Record<string, { color: string; bg: string; icon: typeof TrendingUp }> = {
  "买入": { color: "text-bull", bg: "bg-bull/15 border-bull/30", icon: TrendingUp },
  "增持": { color: "text-bull", bg: "bg-bull/10 border-bull/20", icon: TrendingUp },
  "持有": { color: "text-gold", bg: "bg-gold/10 border-gold/20", icon: Minus },
  "减持": { color: "text-bear", bg: "bg-bear/10 border-bear/20", icon: TrendingDown },
  "卖出": { color: "text-bear", bg: "bg-bear/15 border-bear/30", icon: TrendingDown },
}

function getConfidenceColor(c: number) {
  if (c >= 8) return "bg-bull"
  if (c >= 5) return "bg-gold"
  return "bg-bear"
}

export default function DecisionCard({
  rating,
  confidence,
  targetPrice,
  stopLoss,
  timeHorizon,
  coreLogic,
  operationPlan,
  totalTime,
  className,
}: DecisionCardProps) {
  const config = RATING_CONFIG[rating] || RATING_CONFIG["持有"]
  const RatingIcon = config.icon
  const [copied, setCopied] = useState(false)

  const hasOperationPlan = operationPlan && (
    operationPlan.entryStrategy ||
    operationPlan.positionSizing ||
    operationPlan.takeProfit ||
    operationPlan.timeStop
  )

  const handleCopy = () => {
    const lines = [
      `投资评级: ${rating}`,
      `信心指数: ${confidence}/10`,
      targetPrice ? `目标价: ${targetPrice}` : "",
      stopLoss ? `止损价: ${stopLoss}` : "",
      timeHorizon ? `时间周期: ${timeHorizon}` : "",
      coreLogic ? `核心逻辑: ${coreLogic}` : "",
    ]
    if (hasOperationPlan) {
      lines.push("")
      lines.push("--- 操作计划 ---")
      if (operationPlan.entryStrategy) lines.push(`入场策略: ${operationPlan.entryStrategy}`)
      if (operationPlan.positionSizing) lines.push(`仓位管理: ${operationPlan.positionSizing}`)
      if (operationPlan.takeProfit) lines.push(`止盈计划: ${operationPlan.takeProfit}`)
      if (operationPlan.timeStop) lines.push(`时间止损: ${operationPlan.timeStop}`)
    }
    navigator.clipboard.writeText(lines.filter(Boolean).join("\n"))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={cn(
      "rounded-xl border-2 p-4 animate-fade-up relative",
      config.bg,
      className
    )}>
      {/* Copy button */}
      <button
        onClick={handleCopy}
        className="absolute top-3 right-3 flex items-center gap-1 text-xs text-muted-foreground
                   hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-surface-2/50"
      >
        {copied ? <Check className="w-3 h-3 text-bull" /> : <Copy className="w-3 h-3" />}
        {copied ? "已复制" : "复制"}
      </button>

      {/* Header */}
      <div className="flex items-center justify-between mb-3 pr-14">
        <div className="flex items-center gap-2">
          <Target className={cn("w-5 h-5", config.color)} />
          <span className="text-sm font-bold text-foreground">最终决策</span>
          {totalTime && (
            <span className="text-[10px] text-muted-foreground ml-1">({totalTime})</span>
          )}
        </div>
        {/* Rating Badge */}
        <div className={cn(
          "flex items-center gap-1.5 px-3 py-1.5 rounded-full font-bold text-sm",
          config.color,
          config.bg,
        )}>
          <RatingIcon className="w-4 h-4" />
          {rating}
        </div>
      </div>

      {/* Confidence Bar */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-muted-foreground">信心指数</span>
          <span className={cn(
            "text-sm font-bold mono",
            confidence >= 8 ? "text-bull" : confidence >= 5 ? "text-gold" : "text-bear"
          )}>{confidence}/10</span>
        </div>
        <div className="h-2 bg-surface-2 rounded-full overflow-hidden">
          <div
            className={cn("h-full rounded-full transition-all duration-1000", getConfidenceColor(confidence))}
            style={{ width: `${confidence * 10}%` }}
          />
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        {targetPrice && (
          <div className="bg-surface-2/60 rounded-lg px-2.5 py-2 text-center">
            <div className="text-[10px] text-muted-foreground mb-0.5">目标价</div>
            <div className="text-xs font-semibold text-foreground mono">{targetPrice}</div>
          </div>
        )}
        {stopLoss && (
          <div className="bg-surface-2/60 rounded-lg px-2.5 py-2 text-center">
            <div className="text-[10px] text-muted-foreground mb-0.5 flex items-center justify-center gap-0.5">
              <Shield className="w-2.5 h-2.5" />止损
            </div>
            <div className="text-xs font-semibold text-bear mono">{stopLoss}</div>
          </div>
        )}
        {timeHorizon && (
          <div className="bg-surface-2/60 rounded-lg px-2.5 py-2 text-center">
            <div className="text-[10px] text-muted-foreground mb-0.5">周期</div>
            <div className="text-xs font-semibold text-foreground">{timeHorizon}</div>
          </div>
        )}
      </div>

      {/* Core Logic */}
      {coreLogic && (
        <div className="text-xs text-foreground/80 leading-relaxed border-t border-border/50 pt-2">
          <span className="font-medium text-foreground">核心逻辑：</span>
          {coreLogic}
        </div>
      )}

      {/* Operation Plan */}
      {hasOperationPlan && (
        <div className="mt-3 border-t border-border/50 pt-3">
          <div className="text-xs font-bold text-foreground mb-2 flex items-center gap-1.5">
            <Crosshair className="w-3.5 h-3.5" />
            操作计划
          </div>
          <div className="space-y-2">
            {operationPlan.entryStrategy && (
              <div className="flex items-start gap-2 text-xs">
                <ArrowUpRight className="w-3 h-3 mt-0.5 text-bull shrink-0" />
                <div>
                  <span className="font-medium text-foreground">入场策略：</span>
                  <span className="text-foreground/80">{operationPlan.entryStrategy}</span>
                </div>
              </div>
            )}
            {operationPlan.positionSizing && (
              <div className="flex items-start gap-2 text-xs">
                <PieChart className="w-3 h-3 mt-0.5 text-gold shrink-0" />
                <div>
                  <span className="font-medium text-foreground">仓位管理：</span>
                  <span className="text-foreground/80">{operationPlan.positionSizing}</span>
                </div>
              </div>
            )}
            {operationPlan.takeProfit && (
              <div className="flex items-start gap-2 text-xs">
                <Target className="w-3 h-3 mt-0.5 text-bull shrink-0" />
                <div>
                  <span className="font-medium text-foreground">止盈计划：</span>
                  <span className="text-foreground/80">{operationPlan.takeProfit}</span>
                </div>
              </div>
            )}
            {operationPlan.timeStop && (
              <div className="flex items-start gap-2 text-xs">
                <Clock className="w-3 h-3 mt-0.5 text-bear shrink-0" />
                <div>
                  <span className="font-medium text-foreground">时间止损：</span>
                  <span className="text-foreground/80">{operationPlan.timeStop}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
