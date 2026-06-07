import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatNumber(n: number, decimals = 2): string {
  if (Math.abs(n) >= 1e12) return (n / 1e12).toFixed(1) + "T"
  if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(1) + "B"
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + "M"
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + "K"
  return n.toFixed(decimals)
}

export function formatPct(n: number): string {
  return (n >= 0 ? "+" : "") + n.toFixed(2) + "%"
}
