import { useState, useEffect, useCallback } from "react"
import type { Market } from "@/lib/api"

export interface FavoriteStock {
  symbol: string
  name: string
  market: Market
  addedAt: number
  group: string
}

export const FAVORITE_GROUPS = ["全部", "关注", "持仓", "观察"] as const
export type FavoriteGroup = typeof FAVORITE_GROUPS[number]

const STORAGE_KEY_V2 = "zhixi_favorites_v2"
const STORAGE_KEY_OLD = "zhixi_favorites"
const MAX_FAVORITES = 20

function loadFavorites(): FavoriteStock[] {
  try {
    // 优先读取 v2
    let raw = localStorage.getItem(STORAGE_KEY_V2)
    if (!raw) {
      // 尝试迁移旧版数据
      const oldRaw = localStorage.getItem(STORAGE_KEY_OLD)
      if (oldRaw) {
        const oldData = JSON.parse(oldRaw)
        if (Array.isArray(oldData) && oldData.length > 0) {
          const migrated: FavoriteStock[] = oldData
            .filter(
              (f: unknown) =>
                typeof f === "object" && f !== null &&
                typeof (f as Record<string, unknown>).symbol === "string" &&
                typeof (f as Record<string, unknown>).name === "string"
            )
            .map((f: Record<string, unknown>) => ({
              symbol: (f.symbol as string).toUpperCase(),
              name: f.name as string,
              market: "us" as Market,
              addedAt: typeof f.addedAt === "number" ? f.addedAt : Date.now(),
              group: "关注",
            }))
          saveFavorites(migrated)
          // 删除旧key
          localStorage.removeItem(STORAGE_KEY_OLD)
          return migrated
        }
      }
      return []
    }
    const data = JSON.parse(raw)
    if (!Array.isArray(data)) return []
    return data
      .filter(
        (f: unknown) =>
          typeof f === "object" &&
          f !== null &&
          typeof (f as FavoriteStock).symbol === "string" &&
          typeof (f as FavoriteStock).name === "string" &&
          ((f as FavoriteStock).market === "us" || (f as FavoriteStock).market === "cn")
      )
      .map((f: FavoriteStock) => ({
        ...f,
        group: f.group || "关注",
      }))
  } catch {
    return []
  }
}

function saveFavorites(favorites: FavoriteStock[]) {
  try {
    localStorage.setItem(STORAGE_KEY_V2, JSON.stringify(favorites))
  } catch {
    // localStorage full or unavailable
  }
}

export function useFavorites() {
  const [favorites, setFavorites] = useState<FavoriteStock[]>([])

  // 初始化加载
  useEffect(() => {
    setFavorites(loadFavorites())
  }, [])

  const addFavorite = useCallback(
    (symbol: string, name: string, market: Market = "us", group = "关注") => {
      setFavorites((prev) => {
        if (prev.length >= MAX_FAVORITES) return prev
        if (prev.some((f) => f.symbol === symbol.toUpperCase() && f.market === market)) return prev
        const next = [
          ...prev,
          { symbol: symbol.toUpperCase(), name, market, addedAt: Date.now(), group },
        ]
        saveFavorites(next)
        return next
      })
    },
    []
  )

  const removeFavorite = useCallback((symbol: string, market: Market = "us") => {
    setFavorites((prev) => {
      const next = prev.filter(
        (f) => !(f.symbol === symbol.toUpperCase() && f.market === market)
      )
      saveFavorites(next)
      return next
    })
  }, [])

  const isFavorite = useCallback(
    (symbol: string, market: Market = "us") => {
      return favorites.some(
        (f) => f.symbol === symbol.toUpperCase() && f.market === market
      )
    },
    [favorites]
  )

  const toggleFavorite = useCallback(
    (symbol: string, name: string, market: Market = "us") => {
      if (isFavorite(symbol, market)) {
        removeFavorite(symbol, market)
      } else {
        addFavorite(symbol, name, market)
      }
    },
    [isFavorite, addFavorite, removeFavorite]
  )

  const setGroup = useCallback((symbol: string, market: Market, group: string) => {
    setFavorites((prev) => {
      const next = prev.map((f) =>
        f.symbol === symbol.toUpperCase() && f.market === market
          ? { ...f, group }
          : f
      )
      saveFavorites(next)
      return next
    })
  }, [])

  return {
    favorites,
    addFavorite,
    removeFavorite,
    isFavorite,
    toggleFavorite,
    setGroup,
    hasFavorites: favorites.length > 0,
  }
}
