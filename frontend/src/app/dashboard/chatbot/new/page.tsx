'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { ArrowLeft, Bot, Loader2, MessageSquare } from 'lucide-react'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { chatbotService, DEFAULT_CHATBOT_CONFIG } from '@/lib/chatbots'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const inputClass =
  'h-11 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-[14px] text-slate-900 outline-none transition-colors placeholder:text-slate-400 focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15'

const selectTriggerClass =
  'h-11 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-[14px] text-slate-900 outline-none transition-colors hover:border-slate-300 focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 data-[state=open]:border-[#0F6A59] data-[state=open]:ring-2 data-[state=open]:ring-[#0F6A59]/15 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500'
// Radix Select can't use an empty value, so "choose later" gets a sentinel.
const LATER = '__later__'

export default function NewChatbotPage() {
  const router = useRouter()
  const [name, setName] = useState('Website chatbot')
  const [agentId, setAgentId] = useState('')
  const [agents, setAgents] = useState<{ id: string; name: string }[] | null>(null)
  const [saving, setSaving] = useState(false)
  const [nameError, setNameError] = useState<string | null>(null)

  useEffect(() => {
    apiClient
      .get<{ agents: { id: string; name: string }[] }>(API_ENDPOINTS.AGENTS)
      .then((res) => {
        const list = res.data.agents || []
        setAgents(list)
        if (list.length === 1) setAgentId(list[0].id)
      })
      .catch(() => setAgents([]))
  }, [])

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setNameError('Give your chatbot a name.')
      return
    }
    setSaving(true)
    try {
      // Branding is sent explicitly: the server's defaults predate the Voicecon
      // palette and must stay as they are for chatbots already installed.
      const bot = await chatbotService.create({ name: name.trim(), agent_id: agentId || null, config: DEFAULT_CHATBOT_CONFIG })
      toast.success('Chatbot created')
      router.push(`/dashboard/chatbot/${bot.id}`)
    } catch (err) {
      toast.error(getErrorMessage(err))
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <Link href="/dashboard/chatbot" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800">
        <ArrowLeft className="h-4 w-4" /> Back to chatbots
      </Link>

      <form onSubmit={create} noValidate className="rounded-2xl border border-slate-200 bg-white card-shadow">
        <div className="flex items-start gap-3 border-b border-slate-100 p-6">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0F6A59]/10 text-[#0F6A59]">
            <MessageSquare className="h-5 w-5" />
          </span>
          <div>
            <h2 className="font-poppins text-lg font-semibold text-slate-900">New chatbot</h2>
            <p className="mt-0.5 text-[13px] text-slate-500">You can brand it and get the install code on the next screen.</p>
          </div>
        </div>

        <div className="space-y-5 p-6">
          <div>
            <label htmlFor="cb-name" className="mb-1.5 block text-[13px] font-semibold text-slate-700">Name</label>
            <input
              id="cb-name"
              value={name}
              maxLength={255}
              autoFocus
              onChange={(e) => { setName(e.target.value); setNameError(null) }}
              aria-invalid={!!nameError}
              className={inputClass}
              placeholder="e.g. Main website"
            />
            {nameError ? (
              <p className="mt-1.5 text-[12px] text-red-600">{nameError}</p>
            ) : (
              <p className="mt-1.5 text-[12px] text-slate-500">Only you and your team see this.</p>
            )}
          </div>

          <div>
            <label htmlFor="cb-agent" className="mb-1.5 block text-[13px] font-semibold text-slate-700">Answered by</label>
            {agents === null ? (
              <div className="h-11 animate-pulse rounded-xl bg-slate-100" />
            ) : agents.length === 0 ? (
              <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[13px] text-amber-900">
                <Bot className="mt-0.5 h-4 w-4 flex-shrink-0" />
                <p>
                  You don’t have an agent yet. You can create the chatbot now and link one later, or{' '}
                  <Link href="/dashboard/agents/new" className="font-semibold underline">create an agent</Link> first.
                </p>
              </div>
            ) : (
              <Select value={agentId || LATER} onValueChange={(value) => setAgentId(value === LATER ? '' : value)}>
                <SelectTrigger id="cb-agent" className={selectTriggerClass}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent searchable={agents.length > 6}>
                  <SelectItem value={LATER} textValue="Choose later">
                    <span className="text-slate-500">Choose later</span>
                  </SelectItem>
                  {agents.map((a) => (
                    <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <p className="mt-1.5 text-[12px] text-slate-500">
              The agent’s prompt, knowledge base and tools answer the chat. You can change this any time.
            </p>
          </div>
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-slate-100 bg-slate-50/60 p-4 sm:flex-row sm:justify-end sm:px-6">
          <Link href="/dashboard/chatbot" className="inline-flex h-11 items-center justify-center rounded-xl border border-slate-200 bg-white px-5 text-[14px] font-semibold text-slate-700 hover:bg-slate-50">
            Cancel
          </Link>
          <button
            type="submit"
            disabled={saving}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#0F6A59] px-5 text-[14px] font-semibold text-white shadow-sm hover:bg-[#0c5a4b] disabled:opacity-60"
          >
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Create chatbot
          </button>
        </div>
      </form>
    </div>
  )
}
