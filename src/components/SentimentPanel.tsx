import { useState, useEffect } from "react"
import { Newspaper, Loader2, TrendingUp, TrendingDown, Minus, ExternalLink, Clock } from "lucide-react"
import { cn } from "@/lib/utils"
import { fetchSentiment, type SentimentResult, type SentimentArticle, type NewsItem, type Market } from "@/lib/api"

interface Props {
  symbol: string
  market: Market
  news?: NewsItem[]
  className?: string
}

const LABEL_COLORS: Record<string, string> = {
  "强烈看多": "text-green-400 bg-green-500/10 border-green-500/30",
  "偏多": "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  "中性": "text-muted-foreground bg-surface-2 border-border",
  "偏空": "text-orange-400 bg-orange-500/10 border-orange-500/30",
  "强烈看空": "text-red-400 bg-red-500/10 border-red-500/30",
  "无数据": "text-muted-foreground bg-surface-2 border-border",
}

export default function SentimentPanel({ symbol, market, news = [], className }: Props) {
  const [result, setResult] = useState<SentimentResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError("")
      try {
        const data = await fetchSentiment(symbol, market)
        if (!cancelled) setResult(data)
      } catch (e: any) {
        if (!cancelled) setError(e.message || "舆情分析失败")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [symbol, market])

  if (loading) {
    return (
      <div className={cn("card-base p-5 flex items-center justify-center gap-2 text-muted-foreground", className)}>
        <Loader2 className="w-4 h-4 animate-spin" />
        <span className="text-xs">分析舆情中...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className={cn("card-base p-5", className)}>
        <p className="text-xs text-muted-foreground">{error}</p>
      </div>
    )
  }

  if (!result) {
    return (
      <div className={cn("card-base p-5", className)}>
        <div className="flex items-center gap-2 mb-3">
          <Newspaper className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">舆情分析</h3>
        </div>
        <p className="text-xs text-muted-foreground text-center py-4">暂无舆情数据，请稍后重试</p>
      </div>
    )
  }

  const { aggregate } = result
  const labelClass = LABEL_COLORS[result.label] || LABEL_COLORS["中性"]

  return (
    <div className={cn("card-base p-5", className)}>
      <div className="flex items-center gap-2 mb-3">
        <Newspaper className="w-4 h-4 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">舆情分析</h3>
      </div>

      {/* 情绪概览 */}
      <div className="flex items-center gap-3 mb-4">
        {/* 评分环 */}
        <div className="relative w-16 h-16 shrink-0">
          <svg className="w-16 h-16 -rotate-90" viewBox="0 0 64 64">
            <circle cx="32" cy="32" r="28" fill="none" stroke="currentColor"
              className="text-surface-2" strokeWidth="5" />
            <circle cx="32" cy="32" r="28" fill="none"
              stroke={result.score > 0 ? "#22c55e" : result.score < 0 ? "#ef4444" : "#6b7280"}
              strokeWidth="5" strokeLinecap="round"
              strokeDasharray={`${Math.abs(result.score) * 176} 176`}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-sm font-bold mono">{result.score >= 0 ? "+" : ""}{result.score.toFixed(1)}</span>
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <span className={cn("inline-block px-2 py-0.5 rounded-full text-[10px] font-medium border", labelClass)}>
            {result.label}
          </span>
          <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed">{result.summary}</p>
        </div>
      </div>

      {/* 情绪分布条 */}
      <div className="mb-4">
        <div className="flex h-2 rounded-full overflow-hidden bg-surface-2">
          <div
            className="bg-green-500 transition-all"
            style={{ width: `${aggregate.positive_ratio * 100}%` }}
          />
          <div
            className="bg-muted-foreground/30 transition-all"
            style={{ width: `${aggregate.neutral_ratio * 100}%` }}
          />
          <div
            className="bg-red-500 transition-all"
            style={{ width: `${aggregate.negative_ratio * 100}%` }}
          />
        </div>
        <div className="flex justify-between mt-1 text-[10px] text-muted-foreground">
          <span>正面 {Math.round(aggregate.positive_ratio * 100)}%</span>
          <span>中性 {Math.round(aggregate.neutral_ratio * 100)}%</span>
          <span>负面 {Math.round(aggregate.negative_ratio * 100)}%</span>
        </div>
      </div>

      {/* 顶部文章 */}
      {aggregate.top_positive.length > 0 && (
        <div className="mb-3">
          <p className="text-[10px] text-muted-foreground mb-1.5 uppercase tracking-wider font-medium">利好信号</p>
          <ArticleList articles={aggregate.top_positive} type="positive" />
        </div>
      )}
      {aggregate.top_negative.length > 0 && (
        <div>
          <p className="text-[10px] text-muted-foreground mb-1.5 uppercase tracking-wider font-medium">风险信号</p>
          <ArticleList articles={aggregate.top_negative} type="negative" />
        </div>
      )}

      {aggregate.top_positive.length === 0 && aggregate.top_negative.length === 0 && (
        <p className="text-xs text-muted-foreground text-center py-2">暂无显著信号文章</p>
      )}

      {/* 全部文章列表 */}
      {result.articles.length > 0 && (
        <details className="mt-3">
          <summary className="text-[10px] text-muted-foreground cursor-pointer hover:text-foreground transition-colors">
            全部 {result.articles.length} 篇文章
          </summary>
          <div className="mt-2 space-y-1.5 max-h-60 overflow-y-auto">
            <ArticleList articles={result.articles.slice(0, 20)} type="all" />
          </div>
        </details>
      )}

      {/* 相关新闻（合并 NewsFeed） */}
      {news.length > 0 && (
        <details className="mt-3 border-t border-border pt-3">
          <summary className="text-[10px] text-muted-foreground cursor-pointer hover:text-foreground transition-colors flex items-center gap-1.5">
            <Clock className="w-3 h-3" />
            相关新闻 ({news.length} 条)
          </summary>
          <div className="mt-2 space-y-0.5 max-h-64 overflow-y-auto divide-y divide-border">
            {news.map((item, i) => (
              <a key={i} href={item.url} target="_blank" rel="noopener noreferrer"
                className="flex gap-2.5 py-2 px-1 hover:bg-surface-2/50 transition-colors group rounded">
                {item.image && (
                  <img src={item.image} alt="" loading="lazy"
                    className="w-12 h-12 rounded-lg object-cover shrink-0 bg-surface-2 opacity-80 group-hover:opacity-100 transition-opacity" />
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-foreground/90 leading-snug line-clamp-2 group-hover:text-foreground transition-colors">
                    {item.headline}
                  </p>
                  <div className="flex items-center gap-1.5 mt-1">
                    <span className="text-[10px] text-muted-foreground">{item.source}</span>
                    <span className="text-[10px] text-muted-foreground">·</span>
                    <span className="text-[10px] text-muted-foreground">
                      {item.datetime ? new Date(item.datetime * 1000).toLocaleDateString("zh-CN") : ""}
                    </span>
                    <ExternalLink className="w-2.5 h-2.5 text-muted-foreground ml-auto opacity-0 group-hover:opacity-60 transition-opacity" />
                  </div>
                </div>
              </a>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}

function ArticleList({ articles, type }: { articles: SentimentArticle[]; type: "positive" | "negative" | "all" }) {
  return (
    <div className="space-y-1">
      {articles.map((a, i) => (
        <a
          key={i}
          href={a.url || "#"}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(
            "flex items-start gap-2 p-2 rounded text-xs transition-colors",
            "hover:bg-surface-2",
            type === "positive" && "border-l-2 border-green-500/50 bg-green-500/3",
            type === "negative" && "border-l-2 border-red-500/50 bg-red-500/3",
            type === "all" && {
              "border-l-2 border-green-500/50 bg-green-500/3": a.sentiment_score > 0.2,
              "border-l-2 border-red-500/50 bg-red-500/3": a.sentiment_score < -0.2,
            }
          )}
        >
          <span className="shrink-0 mt-0.5">
            {a.sentiment_score > 0.1 ? (
              <TrendingUp className="w-3 h-3 text-bull" />
            ) : a.sentiment_score < -0.1 ? (
              <TrendingDown className="w-3 h-3 text-bear" />
            ) : (
              <Minus className="w-3 h-3 text-muted-foreground" />
            )}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-foreground leading-relaxed line-clamp-2">{a.title}</p>
            <div className="flex items-center gap-2 mt-0.5 text-[10px] text-muted-foreground">
              <span>{a.source}</span>
              {a.published_at && <span>{a.published_at.slice(0, 10)}</span>}
              <span className={cn("mono", a.sentiment_score > 0 ? "text-bull" : a.sentiment_score < 0 ? "text-bear" : "")}>
                {a.sentiment_score >= 0 ? "+" : ""}{a.sentiment_score.toFixed(2)}
              </span>
            </div>
          </div>
          {a.url && <ExternalLink className="w-2.5 h-2.5 text-muted-foreground shrink-0 mt-1" />}
        </a>
      ))}
    </div>
  )
}
