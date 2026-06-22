'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { toast } from 'sonner'
import { Phone } from 'lucide-react'

interface Agent {
  id: string
  name: string
  llm_provider: string
  llm_model: string
  tts_provider: string
  stt_provider: string
  stt_model: string
  first_message: string
  system_prompt: string
  // Conversation settings
  interrupt_enabled: boolean
  interrupt_sensitivity: number
  silence_timeout: number       // ms
  max_call_duration: number     // seconds
  end_call_phrases: string[]
}

interface Message {
  id: string
  role: 'user' | 'agent'
  text: string
  timestamp: Date
}

type CallState = 'idle' | 'starting' | 'listening' | 'processing' | 'speaking' | 'ended'
type SttMode = 'none' | 'deepgram' | 'webspeech'

declare global {
  interface Window { SpeechRecognition: any; webkitSpeechRecognition: any }
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function TestAgentPage() {
  const params = useParams()
  const agentId = params.id as string

  const [agent, setAgent] = useState<Agent | null>(null)
  const [isLoadingAgent, setIsLoadingAgent] = useState(true)
  const [callState, setCallState] = useState<CallState>('idle')
  const [messages, setMessages] = useState<Message[]>([])
  const [liveText, setLiveText] = useState('')
  const [agentText, setAgentText] = useState('')
  const [volumeLevel, setVolumeLevel] = useState(0)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [textInput, setTextInput] = useState('')
  const [idleTimeout, setIdleTimeout] = useState(8000)
  const [sttMode, setSttMode] = useState<SttMode>('none')

  // ── Core refs ─────────────────────────────────────────────────────────────
  const isActiveRef = useRef(false)
  const isPlayingRef = useRef(false)
  const callStateRef = useRef<CallState>('idle')
  const historyRef = useRef<{ role: string; text: string }[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Agent settings refs (stable for use inside callbacks)
  const interruptEnabledRef = useRef(true)
  const endCallPhrasesRef = useRef<string[]>([])
  const maxCallDurationRef = useRef(1800)

  // Audio
  const streamRef = useRef<MediaStream | null>(null)
  const audioQueueRef = useRef<{ audio_base64: string; format: string; text: string }[]>([])
  const currentAudioRef = useRef<HTMLAudioElement | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const drainResolveRef = useRef<(() => void) | null>(null)
  const drainGenRef = useRef(0)

  // Timers
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const animFrameRef = useRef<number>(0)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const idleTimeoutRef = useRef(8000)
  const maxCallTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Session tracking for call history logging
  const callStartedAtRef = useRef<Date | null>(null)
  const elapsedSecondsRef = useRef(0)

  // Recording
  const recordingCtxRef = useRef<AudioContext | null>(null)
  const recordingDestRef = useRef<MediaStreamAudioDestinationNode | null>(null)
  const callRecorderRef = useRef<MediaRecorder | null>(null)
  const recordingChunksRef = useRef<Blob[]>([])

  // Deepgram STT
  const deepgramWsRef = useRef<WebSocket | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const deepgramAvailableRef = useRef(true)

  // Web Speech API fallback
  const recognitionRef = useRef<any>(null)
  const intentionalStopRef = useRef(false)

  // Stable function refs
  const startSpeechRef = useRef<() => void>(() => {})
  const startWebSpeechRef = useRef<() => void>(() => {})
  const startDeepgramSessionRef = useRef<() => void>(() => {})
  const streamResponseRef = useRef<(text: string) => Promise<void>>(async () => {})
  const resetIdleTimerRef = useRef<() => void>(() => {})
  const endCallRef = useRef<() => void>(() => {})

  useEffect(() => { callStateRef.current = callState }, [callState])
  useEffect(() => { idleTimeoutRef.current = idleTimeout }, [idleTimeout])
  useEffect(() => { elapsedSecondsRef.current = elapsedSeconds }, [elapsedSeconds])

  useEffect(() => {
    fetchAgent()
    return () => stopAll()
  }, [agentId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, agentText])

  const fetchAgent = async () => {
    try {
      const res = await apiClient.get<Agent>(API_ENDPOINTS.AGENT(agentId))
      const a = res.data
      setAgent(a)
      // Wire up agent conversation settings
      interruptEnabledRef.current = a.interrupt_enabled ?? true
      endCallPhrasesRef.current = a.end_call_phrases || []
      maxCallDurationRef.current = a.max_call_duration || 1800
      if (a.silence_timeout) {
        setIdleTimeout(a.silence_timeout)
        idleTimeoutRef.current = a.silence_timeout
      }
    } catch (e) {
      toast.error(getErrorMessage(e))
    } finally {
      setIsLoadingAgent(false)
    }
  }

  const addMessage = (role: 'user' | 'agent', text: string) => {
    setMessages(prev => [...prev, { id: Date.now().toString(), role, text, timestamp: new Date() }])
    historyRef.current.push({ role, text })
  }

  // ── CHECK END-CALL PHRASES ────────────────────────────────────────────────
  const containsEndPhrase = (text: string): boolean => {
    if (!endCallPhrasesRef.current.length) return false
    const lower = text.toLowerCase()
    return endCallPhrasesRef.current.some(p => lower.includes(p.toLowerCase()))
  }

  // ── STOP ALL ──────────────────────────────────────────────────────────────
  const stopAll = () => {
    isActiveRef.current = false
    if (idleTimerRef.current) { clearTimeout(idleTimerRef.current); idleTimerRef.current = null }
    if (maxCallTimerRef.current) { clearTimeout(maxCallTimerRef.current); maxCallTimerRef.current = null }
    if (recognitionRef.current) { try { recognitionRef.current.stop() } catch {} }
    if (deepgramWsRef.current) { try { deepgramWsRef.current.close() } catch {}; deepgramWsRef.current = null }
    if (mediaRecorderRef.current) { try { mediaRecorderRef.current.stop() } catch {}; mediaRecorderRef.current = null }
    if (callRecorderRef.current && callRecorderRef.current.state !== 'inactive') {
      try { callRecorderRef.current.stop() } catch {}
    }
    if (currentAudioRef.current) { currentAudioRef.current.pause(); currentAudioRef.current = null }
    if (abortControllerRef.current) { abortControllerRef.current.abort() }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
    cancelAnimationFrame(animFrameRef.current)
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null }
    if (recordingCtxRef.current) { recordingCtxRef.current.close().catch(() => {}); recordingCtxRef.current = null }
    recordingDestRef.current = null
    if (audioCtxRef.current) { audioCtxRef.current.close().catch(() => {}); audioCtxRef.current = null }
    audioQueueRef.current = []
    isPlayingRef.current = false
  }

  // ── VOLUME VISUALIZER + RECORDING SETUP ──────────────────────────────────
  const startVolumeMonitor = (stream: MediaStream) => {
    // Visualizer context
    const ctx = new AudioContext()
    audioCtxRef.current = ctx
    const src = ctx.createMediaStreamSource(stream)
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 256
    src.connect(analyser)
    analyserRef.current = analyser
    const tick = () => {
      if (!analyserRef.current) return
      const d = new Uint8Array(analyserRef.current.frequencyBinCount)
      analyserRef.current.getByteFrequencyData(d)
      setVolumeLevel(Math.min(100, Math.sqrt(d.reduce((a, b) => a + b * b, 0) / d.length) * 3))
      animFrameRef.current = requestAnimationFrame(tick)
    }
    animFrameRef.current = requestAnimationFrame(tick)

    // Recording context — separate so we can close it independently
    try {
      const recCtx = new AudioContext()
      recordingCtxRef.current = recCtx
      const dest = recCtx.createMediaStreamDestination()
      recordingDestRef.current = dest
      // Route mic into recording
      const micSrc = recCtx.createMediaStreamSource(stream)
      micSrc.connect(dest)
      // Start recorder
      recordingChunksRef.current = []
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : ''
      const recorder = new MediaRecorder(dest.stream, mimeType ? { mimeType } : undefined)
      recorder.ondataavailable = (e) => { if (e.data.size > 0) recordingChunksRef.current.push(e.data) }
      recorder.start(2000) // chunk every 2s
      callRecorderRef.current = recorder
    } catch {}
  }

  // ── IDLE TIMER ────────────────────────────────────────────────────────────
  const resetIdleTimer = useCallback(() => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current)
    if (idleTimeoutRef.current > 0 && isActiveRef.current) {
      idleTimerRef.current = setTimeout(() => {
        if (isActiveRef.current && callStateRef.current === 'listening') {
          streamResponseRef.current(
            '[The user has been silent. Briefly and naturally check in or continue the conversation.]'
          )
        }
      }, idleTimeoutRef.current)
    }
  }, [])
  useEffect(() => { resetIdleTimerRef.current = resetIdleTimer }, [resetIdleTimer])

  // ── FORCE-STOP AUDIO ──────────────────────────────────────────────────────
  const stopAudioNow = useCallback(() => {
    if (drainResolveRef.current) { drainResolveRef.current(); drainResolveRef.current = null }
    drainGenRef.current++
    if (currentAudioRef.current) { currentAudioRef.current.pause(); currentAudioRef.current = null }
    audioQueueRef.current = []
    isPlayingRef.current = false
  }, [])

  // ── PLAY AUDIO QUEUE ──────────────────────────────────────────────────────
  const drainQueue = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return
    isPlayingRef.current = true
    const myGen = ++drainGenRef.current

    while (audioQueueRef.current.length > 0 && isActiveRef.current) {
      const item = audioQueueRef.current.shift()!
      try {
        const mime = item.format === 'mp3' ? 'audio/mpeg' : `audio/${item.format}`
        const bytes = atob(item.audio_base64)
        const buf = new Uint8Array(bytes.length)
        for (let i = 0; i < bytes.length; i++) buf[i] = bytes.charCodeAt(i)
        const url = URL.createObjectURL(new Blob([buf], { type: mime }))
        const audio = new Audio(url)
        // Route TTS audio into recording context
        if (recordingCtxRef.current && recordingDestRef.current) {
          try {
            const ttsNode = recordingCtxRef.current.createMediaElementSource(audio)
            ttsNode.connect(recordingDestRef.current)
            ttsNode.connect(recordingCtxRef.current.destination)
          } catch {}
        }
        currentAudioRef.current = audio
        await new Promise<void>((resolve) => {
          const done = () => { drainResolveRef.current = null; resolve() }
          drainResolveRef.current = done
          audio.onended = done
          audio.onerror = done
          audio.onabort = done
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
      setTimeout(() => {
        if (isActiveRef.current && callStateRef.current === 'listening') {
          startSpeechRef.current()
        }
      }, 150)
    }
  }, [])

  // ── END CALL (exported via ref) ───────────────────────────────────────────
  const endCall = useCallback(() => {
    const startedAt = callStartedAtRef.current
    const duration = elapsedSecondsRef.current
    const history = [...historyRef.current]
    callStartedAtRef.current = null

    // Snapshot recording chunks before stopAll clears context
    const recorder = callRecorderRef.current
    const chunks = [...recordingChunksRef.current]
    const mimeType = recorder?.mimeType || 'audio/webm'

    stopAll()
    setCallState('ended')
    setLiveText('')
    setAgentText('')
    setSttMode('none')

    if (!startedAt) return

    // Wait briefly for recorder to flush final chunk, then log + upload
    setTimeout(async () => {
      const allChunks = [...chunks, ...recordingChunksRef.current]
      recordingChunksRef.current = []
      callRecorderRef.current = null

      try {
        const res = await apiClient.post<{ id: string }>(`/api/v1/agents/${agentId}/log-session`, {
          started_at: startedAt.toISOString(),
          duration_seconds: duration,
          messages: history,
        })

        if (allChunks.length > 0) {
          const blob = new Blob(allChunks, { type: mimeType })
          if (blob.size > 1000) {
            const fd = new FormData()
            fd.append('file', blob, 'recording.webm')
            await apiClient.post(`/api/v1/agents/${agentId}/calls/${res.data.id}/recording`, fd)
          }
        }
      } catch {}
    }, 400)
  }, [agentId])
  useEffect(() => { endCallRef.current = endCall }, [endCall])

  // ── LLM + TTS STREAM ──────────────────────────────────────────────────────
  const streamResponse = useCallback(async (userText: string) => {
    if (!isActiveRef.current) return
    setCallState('processing')
    callStateRef.current = 'processing'
    setAgentText('')
    stopAudioNow()

    const token = localStorage.getItem('access_token') || ''
    try {
      const ctrl = new AbortController()
      abortControllerRef.current = ctrl

      const res = await fetch(`${API_BASE}/api/v1/agents/${agentId}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ message: userText, history: historyRef.current.slice(-10) }),
        signal: ctrl.signal,
      })

      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
      setCallState('speaking')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let fullText = ''
      let buffer = ''
      let shouldEndCall = false

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
            const event = JSON.parse(raw)
            if (event.type === 'sentence') {
              fullText += (fullText ? ' ' : '') + event.text
              setAgentText(fullText)
              if (event.audio_base64) {
                audioQueueRef.current.push({ audio_base64: event.audio_base64, format: event.audio_format || 'mp3', text: event.text })
                drainQueue()
              }
            } else if (event.type === 'done') {
              fullText = event.full_text || fullText
              shouldEndCall = !!event.end_call
            } else if (event.type === 'error') {
              toast.error(event.message)
            }
          } catch {}
        }
      }

      if (fullText.trim()) addMessage('agent', fullText.trim())
      setAgentText('')

      // End call if agent said a goodbye phrase
      if (shouldEndCall) {
        // Wait for audio to finish, then end call
        const checkEnd = setInterval(() => {
          if (!isPlayingRef.current && audioQueueRef.current.length === 0) {
            clearInterval(checkEnd)
            setTimeout(() => endCallRef.current(), 800)
          }
        }, 200)
        setTimeout(() => { clearInterval(checkEnd); endCallRef.current() }, 8000)
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
      if (isActiveRef.current) {
        setCallState('listening')
        callStateRef.current = 'listening'
        setTimeout(() => startSpeechRef.current(), 150)
      }
    }
  }, [drainQueue, stopAudioNow, agentId])

  // ── DEEPGRAM STT (Primary) ─────────────────────────────────────────────────
  const startDeepgramSession = useCallback(() => {
    if (!isActiveRef.current) return

    // Session already open — re-enter listening state
    if (deepgramWsRef.current?.readyState === WebSocket.OPEN) {
      setCallState('listening')
      callStateRef.current = 'listening'
      resetIdleTimerRef.current()
      return
    }

    const token = localStorage.getItem('access_token') || ''
    const wsBase = API_BASE.replace(/^http(s?)/, (_, s) => `ws${s}`)
    const wsUrl = `${wsBase}/api/v1/agents/${agentId}/stt?token=${encodeURIComponent(token)}`

    let ws: WebSocket
    try { ws = new WebSocket(wsUrl) } catch {
      deepgramAvailableRef.current = false
      setSttMode('webspeech')
      startWebSpeechRef.current()
      return
    }
    deepgramWsRef.current = ws

    ws.onmessage = (e) => {
      if (!isActiveRef.current) return
      try {
        const event = JSON.parse(e.data)

        if (event.type === 'ready') {
          if (!streamRef.current) return
          const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg'].find(
            m => MediaRecorder.isTypeSupported(m)
          ) || ''
          try {
            const recorder = new MediaRecorder(streamRef.current, mimeType ? { mimeType } : {})
            mediaRecorderRef.current = recorder
            recorder.ondataavailable = (ev) => {
              if (ev.data.size > 0 && ws.readyState === WebSocket.OPEN) ws.send(ev.data)
            }
            recorder.start(100)
            setSttMode('deepgram')
            setCallState('listening')
            callStateRef.current = 'listening'
            resetIdleTimerRef.current()
          } catch {
            ws.close()
            deepgramAvailableRef.current = false
            setSttMode('webspeech')
            startWebSpeechRef.current()
          }

        } else if (event.type === 'transcript') {
          const { text, is_final, speech_final } = event
          if (!text?.trim()) return

          // Any speech → reset idle timer
          resetIdleTimerRef.current()
          setLiveText(text)

          // Barge-in: user speaks while agent is processing or speaking
          const agentActive = callStateRef.current === 'speaking' || callStateRef.current === 'processing'
          if (agentActive && (currentAudioRef.current || isPlayingRef.current || abortControllerRef.current)) {
            if (interruptEnabledRef.current) {
              stopAudioNow()
              if (abortControllerRef.current) { abortControllerRef.current.abort(); abortControllerRef.current = null }
              setCallState('listening')
              callStateRef.current = 'listening'
            }
          }

          // Turn complete (Deepgram detected end of speech)
          if (speech_final) {
            if (callStateRef.current === 'processing') return  // already handling a turn
            callStateRef.current = 'processing'
            if (idleTimerRef.current) clearTimeout(idleTimerRef.current)
            setLiveText('')

            // User said goodbye → end call after agent responds
            const userEnding = containsEndPhrase(text.trim())
            addMessage('user', text.trim())

            if (userEnding && !endCallPhrasesRef.current.length) {
              // No configured phrases but user said bye — just let agent respond normally
            }
            streamResponseRef.current(text.trim())
          }

        } else if (event.type === 'error') {
          console.warn('Deepgram error:', event.message)
          ws.close()
        }
      } catch {}
    }

    ws.onerror = () => {
      deepgramWsRef.current = null
      deepgramAvailableRef.current = false
      setSttMode('webspeech')
      if (isActiveRef.current) startWebSpeechRef.current()
    }

    ws.onclose = () => {
      deepgramWsRef.current = null
      if (mediaRecorderRef.current) {
        try { mediaRecorderRef.current.stop() } catch {}
        mediaRecorderRef.current = null
      }
      if (isActiveRef.current && callStateRef.current !== 'ended' && callStateRef.current !== 'idle') {
        if (deepgramAvailableRef.current) {
          setTimeout(() => { if (isActiveRef.current) startDeepgramSessionRef.current() }, 1000)
        } else {
          startWebSpeechRef.current()
        }
      }
    }
  }, [agentId, stopAudioNow])

  // ── WEB SPEECH API (Fallback) ──────────────────────────────────────────────
  const startWebSpeech = useCallback(() => {
    if (!isActiveRef.current) return
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) { toast.error('Speech recognition not supported. Use Chrome or Edge.'); return }

    const recognition = new SpeechRecognition()
    recognitionRef.current = recognition
    recognition.continuous = false
    recognition.interimResults = true
    recognition.lang = 'en-US'
    recognition.maxAlternatives = 1

    recognition.onstart = () => { setCallState('listening'); resetIdleTimerRef.current() }

    recognition.onresult = (e: any) => {
      let interim = '', final = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript
        if (e.results[i].isFinal) final += t
        else interim += t
      }
      setLiveText(interim || final)

      if ((interim || final).trim()) resetIdleTimerRef.current()

      // Barge-in during agent response
      const agentActive = callStateRef.current === 'speaking' || callStateRef.current === 'processing'
      if (agentActive && interruptEnabledRef.current && (interim || final).trim()) {
        stopAudioNow()
        if (abortControllerRef.current) { abortControllerRef.current.abort(); abortControllerRef.current = null }
        setCallState('listening')
        callStateRef.current = 'listening'
      }

      if (final.trim()) {
        intentionalStopRef.current = true
        callStateRef.current = 'processing'
        recognition.stop()
        setLiveText('')
        addMessage('user', final.trim())
        streamResponseRef.current(final.trim())
      }
    }

    recognition.onerror = (e: any) => {
      if (e.error === 'no-speech' && isActiveRef.current && !intentionalStopRef.current) {
        startWebSpeechRef.current()
      } else if (e.error !== 'aborted') {
        console.error('Speech error:', e.error)
      }
    }

    recognition.onend = () => {
      if (intentionalStopRef.current) { intentionalStopRef.current = false; return }
      if (isActiveRef.current && callStateRef.current === 'listening') {
        setTimeout(() => startSpeechRef.current(), 150)
      }
    }

    try { recognition.start() } catch {}
  }, [stopAudioNow])

  // ── UNIFIED START LISTENING ────────────────────────────────────────────────
  const startListening = useCallback(() => {
    if (!isActiveRef.current) return
    if (deepgramWsRef.current?.readyState === WebSocket.OPEN) {
      setCallState('listening')
      callStateRef.current = 'listening'
      resetIdleTimerRef.current()
    } else if (deepgramAvailableRef.current) {
      startDeepgramSessionRef.current()
    } else {
      startWebSpeechRef.current()
    }
  }, [])

  // Sync all stable refs
  useEffect(() => { startSpeechRef.current = startListening }, [startListening])
  useEffect(() => { startWebSpeechRef.current = startWebSpeech }, [startWebSpeech])
  useEffect(() => { startDeepgramSessionRef.current = startDeepgramSession }, [startDeepgramSession])
  useEffect(() => { streamResponseRef.current = streamResponse }, [streamResponse])

  // ── START CALL ────────────────────────────────────────────────────────────
  const startCall = async () => {
    setCallState('starting')
    setMessages([])
    setAgentText('')
    setLiveText('')
    setElapsedSeconds(0)
    setSttMode('none')
    historyRef.current = []
    isActiveRef.current = true
    deepgramAvailableRef.current = true
    callStartedAtRef.current = new Date()
    elapsedSecondsRef.current = 0

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      startVolumeMonitor(stream)
    } catch {
      toast.error('Microphone access denied.')
      setCallState('idle')
      return
    }

    timerRef.current = setInterval(() => setElapsedSeconds(s => s + 1), 1000)

    // Max call duration auto-end
    const maxSec = maxCallDurationRef.current
    if (maxSec > 0) {
      maxCallTimerRef.current = setTimeout(() => {
        if (isActiveRef.current) {
          toast.info('Max call duration reached.')
          endCallRef.current()
        }
      }, maxSec * 1000)
    }

    if (agent?.first_message) {
      setCallState('speaking')
      addMessage('agent', agent.first_message)
      await streamGreeting(agent.first_message)
    } else {
      startDeepgramSession()
    }
  }

  const streamGreeting = async (text: string) => {
    try {
      const res = await apiClient.post<{ audio_base64: string; audio_format: string }>(
        `${API_ENDPOINTS.AGENT(agentId)}/speak`, { text }
      )
      const mime = res.data.audio_format === 'mp3' ? 'audio/mpeg' : `audio/${res.data.audio_format}`
      const bytes = atob(res.data.audio_base64)
      const buf = new Uint8Array(bytes.length)
      for (let i = 0; i < bytes.length; i++) buf[i] = bytes.charCodeAt(i)
      const url = URL.createObjectURL(new Blob([buf], { type: mime }))
      const audio = new Audio(url)
      // Route greeting into recording context
      if (recordingCtxRef.current && recordingDestRef.current) {
        try {
          const ttsNode = recordingCtxRef.current.createMediaElementSource(audio)
          ttsNode.connect(recordingDestRef.current)
          ttsNode.connect(recordingCtxRef.current.destination)
        } catch {}
      }
      currentAudioRef.current = audio
      await audio.play()
      await new Promise<void>(r => { audio.onended = () => r() })
    } catch {}
    if (isActiveRef.current) startDeepgramSession()
  }

  // ── TEXT SEND ─────────────────────────────────────────────────────────────
  const sendTextMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    const text = textInput.trim()
    if (!text || callState === 'processing' || callState === 'speaking') return
    setTextInput('')
    stopAudioNow()
    addMessage('user', text)
    await streamResponse(text)
  }

  const formatTime = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

  const isLive = callState !== 'idle' && callState !== 'ended'

  const stateInfo: Record<CallState, { label: string; bar: string }> = {
    idle:       { label: 'Ready to start', bar: '' },
    starting:   { label: 'Connecting...', bar: 'bg-yellow-500/10 border-b border-yellow-500/20' },
    listening:  { label: 'Listening...', bar: 'bg-green-500/10 border-b border-green-500/20' },
    processing: { label: 'Thinking...', bar: 'bg-blue-500/10 border-b border-blue-500/20' },
    speaking:   { label: 'Speaking...', bar: 'bg-purple-500/10 border-b border-purple-500/20' },
    ended:      { label: 'Call ended', bar: '' },
  }

  if (isLoadingAgent) return (
    <div className="flex h-[400px] items-center justify-center text-muted-foreground">Loading...</div>
  )

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Live Call: {agent?.name}</h1>
          <p className="text-sm text-muted-foreground">
            {agent?.llm_model} · {agent?.tts_provider} Flash ·{' '}
            {sttMode === 'deepgram' ? 'Deepgram Nova-3' : sttMode === 'webspeech' ? 'Web Speech (fallback)' : 'STT pending'}
          </p>
        </div>
        <div className="flex gap-2">
          <Link href={`/dashboard/agents/${agentId}/edit`}><Button variant="outline" size="sm">Edit</Button></Link>
          <Link href={`/dashboard/agents/${agentId}`}><Button variant="outline" size="sm">← Back</Button></Link>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* ── Main call panel ── */}
        <div className="lg:col-span-2 rounded-xl border bg-card flex flex-col overflow-hidden" style={{ height: 600 }}>

          {/* Status bar */}
          <div className={`flex items-center justify-between px-4 py-3 ${stateInfo[callState].bar || 'bg-muted/50'}`}>
            <div className="flex items-center gap-3">
              {isLive && (
                <div className="flex items-end gap-0.5 h-5">
                  {[0.3, 0.7, 1, 0.7, 0.4].map((h, i) => (
                    <div key={i}
                      className={`w-1 rounded-full transition-all duration-100 ${
                        callState === 'listening' ? 'bg-green-500'
                        : callState === 'speaking' ? 'bg-purple-500'
                        : 'bg-primary/40'}`}
                      style={{ height: `${Math.max(3, (volumeLevel / 100) * h * 20)}px` }}
                    />
                  ))}
                </div>
              )}
              <span className="text-sm font-medium">{stateInfo[callState].label}</span>
              {sttMode === 'deepgram' && isLive && (
                <span className="text-xs text-green-700 bg-green-500/15 px-1.5 py-0.5 rounded font-medium">Deepgram</span>
              )}
            </div>
            {isLive && (
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-muted-foreground">{formatTime(elapsedSeconds)}</span>
                <span className="text-xs font-medium text-green-600 bg-green-500/10 px-2 py-0.5 rounded-full">● LIVE</span>
              </div>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.length === 0 && !isLive && (
              <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground gap-3">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                  <Phone className="h-8 w-8 text-muted-foreground/50" />
                </div>
                <p className="font-medium text-lg">Live Voice Agent</p>
                <p className="text-sm max-w-xs">
                  Real-time Deepgram STT · ElevenLabs TTS · Barge-in · Auto end-call detection.
                </p>
              </div>
            )}

            {messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 ${
                  msg.role === 'user'
                    ? 'bg-primary text-primary-foreground rounded-br-none'
                    : 'bg-muted rounded-bl-none'
                }`}>
                  {msg.role === 'agent' && (
                    <p className="text-xs font-semibold text-muted-foreground mb-1">{agent?.name}</p>
                  )}
                  <p className="text-sm leading-relaxed">{msg.text}</p>
                  <p className="text-xs opacity-50 mt-1">{msg.timestamp.toLocaleTimeString()}</p>
                </div>
              </div>
            ))}

            {liveText && (
              <div className="flex justify-end">
                <div className="max-w-[80%] rounded-2xl px-4 py-2.5 bg-primary/20 rounded-br-none border border-primary/30">
                  <p className="text-sm italic text-primary/80">{liveText}</p>
                </div>
              </div>
            )}

            {agentText && (
              <div className="flex justify-start">
                <div className="max-w-[80%] rounded-2xl px-4 py-2.5 bg-muted rounded-bl-none">
                  <p className="text-xs font-semibold text-muted-foreground mb-1">{agent?.name}</p>
                  <p className="text-sm leading-relaxed">{agentText}</p>
                  <div className="flex gap-1 mt-1.5">
                    {[0, 150, 300].map(d => (
                      <div key={d} className="w-1.5 h-1.5 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: `${d}ms` }} />
                    ))}
                  </div>
                </div>
              </div>
            )}

            {callState === 'processing' && !agentText && (
              <div className="flex justify-start">
                <div className="bg-muted rounded-2xl rounded-bl-none px-4 py-3">
                  <div className="flex gap-1">
                    {[0, 150, 300].map(d => (
                      <div key={d} className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" style={{ animationDelay: `${d}ms` }} />
                    ))}
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Controls */}
          <div className="border-t p-3">
            {!isLive ? (
              <Button className="w-full" size="lg" onClick={startCall}>Start Live Call</Button>
            ) : (
              <div className="space-y-2">
                <form onSubmit={sendTextMessage} className="flex gap-2">
                  <input
                    value={textInput}
                    onChange={e => setTextInput(e.target.value)}
                    placeholder={callState === 'listening' ? 'Just speak, or type here...' : 'Type a message...'}
                    disabled={callState === 'processing'}
                    className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
                  />
                  <Button type="submit" size="sm" disabled={!textInput.trim() || callState === 'processing'}>Send</Button>
                </form>
                <Button onClick={endCall} variant="destructive" className="w-full" size="sm">End Call</Button>
              </div>
            )}
          </div>
        </div>

        {/* ── Right panel ── */}
        <div className="space-y-4">
          <div className="rounded-xl border bg-card p-4 space-y-3">
            <h3 className="font-semibold">Agent Config</h3>
            <div className="space-y-2 text-sm">
              {[
                { label: 'LLM', value: agent?.llm_model },
                { label: 'TTS', value: 'ElevenLabs' },
                { label: 'STT', value: sttMode === 'deepgram' ? 'Deepgram Nova-3' : sttMode === 'webspeech' ? 'Web Speech' : 'Auto' },
                { label: 'Barge-in', value: agent?.interrupt_enabled ? `On (${agent.interrupt_sensitivity})` : 'Off' },
                { label: 'Max duration', value: agent ? `${Math.floor(agent.max_call_duration / 60)}m` : '—' },
              ].map(({ label, value }) => (
                <div key={label} className="flex justify-between">
                  <span className="text-muted-foreground">{label}</span>
                  <span className="font-mono text-xs bg-muted px-2 py-0.5 rounded">{value}</span>
                </div>
              ))}
              {agent?.end_call_phrases?.length ? (
                <div className="flex justify-between items-start">
                  <span className="text-muted-foreground">End phrases</span>
                  <span className="font-mono text-xs bg-muted px-2 py-0.5 rounded max-w-[60%] truncate">
                    {agent.end_call_phrases.join(', ')}
                  </span>
                </div>
              ) : null}
            </div>
          </div>

          <div className="rounded-xl border bg-card p-4 space-y-2 text-sm">
            <h3 className="font-semibold">Call Stats</h3>
            <div className="flex justify-between"><span className="text-muted-foreground">Duration</span><span className="font-mono">{formatTime(elapsedSeconds)}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Your turns</span><span>{messages.filter(m => m.role === 'user').length}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Agent turns</span><span>{messages.filter(m => m.role === 'agent').length}</span></div>
          </div>

          <div className="rounded-xl border bg-card p-4 space-y-1.5 text-sm">
            <h3 className="font-semibold">Pipeline</h3>
            <p className="text-muted-foreground">Deepgram Nova-3 (~150ms)</p>
            <p className="text-muted-foreground">LLM sentence streaming</p>
            <p className="text-muted-foreground">ElevenLabs TTS (~75ms)</p>
            <p className="text-muted-foreground">Barge-in during processing</p>
            <p className="text-muted-foreground">Auto end-call on phrases</p>
          </div>

          {/* Idle Timeout */}
          <div className="rounded-xl border bg-card p-4 space-y-3">
            <h3 className="font-semibold text-sm">Idle Timeout <span className="text-muted-foreground font-normal">(from silence_timeout)</span></h3>
            <input
              type="range" min={0} max={30000} step={500} value={idleTimeout}
              onChange={e => setIdleTimeout(Number(e.target.value))}
              className="w-full accent-primary"
            />
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Off</span>
              <span className="font-mono font-medium">
                {idleTimeout === 0 ? 'Off' : idleTimeout < 1000 ? `${idleTimeout}ms` : `${(idleTimeout / 1000).toFixed(1)}s`}
              </span>
              <span className="text-muted-foreground">30s</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
