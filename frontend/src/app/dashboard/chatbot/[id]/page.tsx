'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { toast } from 'sonner'
import {
  AlertCircle, ArrowLeft, Bot, Check, Code2, Copy, Loader2, MessageSquare, Palette, Settings2, Trash2,
} from 'lucide-react'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { chatbotService, DEFAULT_CHATBOT_CONFIG, type Chatbot, type ChatbotConfig } from '@/lib/chatbots'
import { PERMISSIONS } from '@/lib/workspace'
import { usePermission } from '@/store/workspaceStore'
import { useConfirm } from '@/hooks/use-confirm'
import { ChatbotAppearance } from '@/components/chatbot/ChatbotAppearance'
import { ChatbotConversations } from '@/components/chatbot/ChatbotConversations'
import { ChatbotStatus } from '@/components/chatbot/ChatbotStatus'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

type Tab = 'setup' | 'appearance' | 'install' | 'conversations'

const TABS: { id: Tab; label: string; icon: typeof Settings2 }[] = [
  { id: 'setup', label: 'Setup', icon: Settings2 },
  { id: 'appearance', label: 'Appearance', icon: Palette },
  { id: 'install', label: 'Install', icon: Code2 },
  { id: 'conversations', label: 'Conversations', icon: MessageSquare },
]

const inputClass =
  'h-11 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-[14px] text-slate-900 outline-none transition-colors focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 disabled:bg-slate-50 disabled:text-slate-500'
const labelClass = 'mb-1.5 block text-[13px] font-semibold text-slate-700'
const selectTriggerClass =
  'h-11 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-[14px] text-slate-900 outline-none transition-colors hover:border-slate-300 focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 data-[state=open]:border-[#0F6A59] data-[state=open]:ring-2 data-[state=open]:ring-[#0F6A59]/15 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500'
// Radix Select can't use an empty value, so "no agent" gets a sentinel.
const NO_AGENT = '__none__'

