'use client'

import { useState, useEffect, useRef } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import {
  ArrowLeft, Phone, PhoneIncoming, PhoneOutgoing, DollarSign,
  Bot, User, Play, Pause, Volume2, Activity, FileText, ChevronRight,
  Mic, Cpu, Tag,
} from 'lucide-react'

interface CallDetail {
  id: string
  agent_id: string | null
  direction: 'inbound' | 'outbound' | 'test'
  status: string
  from_number: string
  to_number: string
  started_at: string | null
  answered_at: string | null
  ended_at: string | null
  duration_seconds: number | null
  recording_url: string | null
  recording_duration: number | null
  transcript: string | null
  transcript_json: TranscriptEntry[] | null
  sentiment_score: number | null
  sentiment_label: string | null
  cost_stt: number | null
  cost_llm: number | null
  cost_tts: number | null
  cost_telephony: number | null
  cost_total: number | null
  tags: string[]
  created_at: string
  updated_at: string
}

interface TranscriptEntry {
  role: 'user' | 'agent' | 'assistant'
  text: string
  timestamp?: string
  confidence?: number
}

const statusConfig: Record<string, { color: string; bg: string }> = {
  completed:   { color: 'text-emerald-700', bg: 'bg-emerald-50 border-emerald-200' },
  failed:      { color: 'text-red-700',     bg: 'bg-red-50 border-red-200' },
  missed:      { color: 'text-amber-700',   bg: 'bg-amber-50 border-amber-200' },
  in_progress: { color: 'text-blue-700',    bg: 'bg-blue-50 border-blue-200' },
  initiated:   { color: 'text-slate-600',   bg: 'bg-slate-50 border-slate-200' },
}

