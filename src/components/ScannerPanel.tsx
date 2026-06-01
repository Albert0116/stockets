import { useState } from "react"
import { Loader2, Zap, Check, Play } from "lucide-react"
import { cn } from "@/lib/utils"

interface ScanResult {
  symbol: string
  name: string
  market: string
  price: number
  change_pct: number
  volume_ratio?: number
  turnover?: number
  score: number
  reason: string
}

interface Strategy {
  id: string
  name: string
  description: string
}

interface ScannerPanelProps {
  className?: string
}

const STRATEGY_COLORS: Record<string, string> = {
  volume_breakout: "border-bull/30 bg-bull/5",
  oversold_bounce: "border-gold/30 bg-gold/5",
  steady_growth: "border-blue-500/30 bg-blue-500/5",
  new_high: "border-purple-500/30 bg-purple-500/5",
}

export default function ScannerPanel({ className }: ScannerPanelProps) {
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [batchResults, setBatchResults] = useState<Record<string, ScanResult[]>>({})
  const [error, setError] = useState("")
  const [expanded, setExpanded] = useState(false)

  const loadStrategies = async () => {
    try {
      const r = await fetch("http://localhost:8888/api/scanner/strategies")
      const data = await r.json()
      setStrategies(data.strategies || [])
    } catch { /* ignore */ }
  }

  const toggleStrategy = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const runBatchScan = async () => {
    if (selected.size === 0) return
    setLoading(true)
    setError("")
    setBatchResults({})
    try {
      const r = await fetch("http://localhost:8888/api/scanner/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategies: Array.from(selected), top_n: 10 }),
      })
      const data = await r.json()
      if (r.ok) {
        setBatchResults(data.results || {})
        const total = Object.values(data.results as Record<string, unknown[]>).reduce((s: number, v) => s + v.length, 0)
        if (total === 0) setError("当前没有符合条件的股票（非交易时段或网络受限）")
      } else {
        setError(data.detail || "扫描失败")
      }
    } catch {
      setError("扫描服务不可用，请确认后端已启动")
    } finally {
      setLoading(false)
    }
  }

  if (!expanded) {
    return (
      <button
        onClick={() => { setExpanded(true); loadStrategies() }}
        className={cn(
          "w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg",
          "border border-border/50 hover:border-primary/50 text-xs text-muted-foreground",
          "hover:text-foreground hover:bg-surface-2/50 transition-all",
          className
        )}
      >
        <Zap className="w-3.5 h-3.5" />
        自动选股扫描
      </button>
    )
  }

  const hasResults = Object.keys(batchResults).length > 0

  return (
    <div className={cn("rounded-xl border border-border/50 p-4", className)}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-gold" />
          <span className="text-sm font-bold text-foreground">自动选股扫描</span>
          <span className="text-[10px] text-muted-foreground ml-1">
            {selected.size > 0 ? `已选 ${selected.size}` : "多选策略后一键扫描"}
          </span>
        </div>
        <button
          onClick={() => setExpanded(false)}
          className="text-[10px] text-muted-foreground hover:text-foreground"
        >
          收起
        </button>
      </div>

      {/* 策略选择（多选 toggle） */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {strategies.length === 0 && (
          <span className="text-xs text-muted-foreground">加载策略中...</span>
        )}
        {strategies.map((s) => {
          const isSelected = selected.has(s.id)
          return (
            <button
              key={s.id}
              onClick={() => toggleStrategy(s.id)}
              disabled={loading}
              className={cn(
                "px-2.5 py-1 rounded text-xs transition-all flex items-center gap-1",
                isSelected
                  ? "bg-primary/15 text-primary border border-primary/30"
                  : "bg-surface-2/60 text-foreground/80 border border-transparent hover:border-border"
              )}
              title={s.description}
            >
              {isSelected && <Check className="w-3 h-3" />}
              {s.name}
            </button>
          )
        })}
      </div>

      {/* 一键执行按钮 */}
      <button
        onClick={runBatchScan}
        disabled={selected.size === 0 || loading}
        className={cn(
          "w-full py-2 rounded-lg text-xs font-medium flex items-center justify-center gap-2 transition-all mb-3",
          selected.size === 0
            ? "bg-surface-2/40 text-muted-foreground cursor-not-allowed"
            : "bg-primary/10 text-primary border border-primary/30 hover:bg-primary/20"
        )}
      >
        {loading ? (
          <>
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            正在扫描全市场...
          </>
        ) : (
          <>
            <Play className="w-3.5 h-3.5" />
            执行选中策略（{selected.size}个）
          </>
        )}
      </button>

      {/* 错误 */}
      {error && !loading && (
        <div className="text-xs text-muted-foreground text-center py-3">{error}</div>
      )}

      {/* 结果（按策略分组） */}
      {hasResults && !loading && (
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {Object.entries(batchResults).map(([strategyId, results]) => {
            const strategy = strategies.find(s => s.id === strategyId)
            const colorClass = STRATEGY_COLORS[strategyId] || ""
            if (results.length === 0) return null
            return (
              <div key={strategyId}>
                <div className={cn(
                  "text-[10px] font-bold text-foreground px-2 py-1 rounded mb-1 border",
                  colorClass
                )}>
                  {strategy?.name || strategyId} ({results.length}只)
                </div>
                {results.map((r, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded-lg bg-surface-2/40
                               hover:bg-surface-2/60 transition-colors cursor-pointer mb-0.5"
                    onClick={() => {
                      window.dispatchEvent(new CustomEvent("select-stock", {
                        detail: { symbol: r.symbol, market: r.market }
                      }))
                    }}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-bold text-foreground">{r.symbol}</span>
                        <span className="text-xs text-foreground/80 truncate">{r.name}</span>
                      </div>
                    </div>
                    <div className="text-right ml-2 shrink-0">
                      <div className="text-xs font-mono font-bold text-foreground">¥{r.price.toFixed(2)}</div>
                      <div className={cn(
                        "text-[10px] font-mono",
                        r.change_pct >= 0 ? "text-bull" : "text-bear"
                      )}>
                        {r.change_pct >= 0 ? "+" : ""}{r.change_pct.toFixed(2)}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
