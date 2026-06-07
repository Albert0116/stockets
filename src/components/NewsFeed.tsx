import { ExternalLink, Clock } from "lucide-react"
import { cn } from "@/lib/utils"
import type { NewsItem } from "@/lib/api"

interface NewsFeedProps {
  news: NewsItem[]
  className?: string
}

export default function NewsFeed({ news, className }: NewsFeedProps) {
  if (!news.length) return null

  return (
    <div className={cn("card-base", className)}>
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
        <Clock className="w-4 h-4 text-muted-foreground" />
        <span className="font-semibold text-sm text-foreground">最新资讯</span>
        <span className="text-xs text-muted-foreground ml-auto">{news.length} 条</span>
      </div>
      <div className="divide-y divide-border">
        {news.map((item, i) => (
          <a key={i} href={item.url} target="_blank" rel="noopener noreferrer"
            className="flex gap-3 px-4 py-3 hover:bg-surface-2/50 transition-colors group">
            {item.image && (
              <img src={item.image} alt="" loading="lazy"
                className="w-14 h-14 rounded-lg object-cover shrink-0 bg-surface-2 opacity-80 group-hover:opacity-100 transition-opacity" />
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm text-foreground/90 leading-snug line-clamp-2 group-hover:text-foreground transition-colors">
                {item.headline}
              </p>
              <div className="flex items-center gap-2 mt-1.5">
                <span className="text-xs text-muted-foreground">{item.source}</span>
                <span className="text-xs text-muted-foreground">·</span>
                <span className="text-xs text-muted-foreground">
                  {new Date(item.datetime * 1000).toLocaleDateString("zh-CN")}
                </span>
                <ExternalLink className="w-3 h-3 text-muted-foreground ml-auto opacity-0 group-hover:opacity-60 transition-opacity" />
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  )
}
