import { useState, useCallback, useEffect, useRef, useMemo } from "react"
import { Activity, Github, RefreshCw, Loader2, AlertCircle, BarChart2, Star, Bell } from "lucide-react"
import { cn, formatPct } from "@/lib/utils"
import { API_BASE, fetchQuote, fetchNews, fetchTrending, type QuoteData, type NewsItem, type Market, type TrendingData } from "@/lib/api"
import { useFavorites } from "@/hooks/useFavorites"
import { useMarket } from "@/hooks/useMarket"
import SearchBar from "@/components/SearchBar"
import QuoteCard from "@/components/QuoteCard"
import StockChart from "@/components/StockChart"
import AnalysisTabs from "@/components/AnalysisTabs"
import WatchlistBar from "@/components/WatchlistBar"
import MarketSelector from "@/components/MarketSelector"
import ScannerPanel from "@/components/ScannerPanel"
import SettingsPanel from "@/components/SettingsPanel"
import BacktestPanel from "@/components/BacktestPanel"
import SentimentPanel from "@/components/SentimentPanel"
import AlertsPanel from "@/components/AlertsPanel"
import PortfolioPanel from "@/components/PortfolioPanel"
import ComparePanel from "@/components/ComparePanel"

const FALLBACK_US = ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", "BABA"]
const FALLBACK_CN = ["600519", "000858", "000001", "300750", "002594", "601318", "000333", "688981"]

