import { useState, useEffect } from "react"
import { Bell, Settings2, Save, Loader2, CheckCircle, Mail, Search, MessageCircle, Smartphone } from "lucide-react"
import { cn } from "@/lib/utils"
import { API_BASE } from "@/lib/api"

interface NotifyConfig {
  email_from: string
  email_password: string
  email_to: string
  smtp_server: string
  smtp_port: number
  smtp_ssl: boolean
  serverchan_key: string
  bark_url: string
}

interface SettingsPanelProps {
  className?: string
}

const DEFAULT_CONFIG: NotifyConfig = {
  email_from: "", email_password: "", email_to: "",
  smtp_server: "", smtp_port: 465, smtp_ssl: true,
  serverchan_key: "", bark_url: "",
}

export default function SettingsPanel({ className }: SettingsPanelProps) {
  const [expanded, setExpanded] = useState(false)
  const [config, setConfig] = useState<NotifyConfig>(DEFAULT_CONFIG)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [showEmailAdvanced, setShowEmailAdvanced] = useState(false)

  useEffect(() => {
    if (expanded) loadConfig()
  }, [expanded])

  const loadConfig = async () => {
    try {
      const r = await fetch(`${API_BASE}/api/settings/notify`)
      if (r.ok) {
        const data = await r.json()
        setConfig({ ...DEFAULT_CONFIG, ...data })
      }
    } catch { /* ignore */ }
  }

  const autoDetectSMTP = async () => {
    if (!config.email_from.includes("@")) return
    try {
      const r = await fetch(`${API_BASE}/api/settings/smtp-detect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: config.email_from }),
      })
      if (r.ok) {
        const smtp = await r.json()
        setConfig(prev => ({
          ...prev,
          smtp_server: smtp.server || prev.smtp_server,
          smtp_port: smtp.port || prev.smtp_port,
          smtp_ssl: smtp.use_ssl ?? prev.smtp_ssl,
        }))
      }
    } catch { /* ignore */ }
  }

  const saveConfig = async () => {
    setSaving(true)
    setSaved(false)
    try {
      const r = await fetch(`${API_BASE}/api/settings/notify`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      })
      if (r.ok) {
        setSaved(true)
        setTimeout(() => setSaved(false), 2000)
      }
    } catch { /* ignore */ }
    finally { setSaving(false) }
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
        <Settings2 className="w-3.5 h-3.5" />
        预警通知设置
      </button>
    )
  }

  return (
    <div className={cn("rounded-xl border border-border/50 p-4", className)}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Bell className="w-4 h-4 text-primary" />
          <span className="text-sm font-bold text-foreground">通知配置</span>
        </div>
        <button
          onClick={() => setExpanded(false)}
          className="text-[10px] text-muted-foreground hover:text-foreground"
        >
          收起
        </button>
      </div>

      <p className="text-[11px] text-muted-foreground mb-3 leading-relaxed">
        预警触发后通过以下渠道通知你。至少配置一个即可。
      </p>

      {/* ── 邮箱通知（主要）── */}
      <div className="mb-4 p-3 rounded-lg bg-surface-2/40 border border-border/30">
        <div className="flex items-center gap-1.5 mb-2">
          <Mail className="w-3.5 h-3.5 text-primary" />
          <span className="text-xs font-bold text-foreground">邮箱通知</span>
        </div>

        <div className="space-y-2">
          <div>
            <label className="text-[10px] text-muted-foreground mb-0.5 block">发件邮箱</label>
            <div className="flex gap-2">
              <input
                type="email"
                value={config.email_from}
                onChange={(e) => setConfig({ ...config, email_from: e.target.value })}
                placeholder="your@qq.com"
                className="flex-1 px-2.5 py-1.5 rounded bg-surface-2 text-xs
                           placeholder:text-muted-foreground border border-border/50 outline-none
                           focus:border-primary/50 transition-colors"
              />
              <button
                onClick={autoDetectSMTP}
                className="px-2 py-1.5 rounded text-[10px] bg-surface-2 text-muted-foreground
                           hover:text-foreground border border-border/50 transition-colors shrink-0"
              >
                <Search className="w-3 h-3" />
              </button>
            </div>
          </div>

          <div>
            <label className="text-[10px] text-muted-foreground mb-0.5 block">
              授权码（非邮箱密码）
            </label>
            <input
              type="password"
              value={config.email_password}
              onChange={(e) => setConfig({ ...config, email_password: e.target.value })}
              placeholder="QQ邮箱→设置→POP3/SMTP→生成授权码"
              className="w-full px-2.5 py-1.5 rounded bg-surface-2 text-xs
                         placeholder:text-muted-foreground border border-border/50 outline-none
                         focus:border-primary/50 transition-colors"
            />
            <div className="text-[10px] text-muted-foreground mt-0.5">
              QQ邮箱: 设置→账户→POP3/SMTP服务→生成授权码
            </div>
          </div>

          <div>
            <label className="text-[10px] text-muted-foreground mb-0.5 block">接收通知的邮箱</label>
            <input
              type="email"
              value={config.email_to}
              onChange={(e) => setConfig({ ...config, email_to: e.target.value })}
              placeholder="接收预警的邮箱（可与发件相同）"
              className="w-full px-2.5 py-1.5 rounded bg-surface-2 text-xs
                         placeholder:text-muted-foreground border border-border/50 outline-none
                         focus:border-primary/50 transition-colors"
            />
          </div>

          {/* 高级SMTP设置 */}
          <button
            onClick={() => setShowEmailAdvanced(!showEmailAdvanced)}
            className="text-[10px] text-primary hover:underline"
          >
            {showEmailAdvanced ? "收起高级设置" : "高级SMTP设置（已自动检测）"}
          </button>
          {showEmailAdvanced && (
            <div className="space-y-2 pt-1">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={config.smtp_server}
                  onChange={(e) => setConfig({ ...config, smtp_server: e.target.value })}
                  placeholder="SMTP服务器"
                  className="flex-1 px-2.5 py-1.5 rounded bg-surface-2 text-xs
                             placeholder:text-muted-foreground border border-border/50 outline-none"
                />
                <input
                  type="number"
                  value={config.smtp_port}
                  onChange={(e) => setConfig({ ...config, smtp_port: Number(e.target.value) })}
                  className="w-20 px-2.5 py-1.5 rounded bg-surface-2 text-xs
                             placeholder:text-muted-foreground border border-border/50 outline-none"
                  placeholder="端口"
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── 其他渠道（折叠）── */}
      <details className="mb-4 group">
        <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground flex items-center gap-1">
          <MessageCircle className="w-3 h-3" />
          更多渠道（ServerChan / Bark）
        </summary>
        <div className="mt-2 space-y-2 pl-4">
          <div>
            <label className="text-[10px] text-muted-foreground mb-0.5 block">ServerChan 微信推送</label>
            <input
              type="text"
              value={config.serverchan_key}
              onChange={(e) => setConfig({ ...config, serverchan_key: e.target.value })}
              placeholder="SendKey"
              className="w-full px-2.5 py-1.5 rounded bg-surface-2 text-xs
                         placeholder:text-muted-foreground border border-border/50 outline-none"
            />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground mb-0.5 block">Bark iOS推送</label>
            <input
              type="text"
              value={config.bark_url}
              onChange={(e) => setConfig({ ...config, bark_url: e.target.value })}
              placeholder="https://api.day.app/your_key"
              className="w-full px-2.5 py-1.5 rounded bg-surface-2 text-xs
                         placeholder:text-muted-foreground border border-border/50 outline-none"
            />
          </div>
        </div>
      </details>

      {/* Save */}
      <button
        onClick={saveConfig}
        disabled={saving}
        className={cn(
          "w-full py-2 rounded-lg text-xs font-medium flex items-center justify-center gap-2 transition-colors",
          saved
            ? "bg-bull/15 text-bull border border-bull/30"
            : "bg-primary/10 text-primary border border-primary/30 hover:bg-primary/20"
        )}
      >
        {saving ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : saved ? (
          <>
            <CheckCircle className="w-3.5 h-3.5" />
            已保存
          </>
        ) : (
          <>
            <Save className="w-3.5 h-3.5" />
            保存配置
          </>
        )}
      </button>
    </div>
  )
}
