import { cn } from "@/lib/utils"
import type { Market } from "@/lib/api"

interface MarketSelectorProps {
  market: Market
  onChange: (m: Market) => void
  className?: string
}

export default function MarketSelector({ market, onChange, className }: MarketSelectorProps) {
  const isCN = market === "cn"

  return (
    <div className={cn("flex rounded-lg bg-surface-2 border border-border p-0.5", className)}>
      <button
        onClick={() => onChange("us")}
        className={cn(
          "px-3 py-1 rounded-md text-xs font-medium transition-all duration-150",
          !isCN
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground"
        )}
      >
        美股
      </button>
      <button
        onClick={() => onChange("cn")}
        className={cn(
          "px-3 py-1 rounded-md text-xs font-medium transition-all duration-150",
          isCN
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground"
        )}
      >
        A股
      </button>
    </div>
  )
}