function fmtDur(s: number | null) {
  if (!s) return '—'
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`
}

function fmtDate(d: string | null) {
  if (!d) return '—'
  return new Date(d).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-slate-100 last:border-0">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="text-sm font-semibold text-slate-800">{value}</span>
    </div>
  )
}

function SentimentBar({ score, label }: { score: number | null; label: string | null }) {
  if (score == null) return <p className="text-sm text-slate-400 italic">No sentiment data</p>
  const pct = Math.round(score * 100)
  const color = pct >= 70 ? 'bg-emerald-500' : pct >= 40 ? 'bg-amber-400' : 'bg-red-400'
  const textColor = pct >= 70 ? 'text-emerald-700' : pct >= 40 ? 'text-amber-700' : 'text-red-600'
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className={`text-sm font-semibold capitalize ${textColor}`}>{label || (pct >= 70 ? 'Positive' : pct >= 40 ? 'Neutral' : 'Negative')}</span>
        <span className="text-sm font-bold text-slate-800">{pct}/100</span>
      </div>
      <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-700 ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function AudioPlayer({ url }: { url: string }) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [playing, setPlaying] = useState(false)
  const [current, setCurrent] = useState(0)
  const [duration, setDuration] = useState(0)

  const toggle = () => {
    const a = audioRef.current
    if (!a) return
    if (playing) { a.pause(); setPlaying(false) }
    else { a.play(); setPlaying(true) }
  }

  const fmtT = (t: number) => `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(Math.floor(t % 60)).padStart(2, '0')}`

  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
      <audio
        ref={audioRef}
        src={url}
        onTimeUpdate={e => setCurrent(e.currentTarget.currentTime)}
        onLoadedMetadata={e => setDuration(e.currentTarget.duration)}
        onEnded={() => setPlaying(false)}
      />
      <button
        onClick={toggle}
        className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-blue-600 text-white hover:bg-blue-700 transition-colors"
      >
        {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 ml-0.5" />}
      </button>
      <div className="flex-1 min-w-0">
        <input
          type="range"
          min={0}
          max={duration || 100}
          value={current}
          onChange={e => {
            const t = Number(e.target.value)
            setCurrent(t)
            if (audioRef.current) audioRef.current.currentTime = t
          }}
          className="w-full accent-indigo-600"
        />
      </div>
      <span className="text-xs font-mono text-slate-500 flex-shrink-0">
        {fmtT(current)} / {fmtT(duration)}
      </span>
      <Volume2 className="h-4 w-4 text-slate-400 flex-shrink-0" />
    </div>
  )
}

export default function CallDetailPage() {
  const params = useParams()
  const callId = params.id as string

  const [call, setCall] = useState<CallDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!callId) return
    apiClient.get<CallDetail>(API_ENDPOINTS.CALL(callId))
      .then(r => setCall(r.data))
      .catch(e => toast.error(getErrorMessage(e)))
      .finally(() => setIsLoading(false))
  }, [callId])

  if (isLoading) return (
    <div className="max-w-4xl mx-auto space-y-4 animate-pulse">
      <div className="h-8 w-48 bg-slate-200 rounded-lg" />
      <div className="h-28 bg-slate-100 rounded-2xl" />
      <div className="grid grid-cols-3 gap-4">
        {[1,2,3].map(i => <div key={i} className="h-36 bg-slate-100 rounded-xl" />)}
      </div>
    </div>
  )

  if (!call) return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <Phone className="h-12 w-12 text-slate-200 mb-3" />
      <p className="text-slate-500">Call not found</p>
      <Link href="/dashboard/calls" className="mt-4 text-sm text-blue-600 hover:underline">Back to calls</Link>
    </div>
  )

  const status = statusConfig[call.status] || statusConfig.initiated
  const transcript: TranscriptEntry[] = call.transcript_json
    ? call.transcript_json
    : call.transcript
    ? call.transcript.split('\n').filter(Boolean).map(line => {
        const isAgent = line.startsWith('Agent:') || line.startsWith('AI:') || line.startsWith('Assistant:')
        const text = line.replace(/^(Agent:|AI:|Assistant:|User:|Human:)\s*/i, '')
        return { role: isAgent ? 'agent' : 'user', text }
      })
    : []

  const totalCost = call.cost_total
    ?? ((call.cost_stt || 0) + (call.cost_llm || 0) + (call.cost_tts || 0) + (call.cost_telephony || 0))

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Link href="/dashboard/calls" className="flex items-center gap-1 hover:text-slate-700 transition-colors">
          <ArrowLeft className="h-3.5 w-3.5" /> Calls
        </Link>
        <ChevronRight className="h-3.5 w-3.5" />
        <span className="text-slate-900 font-medium font-mono text-xs">{call.id.slice(0, 8)}…</span>
      </div>

      {/* Hero card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-slate-100">
              {call.direction === 'inbound'
                ? <PhoneIncoming className="h-5 w-5 text-slate-600" />
                : <PhoneOutgoing className="h-5 w-5 text-slate-600" />
              }
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-lg font-bold text-slate-900">{call.from_number || '—'}</span>
                <span className="text-slate-400 text-sm">→</span>
                <span className="text-sm text-slate-600">{call.to_number || '—'}</span>
                <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${status.bg} ${status.color}`}>
                  {call.status}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5 capitalize">{call.direction} · {fmtDate(call.started_at)}</p>
            </div>
          </div>
          <div className="flex items-center gap-4 text-sm flex-shrink-0">
            <div className="text-center">
              <p className="text-lg font-bold text-slate-900">{fmtDur(call.duration_seconds)}</p>
              <p className="text-xs text-slate-400">Duration</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold text-slate-900">
                {totalCost ? `$${Number(totalCost).toFixed(4)}` : '—'}
              </p>
              <p className="text-xs text-slate-400">Cost</p>
            </div>
          </div>
        </div>
      </div>

      {/* Main grid */}
      <div className="grid gap-5 lg:grid-cols-3">

        {/* Transcript — 2 cols */}
        <div className="lg:col-span-2 space-y-4">
          {/* Recording player */}
          {call.recording_url && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-800 mb-3">
                <Volume2 className="h-4 w-4 text-blue-500" />
                Recording
              </h3>
              <AudioPlayer url={
                call.recording_url?.startsWith('/')
                  ? `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${call.recording_url}`
                  : call.recording_url
              } />
              {call.recording_duration && (
                <p className="text-xs text-slate-400 mt-2">
                  Duration: {fmtDur(call.recording_duration)}
                </p>
              )}
            </div>
          )}

          {/* Transcript */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-800 mb-4">
              <FileText className="h-4 w-4 text-slate-400" />
              Transcript
              {transcript.length > 0 && (
                <span className="ml-auto text-xs text-slate-400 font-normal">{transcript.length} turns</span>
              )}
            </h3>

            {transcript.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <FileText className="h-10 w-10 text-slate-200 mb-3" />
                <p className="text-sm text-slate-400">No transcript available</p>
                <p className="text-xs text-slate-300 mt-1">Transcripts appear for completed calls</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-[480px] overflow-y-auto pr-1">
                {transcript.map((entry, i) => {
                  const isAgent = entry.role === 'agent' || entry.role === 'assistant'
                  return (
                    <div key={i} className={`flex gap-2.5 ${isAgent ? 'justify-start' : 'justify-end'}`}>
                      {isAgent && (
                        <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 mt-1">
                          <Bot className="h-3.5 w-3.5 text-blue-600" />
                        </div>
                      )}
                      <div className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 ${
                        isAgent
                          ? 'bg-slate-100 text-slate-800 rounded-bl-sm'
                          : 'bg-blue-600 text-white rounded-br-sm'
                      }`}>
                        <p className="text-sm leading-relaxed">{entry.text}</p>
                        {entry.timestamp && (
                          <p className={`text-xs mt-1 ${isAgent ? 'text-slate-400' : 'text-blue-200'}`}>
                            {new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </p>
                        )}
                      </div>
                      {!isAgent && (
                        <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-slate-200 mt-1">
                          <User className="h-3.5 w-3.5 text-slate-600" />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {/* Raw transcript fallback */}
            {call.transcript && transcript.length === 0 && (
              <pre className="text-xs text-slate-600 bg-slate-50 rounded-lg p-4 whitespace-pre-wrap font-mono max-h-80 overflow-y-auto">
                {call.transcript}
              </pre>
            )}
          </div>
        </div>

        {/* Sidebar — 1 col */}
        <div className="space-y-4">
          {/* Call info */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-800 mb-3">
              <Phone className="h-4 w-4 text-slate-400" />
              Call Details
            </h3>
            <InfoRow label="Direction" value={<span className="capitalize">{call.direction}</span>} />
            <InfoRow label="Status" value={
              <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${status.bg} ${status.color}`}>
                {call.status}
              </span>
            } />
            <InfoRow label="Started" value={fmtDate(call.started_at)} />
            <InfoRow label="Answered" value={fmtDate(call.answered_at)} />
            <InfoRow label="Ended" value={fmtDate(call.ended_at)} />
            <InfoRow label="Duration" value={fmtDur(call.duration_seconds)} />
            {call.agent_id && (
              <InfoRow label="Agent ID" value={
                <Link href={`/dashboard/agents/${call.agent_id}`} className="font-mono text-xs text-blue-600 hover:underline">
                  {call.agent_id.slice(0, 8)}…
                </Link>
              } />
            )}
          </div>

          {/* Sentiment */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-800 mb-3">
              <Activity className="h-4 w-4 text-slate-400" />
              Sentiment
            </h3>
            <SentimentBar score={call.sentiment_score} label={call.sentiment_label} />
          </div>

          {/* Cost breakdown */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-800 mb-3">
              <DollarSign className="h-4 w-4 text-slate-400" />
              Cost Breakdown
            </h3>
            {[
              { label: 'STT',       value: call.cost_stt,       icon: Mic },
              { label: 'LLM',       value: call.cost_llm,       icon: Cpu },
              { label: 'TTS',       value: call.cost_tts,       icon: Volume2 },
              { label: 'Telephony', value: call.cost_telephony, icon: Phone },
            ].map(({ label, value, icon: Icon }) => (
              <div key={label} className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
                <div className="flex items-center gap-1.5 text-xs text-slate-500">
                  <Icon className="h-3.5 w-3.5" />
                  {label}
                </div>
                <span className="text-sm font-medium text-slate-700">
                  {value != null ? `$${Number(value).toFixed(4)}` : '—'}
                </span>
              </div>
            ))}
            <div className="flex items-center justify-between pt-2 mt-1 border-t border-slate-200">
              <span className="text-xs font-semibold text-slate-700">Total</span>
              <span className="text-sm font-bold text-slate-900">
                {totalCost ? `$${Number(totalCost).toFixed(4)}` : '—'}
              </span>
            </div>
          </div>

          {/* Tags */}
          {call.tags && call.tags.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-800 mb-3">
                <Tag className="h-4 w-4 text-slate-400" />
                Tags
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {call.tags.map(tag => (
                  <span key={tag} className="px-2.5 py-1 bg-slate-100 text-slate-600 rounded-full text-xs font-medium">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
