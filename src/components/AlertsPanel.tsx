import { useState, useEffect, useCallback } from "react"
import { Bell, Loader2, Plus, Trash2, X, TrendingUp, TrendingDown, BarChart3, Zap, History, Wifi, Mail, MessageSquare, Smartphone } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  fetchAlerts, createAlert, deleteAlert, fetchAlertHistory,
  type AlertRule, type AlertConditionType, type AlertHistoryItem, type Market,
  ALERT_CONDITION_LABELS,
} from "@/lib/api"

interface Props {
  symbol: string
  market: Market
  className?: string
  onClose?: () => void
  /** 嵌入模式：无边框，无标题栏 */
  embedded?: boolean
}

const CONDITIONS: { type: AlertConditionType; icon: typeof TrendingUp; unit: string; placeholder: string }[] = [
  { type: "price_above", icon: TrendingUp, unit: "元/美元", placeholder: "如 200" },
  { type: "price_below", icon: TrendingDown, unit: "元/美元", placeholder: "如 150" },
  { type: "change_pct_above", icon: TrendingUp, unit: "%", placeholder: "如 5" },
  { type: "change_pct_below", icon: TrendingDown, unit: "%", placeholder: "如 -5" },
  { type: "volume_spike", icon: BarChart3, unit: "倍", placeholder: "如 2 (放量2倍)" },
]

function conditionIcon(type: string) {
  switch (type) {
    case "price_above":
    case "change_pct_above":
      return <TrendingUp className="w-3.5 h-3.5 text-bull" />
    case "price_below":
    case "change_pct_below":
      return <TrendingDown className="w-3.5 h-3.5 text-bear" />
    case "volume_spike":
      return <Zap className="w-3.5 h-3.5 text-gold" />
    default:
      return <Bell className="w-3.5 h-3.5 text-muted-foreground" />
  }
}

function formatValue(rule: AlertRule) {
  const label = ALERT_CONDITION_LABELS[rule.condition_type as AlertConditionType] ?? rule.condition_type
  const v = rule.condition_value
  if (rule.condition_type === "change_pct_above" || rule.condition_type === "change_pct_below") return `${label} ${v}%`
  if (rule.condition_type === "volume_spike") return `${label} ${v}x`
  return `${label} ${v}`
}

