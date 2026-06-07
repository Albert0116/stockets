// API 基地址 - 支持环境变量配置
export const API_BASE = import.meta.env.VITE_API_BASE as string || "http://localhost:8888"

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

// P1-11: 公共 SSE 流解析器
export async function* parseSSEStream(res: Response): AsyncGenerator<string> {
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
        yield payload
      }
    }
  }
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
  for await (const raw of parseSSEStream(res)) {
    try {
      const json = JSON.parse(raw)
      if (json.text) yield json.text
      if (json.error) throw new Error(json.error)
    } catch { /* skip parse errors */ }
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
  // P0-8: 操作计划和总耗时
  operation_plan?: {
    entry_strategy?: string
    position_sizing?: string
    take_profit?: string
    time_stop?: string
  }
  total_time?: string
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
  for await (const raw of parseSSEStream(res)) {
    try {
      yield JSON.parse(raw) as MultiAgentEvent
    } catch { /* skip parse errors */ }
  }
}

// ========== Backtest Types ==========

export interface BacktestStrategy {
  key: string
  name: string
  description: string
  params: Record<string, number>
  param_descriptions: Record<string, string>
  recommended_markets: string[]
}

export interface BacktestParams {
  symbol: string
  market: Market
  strategy_key: string
  params?: Record<string, number>
  period: string
  initial_cash: number
}

export interface BacktestResult {
  symbol: string
  strategy: string
  total_return_pct: number
  annual_return_pct: number
  max_drawdown_pct: number
  sharpe_ratio: number
  sortino_ratio: number
  calmar_ratio: number
  win_rate_pct: number
  profit_factor: number
  total_trades: number
  winning_trades: number
  losing_trades: number
  avg_win_pct: number
  avg_loss_pct: number
  avg_holding_days: number
  buy_hold_return_pct: number
  vs_buy_hold: number
  final_value: number
  total_return: number
  initial_cash: number
  data_start: string
  data_end: string
  data_days: number
  run_time_ms: number
  trades: {
    date: string
    action: string
    price: number
    size: number
    pnl: number
    pnl_pct: number
    holding_days: number
  }[]
  equity_curve?: { date: string; value: number }[]
  buy_hold_curve?: { date: string; value: number }[]
  error?: string
}

export async function fetchBacktestStrategies(): Promise<BacktestStrategy[]> {
  const res = await fetch(`${API_BASE}/api/backtest/strategies`)
  if (!res.ok) return []
  return res.json()
}

