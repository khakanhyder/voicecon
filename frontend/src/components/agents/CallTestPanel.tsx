'use client'

/**
 * Live test-call drawer. Lifted out of the old standalone agent view page so the
 * agent editor — now the only agent detail page — can host it unchanged.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { apiClient, getErrorMessage, publicErrorText } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import {
  Bot, Mic, Volume2, Phone, PhoneOff, PhoneCall, X, Send, Radio, Wifi, Zap,
} from 'lucide-react'
import { getAccessToken } from '@/lib/session'

/** Only the fields the drawer actually reads off the agent. */
export interface TestCallAgent {
  name: string
  first_message: string
  interrupt_enabled?: boolean
  /** 0-1: how many words it takes to cut the agent off (see interruptMinWords). */
  interrupt_sensitivity?: number
  max_call_duration?: number
  /** Browser noise suppression on the test microphone. */
  background_noise_reduction?: boolean
}

/** Words the caller must say before they barge in: 1 at full sensitivity,
 *  3 at zero, so a cough or an "mm-hm" doesn't stop the agent mid-sentence.
 *  Mirrors voice_session.py's rule for phone calls. */
const interruptMinWords = (sensitivity: number) => Math.max(1, Math.round(3 - 2 * sensitivity))
const wordCount = (text: string) => text.trim().split(/\s+/).filter(Boolean).length

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