export default function ChatbotDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const canWrite = usePermission(PERMISSIONS.agentsWrite)
  const { confirm, ConfirmDialog } = useConfirm()

  const [chatbot, setChatbot] = useState<Chatbot | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [agents, setAgents] = useState<{ id: string; name: string }[]>([])
  const [tab, setTab] = useState<Tab>('setup')

  // Editable copy; saved together so Setup and Appearance share one Save.
  const [name, setName] = useState('')
  const [agentId, setAgentId] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [config, setConfig] = useState<ChatbotConfig>(DEFAULT_CHATBOT_CONFIG)
  const [saving, setSaving] = useState(false)
  const [copied, setCopied] = useState(false)

  const adopt = useCallback((bot: Chatbot) => {
    setChatbot(bot)
    setName(bot.name)
    setAgentId(bot.agent_id ?? '')
    setEnabled(bot.enabled)
    setConfig({ ...DEFAULT_CHATBOT_CONFIG, ...bot.config })
  }, [])

  useEffect(() => {
    chatbotService.get(id).then(adopt).catch((err) => setLoadError(getErrorMessage(err)))
    apiClient
      .get<{ agents: { id: string; name: string }[] }>(API_ENDPOINTS.AGENTS)
      .then((res) => setAgents(res.data.agents || []))
      .catch(() => setAgents([]))
  }, [id, adopt])

  const dirty = useMemo(() => {
    if (!chatbot) return false
    return (
      name.trim() !== chatbot.name ||
      (agentId || null) !== chatbot.agent_id ||
      enabled !== chatbot.enabled ||
      (Object.keys(config) as (keyof ChatbotConfig)[]).some((k) => config[k] !== chatbot.config[k])
    )
  }, [chatbot, name, agentId, enabled, config])

  const save = async () => {
    if (!chatbot) return
    if (!name.trim()) {
      setTab('setup')
      toast.error('Give your chatbot a name.')
      return
    }
    setSaving(true)
    try {
      adopt(await chatbotService.update(chatbot.id, { name: name.trim(), agent_id: agentId || null, enabled, config }))
      toast.success('Chatbot saved')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    if (!chatbot) return
    const ok = await confirm({
      title: 'Delete chatbot',
      description: `Delete “${chatbot.name}” and its conversations? The chat disappears from every site it’s installed on. This can’t be undone.`,
      confirmText: 'Delete chatbot',
      isDestructive: true,
    })
    if (!ok) return
    try {
      await chatbotService.remove(chatbot.id)
      toast.success('Chatbot deleted')
      router.push('/dashboard/chatbot')
    } catch (err) {
      toast.error(getErrorMessage(err))
    }
  }

  const copy = () => {
    if (!chatbot) return
    navigator.clipboard.writeText(chatbot.embed_snippet)
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }

  if (loadError) {
    return (
      <div className="flex flex-col items-center rounded-2xl border border-slate-200 bg-white px-6 py-16 text-center">
        <AlertCircle className="h-8 w-8 text-red-400" />
        <p className="mt-3 text-[14px] font-semibold text-slate-800">{loadError}</p>
        <Link href="/dashboard/chatbot" className="mt-4 text-sm font-semibold text-[#0F6A59] hover:underline">Back to chatbots</Link>
      </div>
    )
  }
  if (!chatbot) {
    return <div className="flex justify-center py-20"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>
  }

  const editable = canWrite && tab !== 'install' && tab !== 'conversations'

  return (
    <div className="space-y-5">
      <Link href="/dashboard/chatbot" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800">
        <ArrowLeft className="h-4 w-4" /> All chatbots
      </Link>

      {/* Title row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl text-white" style={{ background: chatbot.config.accent_color || '#0F6A59' }}>
            <MessageSquare className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="truncate font-poppins text-xl font-semibold text-slate-900">{chatbot.name}</h2>
              <ChatbotStatus chatbot={chatbot} />
            </div>
            <p className="mt-0.5 text-[13px] text-slate-500">
              {chatbot.agent ? <>Answered by <Link href={`/dashboard/agents/${chatbot.agent.id}`} className="font-medium text-[#0F6A59] hover:underline">{chatbot.agent.name}</Link></> : 'No agent linked'}
              {' · '}{chatbot.session_count} conversation{chatbot.session_count === 1 ? '' : 's'}
            </p>
          </div>
        </div>
        {canWrite && (
          <button onClick={remove} className="inline-flex h-10 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 text-sm font-medium text-slate-600 hover:border-red-200 hover:bg-red-50 hover:text-red-600">
            <Trash2 className="h-4 w-4" /> Delete
          </button>
        )}
      </div>

      {!chatbot.agent && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-900">
          <Bot className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <p>This chatbot won’t appear on your site until an agent is linked to answer it. Choose one under <strong>Setup</strong>.</p>
        </div>
      )}

      <div className="rounded-2xl border border-slate-200 bg-white card-shadow">
        {/* Tabs */}
        <div role="tablist" aria-label="Chatbot settings" className="flex gap-1 overflow-x-auto border-b border-slate-100 px-3 pt-3 [scrollbar-width:none] sm:px-5">
          {TABS.map(({ id: tabId, label, icon: Icon }) => (
            <button
              key={tabId}
              role="tab"
              aria-selected={tab === tabId}
              onClick={() => setTab(tabId)}
              className={`-mb-px inline-flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 text-[14px] font-medium transition-colors ${
                tab === tabId ? 'border-[#0F6A59] text-[#0F6A59]' : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <Icon className="h-4 w-4" /> {label}
            </button>
          ))}
        </div>

        <div className="p-5 sm:p-6">
          {tab === 'setup' && (
            <div className="max-w-xl space-y-5">
              <div>
                <label htmlFor="cb-name" className={labelClass}>Name</label>
                <input id="cb-name" value={name} maxLength={255} disabled={!canWrite} onChange={(e) => setName(e.target.value)} className={inputClass} />
              </div>
              <div>
                <label htmlFor="cb-agent" className={labelClass}>Answered by</label>
                <Select
                  value={agentId || NO_AGENT}
                  onValueChange={(value) => setAgentId(value === NO_AGENT ? '' : value)}
                  disabled={!canWrite}
                >
                  <SelectTrigger id="cb-agent" className={selectTriggerClass}>
                    <SelectValue placeholder="Choose an agent" />
                  </SelectTrigger>
                  <SelectContent searchable={agents.length > 6}>
                    <SelectItem value={NO_AGENT} textValue="No agent">
                      <span className="text-slate-500">No agent (chatbot hidden)</span>
                    </SelectItem>
                    {agents.map((a) => (
                      <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                    ))}
                    {/* A linked agent that isn't in the list (e.g. still loading) stays selectable. */}
                    {chatbot.agent && !agents.some((a) => a.id === chatbot.agent!.id) && (
                      <SelectItem value={chatbot.agent.id}>{chatbot.agent.name}</SelectItem>
                    )}
                  </SelectContent>
                </Select>
                <p className="mt-1.5 text-[12px] text-slate-500">
                  Its prompt, knowledge base and tools answer the chat. Changing it doesn’t change your install code.
                </p>
              </div>
              <div className="flex items-center justify-between gap-4 rounded-xl border border-slate-200 px-4 py-3">
                <div>
                  <p className="text-[14px] font-semibold text-slate-800">Show on my website</p>
                  <p className="text-[12px] text-slate-500">Turn off to hide the chat everywhere it’s installed, without removing the code.</p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={enabled}
                  aria-label="Show on my website"
                  disabled={!canWrite}
                  onClick={() => setEnabled((v) => !v)}
                  className={`relative h-6 w-11 flex-shrink-0 rounded-full transition-colors disabled:opacity-50 ${enabled ? 'bg-[#0F6A59]' : 'bg-slate-300'}`}
                >
                  <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${enabled ? 'left-[22px]' : 'left-0.5'}`} />
                </button>
              </div>
            </div>
          )}

          {tab === 'appearance' && <ChatbotAppearance config={config} onChange={setConfig} disabled={!canWrite} />}

          {tab === 'install' && (
            <div className="max-w-3xl space-y-4">
              <div>
                <h3 className="text-[15px] font-semibold text-slate-900">Add the chat to your website</h3>
                <p className="mt-1 text-[13px] text-slate-500">
                  Paste this line into the <code className="rounded bg-slate-100 px-1">&lt;head&gt;</code> of every page where the chat should appear.
                  It keeps working if you change the agent, the branding or the name.
                </p>
              </div>
              <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
                <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
                  <span className="text-[12px] font-medium text-slate-400">HTML</span>
                  <button onClick={copy} className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[12px] font-medium text-slate-200 hover:bg-slate-800">
                    {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <pre className="whitespace-pre-wrap break-all p-4 text-[12.5px] leading-relaxed text-slate-100">{chatbot.embed_snippet}</pre>
              </div>
              {!chatbot.live && (
                <p className="text-[13px] text-amber-700">
                  The chat is currently hidden on your site — {!chatbot.agent ? 'link an agent under Setup' : !chatbot.enabled ? 'turn on “Show on my website” under Setup' : 'the linked agent is paused'}.
                </p>
              )}
            </div>
          )}

          {tab === 'conversations' && <ChatbotConversations chatbotId={chatbot.id} />}
        </div>

        {editable && (
          <div className="flex flex-col-reverse gap-2 border-t border-slate-100 bg-slate-50/60 px-5 py-4 sm:flex-row sm:items-center sm:justify-end sm:px-6">
            {dirty && <span className="text-[12px] text-slate-500 sm:mr-auto">Unsaved changes</span>}
            <button
              type="button"
              onClick={() => adopt(chatbot)}
              disabled={!dirty || saving}
              className="inline-flex h-11 items-center justify-center rounded-xl border border-slate-200 bg-white px-5 text-[14px] font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              Discard
            </button>
            <button
              type="button"
              onClick={save}
              disabled={!dirty || saving}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#0F6A59] px-5 text-[14px] font-semibold text-white shadow-sm hover:bg-[#0c5a4b] disabled:opacity-50"
            >
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              Save changes
            </button>
          </div>
        )}
      </div>
      <ConfirmDialog />
    </div>
  )
}