export async function runBacktest(params: BacktestParams): Promise<BacktestResult> {
  const res = await fetch(`${API_BASE}/api/backtest/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error("Backtest failed")
  return res.json()
}

export async function scanBestStrategy(symbol: string, market: Market, period = "1y"): Promise<{ symbol: string; results: BacktestResult[] }> {
  const res = await fetch(`${API_BASE}/api/backtest/scan-best`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, market, period }),
  })
  if (!res.ok) throw new Error("Scan failed")
  return res.json()
}

// ========== Sentiment Types ==========

export interface SentimentArticle {
  title: string
  summary: string
  source: string
  url: string
  published_at: string
  sentiment_score: number
}

export interface SentimentAggregate {
  score: number
  label: string
  positive_ratio: number
  negative_ratio: number
  neutral_ratio: number
  total_articles: number
  top_positive: SentimentArticle[]
  top_negative: SentimentArticle[]
}

export interface SentimentResult {
  symbol: string
  market: string
  score: number
  label: string
  summary: string
  aggregate: SentimentAggregate
  articles: SentimentArticle[]
}

export interface QuickSentiment {
  symbol: string
  score: number
  label: string
  article_count: number
  positive_ratio: number
}

export async function fetchSentiment(symbol: string, market: Market = "us"): Promise<SentimentResult> {
  const res = await fetch(`${API_BASE}/api/sentiment/analyze/${symbol}?market=${market}`)
  if (!res.ok) throw new Error("Sentiment fetch failed")
  return res.json()
}

export async function fetchQuickSentiment(symbol: string, market: Market = "us"): Promise<QuickSentiment> {
  const res = await fetch(`${API_BASE}/api/sentiment/quick/${symbol}?market=${market}`)
  if (!res.ok) throw new Error("Quick sentiment failed")
  return res.json()
}

// ========== Alert Types ==========

export interface AlertRule {
  id: number
  symbol: string
  market: string
  condition_type: string
  condition_value: string
  created_at?: string
}

export type AlertConditionType =
  | "price_above"
  | "price_below"
  | "change_pct_above"
  | "change_pct_below"
  | "volume_spike"

export const ALERT_CONDITION_LABELS: Record<AlertConditionType, string> = {
  price_above: "价格突破",
  price_below: "价格跌破",
  change_pct_above: "涨幅超过",
  change_pct_below: "跌幅超过",
  volume_spike: "成交量异动",
}

export async function fetchAlerts(symbol?: string): Promise<AlertRule[]> {
  const params = symbol ? `?symbol=${symbol}` : ""
  const res = await fetch(`${API_BASE}/api/alerts${params}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.items ?? []
}

export async function createAlert(
  symbol: string,
  market: Market,
  conditionType: AlertConditionType,
  conditionValue: string,
): Promise<{ ok: boolean; id?: number; error?: string }> {
  const res = await fetch(`${API_BASE}/api/alerts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, market, condition_type: conditionType, condition_value: conditionValue }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    return { ok: false, error: err.detail ?? "创建预警失败" }
  }
  return res.json()
}

export async function deleteAlert(ruleId: number): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/alerts/${ruleId}`, { method: "DELETE" })
  return res.ok
}

// ========== Alert History ==========

export interface AlertHistoryItem {
  id: number
  rule_id: number
  symbol: string
  condition_type: string
  condition_value: string
  triggered_value: string
  triggered_at: string
  rule_condition_type?: string
  rule_condition_value?: string
}

export async function fetchAlertHistory(symbol?: string, limit = 50): Promise<AlertHistoryItem[]> {
  const params = new URLSearchParams()
  if (symbol) params.set("symbol", symbol)
  params.set("limit", String(limit))
  const res = await fetch(`${API_BASE}/api/alerts/history?${params}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.items ?? []
}

// ========== Trending ==========

export interface TrendingStock {
  symbol: string
  name?: string
  price: number
  change_pct: number
}

export interface TrendingData {
  gainers: TrendingStock[]
  losers: TrendingStock[]
  active: TrendingStock[]
}

export async function fetchTrending(market: Market = "us"): Promise<TrendingData> {
  const res = await fetch(`${API_BASE}/api/market/trending?market=${market}`)
  if (!res.ok) return { gainers: [], losers: [], active: [] }
  return res.json()
}

// ========== Indicators ==========

export interface IndicatorData {
  dates: string[]
  ma10: (number | null)[]
  ma60: (number | null)[]
  rsi: (number | null)[]
  macd: {
    macd: (number | null)[]
    signal: (number | null)[]
    histogram: (number | null)[]
  }
  bollinger: {
    upper: (number | null)[]
    middle: (number | null)[]
    lower: (number | null)[]
  }
}

export async function fetchIndicators(symbol: string, period = "6mo", market: Market = "us"): Promise<IndicatorData | null> {
  const res = await fetch(`${API_BASE}/api/indicators/${symbol}?period=${period}&market=${market}`)
  if (!res.ok) return null
  return res.json()
}

// ========== Portfolio ==========

export interface PortfolioPosition {
  id: number
  symbol: string
  market: string
  buy_price: number
  quantity: number
  buy_date: string
  notes: string
  group_name: string
  created_at: number
  updated_at: number
  current_price?: number
  market_value?: number
  pnl?: number
  pnl_pct?: number
}

export interface PortfolioSummary {
  positions: PortfolioPosition[]
  total_cost: number
  total_value: number
  total_pnl: number
  total_pnl_pct: number
  position_count: number
}

export async function fetchPortfolio(market?: string): Promise<PortfolioPosition[]> {
  const params = market ? `?market=${market}` : ""
  const res = await fetch(`${API_BASE}/api/portfolio${params}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.items ?? []
}

export async function fetchPortfolioSummary(market?: string): Promise<PortfolioSummary | null> {
  const params = market ? `?market=${market}` : ""
  const res = await fetch(`${API_BASE}/api/portfolio/summary${params}`)
  if (!res.ok) return null
  return res.json()
}

export async function addPortfolioPosition(data: {
  symbol: string; market?: string; buy_price: number; quantity: number
  buy_date?: string; notes?: string; group_name?: string
}): Promise<{ ok: boolean; id?: number }> {
  const res = await fetch(`${API_BASE}/api/portfolio`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  if (!res.ok) return { ok: false }
  return res.json()
}

export async function updatePortfolioPosition(data: {
  id: number; buy_price?: number; quantity?: number; notes?: string; group_name?: string
}): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/portfolio`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
  return res.ok
}

export async function removePortfolioPosition(id: number): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/portfolio/${id}`, { method: "DELETE" })
  return res.ok
}
