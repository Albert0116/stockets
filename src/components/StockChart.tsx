import { useState, useEffect, useMemo } from "react"
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Area, BarChart
} from "recharts"
import { cn } from "@/lib/utils"
import { fetchCandles, fetchIndicators, type CandleData, type IndicatorData, type Market } from "@/lib/api"
import { Loader2, TrendingUp } from "lucide-react"

interface ChartProps {
  symbol: string
  market?: Market
  className?: string
}

const PERIODS = [
  { label: "1月", value: "1mo" },
  { label: "3月", value: "3mo" },
  { label: "6月", value: "6mo" },
  { label: "1年", value: "1y" },
  { label: "2年", value: "2y" },
]

const INDICATOR_BUTTONS = [
  { key: "ma10", label: "MA10", color: "hsl(280 60% 55%)" },
  { key: "ma60", label: "MA60", color: "hsl(160 60% 45%)" },
  { key: "boll", label: "BOLL", color: "hsl(45 80% 55%)" },
  { key: "rsi", label: "RSI", color: "hsl(200 80% 55%)" },
  { key: "macd", label: "MACD", color: "hsl(30 80% 55%)" },
] as const

// 计算移动均线
function calcMA(data: CandleData[], n: number): (number | null)[] {
  return data.map((_, i) => {
    if (i < n - 1) return null
    const sum = data.slice(i - n + 1, i + 1).reduce((s, d) => s + d.close, 0)
    return parseFloat((sum / n).toFixed(2))
  })
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ value: number; name: string; color: string }>
  label?: string
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="card-base px-3 py-2.5 text-xs space-y-1 min-w-[140px]">
      <div className="text-muted-foreground mb-1.5 font-medium">{label}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex justify-between gap-4">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="mono font-medium text-foreground">
            {typeof p.value === "number" ? (p.value > 1000 ? (p.value / 1e6).toFixed(2) + "M" : p.value.toFixed(2)) : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

// 蜡烛图形状
function CandleBar(props: {
  x?: number; y?: number; width?: number; height?: number
  open?: number; close?: number; high?: number; low?: number
  payload?: CandleData
}) {
  const { x = 0, y = 0, width = 0, payload } = props
  if (!payload) return null

  const { open, high, low, close } = payload
  const isUp = close >= open
  const color = isUp ? "hsl(142 60% 46%)" : "hsl(0 68% 56%)"

  return (
    <rect x={x} y={y} width={Math.max(width, 1)} height={Math.max(Math.abs(props.height ?? 0), 1)}
      fill={color} fillOpacity={isUp ? 0.85 : 0.85} rx={1} />
  )
}

export default function StockChart({ symbol, market = "us", className }: ChartProps) {
  const [candles, setCandles] = useState<CandleData[]>([])
  const [period, setPeriod] = useState("3mo")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [indicators, setIndicators] = useState<IndicatorData | null>(null)
  const [activeIndicators, setActiveIndicators] = useState<Set<string>>(new Set(["ma10"]))
  const currency = market === "cn" ? "¥" : "$"

  const toggleIndicator = (key: string) => {
    setActiveIndicators(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError("")
    fetchCandles(symbol, period, market)
      .then(data => { if (!cancelled) setCandles(data) })
      .catch(() => { if (!cancelled) setError("数据加载失败，请稍后重试。若频繁出现请检查网络或数据源") })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [symbol, period, market])

  // 加载指标数据
  useEffect(() => {
    if (activeIndicators.size === 0 || candles.length < 30) { setIndicators(null); return }
    const needServer = activeIndicators.has("rsi") || activeIndicators.has("macd") || activeIndicators.has("boll") || activeIndicators.has("ma60")
    if (needServer) {
      fetchIndicators(symbol, period, market).then(data => setIndicators(data)).catch(() => setIndicators(null))
    }
  }, [symbol, period, market, activeIndicators, candles.length])

  const ma5 = calcMA(candles, 5)
  const ma20 = calcMA(candles, 20)

  const chartData = useMemo(() => {
    return candles.map((c, i) => ({
      ...c,
      dateShort: c.date.slice(5),
      ma5: ma5[i],
      ma20: ma20[i],
      ma10: indicators?.ma10?.[i] ?? null,
      ma60: indicators?.ma60?.[i] ?? null,
      bollUpper: indicators?.bollinger?.upper?.[i] ?? null,
      bollMiddle: indicators?.bollinger?.middle?.[i] ?? null,
      bollLower: indicators?.bollinger?.lower?.[i] ?? null,
      rsi: indicators?.rsi?.[i] ?? null,
      macd: indicators?.macd?.macd?.[i] ?? null,
      macdSignal: indicators?.macd?.signal?.[i] ?? null,
      macdHist: indicators?.macd?.histogram?.[i] ?? null,
      isUp: c.close >= c.open,
    }))
  }, [candles, ma5, ma20, indicators])

  const prices = candles.map(c => c.close)
  const minPrice = prices.length ? Math.min(...prices) * 0.997 : 0
  const maxPrice = prices.length ? Math.max(...prices) * 1.003 : 100

  const isPositive = candles.length >= 2
    ? candles[candles.length - 1].close >= candles[0].close
    : true

  const showRSI = activeIndicators.has("rsi")
  const showMACD = activeIndicators.has("macd")

  return (
    <div className={cn("card-base p-4", className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-primary" />
          <span className="font-semibold text-sm text-foreground">{symbol} 价格走势</span>
        </div>
        <div className="flex items-center gap-1">
          {PERIODS.map(p => (
            <button key={p.value} onClick={() => setPeriod(p.value)}
              className={cn(
                "px-2.5 py-1 text-xs rounded-md transition-all duration-150",
                period === p.value
                  ? "bg-primary text-primary-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-surface-2"
              )}>
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* 指标切换按钮 */}
      <div className="flex items-center gap-1.5 mb-3">
        {INDICATOR_BUTTONS.map(btn => (
          <button key={btn.key} onClick={() => toggleIndicator(btn.key)}
            className={cn(
              "px-2 py-0.5 text-[10px] rounded border transition-all",
              activeIndicators.has(btn.key)
                ? "border-primary/50 text-foreground bg-primary/10"
                : "border-border text-muted-foreground hover:text-foreground"
            )}>
            {btn.label}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex items-center justify-center h-52 gap-2 text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">加载中...</span>
        </div>
      )}

      {error && (
        <div className="flex items-center justify-center h-52">
          <span className="text-sm text-muted-foreground text-center">{error}</span>
        </div>
      )}

      {!loading && !error && chartData.length > 0 && (
        <>
          {/* 价格折线图 */}
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={isPositive ? "hsl(142 60% 46%)" : "hsl(0 68% 56%)"} stopOpacity={0.18} />
                  <stop offset="95%" stopColor={isPositive ? "hsl(142 60% 46%)" : "hsl(0 68% 56%)"} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis dataKey="dateShort" tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }}
                tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis domain={[minPrice, maxPrice]} tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }}
                tickLine={false} axisLine={false} tickFormatter={v => `${currency}${v.toFixed(0)}`} width={52} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="close" name="收盘价"
                stroke={isPositive ? "hsl(142 60% 46%)" : "hsl(0 68% 56%)"}
                strokeWidth={1.5} fill="url(#priceGrad)" dot={false} activeDot={{ r: 3 }} />
              <Line type="monotone" dataKey="ma5" name="MA5" stroke="hsl(38 88% 56%)"
                strokeWidth={1} dot={false} connectNulls strokeDasharray="4 2" />
              <Line type="monotone" dataKey="ma20" name="MA20" stroke="hsl(210 100% 58%)"
                strokeWidth={1} dot={false} connectNulls strokeDasharray="4 2" />
              {activeIndicators.has("ma10") && (
                <Line type="monotone" dataKey="ma10" name="MA10" stroke="hsl(280 60% 55%)"
                  strokeWidth={1} dot={false} connectNulls strokeDasharray="4 2" />
              )}
              {activeIndicators.has("ma60") && (
                <Line type="monotone" dataKey="ma60" name="MA60" stroke="hsl(160 60% 45%)"
                  strokeWidth={1} dot={false} connectNulls strokeDasharray="4 2" />
              )}
              {activeIndicators.has("boll") && (
                <>
                  <Line type="monotone" dataKey="bollUpper" name="BOLL上" stroke="hsl(45 80% 55%)"
                    strokeWidth={0.8} dot={false} connectNulls strokeDasharray="3 2" />
                  <Line type="monotone" dataKey="bollMiddle" name="BOLL中" stroke="hsl(45 60% 45%)"
                    strokeWidth={0.8} dot={false} connectNulls />
                  <Line type="monotone" dataKey="bollLower" name="BOLL下" stroke="hsl(45 80% 55%)"
                    strokeWidth={0.8} dot={false} connectNulls strokeDasharray="3 2" />
                </>
              )}
            </ComposedChart>
          </ResponsiveContainer>

          {/* 成交量 */}
          <div className="mt-1">
            <ResponsiveContainer width="100%" height={60}>
              <ComposedChart data={chartData} margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
                <XAxis dataKey="dateShort" hide />
                <YAxis hide />
                <Tooltip content={() => null} />
                <Bar dataKey="volume" name="成交量" shape={<CandleBar />} maxBarSize={6} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* RSI 子图 */}
          {showRSI && (
            <div className="mt-1">
              <p className="text-[9px] text-muted-foreground mb-0.5 px-1">RSI(14)</p>
              <ResponsiveContainer width="100%" height={80}>
                <ComposedChart data={chartData} margin={{ top: 2, right: 8, left: 0, bottom: 0 }}>
                  <XAxis dataKey="dateShort" hide />
                  <YAxis domain={[0, 100]} hide />
                  <Tooltip content={() => null} />
                  <Line type="monotone" dataKey="rsi" name="RSI" stroke="hsl(200 80% 55%)"
                    strokeWidth={1} dot={false} connectNulls />
                  {/* 超买超卖参考线 - 用 Area 模拟 */}
                  <Area type="monotone" dataKey={() => 70} stroke="hsl(0 68% 56%)" strokeOpacity={0.3}
                    strokeWidth={0.5} fill="none" strokeDasharray="3 3" />
                  <Area type="monotone" dataKey={() => 30} stroke="hsl(142 60% 46%)" strokeOpacity={0.3}
                    strokeWidth={0.5} fill="none" strokeDasharray="3 3" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* MACD 子图 */}
          {showMACD && (
            <div className="mt-1">
              <p className="text-[9px] text-muted-foreground mb-0.5 px-1">MACD(12,26,9)</p>
              <ResponsiveContainer width="100%" height={80}>
                <ComposedChart data={chartData} margin={{ top: 2, right: 8, left: 0, bottom: 0 }}>
                  <XAxis dataKey="dateShort" hide />
                  <YAxis hide domain={["auto", "auto"]} />
                  <Tooltip content={() => null} />
                  <Bar dataKey="macdHist" name="MACD柱" fill="hsl(30 80% 55%)" maxBarSize={3} fillOpacity={0.5} />
                  <Line type="monotone" dataKey="macd" name="MACD" stroke="hsl(30 80% 55%)"
                    strokeWidth={1} dot={false} connectNulls />
                  <Line type="monotone" dataKey="macdSignal" name="Signal" stroke="hsl(210 100% 58%)"
                    strokeWidth={1} dot={false} connectNulls />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 图例 */}
          <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground flex-wrap">
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-px bg-gold inline-block" style={{ borderTop: "1px dashed hsl(38 88% 56%)" }} />
              MA5
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-px inline-block" style={{ borderTop: "1px dashed hsl(210 100% 58%)" }} />
              MA20
            </span>
            {activeIndicators.has("ma10") && (
              <span className="flex items-center gap-1.5">
                <span className="w-4 h-px inline-block" style={{ borderTop: "1px dashed hsl(280 60% 55%)" }} />
                MA10
              </span>
            )}
            {activeIndicators.has("ma60") && (
              <span className="flex items-center gap-1.5">
                <span className="w-4 h-px inline-block" style={{ borderTop: "1px dashed hsl(160 60% 45%)" }} />
                MA60
              </span>
            )}
            <span className="text-muted-foreground ml-auto">{chartData.length} 个交易日</span>
          </div>
        </>
      )}
    </div>
  )
}
