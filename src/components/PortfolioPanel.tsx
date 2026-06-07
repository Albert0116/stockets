import { useState, useEffect, useCallback } from "react"
import { Briefcase, Loader2, Plus, Trash2, TrendingUp, TrendingDown, DollarSign, PieChart } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  fetchPortfolioSummary, addPortfolioPosition, removePortfolioPosition,
  type PortfolioSummary, type Market,
} from "@/lib/api"

interface Props {
  market: Market
  className?: string
}

export default function PortfolioPanel({ market, className }: Props) {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [adding, setAdding] = useState(false)

  // 表单状态
  const [symbol, setSymbol] = useState("")
  const [buyPrice, setBuyPrice] = useState("")
  const [quantity, setQuantity] = useState("")
  const [buyDate, setBuyDate] = useState("")
  const [notes, setNotes] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const s = await fetchPortfolioSummary(market)
      setSummary(s)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [market])

  useEffect(() => { load() }, [load])

  const handleAdd = async () => {
    if (!symbol.trim() || !buyPrice || !quantity) return
    setAdding(true)
    const result = await addPortfolioPosition({
      symbol: symbol.trim().toUpperCase(),
      market,
      buy_price: parseFloat(buyPrice),
      quantity: parseFloat(quantity),
      buy_date: buyDate || undefined,
      notes: notes || undefined,
    })
    setAdding(false)
    if (result.ok) {
      setSymbol("")
      setBuyPrice("")
      setQuantity("")
      setBuyDate("")
      setNotes("")
      setShowForm(false)
      await load()
    }
  }

  const handleRemove = async (id: number) => {
    const ok = await removePortfolioPosition(id)
    if (ok) await load()
  }

  const currency = market === "cn" ? "¥" : "$"

  return (
    <div className={cn("card-base p-5", className)}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Briefcase className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">持仓跟踪</h3>
        </div>
        <button onClick={() => setShowForm(v => !v)}
          className="flex items-center gap-1 px-2.5 py-1 text-[11px] rounded-lg border border-border
            text-muted-foreground hover:text-foreground hover:border-primary/40 transition-colors">
          <Plus className="w-3 h-3" />
          添加
        </button>
      </div>

      {/* 添加表单 */}
      {showForm && (
        <div className="mb-4 p-3 rounded-lg border border-border bg-surface-2/30 space-y-2 animate-fade-up">
          <div className="grid grid-cols-2 gap-2">
            <input value={symbol} onChange={e => setSymbol(e.target.value)}
              placeholder={market === "cn" ? "股票代码 如 600519" : "Symbol 如 AAPL"}
              className="h-8 px-2.5 rounded-lg bg-surface-2 border border-border text-sm text-foreground mono
                placeholder:text-muted-foreground/60 focus:outline-none focus:border-primary/50" />
            <input value={buyPrice} onChange={e => setBuyPrice(e.target.value)} type="number" step="0.01"
              placeholder="买入价格"
              className="h-8 px-2.5 rounded-lg bg-surface-2 border border-border text-sm text-foreground mono
                placeholder:text-muted-foreground/60 focus:outline-none focus:border-primary/50" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <input value={quantity} onChange={e => setQuantity(e.target.value)} type="number" step="1"
              placeholder="数量（股）"
              className="h-8 px-2.5 rounded-lg bg-surface-2 border border-border text-sm text-foreground mono
                placeholder:text-muted-foreground/60 focus:outline-none focus:border-primary/50" />
            <input value={buyDate} onChange={e => setBuyDate(e.target.value)} type="date"
              className="h-8 px-2.5 rounded-lg bg-surface-2 border border-border text-sm text-foreground mono
                focus:outline-none focus:border-primary/50" />
          </div>
          <div className="flex gap-2">
            <input value={notes} onChange={e => setNotes(e.target.value)}
              placeholder="备注（可选）"
              className="flex-1 h-8 px-2.5 rounded-lg bg-surface-2 border border-border text-sm text-foreground
                placeholder:text-muted-foreground/60 focus:outline-none focus:border-primary/50" />
            <button onClick={handleAdd} disabled={adding || !symbol.trim() || !buyPrice || !quantity}
              className="h-8 px-3 rounded-lg text-xs font-medium bg-primary text-primary-foreground
                hover:opacity-90 disabled:opacity-50 flex items-center gap-1">
              {adding ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
              添加
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-8 text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin mr-2" />
          <span className="text-xs">加载持仓...</span>
        </div>
      ) : !summary || summary.position_count === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          <PieChart className="w-8 h-8 mx-auto mb-2 opacity-30" />
          <p className="text-xs">暂无持仓记录</p>
          <p className="text-[10px] mt-0.5">点击上方"添加"按钮录入持仓</p>
        </div>
      ) : (
        <>
          {/* 汇总卡片 */}
          <div className="grid grid-cols-3 gap-2 mb-3">
            <div className="p-2 rounded-lg bg-surface-2 text-center">
              <p className="text-[10px] text-muted-foreground">总市值</p>
              <p className="text-sm font-semibold mono text-foreground">
                {currency}{summary.total_value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
              </p>
            </div>
            <div className="p-2 rounded-lg bg-surface-2 text-center">
              <p className="text-[10px] text-muted-foreground">总盈亏</p>
              <p className={cn("text-sm font-semibold mono", summary.total_pnl >= 0 ? "text-bull" : "text-bear")}>
                {summary.total_pnl >= 0 ? "+" : ""}{summary.total_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </p>
            </div>
            <div className="p-2 rounded-lg bg-surface-2 text-center">
              <p className="text-[10px] text-muted-foreground">收益率</p>
              <p className={cn("text-sm font-semibold mono", summary.total_pnl_pct >= 0 ? "text-bull" : "text-bear")}>
                {summary.total_pnl_pct >= 0 ? "+" : ""}{summary.total_pnl_pct.toFixed(2)}%
              </p>
            </div>
          </div>

          {/* 持仓列表 */}
          <div className="space-y-1.5 max-h-56 overflow-y-auto">
            {summary.positions.map(pos => (
              <div key={pos.id}
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-2/50 group">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="mono text-xs font-semibold text-foreground">{pos.symbol}</span>
                    <span className="text-[10px] text-muted-foreground">{pos.group_name}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 text-[10px] text-muted-foreground">
                    <span>{pos.quantity}股 × {currency}{pos.buy_price}</span>
                    {pos.current_price && (
                      <span>→ {currency}{pos.current_price}</span>
                    )}
                  </div>
                </div>
                {(pos.pnl !== undefined) && (
                  <div className="text-right">
                    <p className={cn("text-xs font-semibold mono",
                      (pos.pnl ?? 0) >= 0 ? "text-bull" : "text-bear"
                    )}>
                      {(pos.pnl ?? 0) >= 0 ? "+" : ""}{pos.pnl?.toFixed(0)}
                    </p>
                    <p className={cn("text-[10px] mono",
                      (pos.pnl_pct ?? 0) >= 0 ? "text-bull" : "text-bear"
                    )}>
                      {pos.pnl_pct?.toFixed(1)}%
                    </p>
                  </div>
                )}
                <button onClick={() => handleRemove(pos.id)}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded text-muted-foreground
                    hover:text-bear transition-all">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
