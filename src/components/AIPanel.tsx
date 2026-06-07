import { useState, useRef, useCallback } from "react"
import { Bot, Loader2, Sparkles, FileText, TrendingUp, BarChart3, Copy, Check } from "lucide-react"
import { cn } from "@/lib/utils"
import { streamAnalysis, type QuoteData, type Market } from "@/lib/api"

interface AIPanelProps {
  quote: QuoteData
  market?: Market
  className?: string
}

const ANALYSIS_TYPES = [
  { id: "market", label: "市场分析", icon: TrendingUp, desc: "技术面+基本面综合分析" },
  { id: "forecast", label: "价格预测", icon: BarChart3, desc: "未来7-14日走势预测" },
  { id: "report", label: "研究报告", icon: FileText, desc: "完整专业研究报告" },
]

export default function AIPanel({ quote, market = "us", className }: AIPanelProps) {
  const [activeType, setActiveType] = useState("market")
  const [content, setContent] = useState("")
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [copied, setCopied] = useState(false)
  const abortRef = useRef(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const runAnalysis = useCallback(async () => {
    if (loading) return
    abortRef.current = false
    setContent("")
    setDone(false)
    setLoading(true)

    try {
      const gen = streamAnalysis(
        quote.symbol, quote.name, quote.price,
        quote.change_pct, quote.industry, quote.market_cap, activeType, market
      )
      for await (const chunk of gen) {
        if (abortRef.current) break
        setContent(prev => prev + chunk)
        if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
      }
    } catch (e) {
      setContent("⚠️ 分析失败，请检查后端服务是否运行。\n\n" + String(e))
    } finally {
      setLoading(false)
      setDone(true)
    }
  }, [quote, activeType, loading, market])

  const handleCopy = () => {
    navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const renderContent = (text: string) => {
    return text.split("\n").map((line, i) => {
      if (line.startsWith("# ")) return <h1 key={i} className="text-lg font-bold text-foreground mt-3 mb-1">{line.slice(2)}</h1>
      if (line.startsWith("## ")) return <h2 key={i} className="text-base font-semibold text-foreground mt-3 mb-1">{line.slice(3)}</h2>
      if (line.startsWith("### ")) return <h3 key={i} className="text-sm font-semibold text-accent-foreground mt-2 mb-0.5">{line.slice(4)}</h3>
      if (line.startsWith("- ") || line.startsWith("• ")) {
        return <li key={i} className="ml-4 text-sm text-foreground/90 leading-relaxed list-disc list-inside">{line.slice(2)}</li>
      }
      if (line.trim() === "") return <div key={i} className="h-2" />

      const parts = line.split(/(\*\*[^*]+\*\*)/)
      return (
        <p key={i} className="text-sm text-foreground/90 leading-relaxed">
          {parts.map((part, j) =>
            part.startsWith("**") && part.endsWith("**")
              ? <strong key={j} className="font-semibold text-foreground">{part.slice(2, -2)}</strong>
              : part
          )}
        </p>
      )
    })
  }

  return (
    <div className={cn("card-base flex flex-col", className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <div className="relative">
            <Bot className="w-4 h-4 text-primary" />
            {loading && (
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-primary rounded-full animate-pulse" />
            )}
          </div>
          <span className="font-semibold text-sm text-foreground">DeepSeek AI 分析</span>
          <span className="text-xs text-muted-foreground px-1.5 py-0.5 bg-surface-2 rounded mono">
            deepseek-chat
          </span>
        </div>
        {content && (
          <button onClick={handleCopy}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-surface-2">
            {copied ? <Check className="w-3 h-3 text-bull" /> : <Copy className="w-3 h-3" />}
            {copied ? "已复制" : "复制"}
          </button>
        )}
      </div>

      {/* Type Selector */}
      <div className="flex gap-1.5 p-3 border-b border-border shrink-0">
        {ANALYSIS_TYPES.map(t => {
          const Icon = t.icon
          return (
            <button key={t.id} onClick={() => { setActiveType(t.id); setContent(""); setDone(false) }}
              className={cn(
                "flex-1 flex flex-col items-center gap-1 px-2 py-2.5 rounded-lg text-xs transition-all duration-150",
                activeType === t.id
                  ? "bg-accent text-accent-foreground border border-primary/30"
                  : "text-muted-foreground hover:text-foreground hover:bg-surface-2 border border-transparent"
              )}>
              <Icon className="w-4 h-4" />
              <span className="font-medium">{t.label}</span>
              <span className="text-[10px] opacity-70 hidden sm:block">{t.desc}</span>
            </button>
          )
        })}
      </div>

      {/* Content Area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 min-h-[280px] max-h-[420px]">
        {!content && !loading && (
          <div className="h-full flex flex-col items-center justify-center gap-3 text-center">
            <div className="w-12 h-12 rounded-full bg-accent/50 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-accent-foreground" />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground mb-1">
                分析 <span className="text-primary">{quote.symbol}</span>
              </p>
              <p className="text-xs text-muted-foreground">
                选择分析类型，点击下方按钮开始
              </p>
            </div>
          </div>
        )}

        {content && (
          <div className="space-y-0.5 animate-fade-up">
            {renderContent(content)}
            {loading && (
              <span className="inline-block w-1.5 h-4 bg-primary ml-0.5 animate-pulse rounded-sm" />
            )}
          </div>
        )}
      </div>

      {/* Action Button */}
      <div className="p-3 border-t border-border shrink-0">
        <button onClick={runAnalysis} disabled={loading}
          className={cn(
            "w-full h-10 rounded-lg text-sm font-medium flex items-center justify-center gap-2",
            "transition-all duration-200",
            loading
              ? "bg-surface-2 text-muted-foreground cursor-not-allowed"
              : "bg-primary text-primary-foreground hover:opacity-90 active:scale-[0.98] glow-sm"
          )}>
          {loading ? (
            <><Loader2 className="w-4 h-4 animate-spin" />AI 分析中...</>
          ) : done ? (
            <><Sparkles className="w-4 h-4" />重新分析</>
          ) : (
            <><Sparkles className="w-4 h-4" />开始 AI 分析</>
          )}
        </button>
      </div>
    </div>
  )
}
