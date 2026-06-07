import { useState, useEffect, useRef, useMemo } from "react"
import { Star, Loader2, TrendingUp, TrendingDown, X } from "lucide-react"
import { cn, formatPct } from "@/lib/utils"
import { fetchQuote, type QuoteData, type Market } from "@/lib/api"
import type { FavoriteStock } from "@/hooks/useFavorites"
import { FAVORITE_GROUPS } from "@/hooks/useFavorites"
import SearchBar from "./SearchBar"

interface WatchlistBarProps {
  favorites: FavoriteStock[]
  onSelect: (symbol: string) => void
  onRemove: (symbol: string, market: Market) => void
  activeSymbol: string
  market: Market
  className?: string
}

interface FavoriteSnapshot {
  symbol: string
  name: string
  price: number
  changePct: number
  loading: boolean
}

export default function WatchlistBar({
  favorites,
  onSelect,
  onRemove,
  activeSymbol,
  market,
  className,
}: WatchlistBarProps) {
  const [snapshots, setSnapshots] = useState<FavoriteSnapshot[]>([])
  const [showSearch, setShowSearch] = useState(false)
  const [activeGroup, setActiveGroup] = useState<string>("全部")
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // 过滤当前市场的收藏（useMemo 稳定引用，避免 useEffect 无限重建定时器）
  const marketFavorites = useMemo(
    () => favorites.filter((f) => f.market === market),
    [favorites, market]
  )
  // 按分组过滤
  const displayFavorites = useMemo(
    () => activeGroup === "全部" ? marketFavorites : marketFavorites.filter(f => (f.group || "关注") === activeGroup),
    [marketFavorites, activeGroup]
  )
  const currency = market === "cn" ? "¥" : "$"

  // 启动价格轮询
  useEffect(() => {
    if (displayFavorites.length === 0) {
      setSnapshots([])
      return
    }

    const loadAll = async () => {
      const results = await Promise.all(
        displayFavorites.map(async (f) => {
          try {
            const q: QuoteData = await fetchQuote(f.symbol, f.market)
            return {
              symbol: f.symbol,
              name: f.name || q.name,
              price: q.price,
              changePct: q.change_pct,
              loading: false,
            }
          } catch {
            return {
              symbol: f.symbol,
              name: f.name,
              price: 0,
              changePct: 0,
              loading: false,
            }
          }
        })
      )
      setSnapshots(results)
    }

    loadAll()
    timerRef.current = setInterval(loadAll, 30000) // 30秒刷新

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [displayFavorites, market])

  if (marketFavorites.length === 0 && !showSearch) return null

  return (
    <div className={cn("w-full", className)}>
      <div className="max-w-7xl mx-auto px-4">
        <div className="glass-card border border-border/60 rounded-xl overflow-hidden">
          <div className="flex items-center">
            {/* 收藏标题 */}
            <div className="flex items-center gap-1.5 px-3 py-2 border-r border-border shrink-0">
              <Star className="w-3.5 h-3.5 text-gold" />
              <span className="text-xs font-medium text-foreground">自选</span>
              <span className="text-[10px] text-muted-foreground mono">
                {marketFavorites.length}
              </span>
            </div>

            {/* 分组 Tab */}
            <div className="flex items-center gap-0.5 px-2 border-r border-border shrink-0">
              {FAVORITE_GROUPS.map(g => (
                <button key={g} onClick={() => setActiveGroup(g)}
                  className={cn(
                    "px-2 py-1 text-[10px] rounded transition-colors",
                    activeGroup === g
                      ? "bg-primary/15 text-primary font-medium"
                      : "text-muted-foreground hover:text-foreground hover:bg-surface-2/50"
                  )}>
                  {g}
                </button>
              ))}
            </div>

            {/* 收藏股滚动 */}
            {marketFavorites.length > 0 && (
              <div className="flex-1 flex items-center overflow-x-auto scrollbar-none px-1">
                {snapshots.map((s) => {
                  const isActive = s.symbol === activeSymbol
                  const isUp = s.changePct >= 0
                  return (
                    <button
                      key={s.symbol}
                      onClick={() => onSelect(s.symbol)}
                      className={cn(
                        "flex items-center gap-2 px-3 py-2 text-xs shrink-0 transition-colors relative group",
                        "border-r border-border/50",
                        isActive
                          ? "bg-accent/50 text-foreground"
                          : "text-muted-foreground hover:bg-surface-2/50 hover:text-foreground"
                      )}
                    >
                      <div className="text-left">
                        <div className="flex items-center gap-1.5">
                          <span className="mono font-semibold text-foreground">
                            {s.symbol}
                          </span>
                          <span className="text-[10px] text-muted-foreground truncate max-w-[60px]">
                            {s.name}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          {s.loading ? (
                            <Loader2 className="w-2.5 h-2.5 animate-spin" />
                          ) : (
                            <>
                              <span className="mono font-medium">
                                {currency}{s.price.toFixed(2)}
                              </span>
                              <span
                                className={cn(
                                  "mono text-[10px] flex items-center gap-0.5",
                                  isUp ? "text-bull" : "text-bear"
                                )}
                              >
                                {isUp ? (
                                  <TrendingUp className="w-2.5 h-2.5" />
                                ) : (
                                  <TrendingDown className="w-2.5 h-2.5" />
                                )}
                                {formatPct(s.changePct)}
                              </span>
                            </>
                          )}
                        </div>
                      </div>

                      {/* 删除按钮 (hover 显示) */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onRemove(s.symbol, market)
                        }}
                        className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-surface-2 border border-border
                                   flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <X className="w-2.5 h-2.5 text-muted-foreground" />
                      </button>
                    </button>
                  )
                })}
              </div>
            )}

            {/* 添加按钮 */}
            <div className="shrink-0 border-l border-border">
              <button
                onClick={() => setShowSearch(!showSearch)}
                className={cn(
                  "flex items-center gap-1 px-3 py-2 text-xs transition-colors",
                  showSearch
                    ? "bg-accent/50 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-surface-2/50"
                )}
              >
                <span className="text-sm leading-none">+</span>
                <span>添加</span>
              </button>
            </div>
          </div>

          {/* 搜索面板 */}
          {showSearch && (
            <div className="px-3 pb-3 border-t border-border animate-fade-up">
              <div className="pt-3 max-w-md">
                <SearchBar
                  market={market}
                  onSelect={(symbol) => {
                    setShowSearch(false)
                    onSelect(symbol)
                  }}
                />
              </div>
              <p className="text-[10px] text-muted-foreground mt-2">
                搜索股票后，在报价卡片中点击星标收藏
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
