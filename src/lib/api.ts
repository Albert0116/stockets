// API 基地址 - 后端
export const API_BASE = "http://localhost:8888"

export type Market = "us" | "cn"

export interface QuoteData {
  symbol: string
  name: string
  price: number
  change: number
  change_pct: number
  open: number
  high: number
  low: number
  prev_close: number
  logo: string
  exchange: string
  industry: string
  market_cap: number
  currency: string
}

export interface CandleData {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface NewsItem {
  headline: string
  summary: string
  url: string
  datetime: number
  source: string
  image?: string
}

export interface SearchResult {
  symbol: string
  description: string
  type: string
}

export async function fetchQuote(symbol: string, market: Market = "us"): Promise<QuoteData> {
  const res = await fetch(`${API_BASE}/api/quote/${symbol}?market=${market}`)
  if (!res.ok) throw new Error(`Failed to fetch quote for ${symbol}`)
  return res.json()
}

export async function fetchCandles(symbol: string, period = "6mo", market: Market = "us"): Promise<CandleData[]> {
  const res = await fetch(`${API_BASE}/api/candles/${symbol}?period=${period}&market=${market}`)
  if (!res.ok) throw new Error(`Failed to fetch candles for ${symbol}`)
  const data = await res.json()
  return data.data
}

export async function fetchNews(symbol: string, market: Market = "us"): Promise<NewsItem[]> {
  const res = await fetch(`${API_BASE}/api/news/${symbol}?market=${market}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.news
}

export async function searchSymbol(query: string, market: Market = "us"): Promise<SearchResult[]> {
  const res = await fetch(`${API_BASE}/api/search/${query}?market=${market}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.results
}

export async function* streamAnalysis(
  symbol: string,
  name: string,
  price: number,
  change_pct: number,
  industry: string,
  market_cap: number,
  analysis_type: string,
  market: Market = "us",
): AsyncGenerator<string> {
  const res = await fetch(`${API_BASE}/api/analyze/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, name, price, change_pct, industry, market_cap, analysis_type, market }),
  })
  if (!res.ok || !res.body) throw new Error("Stream failed")
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ""
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split("\n")
    buf = lines.pop() || ""
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const payload = line.slice(6).trim()
        if (payload === "[DONE]") return
        try {
          const json = JSON.parse(payload)
          if (json.text) yield json.text
          if (json.error) throw new Error(json.error)
        } catch { /* skip parse errors */ }
      }
    }
  }
}

// ========== Multi-Agent Analysis Types ==========

export interface MultiAgentEvent {
  type: "status" | "agent_start" | "text" | "agent_done" | "decision" | "error"
  agent_id?: string
  agent_name?: string
  icon?: string
  index?: number
  total?: number
  text?: string
  summary?: string
  message?: string
  phase?: string
  // Decision fields
  rating?: string
  confidence?: number
  target_price?: string
  stop_loss?: string
  time_horizon?: string
  core_logic?: string
}

export async function* streamMultiAgentAnalysis(
  symbol: string,
  name: string,
  price: number,
  change_pct: number,
  industry: string,
  market_cap: number,
  market: Market = "us",
): AsyncGenerator<MultiAgentEvent> {
  const res = await fetch(`${API_BASE}/api/analyze/multi-agent/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, name, price, change_pct, industry, market_cap, analysis_type: "multi", market }),
  })
  if (!res.ok || !res.body) throw new Error("Multi-agent stream failed")
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ""
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split("\n")
    buf = lines.pop() || ""
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const payload = line.slice(6).trim()
        if (payload === "[DONE]") return
        try {
          const event: MultiAgentEvent = JSON.parse(payload)
          yield event
        } catch { /* skip parse errors */ }
      }
    }
  }
}
