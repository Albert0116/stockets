import { useState, useEffect } from "react"
import { BarChart3, Loader2, TrendingUp, TrendingDown, Target, Shield, Activity, DollarSign, Clock } from "lucide-react"
import { LineChart, Line as RLine, XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer } from "recharts"
import { cn, formatPct } from "@/lib/utils"
import {
  fetchBacktestStrategies,
  runBacktest,
  scanBestStrategy,
  type BacktestStrategy,
  type BacktestResult,
  type Market,
} from "@/lib/api"

interface Props {
  symbol?: string
  market?: Market
  className?: string
}

const PERIODS = [
  { value: "6mo", label: "6个月" },
  { value: "1y", label: "1年" },
  { value: "2y", label: "2年" },
]

export default function BacktestPanel({ symbol: propSymbol, market: propMarket, className }: Props) {
  const [symbol, setSymbol] = useState(propSymbol || "")
  const [market, setMarket] = useState<Market>(propMarket || "us")
  const [strategies, setStrategies] = useState<BacktestStrategy[]>([])
  const [strategyKey, setStrategyKey] = useState("sma_cross")
  const [period, setPeriod] = useState("1y")
  const [cash, setCash] = useState(100000)
  const [loading, setLoading] = useState(false)
  const [scanLoading, setScanLoading] = useState(false)
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [scanResults, setScanResults] = useState<BacktestResult[]>([])
  const [error, setError] = useState("")
  const [params, setParams] = useState<Record<string, number>>({})

  // 同步外部 prop
  useEffect(() => {
    if (propSymbol) setSymbol(propSymbol)
  }, [propSymbol])
  useEffect(() => {
    if (propMarket) setMarket(propMarket)
  }, [propMarket])

  // 加载策略列表
  useEffect(() => {
    fetchBacktestStrategies().then((s) => {
      setStrategies(s)
      if (s.length > 0) {
        setStrategyKey(s[0].key)
        setParams({ ...s[0].params })
      }
    })
  }, [])

  const currentStrategy = strategies.find((s) => s.key === strategyKey)

  const handleStrategyChange = (key: string) => {
    setStrategyKey(key)
    const s = strategies.find((ss) => ss.key === key)
    if (s) setParams({ ...s.params })
    setResult(null)
  }

  const handleRun = async () => {
    if (!symbol.trim()) return
    setLoading(true)
    setError("")
    setScanResults([])
    try {
      const r = await runBacktest({
        symbol: symbol.trim().toUpperCase(),
        market,
        strategy_key: strategyKey,
        params: Object.keys(params).length > 0 ? params : undefined,
        period,
        initial_cash: cash,
      })
      if (r.error) { setError(r.error); setResult(null) }
      else setResult(r)
    } catch (e: any) {
      setError(e.message || "回测失败")
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  const handleScanBest = async () => {
    if (!symbol.trim()) return
    setScanLoading(true)
    setError("")
    try {
      const data = await scanBestStrategy(symbol.trim().toUpperCase(), market, period)
      setScanResults(data.results || [])
    } catch (e: any) {
      setError(e.message || "扫描失败")
    } finally {
      setScanLoading(false)
    }
  }

  return (
    <div className={cn("card-base p-5", className)}>
      <div className="flex items-center gap-2 mb-4">
        <BarChart3 className="w-4 h-4 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">策略回测</h3>
      </div>

      {/* 输入区 */}
      {!propSymbol && (
        <div className="mb-3">
          <label className="text-[11px] text-muted-foreground mb-1 block">股票代码</label>
          <input
            type="text"
            value={symbol}
            onChange={(e) => { setSymbol(e.target.value); setResult(null) }}
            placeholder={market === "cn" ? "如 600519" : "如 AAPL"}
            className="w-full px-3 py-2 text-sm bg-surface-2 border border-border rounded-lg focus:border-primary/50 focus:outline-none mono"
          />
        </div>
      )}

      {/* 策略选择 */}
      <div className="mb-3">
        <label className="text-[11px] text-muted-foreground mb-1 block">策略</label>
        <select
          value={strategyKey}
          onChange={(e) => handleStrategyChange(e.target.value)}
          className="w-full px-3 py-2 text-sm bg-surface-2 border border-border rounded-lg focus:border-primary/50 focus:outline-none"
        >
          {strategies.map((s) => (
            <option key={s.key} value={s.key}>{s.name}</option>
          ))}
        </select>
        {currentStrategy && (
          <p className="text-[10px] text-muted-foreground mt-1">{currentStrategy.description}</p>
        )}
      </div>

      {/* 策略参数 */}
      {currentStrategy && Object.keys(currentStrategy.params).length > 0 && (
        <div className="mb-3">
          <label className="text-[11px] text-muted-foreground mb-1 block">参数</label>
          <div className="grid grid-cols-2 gap-2">
            {Object.keys(currentStrategy.params).map((k) => (
              <div key={k}>
                <span className="text-[10px] text-muted-foreground">{currentStrategy.param_descriptions?.[k] || k}</span>
                <input
                  type="number"
                  value={params[k] ?? currentStrategy.params[k]}
                  onChange={(e) => setParams((p) => ({ ...p, [k]: Number(e.target.value) || 0 }))}
                  className="w-full px-2 py-1.5 text-xs bg-surface-2 border border-border rounded focus:border-primary/50 focus:outline-none mono"
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 回测周期 + 资金 */}
      <div className="grid grid-cols-2 gap-2 mb-4">
        <div>
          <label className="text-[11px] text-muted-foreground mb-1 block">周期</label>
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="w-full px-2 py-1.5 text-xs bg-surface-2 border border-border rounded focus:border-primary/50 focus:outline-none"
          >
            {PERIODS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-[11px] text-muted-foreground mb-1 block">初始资金</label>
          <input
            type="number"
            value={cash}
            onChange={(e) => setCash(Number(e.target.value) || 100000)}
            className="w-full px-2 py-1.5 text-xs bg-surface-2 border border-border rounded focus:border-primary/50 focus:outline-none mono"
          />
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={handleRun}
          disabled={loading || !symbol.trim()}
          className="flex-1 px-3 py-2 text-xs font-medium bg-primary text-primary-foreground rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {loading ? <Loader2 className="w-3 h-3 animate-spin inline mr-1" /> : <Activity className="w-3 h-3 inline mr-1" />}
          运行回测
        </button>
        <button
          onClick={handleScanBest}
          disabled={scanLoading || !symbol.trim()}
          className="px-3 py-2 text-xs font-medium border border-border rounded-lg hover:border-primary/50 transition-colors disabled:opacity-50"
        >
          {scanLoading ? <Loader2 className="w-3 h-3 animate-spin inline mr-1" /> : <Target className="w-3 h-3 inline mr-1" />}
          扫描最佳
        </button>
      </div>

      {/* 错误 */}
      {error && (
        <div className="p-2.5 rounded-lg bg-bear/8 border border-bear/20 text-xs text-bear mb-3">{error}</div>
      )}

      {/* 单次回测结果 */}
      {result && (
        <div className="p-3 rounded-lg bg-surface-2 border border-border animate-fade-up">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-foreground">{result.strategy}</span>
            <span className={cn(
              "text-xs font-bold mono",
              result.total_return_pct >= 0 ? "text-bull" : "text-bear"
            )}>
              {result.total_return_pct >= 0 ? "+" : ""}{result.total_return_pct.toFixed(2)}%
            </span>
          </div>

          {/* 权益曲线 */}
          {result.equity_curve && result.equity_curve.length > 1 && (
            <div className="mb-2">
              <p className="text-[10px] text-muted-foreground mb-1">权益曲线</p>
              <ResponsiveContainer width="100%" height={150}>
                <LineChart data={result.equity_curve.map((e, i) => ({
                  date: e.date.slice(5),
                  strategy: e.value,
                  buyHold: result.buy_hold_curve?.[i]?.value,
                }))} margin={{ top: 2, right: 4, left: 0, bottom: 0 }}>
                  <XAxis dataKey="date" hide />
                  <YAxis hide domain={["auto", "auto"]} />
                  <RTooltip content={({ active, payload }) => {
                    if (!active || !payload?.length) return null
                    return (
                      <div className="card-base px-2 py-1 text-[10px]">
                        {payload.map(p => (
                          <div key={p.name} style={{ color: p.color }}>
                            {p.name === "strategy" ? "策略" : "持有"}: {(p.value as number).toLocaleString()}
                          </div>
                        ))}
                      </div>
                    )
                  }} />
                  <RLine type="monotone" dataKey="strategy" stroke="hsl(142 60% 46%)" strokeWidth={1.5} dot={false} />
                  <RLine type="monotone" dataKey="buyHold" stroke="hsl(210 100% 58%)" strokeWidth={1} dot={false} strokeDasharray="4 2" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 核心指标 */}
          <div className="grid grid-cols-3 gap-2 text-center">
            {[
              { label: "年化收益", value: `${result.annual_return_pct >= 0 ? "+" : ""}${result.annual_return_pct.toFixed(1)}%`, up: result.annual_return_pct > 0 },
              { label: "最大回撤", value: `${result.max_drawdown_pct.toFixed(1)}%`, up: false },
              { label: "夏普比率", value: result.sharpe_ratio.toFixed(2), up: result.sharpe_ratio > 1 },
            ].map((item) => (
              <div key={item.label} className="p-1.5 rounded bg-surface-1">
                <p className="text-[10px] text-muted-foreground">{item.label}</p>
                <p className={cn("text-xs font-semibold mono", item.up ? "text-bull" : "text-foreground")}>
                  {item.value}
                </p>
              </div>
            ))}
          </div>

          {/* 第二行指标 */}
          <div className="grid grid-cols-4 gap-2 text-center mt-2">
            {[
              { label: "胜率", value: `${result.win_rate_pct.toFixed(1)}%` },
              { label: "盈亏比", value: result.profit_factor > 900 ? "∞" : result.profit_factor.toFixed(2) },
              { label: "交易次数", value: `${result.total_trades}` },
              { label: "vs 持有", value: `${result.vs_buy_hold >= 0 ? "+" : ""}${result.vs_buy_hold.toFixed(1)}%` },
            ].map((item) => (
              <div key={item.label} className="p-1.5 rounded bg-surface-1">
                <p className="text-[10px] text-muted-foreground">{item.label}</p>
                <p className="text-xs font-semibold mono text-foreground">{item.value}</p>
              </div>
            ))}
          </div>

          {/* 资金概况 */}
          <div className="flex items-center justify-between mt-2 px-1 py-1.5 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1">
              <DollarSign className="w-3 h-3" />
              {(result.initial_cash / 1000).toFixed(0)}K → {(result.final_value / 1000).toFixed(1)}K
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {result.data_days}天 · {result.run_time_ms.toFixed(0)}ms
            </span>
          </div>

          {/* 交易明细 */}
          {result.trades && result.trades.length > 0 && (
            <div className="mt-2 border-t border-border/50 pt-2">
              <p className="text-[10px] text-muted-foreground mb-1.5 font-medium">交易明细 (最近10笔)</p>
              <div className="space-y-1 max-h-36 overflow-y-auto">
                {result.trades.slice(0, 10).map((t, i) => (
                  <div key={i} className="flex items-center justify-between text-[10px] px-1.5 py-1 rounded bg-background/50">
                    <span className="mono text-muted-foreground">{t.date}</span>
                    <span className={cn("mono font-medium", t.pnl >= 0 ? "text-bull" : "text-bear")}>
                      {t.pnl >= 0 ? "+" : ""}{t.pnl.toFixed(0)} ({t.pnl_pct.toFixed(1)}%)
                    </span>
                    <span className="text-muted-foreground">{t.holding_days}天</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 扫描结果 */}
      {scanResults.length > 0 && (
        <div className="mt-3 animate-fade-up">
          <p className="text-[11px] text-muted-foreground mb-2 font-medium">策略对比</p>
          <div className="space-y-1.5">
            {scanResults.map((r) => (
              <div
                key={r.strategy}
                className="flex items-center justify-between p-2 rounded bg-surface-2 border border-border hover:border-primary/30 cursor-pointer text-xs"
                onClick={() => {
                  const s = strategies.find((ss) => ss.name === r.strategy)
                  if (s) handleStrategyChange(s.key)
                  setResult(r)
                  setScanResults([])
                }}
              >
                <span className="font-medium text-foreground">{r.strategy}</span>
                <div className="flex items-center gap-3 mono">
                  <span className={cn(r.total_return_pct >= 0 ? "text-bull" : "text-bear")}>
                    {r.total_return_pct >= 0 ? "+" : ""}{r.total_return_pct.toFixed(1)}%
                  </span>
                  <span className="text-muted-foreground">胜率 {r.win_rate_pct.toFixed(0)}%</span>
                  <span className="text-muted-foreground">回撤 {r.max_drawdown_pct.toFixed(1)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
