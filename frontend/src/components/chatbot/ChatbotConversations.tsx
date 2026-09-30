'use client'

import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, ChevronLeft, ChevronRight, Loader2, MessageSquare, RefreshCw } from 'lucide-react'
import { getErrorMessage } from '@/lib/api'
import {
  chatbotService,
  type ChatSessionSummary,
  type ChatTranscriptMessage,
} from '@/lib/chatbots'
import { formatDateTime } from '@/lib/datetime'

const PAGE_SIZE = 20

function when(iso: string) {
  return formatDateTime(iso)
}

/** A chatbot's conversations, with the transcript of the selected one. */
export function ChatbotConversations({ chatbotId }: { chatbotId: string }) {
  const [page, setPage] = useState(1)
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<ChatSessionSummary | null>(null)
  const [transcript, setTranscript] = useState<ChatTranscriptMessage[] | null>(null)
  const [transcriptLoading, setTranscriptLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await chatbotService.sessions(chatbotId, page)
      setSessions(res.sessions)
      setTotal(res.total)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [chatbotId, page])

  useEffect(() => { load() }, [load])

  const open = async (session: ChatSessionSummary) => {
    setSelected(session)
    setTranscript(null)
    setTranscriptLoading(true)
    try {
      setTranscript(await chatbotService.transcript(session.id))
    } catch {
      setTranscript([])
    } finally {
      setTranscriptLoading(false)
    }
  }

  if (loading && sessions.length === 0) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center py-12 text-center">
        <AlertCircle className="h-7 w-7 text-red-400" />
        <p className="mt-3 text-[14px] text-slate-700">{error}</p>
        <button onClick={load} className="mt-4 inline-flex h-10 items-center gap-1.5 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50">
          <RefreshCw className="h-4 w-4" /> Try again
        </button>
      </div>
    )
  }

  if (total === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-200 px-6 py-14 text-center">
        <MessageSquare className="mx-auto h-8 w-8 text-slate-300" />
        <p className="mt-3 text-[15px] font-semibold text-slate-800">No conversations yet</p>
        <p className="mt-1 text-[13px] text-slate-500">Chats from your website will appear here as visitors start them.</p>
      </div>
    )
  }

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <div className="overflow-hidden rounded-2xl border border-slate-200">
        <ul className="divide-y divide-slate-100">
          {sessions.map((s) => (
            <li key={s.id}>
              <button
                onClick={() => open(s)}
                className={`flex w-full items-start gap-3 px-4 py-3 text-left transition-colors ${
                  selected?.id === s.id ? 'bg-[#0F6A59]/[0.05]' : 'hover:bg-slate-50'
                }`}
              >
                <span className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                  <MessageSquare className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[13.5px] font-semibold text-slate-800">{when(s.started_at)}</span>
                  <span className="mt-0.5 block truncate text-[12px] text-slate-500">
                    {s.message_count} messages{s.source_url ? ` · ${s.source_url}` : ''}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
        {pages > 1 && (
          <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2.5 text-[12px] text-slate-500">
            <span>Page {page} of {pages}</span>
            <div className="flex gap-1">
              <button aria-label="Previous page" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded-lg p-1.5 hover:bg-slate-100 disabled:opacity-40">
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button aria-label="Next page" disabled={page >= pages} onClick={() => setPage((p) => p + 1)} className="rounded-lg p-1.5 hover:bg-slate-100 disabled:opacity-40">
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="min-h-[280px] rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
        {!selected ? (
          <p className="flex h-full items-center justify-center text-[13px] text-slate-500">Select a conversation to read it.</p>
        ) : transcriptLoading ? (
          <div className="flex h-full items-center justify-center"><Loader2 className="h-5 w-5 animate-spin text-slate-400" /></div>
        ) : transcript && transcript.length > 0 ? (
          <div className="space-y-2.5">
            {transcript.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-[13px] leading-relaxed ${
                    m.role === 'user' ? 'rounded-br-sm bg-[#0F6A59] text-white' : 'rounded-bl-sm border border-slate-200 bg-white text-slate-800'
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="flex h-full items-center justify-center text-[13px] text-slate-500">No messages in this conversation.</p>
        )}
      </div>
    </div>
  )
}
