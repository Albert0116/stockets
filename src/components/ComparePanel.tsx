import { useState, useCallback } from "react"
import { GitCompareArrows, Loader2, Plus, X } from "lucide-react"
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts"
import { cn } from "@/lib/utils"
import { fetchCandles, fetchQuote, type CandleData, type Market } from "@/lib/api"

interface Props {
  market: Market
  className?: string
}

const COLORS = ["hsl(142 60% 46%)", "hsl(210 100% 58%)", "hsl(38 88% 56%)"]

interface CompareItem {
  symbol: string
  name: string
  color: string
  candles: CandleData[]
  returnPct: number
}

export default function ComparePanel({ market, className }: Props) {
  const [items, setItems] = useState<CompareItem[]>([])
  const [loading, setLoading] = useState(false)
  const [inputValues, setInputValues] = useState<string[]>(["", ""])
  const [error, setError] = useState("")

  const handleCompare = useCallback(async () => {
    const symbols = inputValues.map(v => v.trim().toUpperCase()).filter(Boolean)
    if (symbols.length < 2) { setError("请输入至少2个股票代码"); return }
    if (symbols.length > 3) { setError("最多支持3个股票"); return }
    setError("")
    setLoading(true)
    try {
      const results: CompareItem[] = []
      for (let i = 0; i < symbols.length; i++) {
        const [candles, quote] = await Promise.all([
          fetchCandles(symbols[i], "6mo", market),
          fetchQuote(symbols[i], market).catch(() => null),
        ])
        if (candles.length < 10) continue
        const firstClose = candles[0].close
        const lastClose = candles[candles.length - 1].close
        const returnPct = firstClose > 0 ? ((lastClose - firstClose) / firstClose) * 100 : 0
        results.push({
          symbol: symbols[i],
          name: quote?.name || symbols[i],
          color: COLORS[i],
          candles,
          returnPct: Math.round(returnPct * 100) / 100,
        })
      }
      setItems(results)
    } catch {
      setError("对比数据获取失败")
    } finally {
      setLoading(false)
    }
  }, [inputValues, market])

  const addInput = () => {
    if (inputValues.length < 3) setInputValues(prev => [...prev, ""])
  }

  // 构建归一化数据 (base=100)
  const normalizedData = items.length > 0 ? (() => {
    // 找到共同日期范围
    const allDates = new Set<string>()
    items.forEach(item => item.candles.forEach(c => allDates.add(c.date)))
    const sortedDates = Array.from(allDates).sort()

    // 每只股票的归一化映射
    const normalized: Record<string, Record<string, number>> = {}
    items.forEach(item => {
      const base = item.candles[0]?.close || 1
      const map: Record<string, number> = {}
      item.candles.forEach(c => {
        map[c.date] = Math.round((c.close / base) * 100 * 100) / 100
      })
      normalized[item.symbol] = map
    })

    return sortedDates.map(date => {
      const point: Record<string, any> = { date: date.slice(5) }
      items.forEach(item => {
        if (normalized[item.symbol][date] !== undefined) {
          point[item.symbol] = normalized[item.symbol][date]
        }
      })
      return point
    })
  })() : []

  return (
    <div className={cn("card-base p-5", className)}>
      <div className="flex items-center gap-2 mb-4">
        <GitCompareArrows className="w-4 h-4 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">多股对比</h3>
      </div>

      {/* 输入区 */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        {inputValues.map((val, i) => (
          <div key={i} className="relative">
            <input
              value={val}
              onChange={e => {
                const next = [...inputValues]
                next[i] = e.target.value
                setInputValues(next)
              }}
              placeholder={market === "cn" ? "股票代码" : "Symbol"}
              className="w-28 h-8 px-2.5 pr-7 rounded-lg bg-surface-2 border border-border text-xs text-foreground mono
                placeholder:text-muted-foreground/60 focus:outline-none focus:border-primary/50"
            />
            {inputValues.length > 2 && (
              <button onClick={() => setInputValues(prev => prev.filter((_, j) => j !== i))}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        ))}
        {inputValues.length < 3 && (
          <button onClick={addInput}
            className="h-8 w-8 rounded-lg border border-dashed border-border text-muted-foreground
              hover:text-foreground hover:border-primary/40 flex items-center justify-center">
            <Plus className="w-3 h-3" />
          </button>
        )}
        <button onClick={handleCompare} disabled={loading}
          className="h-8 px-3 rounded-lg text-xs font-medium bg-primary text-primary-foreground
            hover:opacity-90 disabled:opacity-50 flex items-center gap-1">
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <GitCompareArrows className="w-3 h-3" />}
          对比
        </button>
      </div>

      {error && <p className="text-[11px] text-bear mb-2">{error}</p>}

      {/* 归一化价格图 */}
      {normalizedData.length > 0 && (
        <div className="mb-3">
          <p className="text-[10px] text-muted-foreground mb-1">归一化价格走势 (基准=100)</p>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={normalizedData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 9 }}
                tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 9 }}
                tickLine={false} axisLine={false} width={36} />
              <Tooltip content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null
                return (
                  <div className="card-base px-2 py-1.5 text-[10px]">
                    <div className="text-muted-foreground mb-1">{label}</div>
                    {payload.map(p => (
                      <div key={p.name} className="flex justify-between gap-3" style={{ color: p.color }}>
                        <span>{p.name}</span>
                        <span className="mono font-medium">{(p.value as number).toFixed(1)}</span>
                      </div>
                    ))}
                  </div>
                )
              }} />
              {items.map(item => (
                <Line key={item.symbol} type="monotone" dataKey={item.symbol}
                  stroke={item.color} strokeWidth={1.5} dot={false} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* 对比指标表格 */}
      {items.length > 0 && (
        <div className="border-t border-border/50 pt-2">
          <table className="w-full text-[10px]">
            <thead>
              <tr className="text-muted-foreground">
                <th className="text-left py-1 font-medium">股票</th>
                <th className="text-right py-1 font-medium">6月涨幅</th>
                <th className="text-right py-1 font-medium">最高</th>
                <th className="text-right py-1 font-medium">最低</th>
                <th className="text-right py-1 font-medium">振幅</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => {
                const closes = item.candles.map(c => c.close)
                const high = Math.max(...closes)
                const low = Math.min(...closes)
                const amplitude = low > 0 ? ((high - low) / low * 100) : 0
                return (
                  <tr key={item.symbol} className="border-t border-border/30">
                    <td className="py-1.5">
                      <span className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                        <span className="mono font-medium text-foreground">{item.symbol}</span>
                      </span>
                    </td>
                    <td className={cn("py-1.5 text-right mono font-medium",
                      item.returnPct >= 0 ? "text-bull" : "text-bear"
                    )}>
                      {item.returnPct >= 0 ? "+" : ""}{item.returnPct.toFixed(1)}%
                    </td>
                    <td className="py-1.5 text-right mono text-foreground">{high.toFixed(2)}</td>
                    <td className="py-1.5 text-right mono text-foreground">{low.toFixed(2)}</td>
                    <td className="py-1.5 text-right mono text-foreground">{amplitude.toFixed(1)}%</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
