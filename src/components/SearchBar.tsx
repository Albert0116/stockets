import React, { useState, useRef, useEffect } from "react"
import { Search, X, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { searchSymbol, type SearchResult, type Market } from "@/lib/api"

interface SearchBarProps {
  onSelect: (symbol: string) => void
  market?: Market
  className?: string
}

export default function SearchBar({ onSelect, market = "us", className }: SearchBarProps) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  // 市场切换时清空结果
  useEffect(() => {
    setQuery("")
    setResults([])
    setOpen(false)
  }, [market])

  const handleChange = (val: string) => {
    setQuery(val)
    if (!val.trim()) { setResults([]); setOpen(false); return }
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await searchSymbol(val.trim(), market)
        setResults(res)
        setOpen(res.length > 0)
      } finally { setLoading(false) }
    }, 350)
  }

  const handleSelect = (symbol: string) => {
    setQuery(symbol)
    setOpen(false)
    onSelect(symbol)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && query.trim()) {
      setOpen(false)
      onSelect(query.trim().toUpperCase())
    }
  }

  const placeholder = market === "cn"
    ? "搜索A股代码或名称... (如 600519, 000001)"
    : "搜索股票代码或名称... (如 AAPL, TSLA)"

  return (
    <div ref={wrapRef} className={cn("relative", className)}>
      <div className="relative flex items-center">
        <Search className="absolute left-3 h-4 w-4 text-muted-foreground pointer-events-none" />
        {loading && <Loader2 className="absolute right-10 h-3.5 w-3.5 text-muted-foreground animate-spin" />}
        {query && (
          <button onClick={() => { setQuery(""); setResults([]); setOpen(false) }}
            className="absolute right-3 h-4 w-4 text-muted-foreground hover:text-foreground transition-colors">
            <X className="h-4 w-4" />
          </button>
        )}
        <input
          value={query}
          onChange={e => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className={cn(
            "w-full h-10 pl-9 pr-10 rounded-lg text-sm",
            "bg-surface-2 border border-border text-foreground",
            "placeholder:text-muted-foreground",
            "focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30",
            "transition-all duration-200"
          )}
        />
      </div>

      {open && results.length > 0 && (
        <div className="absolute top-full mt-1.5 w-full z-50 card-base overflow-hidden animate-fade-up max-h-80 overflow-y-auto">
          {results.map(r => (
            <button key={r.symbol} onClick={() => handleSelect(r.symbol)}
              className="w-full px-4 py-2.5 flex items-center gap-3 hover:bg-accent/50 transition-colors text-left">
              <span className="mono text-sm font-medium text-primary w-16 shrink-0">{r.symbol}</span>
              <span className="text-sm text-foreground truncate">{r.description}</span>
              {r.type && <span className="text-xs text-muted-foreground ml-auto shrink-0">{r.type}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
