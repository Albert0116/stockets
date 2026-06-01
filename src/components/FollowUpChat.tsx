import { useState, useRef, useEffect } from "react"
import { cn } from "@/lib/utils"
import { Send, MessageCircle, Loader2 } from "lucide-react"

interface Message {
  role: "user" | "assistant"
  content: string
}

interface FollowUpChatProps {
  symbol: string
  market: string
  analysisContext: string  // 分析摘要上下文
  className?: string
}

export default function FollowUpChat({ symbol, market, analysisContext, className }: FollowUpChatProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const handleSend = async () => {
    const question = input.trim()
    if (!question || loading) return

    setInput("")
    setMessages(prev => [...prev, { role: "user", content: question }])
    setLoading(true)

    try {
      const resp = await fetch("/api/chat/follow-up", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, market, question, context: analysisContext }),
      })

      if (!resp.ok) throw new Error("请求失败")

      const reader = resp.body?.getReader()
      if (!reader) throw new Error("无法读取响应")

      const decoder = new TextDecoder()
      let assistantText = ""

      setMessages(prev => [...prev, { role: "assistant", content: "" }])

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split("\n")

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          const raw = line.slice(6)
          if (raw === "[DONE]") break
          try {
            const data = JSON.parse(raw)
            if (data.text) {
              assistantText += data.text
              setMessages(prev => {
                const updated = [...prev]
                updated[updated.length - 1] = { role: "assistant", content: assistantText }
                return updated
              })
            }
          } catch { /* ignore */ }
        }
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: "assistant", content: "抱歉，请求出错，请重试。" }])
    } finally {
      setLoading(false)
    }
  }

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className={cn(
          "w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg",
          "border border-border/50 hover:border-border text-xs text-muted-foreground",
          "hover:text-foreground hover:bg-surface-2/50 transition-all",
          className
        )}
      >
        <MessageCircle className="w-3.5 h-3.5" />
        对分析结果有疑问？点击追问
      </button>
    )
  }

  return (
    <div className={cn("rounded-lg border border-border/50 overflow-hidden", className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-surface-2/30 border-b border-border/30">
        <div className="flex items-center gap-1.5 text-xs font-medium text-foreground">
          <MessageCircle className="w-3.5 h-3.5" />
          追问分析师
        </div>
        <button
          onClick={() => setExpanded(false)}
          className="text-[10px] text-muted-foreground hover:text-foreground"
        >
          收起
        </button>
      </div>

      {/* Messages */}
      <div className="max-h-60 overflow-y-auto p-3 space-y-2.5">
        {messages.length === 0 && (
          <div className="text-xs text-muted-foreground text-center py-3">
            可以问关于 {symbol} 的任何后续问题，例如：<br/>
            "这个价位适合加仓吗？" "有哪些潜在利空？"
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
            <div className={cn(
              "max-w-[85%] rounded-lg px-3 py-2 text-xs leading-relaxed",
              msg.role === "user"
                ? "bg-blue-500/15 text-foreground"
                : "bg-surface-2/60 text-foreground/90"
            )}>
              {msg.content || (loading && i === messages.length - 1 && (
                <Loader2 className="w-3 h-3 animate-spin" />
              ))}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="flex items-center gap-2 p-2 border-t border-border/30">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="输入追问..."
          className="flex-1 bg-transparent text-xs text-foreground placeholder:text-muted-foreground
                     outline-none px-2 py-1.5"
          disabled={loading}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || loading}
          className="p-1.5 rounded text-muted-foreground hover:text-foreground
                     hover:bg-surface-2/50 disabled:opacity-30 transition-colors"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}