// Messages sent back with each turn; matches the backend's VOICE_HISTORY_TURNS.
// It was 10, which a booking conversation outgrows in a minute, so the agent
// forgot the caller's name and the day it had just offered.
const HISTORY_SENT = 40
const MIN_CHECK_IN_MS = 15000
// After pausing for a sound from the caller, how long to wait for words before
// carrying on; and how many pauses for nothing (noise) before no longer pausing
// on sound alone. Same values as voice_session.py.
const PAUSE_CONFIRM_MS = 1200
const MAX_FALSE_PAUSES = 2

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
  const [mounted,   setMounted]   = useState(false)
  useEffect(() => { setMounted(true) }, [])
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
  // Deepgram sends a turn as several "final" segments and marks only the last
  // one speech_final. Sending just that segment dropped everything said before
  // it, which is how "0300 1234567" arrived as "one two three".
  const finalBufRef       = useRef('')
  const interruptRef      = useRef(true)
  const interruptWordsRef = useRef(2)
  const noiseReductionRef = useRef(true)
  const maxDurRef         = useRef(1800)
  const idleTimeoutRef    = useRef(8000)
  const streamRef         = useRef<MediaStream | null>(null)
  const audioQueueRef     = useRef<{ audio_base64: string; format: string; text: string }[]>([])
  // One reply at a time. Bumped whenever a reply is started or cancelled, so
  // a /respond stream that is no longer the current one cannot speak.
  const respGenRef        = useRef(0)
  // The current /respond stream is still delivering sentences.
  const streamOpenRef     = useRef(false)
  // Whether any of the current reply has been played, and which sentences.
  const replyAudibleRef   = useRef(false)
  const replyHeardRef     = useRef<string[]>([])
  // The caller's words the current reply is answering.
  const lastUserRef       = useRef('')
  // Extra wait before answering a sentence that trails off (set by the relay).
  const holdTimerRef      = useRef<ReturnType<typeof setTimeout> | null>(null)
  // The caller finished speaking while the agent was busy: answered next.
  const heardWaitingRef   = useRef(false)
  // finalBufRef as it stood when the caller last stopped speaking.
  const bufAtPauseRef     = useRef('')
  // The agent's audio is paused because the caller made a sound. Words decide
  // whether it was an interruption (reply dropped) or not (audio resumes).
  const pausedRef         = useRef(false)
  const pauseTimerRef     = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pauseHeardRef     = useRef(false)
  const falsePausesRef    = useRef(0)
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
  // No microphone (denied, absent, or blocked by the browser): the call runs
  // on typed messages only and never tries to start speech recognition.
  const textOnlyRef       = useRef(false)

  useEffect(() => { callStateRef.current = callState }, [callState])

  // Sync agent settings on open
  useEffect(() => {
    if (open && agent) {
      interruptRef.current  = agent.interrupt_enabled ?? true
      interruptWordsRef.current = interruptMinWords(Number(agent.interrupt_sensitivity ?? 0.5))
      noiseReductionRef.current = agent.background_noise_reduction ?? true
      maxDurRef.current     = agent.max_call_duration || 1800
      // The check-in after the caller goes quiet. silence_timeout is the
      // end-of-turn pause (applied server-side by the STT relay), not this.
      idleTimeoutRef.current = MIN_CHECK_IN_MS
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
    // The relay waits longer for an answer to "what's your number?" than to
    // a yes/no question, so it needs the agent's last line.
    if (role === 'agent' && dgWsRef.current?.readyState === WebSocket.OPEN) {
      try { dgWsRef.current.send(JSON.stringify({ type: 'agent_said', text })) } catch {}
    }
  }


  const stopAll = () => {
    isActiveRef.current = false
    if (idleTimerRef.current) { clearTimeout(idleTimerRef.current); idleTimerRef.current = null }
    if (maxTimerRef.current)  { clearTimeout(maxTimerRef.current);  maxTimerRef.current = null }
    if (holdTimerRef.current) { clearTimeout(holdTimerRef.current); holdTimerRef.current = null }
    respGenRef.current++
    streamOpenRef.current = false
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
    if (pauseTimerRef.current) { clearTimeout(pauseTimerRef.current); pauseTimerRef.current = null }
    pausedRef.current = false
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
        replyAudibleRef.current = true
        replyHeardRef.current.push(item.text)
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
    // Not while the reply is still arriving: the gap before its next sentence
    // is the agent mid-reply, not the caller's turn.
    if (myGen === drainGenRef.current && isActiveRef.current && !streamOpenRef.current
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
    // A request still in flight is dropped before the next one starts. Two
    // used to run side by side, and the caller heard both replies.
    if (abortCtrlRef.current) { abortCtrlRef.current.abort(); abortCtrlRef.current = null }
    const gen = ++respGenRef.current
    const stale = () => gen !== respGenRef.current
    setCallState('processing')
    callStateRef.current = 'processing'
    setAgentText('')
    stopAudioNow()
    replyAudibleRef.current = false
    replyHeardRef.current   = []
    streamOpenRef.current   = true
    const token = getAccessToken() || ''
    try {
      const ctrl = new AbortController()
      abortCtrlRef.current = ctrl
      const res = await fetch(`${API_BASE}/api/v1/agents/${agentId}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ message: userText, history: historyRef.current.slice(-HISTORY_SENT) }),
        signal: ctrl.signal,
      })
      if (stale()) return
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
      setCallState('speaking')
      callStateRef.current = 'speaking'
      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      let fullText = '', buffer = '', shouldEnd = false
      while (true) {
        const { done, value } = await reader.read()
        if (stale()) { reader.cancel().catch(() => {}); return }
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
                audioQueueRef.current.push({ audio_base64: ev.audio_base64, format: ev.audio_format || 'mp3', text: ev.text })
                drainQueue()
              }
            } else if (ev.type === 'tool_result') {
              // Kept for later turns: today's date, the free slots offered, a
              // booking that already went through. Sent as a system note, which
              // every backend version accepts.
              historyRef.current.push({ role: 'system', text: `Earlier in this call, the ${ev.name} tool returned: ${ev.result}` })
            } else if (ev.type === 'error') {
              // The caller only ever hears the generic line in `sentence`/
              // `done` — this `reason` is for the workspace owner testing the
              // agent, naming the actual cause (bad key, no model, quota)
              // instead of leaving them to probe the API to find it (M3).
              if (ev.reason) toast.error(publicErrorText(ev.reason, 'The agent couldn’t respond just now. Please try again.'), { duration: 8000 })
            } else if (ev.type === 'done') {
              fullText  = ev.full_text || fullText
              shouldEnd = !!ev.end_call
            }
          } catch {}
        }
      }
      streamOpenRef.current = false
      if (abortCtrlRef.current === ctrl) abortCtrlRef.current = null
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
      if (stale()) return
      streamOpenRef.current = false
      if (e?.name === 'AbortError') return
      toast.error(getErrorMessage(e, 'The agent couldn’t respond just now. Please try again.'))
      if (isActiveRef.current) { setCallState('listening'); callStateRef.current = 'listening'; setTimeout(() => startSpeechRef.current(), 150) }
    }
  }, [drainQueue, stopAudioNow, agentId])

  const agentBusy = () => callStateRef.current === 'speaking' || callStateRef.current === 'processing'

  const sendHeardTurn = () => {
    if (holdTimerRef.current) { clearTimeout(holdTimerRef.current); holdTimerRef.current = null }
    const heard = finalBufRef.current.trim()
    if (!heard) return
    // The agent is mid-reply and was not interrupted: answer this once it
    // has finished, rather than starting a second reply over the first.
    if (agentBusy()) { heardWaitingRef.current = true; return }
    heardWaitingRef.current = false
    finalBufRef.current = ''
    bufAtPauseRef.current = ''
    lastUserRef.current = heard
    callStateRef.current = 'processing'
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current)
    setLiveText('')
    addMessage('user', heard)
    streamRespRef.current(heard)
  }

  /** The caller has stopped speaking. `holdMs` is how much longer to wait
   *  when the sentence trails off; `backchannel` marks an "mm-hm". Both come
   *  from the relay, which applies the same rules as a phone call. */
  const endOfSpeech = (holdMs = 0, backchannel = false) => {
    if (holdTimerRef.current) { clearTimeout(holdTimerRef.current); holdTimerRef.current = null }
    // They finished without saying enough to interrupt.
    resumeReply()
    if (backchannel && agentBusy()) {
      // A listening noise over the agent is not a turn.
      finalBufRef.current = bufAtPauseRef.current
      setLiveText('')
      return
    }
    bufAtPauseRef.current = finalBufRef.current
    if (holdMs > 0 && !agentBusy()) holdTimerRef.current = setTimeout(sendHeardTurn, holdMs)
    else sendHeardTurn()
  }

  /** Stop the reply in flight. With nothing of it heard yet the caller had
   *  only paused, so their words go back to be answered with what they say
   *  next (`merge`). Otherwise it is an interruption, and the conversation
   *  keeps only the part of the reply that was played. */
  const cancelReply = (merge: boolean) => {
    respGenRef.current++
    streamOpenRef.current = false
    if (abortCtrlRef.current) { abortCtrlRef.current.abort(); abortCtrlRef.current = null }
    const heard = replyHeardRef.current.join(' ').trim()
    stopAudioNow()
    setAgentText('')
    const last = historyRef.current[historyRef.current.length - 1]
    if (merge) {
      if (last?.role === 'user' && last.text === lastUserRef.current) {
        historyRef.current.pop()
        setMessages(prev => {
          const i = prev.map(m => m.role === 'user' && m.text === last.text).lastIndexOf(true)
          return i < 0 ? prev : prev.filter((_, j) => j !== i)
        })
        finalBufRef.current = `${last.text} ${finalBufRef.current}`.trim()
      }
    } else if (heard) {
      addMessage('agent', `${heard}…`)
    }
    replyAudibleRef.current = false
    replyHeardRef.current   = []
    setCallState('listening')
    callStateRef.current = 'listening'
  }

  /** Carry on from where the agent paused: the sound was not an interruption. */
  const resumeReply = () => {
    if (pauseTimerRef.current) { clearTimeout(pauseTimerRef.current); pauseTimerRef.current = null }
    if (!pausedRef.current) return
    pausedRef.current = false
    // Nothing was said: noise. A microphone that keeps doing this would make
    // the agent stutter, so stop pausing on it.
    if (!pauseHeardRef.current) falsePausesRef.current++
    currentAudioRef.current?.play().catch(() => {})
  }

  /** The caller's voice has started — before any words are transcribed. Stop
   *  talking at once and listen; waiting for the words left the agent talking
   *  over the caller for a second or two. */
  const pauseReply = () => {
    if (!interruptRef.current || pausedRef.current || falsePausesRef.current >= MAX_FALSE_PAUSES) return
    if (!agentBusy() || !replyAudibleRef.current || !currentAudioRef.current) return
    pausedRef.current = true
    pauseHeardRef.current = false
    currentAudioRef.current.pause()
    pauseTimerRef.current = setTimeout(resumeReply, PAUSE_CONFIRM_MS)
  }

  /** The caller is speaking (interim transcripts included). */
  const onCallerSpeech = (heardSoFar: string, backchannelSoFar = false) => {
    if (holdTimerRef.current) { clearTimeout(holdTimerRef.current); holdTimerRef.current = null }
    heardWaitingRef.current = false
    if (!agentBusy()) return
    if (!replyAudibleRef.current) cancelReply(true)
    else if (interruptRef.current && wordCount(heardSoFar) >= interruptWordsRef.current) cancelReply(false)
    else if (pausedRef.current) {
      pauseHeardRef.current = true
      // "Mm-hm" is listening, not interrupting: carry on. Anything else is
      // words, but not yet enough to count: keep listening.
      if (backchannelSoFar) resumeReply()
      else {
        if (pauseTimerRef.current) clearTimeout(pauseTimerRef.current)
        pauseTimerRef.current = setTimeout(resumeReply, PAUSE_CONFIRM_MS)
      }
    }
    // Heard over the agent but not acted on: "the agent would not stop" is
    // otherwise impossible to tell apart from words that never arrived.
    else console.info('[test call] heard over the agent, not interrupting:', heardSoFar.trim(),
      { words: wordCount(heardSoFar), needed: interruptWordsRef.current, interruptions: interruptRef.current })
  }

  const startDeepgramSession = useCallback(() => {
    if (!isActiveRef.current) return
    if (dgWsRef.current?.readyState === WebSocket.OPEN) {
      setCallState('listening'); callStateRef.current = 'listening'; resetIdleRef.current(); return
    }
    const token  = getAccessToken() || ''
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
          const { text, is_final, speech_final, hold_ms, backchannel } = ev
          // The message that carries speech_final often has an empty
          // transcript (the words already arrived in an earlier "final"
          // segment) — returning early here used to eat the commit signal
          // itself, so the turn hung until the utterance_end fallback ~1-1.5s
          // later, or forever if that never fired either.
          if (text?.trim()) {
            resetIdleRef.current()
            if (is_final) finalBufRef.current = `${finalBufRef.current} ${text}`.trim()
            // Words since the caller last paused: what counts towards
            // interrupting, not a sentence still waiting to be answered.
            onCallerSpeech(`${finalBufRef.current} ${is_final ? '' : text}`.slice(bufAtPauseRef.current.length), !!ev.backchannel_so_far)
            setLiveText(is_final ? finalBufRef.current : `${finalBufRef.current} ${text}`.trim())
          }
          if (speech_final) endOfSpeech(hold_ms, backchannel)
        } else if (ev.type === 'speech_started') {
          pauseReply()
        } else if (ev.type === 'utterance_end') {
          // Deepgram's fallback end-of-turn, for when noise kept speech_final
          // from ever arriving.
          endOfSpeech(ev.hold_ms, ev.backchannel)
        } else if (ev.type === 'error') {
          // Deepgram unusable (bad/missing key). Don't retry it — onclose would loop forever.
          dgAvailRef.current = false
          setSttMode('webspeech')
          toast.error('Voice input isn’t available right now — you can still type to test the agent.')
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
      if ((interim || final).trim()) onCallerSpeech(interim || final)
      if (final.trim() && !agentBusy()) {
        // Includes the words of a reply cancelled before it was heard.
        const said = `${finalBufRef.current} ${final}`.trim()
        finalBufRef.current = ''
        lastUserRef.current = said
        intentStopRef.current = true; callStateRef.current = 'processing'; r.stop(); setLiveText(''); addMessage('user', said); streamRespRef.current(said)
      }
    }
    r.onerror = (e: any) => { if (e.error === 'no-speech' && isActiveRef.current && !intentStopRef.current) startWebSpeechRef.current() }
    r.onend   = () => { if (intentStopRef.current) { intentStopRef.current = false; return }; if (isActiveRef.current && callStateRef.current === 'listening') setTimeout(() => startSpeechRef.current(), 150) }
    try { r.start() } catch {}
  }, [stopAudioNow])

  const startListening = useCallback(() => {
    if (!isActiveRef.current) return
    if (textOnlyRef.current) { setCallState('listening'); callStateRef.current = 'listening'; resetIdleRef.current(); return }
    if (dgWsRef.current?.readyState === WebSocket.OPEN) {
      setCallState('listening'); callStateRef.current = 'listening'; resetIdleRef.current()
      if (heardWaitingRef.current) sendHeardTurn()
    }
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
      replyAudibleRef.current = true
      await audio.play()
      await new Promise<void>(r2 => { audio.onended = () => r2() })
    } catch {}
    if (isActiveRef.current) startListening()
  }

  const startCall = async () => {
    setCallState('starting')
    setMessages([]); setAgentText(''); setLiveText(''); setElapsed(0); setSttMode('none')
    historyRef.current  = []
    finalBufRef.current = ''
    bufAtPauseRef.current   = ''
    heardWaitingRef.current = false
    falsePausesRef.current  = 0
    isActiveRef.current = true
    dgAvailRef.current  = true
    textOnlyRef.current = false
    try {
      const nr = noiseReductionRef.current
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { noiseSuppression: nr, echoCancellation: true, autoGainControl: nr },
      })
      streamRef.current = stream
      startVolumeMonitor(stream)
    } catch {
      // The panel promises "real voice or text input": without a microphone,
      // keep the call going on typed messages instead of refusing to start.
      textOnlyRef.current = true
      dgAvailRef.current  = false
      toast.info('Microphone unavailable — continuing in text-only mode. Type your messages below.')
    }
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
      startListening()
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

  // Portal to <body>: the dashboard layout has transformed/animated ancestors,
  // which turn `position: fixed` into "relative to that ancestor" and clip the
  // drawer's top. Rendering at the body keeps it truly full-viewport.
  if (!mounted) return null

  return createPortal(
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-40 bg-black/30 backdrop-blur-sm transition-opacity duration-300 ${open ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={onClose}
      />

      {/* Sliding panel. While closed it is only moved off screen, so it is made
          inert as well — otherwise its buttons stay in the tab order. */}
      <div
        role="dialog"
        aria-label="Live test call"
        aria-hidden={!open}
        {...(!open ? { inert: '' } : {})}
        className={`touch-targets fixed top-0 right-0 bottom-0 z-50 w-full sm:w-[480px] bg-white shadow-2xl flex flex-col transition-transform duration-300 ease-out ${open ? 'translate-x-0' : 'translate-x-full'}`}>

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
          <button type="button" aria-label="Close test call" onClick={onClose} className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors">
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
                  aria-label="Message to the agent"
                  disabled={callState === 'processing'}
                  className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2 text-sm text-slate-800 placeholder:text-slate-400 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-500/20 disabled:opacity-50 transition-all"
                />
                <button
                  type="submit"
                  aria-label="Send message"
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
    </>,
    document.body,
  )
}