export default function AlertsPanel({ symbol, market, className, onClose, embedded = false }: Props) {
  const [alerts, setAlerts] = useState<AlertRule[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState("")
  const [history, setHistory] = useState<AlertHistoryItem[]>([])
  const [showHistory, setShowHistory] = useState(false)

  // 新建表单状态
  const [newType, setNewType] = useState<AlertConditionType>("price_above")
  const [newValue, setNewValue] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [list, hist] = await Promise.all([fetchAlerts(symbol), fetchAlertHistory(symbol, 20)])
      setAlerts(list)
      setHistory(hist)
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }, [symbol])

  useEffect(() => { load() }, [load])

  const handleCreate = async () => {
    if (!newValue.trim()) return
    setCreating(true)
    setError("")
    const result = await createAlert(symbol, market, newType, newValue.trim())
    if (result.ok) {
      setNewValue("")
      setShowForm(false)
      await load()
    } else {
      setError(result.error ?? "创建失败")
    }
    setCreating(false)
  }

  const handleDelete = async (id: number) => {
    const ok = await deleteAlert(id)
    if (ok) setAlerts(prev => prev.filter(a => a.id !== id))
  }

  const currentCondition = CONDITIONS.find(c => c.type === newType)!

  const inner = (
    <div className="flex flex-col gap-3">
      {/* 通知渠道状态 */}
      <div className="flex items-center gap-3 px-1">
        {[
          { icon: Wifi, label: "应用内", active: true },
          { icon: Mail, label: "邮件", active: false },
          { icon: MessageSquare, label: "微信", active: false },
          { icon: Smartphone, label: "推送", active: false },
        ].map(ch => (
          <div key={ch.label} className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <span className={cn("w-1.5 h-1.5 rounded-full", ch.active ? "bg-bull" : "bg-muted-foreground/40")} />
            {ch.label}
          </div>
        ))}
      </div>
      {/* 现有预警列表 */}
      {loading ? (
        <div className="flex items-center justify-center gap-2 py-6 text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-xs">加载预警...</span>
        </div>
      ) : alerts.length === 0 ? (
        <div className="text-center py-6 text-muted-foreground">
          <Bell className="w-8 h-8 mx-auto mb-2 opacity-30" />
          <p className="text-xs">暂无预警规则</p>
          <p className="text-[10px] mt-0.5">点击下方按钮设置价格或涨跌幅预警</p>
        </div>
      ) : (
        <div className="space-y-1.5">
          {alerts.map(rule => (
            <div key={rule.id}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-2/50 group">
              {conditionIcon(rule.condition_type)}
              <div className="flex-1 min-w-0">
                <p className="text-xs text-foreground font-medium">{formatValue(rule)}</p>
                {rule.created_at && (
                  <p className="text-[10px] text-muted-foreground">
                    {new Date(rule.created_at).toLocaleDateString("zh-CN")}
                  </p>
                )}
              </div>
              <button onClick={() => handleDelete(rule.id)}
                className="opacity-0 group-hover:opacity-100 p-1 rounded text-muted-foreground hover:text-bear transition-all">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* 触发历史 */}
      {history.length > 0 && (
        <div className="border-t border-border/50 pt-2">
          <button
            onClick={() => setShowHistory(v => !v)}
            className="flex items-center gap-1.5 text-[10px] text-muted-foreground hover:text-foreground transition-colors">
            <History className="w-3 h-3" />
            触发历史 ({history.length})
            <span className="text-[9px]">{showHistory ? "▲" : "▼"}</span>
          </button>
          {showHistory && (
            <div className="space-y-1 mt-1.5 max-h-32 overflow-y-auto">
              {history.map(h => (
                <div key={h.id} className="flex items-center justify-between text-[10px] px-2 py-1 rounded bg-surface-1">
                  <span className="mono text-muted-foreground">{h.symbol}</span>
                  <span className="text-foreground">{ALERT_CONDITION_LABELS[h.condition_type as AlertConditionType] ?? h.condition_type}</span>
                  <span className="text-muted-foreground">{h.triggered_at?.slice(0, 16).replace("T", " ")}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 新建表单 */}
      {showForm ? (
        <div className="border border-border rounded-lg p-3 space-y-2.5 animate-fade-up">
          <div className="flex gap-1.5 flex-wrap">
            {CONDITIONS.map(c => {
              const Icon = c.icon
              return (
                <button key={c.type} onClick={() => setNewType(c.type)}
                  className={cn(
                    "flex items-center gap-1 px-2 py-1.5 rounded text-[11px] transition-all",
                    newType === c.type
                      ? "bg-accent text-accent-foreground border border-primary/30"
                      : "text-muted-foreground hover:text-foreground hover:bg-surface-2 border border-transparent"
                  )}>
                  <Icon className="w-3 h-3" />
                  {ALERT_CONDITION_LABELS[c.type]}
                </button>
              )
            })}
          </div>
          <div className="flex gap-2">
            <input
              value={newValue}
              onChange={e => setNewValue(e.target.value)}
              placeholder={currentCondition.placeholder}
              className="flex-1 h-8 px-2.5 rounded-lg bg-surface-2 border border-border text-sm text-foreground mono
                placeholder:text-muted-foreground/60 focus:outline-none focus:border-primary/50 transition-colors"
              onKeyDown={e => e.key === "Enter" && handleCreate()}
            />
            <button onClick={handleCreate} disabled={creating || !newValue.trim()}
              className={cn(
                "h-8 px-3 rounded-lg text-xs font-medium flex items-center gap-1.5",
                creating || !newValue.trim()
                  ? "bg-surface-2 text-muted-foreground cursor-not-allowed"
                  : "bg-primary text-primary-foreground hover:opacity-90"
              )}>
              {creating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
              添加
            </button>
          </div>
          {error && <p className="text-[11px] text-bear">{error}</p>}
        </div>
      ) : (
        <button onClick={() => setShowForm(true)}
          className="w-full h-8 rounded-lg border border-dashed border-border text-xs text-muted-foreground
            hover:text-foreground hover:border-primary/40 transition-colors flex items-center justify-center gap-1.5">
          <Plus className="w-3.5 h-3.5" />
          新建预警
        </button>
      )}
    </div>
  )

  // 嵌入模式：直接返回内容
  if (embedded) return <div className={className}>{inner}</div>

  // 抽屉模式：带标题栏和关闭按钮
  return (
    <div className={cn("card-base flex flex-col max-h-[70vh]", className)}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <Bell className="w-4 h-4 text-primary" />
          <span className="font-semibold text-sm text-foreground">预警管理</span>
          <span className="text-xs text-muted-foreground mono">{symbol}</span>
        </div>
        {onClose && (
          <button onClick={onClose}
            className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-surface-2 transition-colors">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {inner}
      </div>
    </div>
  )
}