// 收藏股概览组件（欢迎页）
function FavoritesOverview({
  favorites,
  onSelect,
  market,
}: {
  favorites: { symbol: string; name: string; market: Market }[]
  onSelect: (sym: string) => void
  market: Market
}) {
  const [prices, setPrices] = useState<Record<string, { price: number; changePct: number }>>({})
  const currency = market === "cn" ? "¥" : "$"
  const filtered = favorites.filter((f) => f.market === market)

  useEffect(() => {
    const load = async () => {
      const results: Record<string, { price: number; changePct: number }> = {}
      await Promise.all(
        filtered.map(async (f) => {
          try {
            const q = await fetchQuote(f.symbol, f.market)
            results[f.symbol] = { price: q.price, changePct: q.change_pct }
          } catch { /* skip */ }
        })
      )
      setPrices(results)
    }
    if (filtered.length > 0) load()
  }, [favorites, market])

  if (filtered.length === 0) return null

  return (
    <div className="mb-8">
      <p className="text-xs text-muted-foreground mb-3 uppercase tracking-wider font-medium flex items-center gap-1.5">
        <Star className="w-3 h-3 text-gold" />我的自选
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
        {filtered.map((f) => {
          const p = prices[f.symbol]
          const isUp = p && p.changePct >= 0
          return (
            <button
              key={`${f.market}-${f.symbol}`}
              onClick={() => onSelect(f.symbol)}
              className="card-base p-3 text-left hover:border-primary/40 transition-colors group"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="mono text-sm font-semibold text-foreground">{f.symbol}</span>
                {p && (
                  <span className={cn("text-[10px] mono font-medium", isUp ? "text-bull" : "text-bear")}>
                    {formatPct(p.changePct)}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-muted-foreground truncate">{f.name}</p>
              {p ? (
                <p className="text-sm mono font-semibold text-foreground mt-1">{currency}{p.price.toFixed(2)}</p>
              ) : (
                <div className="h-5 w-16 shimmer-bg rounded mt-1" />
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default function App() {
  const [symbol, setSymbol] = useState("")
  const [quote, setQuote] = useState<QuoteData | null>(null)
  const [news, setNews] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [backendOk, setBackendOk] = useState<boolean | null>(null)
  const [showAlerts, setShowAlerts] = useState(false)
  const { market, setMarket, currency } = useMarket()
  const { favorites, toggleFavorite, isFavorite, removeFavorite, setGroup, hasFavorites } = useFavorites()
  // P1-10: 用 useMemo 稳定 favorites 引用，避免子组件不必要的重渲染
  const stableFavorites = useMemo(() => favorites, [favorites])
  const [trending, setTrending] = useState<TrendingData | null>(null)

  const popular = useMemo(() => {
    if (trending && (trending.gainers.length > 0 || trending.active.length > 0)) {
      const all = [...trending.gainers, ...trending.losers, ...trending.active]
      return [...new Set(all.map(s => s.symbol))].slice(0, 10)
    }
    return market === "cn" ? FALLBACK_CN : FALLBACK_US
  }, [trending, market])

  // 检测后端
  useEffect(() => {
    fetch(`${API_BASE}/api/health`)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false))
  }, [])

  const loadStock = useCallback(async (sym: string) => {
    if (!sym.trim()) return
    const upper = sym.trim().toUpperCase()
    setLoading(true)
    setError("")
    setQuote(null)
    setNews([])
    setSymbol(upper)
    try {
      const [q, n] = await Promise.all([
        fetchQuote(upper, market),
        fetchNews(upper, market),
      ])
      setQuote(q)
      setNews(n)
    } catch {
      setError(`无法获取 ${upper} 的数据，请检查股票代码或后端服务`)
    } finally {
      setLoading(false)
    }
  }, [market])

  // 加载动态热门股票
  useEffect(() => {
    fetchTrending(market).then(setTrending).catch(() => setTrending(null))
  }, [market])

  // 监听来自扫描器的选股事件（用ref避免依赖问题）
  const loadStockRef = useRef(loadStock)
  loadStockRef.current = loadStock
  const marketRef = useRef(market)
  marketRef.current = market

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail
      if (detail?.symbol) {
        if (detail.market && detail.market !== marketRef.current) {
          setMarket(detail.market)
        }
        loadStockRef.current(detail.symbol)
      }
    }
    // 快捷加自选
    const addHandler = (e: Event) => {
      const d = (e as CustomEvent).detail
      if (d?.symbol) {
        toggleFavorite(d.symbol, d.name || d.symbol, d.market || marketRef.current)
      }
    }
    // 快捷设预警
    const alertHandler = (e: Event) => {
      const d = (e as CustomEvent).detail
      if (d?.symbol) {
        setShowAlerts(true)
        if (d.symbol !== symbol) {
          loadStockRef.current(d.symbol)
        }
      }
    }
    window.addEventListener("select-stock", handler)
    window.addEventListener("add-to-watchlist", addHandler)
    window.addEventListener("quick-alert", alertHandler)
    return () => {
      window.removeEventListener("select-stock", handler)
      window.removeEventListener("add-to-watchlist", addHandler)
      window.removeEventListener("quick-alert", alertHandler)
    }
  }, [toggleFavorite, symbol])

  // 市场切换时重新加载当前股票
  const handleMarketChange = useCallback((m: Market) => {
    setMarket(m)
    // 切换市场时清除当前股票（代码格式不同）
    setSymbol("")
    setQuote(null)
    setNews([])
    setError("")
  }, [setMarket])

  const handleRefresh = () => { if (symbol) loadStock(symbol) }

  const handleToggleFavorite = useCallback((sym: string, name: string) => {
    toggleFavorite(sym, name, market)
  }, [toggleFavorite, market])

  const handleIsFavorite = useCallback((sym: string) => {
    return isFavorite(sym, market)
  }, [isFavorite, market])

  const handleRemoveFavorite = useCallback((sym: string, m: Market) => {
    removeFavorite(sym, m)
  }, [removeFavorite])

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* ─── Header ─── */}
      <header className="sticky top-0 z-40 border-b border-border glass">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-4">
          {/* Logo */}
          <div className="flex items-center gap-2 shrink-0">
            <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center glow-sm">
              <Activity className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="font-bold text-sm tracking-tight text-foreground">
              智析
              <span className="ml-1.5 text-xs font-normal text-muted-foreground mono">DeepSeek</span>
            </span>
          </div>

          {/* Search */}
          <div className="flex-1 max-w-lg">
            <SearchBar onSelect={loadStock} market={market} />
          </div>

          {/* Market Selector */}
          <MarketSelector market={market} onChange={handleMarketChange} />

          {/* Actions */}
          <div className="flex items-center gap-2 shrink-0">
            {/* 刷新按钮 */}
            {symbol && (
              <button onClick={handleRefresh} disabled={loading}
                className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-surface-2 transition-colors">
                <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
              </button>
            )}
            {/* 预警铃铛 */}
            <button onClick={() => setShowAlerts(v => !v)}
              className={cn(
                "relative p-2 rounded-lg transition-colors",
                showAlerts
                  ? "text-primary bg-primary/10"
                  : "text-muted-foreground hover:text-foreground hover:bg-surface-2"
              )}>
              <Bell className="w-4 h-4" />
            </button>
            {/* 后端状态指示 */}
            <div className={cn(
              "flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-full",
              backendOk === null ? "text-muted-foreground" :
              backendOk ? "text-bull bg-bull/10" : "text-bear bg-bear/10"
            )}>
              <span className={cn(
                "w-1.5 h-1.5 rounded-full",
                backendOk === null ? "bg-muted-foreground animate-pulse" :
                backendOk ? "bg-bull" : "bg-bear"
              )} />
              {backendOk === null ? "连接中" : backendOk ? "服务正常" : "后端离线"}
            </div>
          </div>
        </div>
      </header>

      {/* 收藏栏 */}
      <WatchlistBar
        favorites={favorites}
        onSelect={loadStock}
        onRemove={handleRemoveFavorite}
        activeSymbol={symbol}
        market={market}
      />

      <main className="max-w-7xl mx-auto px-4 py-6">

        {/* 后端离线提示 */}
        {backendOk === false && (
          <div className="mb-6 p-4 rounded-lg border border-bear/30 bg-bear/8 flex items-start gap-3 animate-fade-up">
            <AlertCircle className="w-5 h-5 text-bear shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-foreground">后端服务未启动</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                请在项目目录运行：
                <code className="mono ml-1 px-1.5 py-0.5 bg-surface-2 rounded text-foreground">
                  "C:\Users\lxz_y\.conda\envs\finrobot\python.exe" server.py
                </code>
              </p>
            </div>
          </div>
        )}

        {/* 未搜索时显示欢迎页 */}
        {!symbol && !loading && (
          <div className="animate-fade-up">
            {/* Hero */}
            <div className="relative rounded-2xl overflow-hidden mb-8 border border-border">
              <img src="/images/hero.png" alt="智析 AI 股票分析" loading="eager"
                className="w-full h-52 object-cover opacity-60" />
              <div className="absolute inset-0 bg-gradient-to-t from-background via-background/60 to-transparent" />
              <div className="absolute bottom-0 left-0 right-0 p-6">
                <h1 className="text-2xl font-bold text-foreground mb-1">
                  智析 AI 股票分析系统
                </h1>
                <p className="text-sm text-muted-foreground">
                  由 DeepSeek 大模型驱动 · {market === "cn" ? "AKShare" : "Finnhub"} 实时行情 · Multi-Agent 深度分析
                </p>
              </div>
            </div>

            {/* 收藏概览 */}
            <FavoritesOverview favorites={stableFavorites} onSelect={loadStock} market={market} />

            {/* 热门入口 */}
            <div>
              <p className="text-xs text-muted-foreground mb-3 uppercase tracking-wider font-medium">
                热门{market === "cn" ? "A股" : "股票"}
              </p>
              {/* 分类标签 */}
              {trending && (trending.gainers.length > 0 || trending.losers.length > 0) && (
                <div className="flex gap-3 mb-2">
                  {trending.gainers.length > 0 && (
                    <div className="text-[10px]">
                      <span className="text-bull font-medium">▲ 涨幅榜</span>
                      {trending.gainers.slice(0, 3).map(s => (
                        <button key={s.symbol} onClick={() => loadStock(s.symbol)}
                          className="ml-1 mono text-muted-foreground hover:text-foreground">{s.symbol}</button>
                      ))}
                    </div>
                  )}
                  {trending.losers.length > 0 && (
                    <div className="text-[10px]">
                      <span className="text-bear font-medium">▼ 跌幅榜</span>
                      {trending.losers.slice(0, 3).map(s => (
                        <button key={s.symbol} onClick={() => loadStock(s.symbol)}
                          className="ml-1 mono text-muted-foreground hover:text-foreground">{s.symbol}</button>
                      ))}
                    </div>
                  )}
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                {popular.map(s => (
                  <button key={s} onClick={() => loadStock(s)}
                    className={cn(
                      "px-4 py-2 rounded-lg text-sm font-medium mono transition-all duration-150",
                      "border border-border text-muted-foreground",
                      "hover:border-primary/50 hover:text-foreground hover:bg-accent/40"
                    )}>
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* 扫描器 + 通知设置 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
              <ScannerPanel />
              <SettingsPanel />
            </div>

            {/* 持仓跟踪 + 多股对比 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              <PortfolioPanel market={market} />
              <ComparePanel market={market} />
            </div>
          </div>
        )}

        {/* 加载中 */}
        {loading && (
          <div className="flex items-center justify-center py-24 gap-3 text-muted-foreground animate-fade-up">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm">加载 {symbol} 数据中...</span>
          </div>
        )}

        {/* 错误 */}
        {error && !loading && (
          <div className="p-5 rounded-lg border border-bear/30 bg-bear/8 flex items-start gap-3 animate-fade-up">
            <AlertCircle className="w-5 h-5 text-bear shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-foreground">获取数据失败</p>
              <p className="text-xs text-muted-foreground mt-0.5">{error}</p>
            </div>
          </div>
        )}

        {/* 主要内容 */}
        {quote && !loading && (
          <div className="space-y-4 animate-fade-up">
            {/* 顶部行: 报价 + K线 */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <QuoteCard
                data={quote}
                isFavorited={handleIsFavorite(quote.symbol)}
                onToggleFavorite={handleToggleFavorite}
                market={market}
              />
              <div className="lg:col-span-2">
                <StockChart symbol={quote.symbol} market={market} />
              </div>
            </div>

            {/* AI分析 (Multi-Agent) */}
            <AnalysisTabs quote={quote} market={market} />

            {/* 舆情分析(含新闻) + 策略回测 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <SentimentPanel symbol={quote.symbol} market={market} news={news} />
              <BacktestPanel symbol={quote.symbol} market={market} />
            </div>

            {/* 预警管理（展开时） */}
            {showAlerts && (
              <AlertsPanel
                symbol={quote.symbol}
                market={market}
                onClose={() => setShowAlerts(false)}
              />
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border mt-12 py-4">
        <div className="max-w-7xl mx-auto px-4 flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <BarChart2 className="w-3.5 h-3.5" />
            <span>智析 · DeepSeek · {market === "cn" ? "AKShare" : "Finnhub"}</span>
          </div>
          <a href="https://github.com/AI4Finance-Foundation/FinRobot" target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1 hover:text-foreground transition-colors">
            <Github className="w-3.5 h-3.5" />
            开源项目
          </a>
        </div>
      </footer>
    </div>
  )
}
