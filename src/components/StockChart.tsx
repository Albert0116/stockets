import { useState, useEffect } from "react"
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Area
} from "recharts"
import { cn } from "@/lib/utils"
import { fetchCandles, type CandleData, type Market } from "@/lib/api"
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

  // 需要从 recharts 坐标系转换 - 用 Bar 替代，这里做简化版折线+成交量
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
  const currency = market === "cn" ? "¥" : "$"

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError("")
    fetchCandles(symbol, period, market)
      .then(data => { if (!cancelled) setCandles(data) })
      .catch(() => { if (!cancelled) setError("数据加载失败，yfinance 可能限流，稍后重试") })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [symbol, period, market])

  const ma5 = calcMA(candles, 5)
  const ma20 = calcMA(candles, 20)

  const chartData = candles.map((c, i) => ({
    ...c,
    dateShort: c.date.slice(5),
    ma5: ma5[i],
    ma20: ma20[i],
    isUp: c.close >= c.open,
  }))

  const prices = candles.map(c => c.close)
  const minPrice = Math.min(...prices) * 0.997
  const maxPrice = Math.max(...prices) * 1.003

  const isPositive = candles.length >= 2
    ? candles[candles.length - 1].close >= candles[0].close
    : true

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

          {/* 图例 */}
          <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-px bg-gold inline-block" style={{ borderTop: "1px dashed hsl(38 88% 56%)" }} />
              MA5
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-4 h-px inline-block" style={{ borderTop: "1px dashed hsl(210 100% 58%)" }} />
              MA20
            </span>
            <span className="text-muted-foreground ml-auto">{chartData.length} 个交易日</span>
          </div>
        </>
      )}
    </div>
  )
}
