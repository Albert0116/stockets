import { TrendingUp, TrendingDown, Building2, DollarSign, Star } from "lucide-react"
import { cn, formatNumber, formatPct } from "@/lib/utils"
import type { QuoteData, Market } from "@/lib/api"

interface QuoteCardProps {
  data: QuoteData
  className?: string
  isFavorited?: boolean
  onToggleFavorite?: (symbol: string, name: string) => void
  market?: Market
}

export default function QuoteCard({ data, className, isFavorited, onToggleFavorite, market = "us" }: QuoteCardProps) {
  const isFav = isFavorited ?? false
  const isUp = data.change_pct >= 0
  const pctText = formatPct(data.change_pct)
  const changeText = (data.change >= 0 ? "+" : "") + data.change.toFixed(2)
  const currency = market === "cn" ? "¥" : "$"

  return (
    <div className={cn("card-base p-5 animate-fade-up", className)}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          {data.logo ? (
            <img src={data.logo} alt={data.name} className="w-9 h-9 rounded-lg object-contain bg-surface-2 p-0.5" />
          ) : (
            <div className="w-9 h-9 rounded-lg bg-accent flex items-center justify-center">
              <Building2 className="w-4 h-4 text-accent-foreground" />
            </div>
          )}
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-foreground mono text-base leading-tight">{data.symbol}</span>
              {onToggleFavorite && (
                <button
                  onClick={(e) => { e.stopPropagation(); onToggleFavorite(data.symbol, data.name) }}
                  className="transition-transform hover:scale-110"
                  title={isFav ? "取消收藏" : "添加收藏"}
                >
                  <Star className={cn("w-3.5 h-3.5", isFav ? "fill-gold text-gold" : "text-muted-foreground")} />
                </button>
              )}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5 truncate max-w-[180px]">{data.name}</div>
          </div>
        </div>
        <div className={cn(
          "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-semibold",
          isUp ? "bg-bull-muted text-bull" : "bg-bear-muted text-bear"
        )}>
          {isUp ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
          {pctText}
        </div>
      </div>

      {/* Price */}
      <div className="mb-4">
        <div className="text-3xl font-bold text-foreground mono tracking-tight">
          {currency}{data.price.toFixed(2)}
        </div>
        <div className={cn("text-sm mt-1 mono", isUp ? "text-bull" : "text-bear")}>
          {changeText} 今日
        </div>
      </div>

      {/* OHLC Grid */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        {[
          { label: "开盘", value: data.open.toFixed(2) },
          { label: "昨收", value: data.prev_close.toFixed(2) },
          { label: "最高", value: data.high.toFixed(2), bull: true },
          { label: "最低", value: data.low.toFixed(2), bear: true },
        ].map(item => (
          <div key={item.label} className="bg-surface-2 rounded-md px-3 py-2">
            <div className="text-xs text-muted-foreground mb-0.5">{item.label}</div>
            <div className={cn(
              "text-sm font-medium mono",
              item.bull ? "text-bull" : item.bear ? "text-bear" : "text-foreground"
            )}>{currency}{item.value}</div>
          </div>
        ))}
      </div>

      {/* Meta */}
      <div className="flex items-center gap-2 flex-wrap">
        {data.market_cap > 0 && (
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <DollarSign className="w-3 h-3" />
            市值 {formatNumber(data.market_cap * 1e6)}
          </div>
        )}
        {data.industry && (
          <div className="text-xs text-muted-foreground px-2 py-0.5 bg-surface-2 rounded">
            {data.industry}
          </div>
        )}
        {data.exchange && (
          <div className="text-xs text-muted-foreground px-2 py-0.5 bg-surface-2 rounded">
            {data.exchange}
          </div>
        )}
      </div>
    </div>
  )
}
