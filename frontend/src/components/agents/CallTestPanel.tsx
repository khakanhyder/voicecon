'use client'

/**
 * Live test-call drawer. Lifted out of the old standalone agent view page so the
 * agent editor — now the only agent detail page — can host it unchanged.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import {
  Bot, Mic, Volume2, Phone, PhoneOff, PhoneCall, X, Send, Radio, Wifi, Zap,
} from 'lucide-react'

/** Only the fields the drawer actually reads off the agent. */
export interface TestCallAgent {
  name: string
  first_message: string
  interrupt_enabled?: boolean
  silence_timeout?: number
  max_call_duration?: number
}

interface Message {
  id: string
  role: 'user' | 'agent'
  text: string
  timestamp: Date
}

type CallState = 'idle' | 'starting' | 'listening' | 'processing' | 'speaking' | 'ended'
type SttMode  = 'none' | 'deepgram' | 'webspeech'
declare global { interface Window { SpeechRecognition: any; webkitSpeechRecognition: any } }

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const formatTime = (s: number) => `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`

const CALL_STATUS: Record<CallState, { label: string; dot: string; bar: string }> = {
  idle:       { label: 'Ready',       dot: 'bg-slate-400',   bar: '' },
  starting:   { label: 'Connecting', dot: 'bg-amber-400 animate-pulse',  bar: 'bg-amber-50' },
  listening:  { label: 'Listening',  dot: 'bg-emerald-500 animate-pulse', bar: 'bg-emerald-50' },
  processing: { label: 'Thinking',   dot: 'bg-blue-500 animate-pulse',    bar: 'bg-blue-50' },
  speaking:   { label: 'Speaking',   dot: 'bg-blue-500 animate-pulse',  bar: 'bg-blue-50' },
  ended:      { label: 'Call ended', dot: 'bg-slate-400',   bar: '' },
}

// ════════════════════════════════════════════════════════════════════════════
// Call Test Panel (right drawer)
// ════════════════════════════════════════════════════════════════════════════

