import { useState, useEffect, useCallback } from "react"
import type { Market } from "@/lib/api"

const STORAGE_KEY = "zhixi_market"

function loadMarket(): Market {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === "us" || v === "cn") return v
  } catch { /* ignore */ }
  return "us"
}

export function useMarket() {
  const [market, setMarketState] = useState<Market>(() => loadMarket())

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, market)
  }, [market])

  const setMarket = useCallback((m: Market) => {
    setMarketState(m)
  }, [])

  const currency = market === "cn" ? "¥" : "$"
  const currencyLabel = market === "cn" ? "CNY" : "USD"
  const marketLabel = market === "cn" ? "A股" : "美股"

  return { market, setMarket, currency, currencyLabel, marketLabel }
}
