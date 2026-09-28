'use client'

/**
 * Chatbot — the website chat channel as its own section.
 *
 * Each chatbot is embedded on a site with one script tag and answered by the
 * agent it's linked to. The link lives here (not on the agent), so a chatbot
 * can be moved to another agent without touching the installed embed code.
 */

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { AlertCircle, ArrowRight, Bot, MessageSquare, Plus, RefreshCw } from 'lucide-react'
import { getErrorMessage } from '@/lib/api'
import { chatbotService, type Chatbot } from '@/lib/chatbots'
import { PERMISSIONS } from '@/lib/workspace'
import { usePermission } from '@/store/workspaceStore'
import { ChatbotStatus } from '@/components/chatbot/ChatbotStatus'

export default function ChatbotListPage() {
  const canWrite = usePermission(PERMISSIONS.agentsWrite)
  const [chatbots, setChatbots] = useState<Chatbot[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      setChatbots(await chatbotService.list())
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (error) {
    return (
      <div className="flex flex-col items-center rounded-2xl border border-slate-200 bg-white px-6 py-16 text-center card-shadow">
        <AlertCircle className="h-8 w-8 text-red-400" />
        <p className="mt-3 text-[14px] font-semibold text-slate-800">{error}</p>
        <button onClick={load} className="mt-4 inline-flex h-10 items-center gap-1.5 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50">
          <RefreshCw className="h-4 w-4" /> Try again
        </button>
      </div>
    )
  }

  if (chatbots === null) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-[190px] animate-pulse rounded-2xl border border-slate-200 bg-white" />
        ))}
      </div>
    )
  }

  if (chatbots.length === 0) {
    return (
      <div className="flex flex-col items-center rounded-2xl border border-slate-200 bg-white px-6 py-16 text-center card-shadow">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#0F6A59]/10 ring-8 ring-[#0F6A59]/[0.04]">
          <MessageSquare className="h-6 w-6 text-[#0F6A59]" />
        </div>
        <h3 className="mt-5 font-poppins text-xl font-semibold tracking-tight text-slate-900">Add a chatbot to your website</h3>
        <p className="mt-1.5 max-w-md text-[14px] text-slate-500">
          Visitors chat by text with one of your agents — same knowledge, same tools. Install it with a single line of code.
        </p>
        {canWrite && (
          <Link
            href="/dashboard/chatbot/new"
            className="mt-6 inline-flex h-11 items-center gap-2 rounded-xl bg-[#0F6A59] px-5 text-[14px] font-semibold text-white shadow-sm hover:bg-[#0c5a4b]"
          >
            <Plus className="h-4 w-4" /> Create a chatbot
          </Link>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* The header's "New Chatbot" is hidden on phones; this stands in. */}
      {canWrite && (
        <div className="flex justify-end sm:hidden">
          <Link href="/dashboard/chatbot/new" className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-[#0F6A59] px-4 text-sm font-semibold text-white">
            <Plus className="h-4 w-4" /> New chatbot
          </Link>
        </div>
      )}
      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {chatbots.map((bot) => (
          <li key={bot.id}>
            <Link
              href={`/dashboard/chatbot/${bot.id}`}
              className="group flex h-full flex-col rounded-2xl border border-slate-200 bg-white p-5 transition-all card-shadow hover:border-[#0F6A59]/40 hover:shadow-[0_8px_30px_-14px_rgba(15,106,89,0.35)]"
            >
              <div className="flex items-start justify-between gap-3">
                <span
                  className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl text-white"
                  style={{ background: bot.config.accent_color || '#0F6A59' }}
                >
                  <MessageSquare className="h-5 w-5" />
                </span>
                <ChatbotStatus chatbot={bot} />
              </div>
              <h3 className="mt-4 truncate text-[16px] font-semibold text-slate-900">{bot.name}</h3>
              <p className="mt-1 flex items-center gap-1.5 truncate text-[13px] text-slate-500">
                <Bot className="h-3.5 w-3.5 flex-shrink-0" />
                {bot.agent ? <>Answered by <span className="font-medium text-slate-700">{bot.agent.name}</span></> : 'No agent linked yet'}
              </p>
              <div className="mt-auto flex items-center justify-between border-t border-slate-100 pt-4 text-[12px] text-slate-500">
                <span>
                  {bot.session_count} conversation{bot.session_count === 1 ? '' : 's'}
                  {bot.last_activity_at && <> · last {new Date(bot.last_activity_at).toLocaleDateString()}</>}
                </span>
                <ArrowRight className="h-4 w-4 text-slate-400 transition-transform group-hover:translate-x-0.5 group-hover:text-[#0F6A59]" />
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