export function CallTestPanel({
  agent, agentId, open, onClose
}: {
  agent: TestCallAgent
  agentId: string
  open: boolean
  onClose: () => void
}) {
  const [callState, setCallState] = useState<CallState>('idle')
  const [messages,  setMessages]  = useState<Message[]>([])
  const [liveText,  setLiveText]  = useState('')
  const [agentText, setAgentText] = useState('')
  const [volume,    setVolume]    = useState(0)
  const [elapsed,   setElapsed]   = useState(0)
  const [textInput, setTextInput] = useState('')
  const [sttMode,   setSttMode]   = useState<SttMode>('none')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // ── Core refs ──────────────────────────────────────────────────────────────
  const isActiveRef       = useRef(false)
  const isPlayingRef      = useRef(false)
  const callStateRef      = useRef<CallState>('idle')
  const historyRef        = useRef<{ role: string; text: string }[]>([])
  const interruptRef      = useRef(true)
  const endPhrasesRef     = useRef<string[]>([])
  const maxDurRef         = useRef(1800)
  const idleTimeoutRef    = useRef(8000)
  const streamRef         = useRef<MediaStream | null>(null)
  const audioQueueRef     = useRef<{ audio_base64: string; format: string }[]>([])
  const currentAudioRef   = useRef<HTMLAudioElement | null>(null)
  const abortCtrlRef      = useRef<AbortController | null>(null)
  const drainResolveRef   = useRef<(() => void) | null>(null)
  const drainGenRef       = useRef(0)
  const timerRef          = useRef<ReturnType<typeof setInterval> | null>(null)
  const animFrameRef      = useRef<number>(0)
  const analyserRef       = useRef<AnalyserNode | null>(null)
  const audioCtxRef       = useRef<AudioContext | null>(null)
  const idleTimerRef      = useRef<ReturnType<typeof setTimeout> | null>(null)
  const maxTimerRef       = useRef<ReturnType<typeof setTimeout> | null>(null)
  const dgWsRef           = useRef<WebSocket | null>(null)
  const mediaRecRef       = useRef<MediaRecorder | null>(null)
  const dgAvailRef        = useRef(true)
  const recognitionRef    = useRef<any>(null)
  const intentStopRef     = useRef(false)
  const startSpeechRef    = useRef<() => void>(() => {})
  const startWebSpeechRef = useRef<() => void>(() => {})
  const startDgRef        = useRef<() => void>(() => {})
  const streamRespRef     = useRef<(t: string) => Promise<void>>(async () => {})
  const resetIdleRef      = useRef<() => void>(() => {})
  const endCallRef        = useRef<() => void>(() => {})

  useEffect(() => { callStateRef.current = callState }, [callState])

  // Sync agent settings on open
  useEffect(() => {
    if (open && agent) {
      interruptRef.current  = agent.interrupt_enabled ?? true
      endPhrasesRef.current = [] // agent.end_call_phrases || []
      maxDurRef.current     = agent.max_call_duration || 1800
      idleTimeoutRef.current = agent.silence_timeout || 8000
    }
    if (!open) stopAll()
  }, [open, agent])

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, agentText])

  // ── Helpers ────────────────────────────────────────────────────────────────
  const addMessage = (role: 'user' | 'agent', text: string) => {
    setMessages(prev => [...prev, { id: Date.now().toString(), role, text, timestamp: new Date() }])
    historyRef.current.push({ role, text })
  }


  const stopAll = () => {
    isActiveRef.current = false
    if (idleTimerRef.current) { clearTimeout(idleTimerRef.current); idleTimerRef.current = null }
    if (maxTimerRef.current)  { clearTimeout(maxTimerRef.current);  maxTimerRef.current = null }
    if (recognitionRef.current)  { try { recognitionRef.current.stop() } catch {} }
    if (dgWsRef.current)         { try { dgWsRef.current.close() } catch {}; dgWsRef.current = null }
    if (mediaRecRef.current)     { try { mediaRecRef.current.stop() } catch {}; mediaRecRef.current = null }
    if (currentAudioRef.current) { currentAudioRef.current.pause(); currentAudioRef.current = null }
    if (abortCtrlRef.current)    { abortCtrlRef.current.abort() }
    if (timerRef.current)        { clearInterval(timerRef.current); timerRef.current = null }
    cancelAnimationFrame(animFrameRef.current)
    if (streamRef.current)  { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null }
    if (audioCtxRef.current){ audioCtxRef.current.close().catch(() => {}); audioCtxRef.current = null }
    audioQueueRef.current = []
    isPlayingRef.current  = false
  }

  const startVolumeMonitor = (stream: MediaStream) => {
    const ctx    = new AudioContext()
    audioCtxRef.current = ctx
    const src    = ctx.createMediaStreamSource(stream)
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 256
    src.connect(analyser)
    analyserRef.current = analyser
    const tick = () => {
      if (!analyserRef.current) return
      const d = new Uint8Array(analyserRef.current.frequencyBinCount)
      analyserRef.current.getByteFrequencyData(d)
      setVolume(Math.min(100, Math.sqrt(d.reduce((a, b) => a + b * b, 0) / d.length) * 3))
      animFrameRef.current = requestAnimationFrame(tick)
    }
    animFrameRef.current = requestAnimationFrame(tick)
  }

  const stopAudioNow = useCallback(() => {
    if (drainResolveRef.current) { drainResolveRef.current(); drainResolveRef.current = null }
    drainGenRef.current++
    if (currentAudioRef.current) { currentAudioRef.current.pause(); currentAudioRef.current = null }
    audioQueueRef.current = []
    isPlayingRef.current  = false
  }, [])

  const resetIdleTimer = useCallback(() => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current)
    if (idleTimeoutRef.current > 0 && isActiveRef.current) {
      idleTimerRef.current = setTimeout(() => {
        if (isActiveRef.current && callStateRef.current === 'listening') {
          streamRespRef.current('[The user has been silent. Briefly check in.]')
        }
      }, idleTimeoutRef.current)
    }
  }, [])
  useEffect(() => { resetIdleRef.current = resetIdleTimer }, [resetIdleTimer])

  const drainQueue = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return
    isPlayingRef.current = true
    const myGen = ++drainGenRef.current
    while (audioQueueRef.current.length > 0 && isActiveRef.current) {
      const item = audioQueueRef.current.shift()!
      try {
        const mime  = item.format === 'mp3' ? 'audio/mpeg' : `audio/${item.format}`
        const bytes = atob(item.audio_base64)
        const buf   = new Uint8Array(bytes.length)
        for (let i = 0; i < bytes.length; i++) buf[i] = bytes.charCodeAt(i)
        const url   = URL.createObjectURL(new Blob([buf], { type: mime }))
        const audio = new Audio(url)
        currentAudioRef.current = audio
        await new Promise<void>(resolve => {
          const done = () => { drainResolveRef.current = null; resolve() }
          drainResolveRef.current = done
          audio.onended = audio.onerror = audio.onabort = done
          audio.play().catch(done)
          setTimeout(done, 30000)
        })
      } catch {}
    }
    drainResolveRef.current = null
    isPlayingRef.current = false
    currentAudioRef.current = null
    if (myGen === drainGenRef.current && isActiveRef.current
        && callStateRef.current !== 'ended' && callStateRef.current !== 'processing') {
      setCallState('listening')
      callStateRef.current = 'listening'
      setTimeout(() => { if (isActiveRef.current) startSpeechRef.current() }, 150)
    }
  }, [])

  const endCall = useCallback(() => {
    stopAll()
    setCallState('ended')
    setLiveText('')
    setAgentText('')
    setSttMode('none')
  }, [])
  useEffect(() => { endCallRef.current = endCall }, [endCall])

  const streamResponse = useCallback(async (userText: string) => {
    if (!isActiveRef.current) return
    setCallState('processing')
    callStateRef.current = 'processing'
    setAgentText('')
    stopAudioNow()
    const token = localStorage.getItem('access_token') || ''
    try {
      const ctrl = new AbortController()
      abortCtrlRef.current = ctrl
      const res = await fetch(`${API_BASE}/api/v1/agents/${agentId}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ message: userText, history: historyRef.current.slice(-10) }),
        signal: ctrl.signal,
      })
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
      setCallState('speaking')
      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      let fullText = '', buffer = '', shouldEnd = false
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue
          try {
            const ev = JSON.parse(raw)
            if (ev.type === 'sentence') {
              fullText += (fullText ? ' ' : '') + ev.text
              setAgentText(fullText)
              if (ev.audio_base64) {
                audioQueueRef.current.push({ audio_base64: ev.audio_base64, format: ev.audio_format || 'mp3' })
                drainQueue()
              }
            } else if (ev.type === 'done') {
              fullText  = ev.full_text || fullText
              shouldEnd = !!ev.end_call
            }
          } catch {}
        }
      }
      if (fullText.trim()) addMessage('agent', fullText.trim())
      setAgentText('')
      if (shouldEnd) {
        const check = setInterval(() => {
          if (!isPlayingRef.current && audioQueueRef.current.length === 0) {
            clearInterval(check); setTimeout(() => endCallRef.current(), 800)
          }
        }, 200)
        setTimeout(() => { clearInterval(check); endCallRef.current() }, 8000)
        return
      }
      if (audioQueueRef.current.length === 0 && !isPlayingRef.current && isActiveRef.current) {
        setCallState('listening')
        callStateRef.current = 'listening'
        setTimeout(() => startSpeechRef.current(), 150)
      }
    } catch (e: any) {
      if (e?.name === 'AbortError') return
      toast.error(e?.message || 'Response failed')
      if (isActiveRef.current) { setCallState('listening'); callStateRef.current = 'listening'; setTimeout(() => startSpeechRef.current(), 150) }
    }
  }, [drainQueue, stopAudioNow, agentId])

  const startDeepgramSession = useCallback(() => {
    if (!isActiveRef.current) return
    if (dgWsRef.current?.readyState === WebSocket.OPEN) {
      setCallState('listening'); callStateRef.current = 'listening'; resetIdleRef.current(); return
    }
    const token  = localStorage.getItem('access_token') || ''
    const wsBase = API_BASE.replace(/^http(s?)/, (_, s) => `ws${s}`)
    let ws: WebSocket
    try { ws = new WebSocket(`${wsBase}/api/v1/agents/${agentId}/stt?token=${encodeURIComponent(token)}`) }
    catch { dgAvailRef.current = false; setSttMode('webspeech'); startWebSpeechRef.current(); return }
    dgWsRef.current = ws
    ws.onmessage = (e) => {
      if (!isActiveRef.current) return
      try {
        const ev = JSON.parse(e.data)
        if (ev.type === 'ready') {
          if (!streamRef.current) return
          const mime = ['audio/webm;codecs=opus','audio/webm','audio/ogg'].find(m => MediaRecorder.isTypeSupported(m)) || ''
          try {
            const rec = new MediaRecorder(streamRef.current, mime ? { mimeType: mime } : {})
            mediaRecRef.current = rec
            rec.ondataavailable = ev2 => { if (ev2.data.size > 0 && ws.readyState === WebSocket.OPEN) ws.send(ev2.data) }
            rec.start(100)
            setSttMode('deepgram'); setCallState('listening'); callStateRef.current = 'listening'; resetIdleRef.current()
          } catch { ws.close(); dgAvailRef.current = false; setSttMode('webspeech'); startWebSpeechRef.current() }
        } else if (ev.type === 'transcript') {
          const { text, speech_final } = ev
          if (!text?.trim()) return
          resetIdleRef.current()
          setLiveText(text)
          const agentBusy = callStateRef.current === 'speaking' || callStateRef.current === 'processing'
          if (agentBusy && interruptRef.current) { stopAudioNow(); if (abortCtrlRef.current) { abortCtrlRef.current.abort(); abortCtrlRef.current = null }; setCallState('listening'); callStateRef.current = 'listening' }
          if (speech_final) {
            if (callStateRef.current === 'processing') return
            callStateRef.current = 'processing'
            if (idleTimerRef.current) clearTimeout(idleTimerRef.current)
            setLiveText('')
            addMessage('user', text.trim())
            streamRespRef.current(text.trim())
          }
        } else if (ev.type === 'error') {
          // Deepgram unusable (bad/missing key). Don't retry it — onclose would loop forever.
          dgAvailRef.current = false
          setSttMode('webspeech')
          toast.error(`Speech-to-text unavailable: ${ev.message || 'unknown error'}`)
          ws.close()
        }
      } catch {}
    }
    ws.onerror  = () => { dgWsRef.current = null; dgAvailRef.current = false; setSttMode('webspeech'); if (isActiveRef.current) startWebSpeechRef.current() }
    ws.onclose  = () => {
      dgWsRef.current = null
      if (mediaRecRef.current) { try { mediaRecRef.current.stop() } catch {}; mediaRecRef.current = null }
      if (isActiveRef.current && callStateRef.current !== 'ended' && callStateRef.current !== 'idle') {
        if (dgAvailRef.current) setTimeout(() => { if (isActiveRef.current) startDgRef.current() }, 1000)
        else startWebSpeechRef.current()
      }
    }
  }, [agentId, stopAudioNow])

  const startWebSpeech = useCallback(() => {
    if (!isActiveRef.current) return
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      toast.error('Speech recognition unavailable — you can still type to test the agent.')
      // Leave the call usable in text-only mode; otherwise callState sticks and sendText is blocked.
      setSttMode('none'); setCallState('listening'); callStateRef.current = 'listening'
      return
    }
    const r = new SR()
    recognitionRef.current = r
    r.continuous = false; r.interimResults = true; r.lang = 'en-US'
    r.onstart = () => { setCallState('listening'); resetIdleRef.current() }
    r.onresult = (e: any) => {
      let interim = '', final = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript
        if (e.results[i].isFinal) final += t; else interim += t
      }
      setLiveText(interim || final)
      if ((interim || final).trim()) resetIdleRef.current()
      const agentBusy = callStateRef.current === 'speaking' || callStateRef.current === 'processing'
      if (agentBusy && interruptRef.current && (interim || final).trim()) { stopAudioNow(); if (abortCtrlRef.current) { abortCtrlRef.current.abort(); abortCtrlRef.current = null }; setCallState('listening'); callStateRef.current = 'listening' }
      if (final.trim()) { intentStopRef.current = true; callStateRef.current = 'processing'; r.stop(); setLiveText(''); addMessage('user', final.trim()); streamRespRef.current(final.trim()) }
    }
    r.onerror = (e: any) => { if (e.error === 'no-speech' && isActiveRef.current && !intentStopRef.current) startWebSpeechRef.current() }
    r.onend   = () => { if (intentStopRef.current) { intentStopRef.current = false; return }; if (isActiveRef.current && callStateRef.current === 'listening') setTimeout(() => startSpeechRef.current(), 150) }
    try { r.start() } catch {}
  }, [stopAudioNow])

  const startListening = useCallback(() => {
    if (!isActiveRef.current) return
    if (dgWsRef.current?.readyState === WebSocket.OPEN) { setCallState('listening'); callStateRef.current = 'listening'; resetIdleRef.current() }
    else if (dgAvailRef.current) startDgRef.current()
    else startWebSpeechRef.current()
  }, [])

  useEffect(() => { startSpeechRef.current     = startListening },      [startListening])
  useEffect(() => { startWebSpeechRef.current   = startWebSpeech },      [startWebSpeech])
  useEffect(() => { startDgRef.current          = startDeepgramSession }, [startDeepgramSession])
  useEffect(() => { streamRespRef.current       = streamResponse },       [streamResponse])

  const streamGreeting = async (text: string) => {
    try {
      const r = await apiClient.post<{ audio_base64: string; audio_format: string }>(
        `${API_ENDPOINTS.AGENT(agentId)}/speak`, { text }
      )
      const mime  = r.data.audio_format === 'mp3' ? 'audio/mpeg' : `audio/${r.data.audio_format}`
      const bytes = atob(r.data.audio_base64)
      const buf   = new Uint8Array(bytes.length)
      for (let i = 0; i < bytes.length; i++) buf[i] = bytes.charCodeAt(i)
      const audio = new Audio(URL.createObjectURL(new Blob([buf], { type: mime })))
      currentAudioRef.current = audio
      await audio.play()
      await new Promise<void>(r2 => { audio.onended = () => r2() })
    } catch {}
    if (isActiveRef.current) startDeepgramSession()
  }

  const startCall = async () => {
    setCallState('starting')
    setMessages([]); setAgentText(''); setLiveText(''); setElapsed(0); setSttMode('none')
    historyRef.current  = []
    isActiveRef.current = true
    dgAvailRef.current  = true
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      startVolumeMonitor(stream)
    } catch { toast.error('Microphone access denied.'); setCallState('idle'); return }
    timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000)
    if (maxDurRef.current > 0) {
      maxTimerRef.current = setTimeout(() => {
        if (isActiveRef.current) { toast.info('Max call duration reached.'); endCallRef.current() }
      }, maxDurRef.current * 1000)
    }
    if (agent.first_message) {
      setCallState('speaking')
      addMessage('agent', agent.first_message)
      await streamGreeting(agent.first_message)
    } else {
      startDeepgramSession()
    }
  }

  const sendText = async (e: React.FormEvent) => {
    e.preventDefault()
    const text = textInput.trim()
    if (!text || callState === 'processing' || callState === 'speaking') return
    setTextInput('')
    stopAudioNow()
    addMessage('user', text)
    await streamResponse(text)
  }

  const isLive = callState !== 'idle' && callState !== 'ended'
  const st     = CALL_STATUS[callState]

  // Waveform bars driven by volume
  const bars = [0.4, 0.7, 1, 0.8, 0.5, 0.9, 0.6]

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-40 bg-black/30 backdrop-blur-sm transition-opacity duration-300 ${open ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={onClose}
      />

      {/* Sliding panel */}
      <div className={`fixed top-0 right-0 bottom-0 z-50 w-full sm:w-[480px] bg-white shadow-2xl flex flex-col transition-transform duration-300 ease-out ${open ? 'translate-x-0' : 'translate-x-full'}`}>

        {/* Panel header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg gradient-primary">
              <PhoneCall className="h-4 w-4 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">Live Test Call</p>
              <p className="text-xs text-slate-500">{agent.name}</p>
            </div>
          </div>
          <button onClick={onClose} className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors">
            <X className="h-4.5 w-4.5" />
          </button>
        </div>

        {/* Status bar */}
        <div className={`flex items-center justify-between px-5 py-2.5 border-b border-slate-100 flex-shrink-0 ${st.bar || 'bg-slate-50'}`}>
          <div className="flex items-center gap-2.5">
            {/* Waveform */}
            {isLive ? (
              <div className="flex items-end gap-0.5 h-4">
                {bars.map((h, i) => (
                  <div key={i}
                    className={`w-0.5 rounded-full transition-all duration-75 ${
                      callState === 'listening'  ? 'bg-emerald-500'
                      : callState === 'speaking' ? 'bg-blue-500'
                      : 'bg-slate-300'
                    }`}
                    style={{ height: `${Math.max(2, (volume / 100) * h * 16)}px` }}
                  />
                ))}
              </div>
            ) : <span className={`h-2 w-2 rounded-full ${st.dot}`} />}
            <span className="text-xs font-medium text-slate-700">{st.label}</span>
            {sttMode === 'deepgram' && isLive && (
              <span className="flex items-center gap-1 text-xs text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full font-medium">
                <Zap className="h-3 w-3" /> Deepgram
              </span>
            )}
          </div>
          {isLive && (
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-slate-500">{formatTime(elapsed)}</span>
              <span className="flex items-center gap-1 text-xs font-semibold text-red-600">
                <Radio className="h-3 w-3" /> LIVE
              </span>
            </div>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
          {messages.length === 0 && !isLive && (
            <div className="flex flex-col items-center justify-center h-full text-center text-slate-400 gap-4 py-8">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100">
                <PhoneCall className="h-8 w-8 text-slate-300" />
              </div>
              <div>
                <p className="font-semibold text-slate-600 text-base">Ready to test</p>
                <p className="text-sm mt-1 text-slate-400 max-w-xs">
                  Start a live call to test your agent with real voice or text input.
                </p>
              </div>
              <div className="flex flex-col gap-1.5 text-xs text-slate-400 bg-slate-50 rounded-xl p-3 w-full text-left">
                <div className="flex items-center gap-2"><Mic     className="h-3 w-3" /> Deepgram real-time STT</div>
                <div className="flex items-center gap-2"><Volume2 className="h-3 w-3" /> ElevenLabs TTS</div>
                <div className="flex items-center gap-2"><Wifi    className="h-3 w-3" /> Barge-in interruption</div>
              </div>
            </div>
          )}

          {messages.map(msg => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'agent' && (
                <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 mr-2 mt-1">
                  <Bot className="h-3.5 w-3.5 text-blue-600" />
                </div>
              )}
              <div className={`max-w-[80%] rounded-2xl px-3.5 py-2.5 ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-sm'
                  : 'bg-slate-100 text-slate-800 rounded-bl-sm'
              }`}>
                <p className="text-sm leading-relaxed">{msg.text}</p>
                <p className={`text-xs mt-1 ${msg.role === 'user' ? 'text-blue-200' : 'text-slate-400'}`}>
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
            </div>
          ))}

          {/* Live transcript bubble */}
          {liveText && (
            <div className="flex justify-end">
              <div className="max-w-[80%] rounded-2xl rounded-br-sm px-3.5 py-2.5 bg-blue-100 border border-blue-200">
                <p className="text-sm italic text-blue-700">{liveText}</p>
              </div>
            </div>
          )}

          {/* Agent streaming bubble */}
          {agentText && (
            <div className="flex justify-start items-start gap-2">
              <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-blue-100">
                <Bot className="h-3.5 w-3.5 text-blue-600" />
              </div>
              <div className="max-w-[80%] rounded-2xl rounded-bl-sm px-3.5 py-2.5 bg-slate-100">
                <p className="text-sm leading-relaxed text-slate-800">{agentText}</p>
                <div className="flex gap-0.5 mt-1.5">
                  {[0,150,300].map(d => <div key={d} className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay:`${d}ms` }} />)}
                </div>
              </div>
            </div>
          )}

          {callState === 'processing' && !agentText && (
            <div className="flex justify-start items-start gap-2">
              <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-blue-100">
                <Bot className="h-3.5 w-3.5 text-blue-600" />
              </div>
              <div className="rounded-2xl rounded-bl-sm px-4 py-3 bg-slate-100">
                <div className="flex gap-1">
                  {[0,150,300].map(d => <div key={d} className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay:`${d}ms` }} />)}
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Stats strip (during call) */}
        {isLive && (
          <div className="flex items-center gap-4 px-5 py-2 border-t border-slate-100 bg-slate-50 text-xs text-slate-500 flex-shrink-0">
            <span>{messages.filter(m => m.role==='user').length} user turn{messages.filter(m=>m.role==='user').length!==1?'s':''}</span>
            <span>{messages.filter(m => m.role==='agent').length} agent turn{messages.filter(m=>m.role==='agent').length!==1?'s':''}</span>
            <span className="ml-auto font-mono">{formatTime(elapsed)}</span>
          </div>
        )}

        {/* Input + controls */}
        <div className="border-t border-slate-200 p-4 flex-shrink-0">
          {!isLive ? (
            <button
              onClick={startCall}
              className="flex w-full items-center justify-center gap-2 rounded-xl gradient-primary py-3 text-sm font-semibold text-white hover:opacity-90 transition-all shadow-sm"
            >
              <Phone className="h-4 w-4" />
              {callState === 'ended' ? 'Start New Call' : 'Start Call'}
            </button>
          ) : (
            <div className="space-y-2.5">
              <form onSubmit={sendText} className="flex gap-2">
                <input
                  value={textInput}
                  onChange={e => { setTextInput(e.target.value); resetIdleRef.current(); }}
                  placeholder={callState === 'listening' ? 'Speaking or type a message…' : 'Type a message…'}
                  disabled={callState === 'processing'}
                  className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2 text-sm text-slate-800 placeholder:text-slate-400 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20 disabled:opacity-50 transition-all"
                />
                <button
                  type="submit"
                  disabled={!textInput.trim() || callState === 'processing'}
                  className="flex items-center justify-center h-10 w-10 rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 transition-all flex-shrink-0"
                >
                  <Send className="h-4 w-4" />
                </button>
              </form>
              <button
                onClick={endCall}
                className="flex w-full items-center justify-center gap-2 rounded-xl border border-red-200 bg-red-50 py-2.5 text-sm font-semibold text-red-600 hover:bg-red-100 transition-all"
              >
                <PhoneOff className="h-4 w-4" /> End Call
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
