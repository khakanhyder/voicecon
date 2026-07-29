'use client'

import { useEffect, useRef, useState } from 'react'
import {
  FileText, Cpu, Volume2, Mic, MessageSquare, Settings, Wrench, BookOpen, ChevronUp, ChevronDown, Check,
} from 'lucide-react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'

// ── LLM Providers & Models ────────────────────────────────────────────────────

export const LLM_PROVIDERS = [
  { value: 'openai',      label: 'OpenAI',         badge: 'Popular' },
  { value: 'anthropic',   label: 'Anthropic',      badge: 'Claude' },
  { value: 'google',      label: 'Google Gemini',  badge: '' },
  { value: 'groq',        label: 'Groq',           badge: 'Ultra-fast' },
  { value: 'xai',         label: 'xAI (Grok)',     badge: 'Real-time' },
  { value: 'mistral',     label: 'Mistral',        badge: 'Open-source' },
  { value: 'together',    label: 'Together AI',    badge: 'OSS Hosting' },
  { value: 'openrouter',  label: 'OpenRouter',     badge: 'Multi-model' },
  { value: 'perplexity',  label: 'Perplexity AI',  badge: '' },
  { value: 'azure_openai',label: 'Azure OpenAI',   badge: 'Enterprise' },
  { value: 'cerebras',    label: 'Cerebras',       badge: 'High perf' },
  { value: 'deepinfra',   label: 'DeepInfra',      badge: '' },
  { value: 'anyscale',    label: 'Anyscale',       badge: '' },
  { value: 'inflection',  label: 'Inflection AI',  badge: '' },
  { value: 'custom',      label: 'Custom LLM',     badge: 'BYOM' },
]

export const LLM_MODELS: Record<string, { label: string; value: string; latency: string }[]> = {
  openai: [
    // ── GPT-5.5 series (latest flagship, Apr 2026) ──
    { value: 'gpt-5.5',             label: 'GPT-5.5',            latency: '~600ms · Latest flagship' },
    { value: 'gpt-5.5-pro',         label: 'GPT-5.5 Pro',        latency: '~900ms · Most powerful' },
    // ── GPT-5.4 series (Mar 2026) ──
    { value: 'gpt-5.4-nano',        label: 'GPT-5.4 Nano',       latency: '~180ms · Fastest GPT-5 · Best for voice' },
    { value: 'gpt-5.4-mini',        label: 'GPT-5.4 Mini',       latency: '~320ms · Fast GPT-5' },
    { value: 'gpt-5.4',             label: 'GPT-5.4',            latency: '~700ms · High quality' },
    { value: 'gpt-5.4-pro',         label: 'GPT-5.4 Pro',        latency: '~900ms · Premium' },
    // ── GPT-5.2 series (Dec 2025) ──
    { value: 'gpt-5.2',             label: 'GPT-5.2',            latency: '~650ms · Balanced' },
    { value: 'gpt-5.2-pro',         label: 'GPT-5.2 Pro',        latency: '~900ms · Premium' },
    // ── GPT-5.1 series (Nov 2025) ──
    { value: 'gpt-5.1',             label: 'GPT-5.1',            latency: '~600ms · Reliable' },
    // ── GPT-5 base (Aug 2025) ──
    { value: 'gpt-5',               label: 'GPT-5',              latency: '~700ms · Original GPT-5' },
    { value: 'gpt-5-mini',          label: 'GPT-5 Mini',         latency: '~350ms · Fast GPT-5' },
    { value: 'gpt-5-nano',          label: 'GPT-5 Nano',         latency: '~200ms · Lightweight GPT-5' },
    { value: 'gpt-5-pro',           label: 'GPT-5 Pro',          latency: '~950ms · Premium GPT-5' },
    // ── GPT-4.1 series (Apr 2025) ──
    { value: 'gpt-4.1-nano',        label: 'GPT-4.1 Nano',       latency: '~150ms · Ultra-fast' },
    { value: 'gpt-4.1-mini',        label: 'GPT-4.1 Mini',       latency: '~300ms · Fast' },
    { value: 'gpt-4.1',             label: 'GPT-4.1',            latency: '~700ms · 1M ctx' },
    // ── GPT-4o series ──
    { value: 'gpt-4o-mini',         label: 'GPT-4o Mini',        latency: '~350ms · Reliable' },
    { value: 'gpt-4o',              label: 'GPT-4o',             latency: '~800ms · Multimodal' },
    // ── Reasoning models (not ideal for voice due to latency) ──
    { value: 'o4-mini',             label: 'o4-mini',            latency: '~3s    · Fast reasoning' },
    { value: 'o3',                  label: 'o3',                 latency: '~8s    · Advanced reasoning' },
    { value: 'o3-mini',             label: 'o3-mini',            latency: '~4s    · Efficient reasoning' },
    { value: 'o1-pro',              label: 'o1-pro',             latency: '~15s   · Deep reasoning' },
    { value: 'o1',                  label: 'o1',                 latency: '~10s   · Reasoning' },
    { value: 'o1-mini',             label: 'o1-mini',            latency: '~4s    · Reasoning' },
    // ── Legacy ──
    { value: 'gpt-4',               label: 'GPT-4',              latency: '~1.5s  · Legacy' },
    { value: 'gpt-4-turbo',         label: 'GPT-4 Turbo',        latency: '~1.2s  · Legacy' },
    { value: 'gpt-4-turbo-preview', label: 'GPT-4 Turbo Preview',latency: '~1.2s  · Legacy' },
    { value: 'gpt-3.5-turbo',       label: 'GPT-3.5 Turbo',      latency: '~200ms · Legacy' },
    { value: 'gpt-3.5-turbo-16k',   label: 'GPT-3.5 Turbo 16k', latency: '~250ms · Legacy' },
  ],
  anthropic: [
    { value: 'claude-haiku-4-5-20251001',  label: 'Claude Haiku 4.5',    latency: '~400ms · Best for voice' },
    { value: 'claude-sonnet-4-6',          label: 'Claude Sonnet 4.6',   latency: '~800ms · Balanced' },
    { value: 'claude-opus-4-6',            label: 'Claude Opus 4.6',     latency: '~2s    · Most powerful' },
    { value: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet',   latency: '~900ms · Proven' },
    { value: 'claude-3-5-haiku-20241022',  label: 'Claude 3.5 Haiku',    latency: '~350ms · Fast' },
    { value: 'claude-3-haiku-20240307',    label: 'Claude 3 Haiku',      latency: '~350ms · Economic' },
  ],
  google: [
    // Gemini 2.5 series — latest (2025)
    { value: 'gemini-2.5-flash-lite',    label: 'Gemini 2.5 Flash-Lite',  latency: '~200ms · Fastest · Best for voice' },
    { value: 'gemini-2.5-flash',         label: 'Gemini 2.5 Flash',      latency: '~350ms · Fast + smart' },
    { value: 'gemini-2.5-pro',           label: 'Gemini 2.5 Pro',        latency: '~900ms · Most capable' },
    // Gemini 2.0 series
    { value: 'gemini-2.0-flash',         label: 'Gemini 2.0 Flash',      latency: '~300ms · Reliable' },
    { value: 'gemini-2.0-flash-thinking', label: 'Gemini 2.0 Flash Thinking', latency: '~600ms · Reasoning' },
    // Legacy
    { value: 'gemini-1.5-flash',         label: 'Gemini 1.5 Flash',      latency: '~400ms · Legacy' },
    { value: 'gemini-1.5-pro',           label: 'Gemini 1.5 Pro',        latency: '~1s    · Legacy' },
  ],
  groq: [
    { value: 'llama-4-scout-17b-16e-instruct',     label: 'Llama 4 Scout 17B',    latency: '~150ms · Fastest' },
    { value: 'llama-4-maverick-17b-128e-instruct', label: 'Llama 4 Maverick 17B', latency: '~200ms · Best balance' },
    { value: 'llama3-70b-8192',                    label: 'Llama 3 70B',          latency: '~300ms · High quality' },
    { value: 'llama3-8b-8192',                     label: 'Llama 3 8B',           latency: '~100ms · Ultra-fast' },
    { value: 'mixtral-8x7b-32768',                 label: 'Mixtral 8x7B',         latency: '~250ms · Good for chat' },
    { value: 'gemma2-9b-it',                       label: 'Gemma 2 9B',           latency: '~150ms · Lightweight' },
  ],
  xai: [
    { value: 'grok-2-1212',   label: 'Grok 2',        latency: '~800ms · Real-time knowledge' },
    { value: 'grok-2-mini',   label: 'Grok 2 Mini',   latency: '~500ms · Balanced' },
    { value: 'grok-beta',     label: 'Grok Beta',     latency: '~900ms · Experimental' },
  ],
  mistral: [
    { value: 'mistral-large-latest',  label: 'Mistral Large',   latency: '~900ms · Most capable' },
    { value: 'mistral-small-latest',  label: 'Mistral Small',   latency: '~400ms · Efficient' },
    { value: 'mistral-7b-instruct',   label: 'Mistral 7B',      latency: '~300ms · Fast open-source' },
    { value: 'mixtral-8x7b-instruct', label: 'Mixtral 8x7B',   latency: '~500ms · Mix of experts' },
    { value: 'codestral-latest',      label: 'Codestral',       latency: '~600ms · Code-optimized' },
  ],
  together: [
    { value: 'meta-llama/Llama-3-70b-chat-hf',  label: 'Llama 3 70B (Together)',  latency: '~400ms' },
    { value: 'meta-llama/Llama-3-8b-chat-hf',   label: 'Llama 3 8B (Together)',   latency: '~200ms' },
    { value: 'mistralai/Mixtral-8x7B-Instruct', label: 'Mixtral 8x7B (Together)', latency: '~350ms' },
    { value: 'Qwen/Qwen2-72B-Instruct',         label: 'Qwen 2 72B',              latency: '~500ms' },
  ],
  openrouter: [
    { value: 'openai/gpt-4o',               label: 'GPT-4o via OpenRouter',       latency: '~700ms' },
    { value: 'anthropic/claude-3.5-sonnet', label: 'Claude 3.5 Sonnet via OR',    latency: '~900ms' },
    { value: 'google/gemini-flash-1.5',     label: 'Gemini Flash 1.5 via OR',     latency: '~400ms' },
    { value: 'meta-llama/llama-3-70b',      label: 'Llama 3 70B via OR',          latency: '~400ms' },
  ],
  perplexity: [
    { value: 'llama-3.1-sonar-large-128k-online', label: 'Sonar Large Online',  latency: '~800ms · Web knowledge' },
    { value: 'llama-3.1-sonar-small-128k-online', label: 'Sonar Small Online',  latency: '~500ms · Fast + web' },
    { value: 'llama-3.1-sonar-large-128k-chat',   label: 'Sonar Large Chat',    latency: '~700ms' },
  ],
  azure_openai: [
    { value: 'gpt-4o',         label: 'GPT-4o (Azure)',       latency: '~700ms · Enterprise' },
    { value: 'gpt-4-turbo',    label: 'GPT-4 Turbo (Azure)',  latency: '~1.2s  · High quality' },
    { value: 'gpt-35-turbo',   label: 'GPT-3.5 Turbo (Azure)',latency: '~200ms · Fast' },
  ],
  cerebras: [
    { value: 'llama3.1-70b',  label: 'Llama 3.1 70B (Cerebras)', latency: '~100ms · Ultra-fast' },
    { value: 'llama3.1-8b',   label: 'Llama 3.1 8B (Cerebras)',  latency: '~50ms  · Fastest' },
  ],
  deepinfra: [
    { value: 'meta-llama/Meta-Llama-3-70B-Instruct', label: 'Llama 3 70B',   latency: '~400ms' },
    { value: 'mistralai/Mistral-7B-Instruct-v0.2',   label: 'Mistral 7B',    latency: '~250ms' },
    { value: 'Qwen/Qwen2-72B-Instruct',              label: 'Qwen 2 72B',    latency: '~450ms' },
  ],
  anyscale: [
    { value: 'meta-llama/Llama-3-70b-chat-hf',  label: 'Llama 3 70B (Anyscale)', latency: '~500ms' },
    { value: 'mistralai/Mistral-7B-Instruct-v0.1', label: 'Mistral 7B (Anyscale)', latency: '~300ms' },
  ],
  inflection: [
    { value: 'inflection_3_pi',       label: 'Inflection 3 Pi',       latency: '~700ms · Empathetic' },
    { value: 'inflection_3_productivity', label: 'Inflection 3 Productivity', latency: '~600ms · Task-focused' },
  ],
  custom: [
    { value: 'custom', label: 'Custom endpoint', latency: 'Depends on your server' },
  ],
}

// ── TTS Providers & Voices ────────────────────────────────────────────────────

export const TTS_PROVIDERS = [
  { value: 'elevenlabs',  label: 'ElevenLabs',  badge: 'Popular · Voice cloning' },
  { value: 'cartesia',    label: 'Cartesia',    badge: 'Ultra-low latency' },
  { value: 'deepgram',    label: 'Deepgram Aura', badge: 'Real-time' },
  { value: 'openai',      label: 'OpenAI TTS',  badge: 'Reliable' },
  { value: 'google',      label: 'Google TTS',  badge: 'Multilingual' },
  { value: 'azure',       label: 'Azure Speech', badge: 'Enterprise' },
  { value: 'playht',      label: 'PlayHT',      badge: 'Voice cloning' },
  { value: 'rimeai',      label: 'RimeAI',      badge: 'Emotional control' },
  { value: 'lmnt',        label: 'LMNT',        badge: 'Real-time optimized' },
  { value: 'neuphonic',   label: 'Neuphonic',   badge: 'Natural AI' },
  { value: 'smallestai',  label: 'SmallestAI',  badge: 'Ultra-fast' },
  { value: 'hume',        label: 'Hume',        badge: 'Emotionally intelligent' },
  { value: 'minimax',     label: 'MiniMax',     badge: 'Multilingual' },
  { value: 'inworld',     label: 'Inworld',     badge: 'Character AI' },
]

export const TTS_VOICES: Record<string, { value: string; label: string; gender: string; style: string }[]> = {
  elevenlabs: [
    { value: '21m00Tcm4TlvDq8ikWAM', label: 'Rachel',  gender: 'Female', style: 'Calm' },
    { value: 'AZnzlk1XvdvUeBnXmlld', label: 'Domi',    gender: 'Female', style: 'Strong' },
    { value: 'EXAVITQu4vr4xnSDxMaL', label: 'Bella',   gender: 'Female', style: 'Soft' },
    { value: 'ErXwobaYiN019PkySvjV',  label: 'Antoni',  gender: 'Male',   style: 'Well-rounded' },
    { value: 'MF3mGyEYCl7XYWbV9V6O', label: 'Elli',    gender: 'Female', style: 'Emotional' },
    { value: 'TxGEqnHWrfWFTfGW9XjX', label: 'Josh',    gender: 'Male',   style: 'Deep' },
    { value: 'VR6AewLTigWG4xSOukaG', label: 'Arnold',  gender: 'Male',   style: 'Crisp' },
    { value: 'pNInz6obpgDQGcFmaJgB', label: 'Adam',    gender: 'Male',   style: 'Narration' },
    { value: 'yoZ06aMxZJJ28mfd3POQ', label: 'Sam',     gender: 'Male',   style: 'Raspy' },
    { value: 'jBpfuIE2acCO8z3wKNLl', label: 'Gigi',    gender: 'Female', style: 'Childlike' },
    { value: 'jsCqWAovK2LkecY7zXl4', label: 'Freya',   gender: 'Female', style: 'Warm' },
    { value: 'onwK4e9ZLuTAKqWW03F9', label: 'Daniel',  gender: 'Male',   style: 'Deep · British' },
  ],
  cartesia: [
    { value: 'a0e99841-438c-4a64-b679-ae501e7d6091', label: 'Barbershop Man',     gender: 'Male',   style: 'Deep' },
    { value: '79a125e8-cd45-4c13-8a67-188112f4dd22', label: 'British Reading Lady',gender: 'Female', style: 'British' },
    { value: '87748186-23bb-4158-a1eb-332911b0b708', label: 'Helpful Woman',       gender: 'Female', style: 'Helpful' },
    { value: '156fb8d2-335b-4950-9cb3-a2d33befec77', label: 'Calm Lady',           gender: 'Female', style: 'Calm' },
    { value: '5c42302c-194b-4d0c-ba1a-8cb485c84ab9', label: 'Female Nurse',        gender: 'Female', style: 'Caring' },
    { value: '638efaaa-4d0c-442e-b701-3fae16aad012', label: 'New York Man',        gender: 'Male',   style: 'American' },
    { value: 'b7d50908-b17c-442d-ad8d-810c63997ed9', label: 'California Girl',     gender: 'Female', style: 'Casual' },
    { value: '694f9389-aac1-45b6-b726-9d9369183238', label: 'Friendly Sidekick',   gender: 'Male',   style: 'Upbeat' },
  ],
  deepgram: [
    { value: 'aura-asteria-en',   label: 'Asteria',  gender: 'Female', style: 'Warm' },
    { value: 'aura-luna-en',      label: 'Luna',     gender: 'Female', style: 'Soft' },
    { value: 'aura-stella-en',    label: 'Stella',   gender: 'Female', style: 'Friendly' },
    { value: 'aura-athena-en',    label: 'Athena',   gender: 'Female', style: 'Professional' },
    { value: 'aura-hera-en',      label: 'Hera',     gender: 'Female', style: 'Calm' },
    { value: 'aura-orion-en',     label: 'Orion',    gender: 'Male',   style: 'Confident' },
    { value: 'aura-arcas-en',     label: 'Arcas',    gender: 'Male',   style: 'Warm' },
    { value: 'aura-perseus-en',   label: 'Perseus',  gender: 'Male',   style: 'Clear' },
    { value: 'aura-angus-en',     label: 'Angus',    gender: 'Male',   style: 'Irish accent' },
    { value: 'aura-orpheus-en',   label: 'Orpheus',  gender: 'Male',   style: 'Deep' },
    { value: 'aura-helios-en',    label: 'Helios',   gender: 'Male',   style: 'British' },
    { value: 'aura-zeus-en',      label: 'Zeus',     gender: 'Male',   style: 'Strong' },
  ],
  openai: [
    { value: 'alloy',   label: 'Alloy',   gender: 'Neutral', style: 'Balanced' },
    { value: 'echo',    label: 'Echo',    gender: 'Male',    style: 'Warm' },
    { value: 'fable',   label: 'Fable',   gender: 'Male',    style: 'British' },
    { value: 'onyx',    label: 'Onyx',    gender: 'Male',    style: 'Deep' },
    { value: 'nova',    label: 'Nova',    gender: 'Female',  style: 'Friendly' },
    { value: 'shimmer', label: 'Shimmer', gender: 'Female',  style: 'Soft' },
  ],
  google: [
    { value: 'en-US-Standard-C',  label: 'Standard C (US)',  gender: 'Female', style: 'Standard' },
    { value: 'en-US-Standard-D',  label: 'Standard D (US)',  gender: 'Male',   style: 'Standard' },
    { value: 'en-US-Neural2-C',   label: 'Neural2 C (US)',   gender: 'Female', style: 'Natural' },
    { value: 'en-US-Neural2-D',   label: 'Neural2 D (US)',   gender: 'Male',   style: 'Natural' },
    { value: 'en-US-Wavenet-C',   label: 'WaveNet C (US)',   gender: 'Female', style: 'WaveNet' },
    { value: 'en-US-Wavenet-D',   label: 'WaveNet D (US)',   gender: 'Male',   style: 'WaveNet' },
    { value: 'en-GB-Neural2-A',   label: 'Neural2 A (UK)',   gender: 'Female', style: 'British' },
    { value: 'en-GB-Neural2-B',   label: 'Neural2 B (UK)',   gender: 'Male',   style: 'British' },
  ],
  azure: [
    { value: 'en-US-JennyNeural',      label: 'Jenny (US)',       gender: 'Female', style: 'Friendly' },
    { value: 'en-US-GuyNeural',        label: 'Guy (US)',         gender: 'Male',   style: 'Newscast' },
    { value: 'en-US-AriaNeural',       label: 'Aria (US)',        gender: 'Female', style: 'Natural' },
    { value: 'en-US-DavisNeural',      label: 'Davis (US)',       gender: 'Male',   style: 'Casual' },
    { value: 'en-GB-SoniaNeural',      label: 'Sonia (UK)',       gender: 'Female', style: 'British' },
    { value: 'en-GB-RyanNeural',       label: 'Ryan (UK)',        gender: 'Male',   style: 'British' },
    { value: 'en-AU-NatashaNeural',    label: 'Natasha (AU)',     gender: 'Female', style: 'Australian' },
    { value: 'en-AU-WilliamNeural',    label: 'William (AU)',     gender: 'Male',   style: 'Australian' },
    { value: 'en-IN-NeerjaNeural',     label: 'Neerja (IN)',      gender: 'Female', style: 'Indian' },
  ],
  playht: [
    { value: 's3://voice-cloning-zero-shot/d9ff78ba-d016-47f6-b0ef-dd630f59414e/female-cs-assistant/manifest.json', label: 'Jennifer', gender: 'Female', style: 'Professional' },
    { value: 's3://voice-cloning-zero-shot/e5df2eb3-5153-47ff-a1e2-5e9f3cfd6f9e/original/manifest.json', label: 'Michael', gender: 'Male', style: 'Confident' },
    { value: 's3://peregrine-voices/angela/manifest.json', label: 'Angela', gender: 'Female', style: 'Warm' },
    { value: 's3://peregrine-voices/cooper_saad/manifest.json', label: 'Cooper', gender: 'Male', style: 'Calm' },
  ],
  rimeai: [
    { value: 'lagoon',    label: 'Lagoon',    gender: 'Female', style: 'Neutral' },
    { value: 'cove',      label: 'Cove',      gender: 'Male',   style: 'Warm' },
    { value: 'brook',     label: 'Brook',     gender: 'Female', style: 'Soft' },
    { value: 'spore',     label: 'Spore',     gender: 'Male',   style: 'Deep' },
    { value: 'marsh',     label: 'Marsh',     gender: 'Male',   style: 'Raspy' },
  ],
  lmnt: [
    { value: 'leah',     label: 'Leah',     gender: 'Female', style: 'Conversational' },
    { value: 'lily',     label: 'Lily',     gender: 'Female', style: 'Warm' },
    { value: 'matt',     label: 'Matt',     gender: 'Male',   style: 'Energetic' },
    { value: 'ryan',     label: 'Ryan',     gender: 'Male',   style: 'Professional' },
    { value: 'zoe',      label: 'Zoe',      gender: 'Female', style: 'Bright' },
  ],
  neuphonic: [
    { value: 'e564ba7e-aa8d-46a2-96a8-8dffedade48c', label: 'Lena',   gender: 'Female', style: 'Natural' },
    { value: 'fc854d4e-d4a1-48da-8ab1-34eed2eedde7', label: 'Steve',  gender: 'Male',   style: 'Clear' },
  ],
  smallestai: [
    { value: 'emily', label: 'Emily', gender: 'Female', style: 'Friendly' },
    { value: 'james', label: 'James', gender: 'Male',   style: 'Professional' },
    { value: 'aria',  label: 'Aria',  gender: 'Female', style: 'Calm' },
  ],
  hume: [
    { value: 'ITO',        label: 'Ito',       gender: 'Neutral', style: 'Expressive' },
    { value: 'KORA',       label: 'Kora',      gender: 'Female',  style: 'Warm' },
    { value: 'DACHER',     label: 'Dacher',    gender: 'Male',    style: 'Calm' },
    { value: 'AURA',       label: 'Aura',      gender: 'Female',  style: 'Upbeat' },
    { value: 'FINN',       label: 'Finn',      gender: 'Male',    style: 'Deep' },
  ],
  minimax: [
    { value: 'female-shaonv',  label: 'Shaonv',   gender: 'Female', style: 'Young female' },
    { value: 'female-tianmei', label: 'Tianmei',  gender: 'Female', style: 'Sweet' },
    { value: 'male-jingying',  label: 'Jingying', gender: 'Male',   style: 'Professional' },
    { value: 'male-qingse',    label: 'Qingse',   gender: 'Male',   style: 'Dynamic' },
    { value: 'presenter_male', label: 'Presenter Male', gender: 'Male', style: 'Newscast' },
  ],
  inworld: [
    { value: 'inworld-ai-voice-1', label: 'Character Voice 1', gender: 'Neutral', style: 'Character' },
    { value: 'inworld-ai-voice-2', label: 'Character Voice 2', gender: 'Male',    style: 'Character' },
    { value: 'inworld-ai-voice-3', label: 'Character Voice 3', gender: 'Female',  style: 'Character' },
  ],
}

// Backward compat export
export const ELEVENLABS_VOICES = TTS_VOICES.elevenlabs

// ── STT Providers & Models ────────────────────────────────────────────────────

export const STT_PROVIDERS = [
  { value: 'deepgram',      label: 'Deepgram',       badge: 'Popular · Real-time' },
  { value: 'assemblyai',    label: 'AssemblyAI',     badge: 'Speaker diarization' },
  { value: 'elevenlabs',    label: 'ElevenLabs STT', badge: 'High accuracy' },
  { value: 'azure',         label: 'Azure Speech',   badge: 'Enterprise' },
  { value: 'gladia',        label: 'Gladia',         badge: 'Multilingual' },
  { value: 'speechmatics',  label: 'Speechmatics',   badge: 'Custom vocabulary' },
  { value: 'soniox',        label: 'Soniox',         badge: '60+ languages' },
  { value: 'whisper',       label: 'OpenAI Whisper', badge: 'Open-source' },
]

export const STT_MODELS: Record<string, { value: string; label: string; desc: string }[]> = {
  deepgram: [
    { value: 'nova-3',   label: 'Nova 3',   desc: 'Best accuracy' },
    { value: 'nova-2',   label: 'Nova 2',   desc: 'Recommended' },
    { value: 'nova',     label: 'Nova',     desc: 'Fast' },
    { value: 'enhanced', label: 'Enhanced', desc: 'Balanced' },
    { value: 'base',     label: 'Base',     desc: 'Lightweight' },
  ],
  assemblyai: [
    { value: 'best',      label: 'Best',       desc: 'Highest accuracy' },
    { value: 'nano',      label: 'Nano',        desc: 'Low latency' },
    { value: 'conformer-2', label: 'Conformer 2', desc: 'Enterprise' },
  ],
  elevenlabs: [
    { value: 'eleven_multilingual_v2', label: 'Multilingual v2', desc: 'Best quality' },
    { value: 'eleven_flash_v2_5',      label: 'Flash v2.5',      desc: 'Ultra-fast' },
  ],
  azure: [
    { value: 'latest',         label: 'Latest',          desc: 'Recommended' },
    { value: 'en-US',          label: 'US English',      desc: 'Optimized' },
    { value: 'conversation',   label: 'Conversation',    desc: 'Natural speech' },
  ],
  gladia: [
    { value: 'fast',           label: 'Fast',            desc: 'Low latency' },
    { value: 'accurate',       label: 'Accurate',        desc: 'Best accuracy' },
  ],
  speechmatics: [
    { value: 'enhanced',       label: 'Enhanced',        desc: 'Custom vocabulary' },
    { value: 'standard',       label: 'Standard',        desc: 'General purpose' },
  ],
  soniox: [
    { value: 'soniox-phone-english', label: 'Phone English', desc: 'Optimized for calls' },
    { value: 'soniox-precision',     label: 'Precision',      desc: 'High accuracy' },
  ],
  whisper: [
    { value: 'whisper-large-v3',  label: 'Whisper Large v3', desc: 'Most accurate' },
    { value: 'whisper-large-v2',  label: 'Whisper Large v2', desc: 'Stable' },
    { value: 'whisper-medium',    label: 'Whisper Medium',   desc: 'Balanced' },
    { value: 'whisper-small',     label: 'Whisper Small',    desc: 'Fast' },
    { value: 'whisper-base',      label: 'Whisper Base',     desc: 'Lightweight' },
  ],
}

export const LANGUAGES = [
  { value: 'en',    label: 'English' },
  { value: 'en-US', label: 'English (US)' },
  { value: 'en-GB', label: 'English (UK)' },
  { value: 'en-AU', label: 'English (AU)' },
  { value: 'es',    label: 'Spanish' },
  { value: 'es-MX', label: 'Spanish (Mexico)' },
  { value: 'fr',    label: 'French' },
  { value: 'fr-CA', label: 'French (Canada)' },
  { value: 'de',    label: 'German' },
  { value: 'it',    label: 'Italian' },
  { value: 'pt',    label: 'Portuguese' },
  { value: 'pt-BR', label: 'Portuguese (Brazil)' },
  { value: 'nl',    label: 'Dutch' },
  { value: 'pl',    label: 'Polish' },
  { value: 'ja',    label: 'Japanese' },
  { value: 'ko',    label: 'Korean' },
  { value: 'zh',    label: 'Chinese (Mandarin)' },
  { value: 'zh-TW', label: 'Chinese (Traditional)' },
  { value: 'ar',    label: 'Arabic' },
  { value: 'hi',    label: 'Hindi' },
  { value: 'ru',    label: 'Russian' },
  { value: 'tr',    label: 'Turkish' },
  { value: 'sv',    label: 'Swedish' },
  { value: 'da',    label: 'Danish' },
  { value: 'fi',    label: 'Finnish' },
  { value: 'no',    label: 'Norwegian' },
]

// ── Tab config ─────────────────────────────────────────────────────────────────

export const AGENT_TABS = [
  { id: 'basic',        label: 'Prompt',         icon: FileText },
  { id: 'llm',          label: 'LLM Selection',  icon: Cpu },
  { id: 'stt',          label: 'Transcriber',    icon: Mic },
  { id: 'voice',        label: 'Voice Selection',icon: Volume2 },
  { id: 'tools',        label: 'Tools',          icon: Wrench },
  { id: 'conversation', label: 'Conversation',   icon: MessageSquare },
  { id: 'advanced',     label: 'Advanced',       icon: Settings },
  { id: 'knowledge',    label: 'Knowledge',      icon: BookOpen },
  { id: 'widget',       label: 'Chat Widget',    icon: MessageSquare },
] as const

export type AgentTabId = typeof AGENT_TABS[number]['id']

// ── Form state type ───────────────────────────────────────────────────────────

export interface AgentFormState {
  name: string
  description: string
  system_prompt: string
  first_message: string
  llm_provider: string
  llm_model: string
  llm_temperature: number
  llm_max_tokens: number
  llm_custom_url: string
  tts_provider: string
  tts_voice_id: string
  tts_speed: number
  tts_pitch: number
  stt_provider: string
  stt_model: string
  stt_language: string
  interrupt_enabled: boolean
  interrupt_sensitivity: number
  silence_timeout: number
  max_call_duration: number
  background_noise_reduction: boolean
  sentiment_analysis_enabled: boolean
  emotion_detection_enabled: boolean
  /** Knowledge bases the agent answers from — the "Files" picker. */
  knowledge_base_ids: string[]
}

export const DEFAULT_FORM: AgentFormState = {
  name: '', description: '', system_prompt: '',
  first_message: 'Hello! How can I help you today?',
  llm_provider: 'openai', llm_model: 'gpt-5.4-nano', llm_temperature: 0.7, llm_max_tokens: 1000, llm_custom_url: '',
  tts_provider: 'elevenlabs', tts_voice_id: '21m00Tcm4TlvDq8ikWAM', tts_speed: 1.0, tts_pitch: 1.0,
  stt_provider: 'deepgram', stt_model: 'nova-2', stt_language: 'en',
  interrupt_enabled: true, interrupt_sensitivity: 0.5,
  silence_timeout: 3000, max_call_duration: 1800,
  background_noise_reduction: true, sentiment_analysis_enabled: false, emotion_detection_enabled: false,
  knowledge_base_ids: [],
}

// ── UI helpers ────────────────────────────────────────────────────────────────

/**
 * Slider with the value shown in a bordered box to the right of the label,
 * matching the Temperature control in the design.
 */
function SliderField({ label, value, min, max, step, format, onChange, hints }: {
  label: string; value: number; min: number; max: number; step: number
  format?: (v: number) => string; onChange: (v: number) => void
  hints?: [string, string, string?]
}) {
  const display = format ? format(value) : String(value)
  const pct = ((value - min) / (max - min)) * 100
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <Label className="text-[15px] font-semibold text-[#000000] font-poppins flex items-center gap-2">
          {label} <span className="flex h-[14px] w-[14px] items-center justify-center rounded-full border border-black text-[9px] font-bold leading-none">i</span>
        </Label>
        <span className="min-w-[50px] rounded-[6px] border border-[#000000] bg-[#0F6A590A] px-3 py-1.5 text-center text-[13px] font-medium text-[#000000] font-poppins">
          {display}
        </span>
      </div>
      <div className="relative pt-1 flex items-center h-4">
        {/* Track below thumb */}
        <div className="absolute w-full h-[2px] bg-slate-200 rounded-full" />
        <div className="absolute h-[2px] bg-[#106959] rounded-full" style={{ width: `${pct}%` }} />
        <input type="range" min={min} max={max} step={step} value={value}
          onChange={e => onChange(step < 1 ? parseFloat(e.target.value) : parseInt(e.target.value))}
          className="w-full appearance-none cursor-pointer bg-transparent absolute"
          style={{ WebkitAppearance: 'none' }}
        />
        {/* Simple style to make standard thumb invisible or styled. Here we just rely on browser thumb, it works fine for standard inputs. But we can style it via global css if needed. */}
      </div>
      {hints && (
        <div className="flex justify-between text-xs text-slate-400">
          <span>{hints[0]}</span>{hints[2] && <span>{hints[2]}</span>}<span>{hints[1]}</span>
        </div>
      )}
    </div>
  )
}

function Toggle({ enabled, onChange }: { enabled: boolean; onChange: (v: boolean) => void }) {
  return (
    <button type="button" onClick={() => onChange(!enabled)}
      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none ${enabled ? 'bg-[#0F6A59]' : 'bg-slate-300'}`}>
      <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${enabled ? 'translate-x-4' : 'translate-x-0.5'}`}/>
    </button>
  )
}

/**
 * Collapsible white card with a title, sub-caption and chevron — the "Model"
 * panel in the design.
 */
function SectionCard({ title, subtitle, icon: Icon, children, hint }: {
  title: string; subtitle?: string; icon?: React.ElementType; hint?: string; children: React.ReactNode
}) {
  const [open, setOpen] = useState(true)
  return (
    <div className="rounded-[10px] border border-[#000000] bg-white overflow-hidden mt-4">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-start justify-between gap-3 px-6 pt-5 pb-4 text-left"
      >
        <div className="flex items-start gap-2.5">
          {Icon && <Icon className="mt-1 h-5 w-5 flex-shrink-0 text-[#0F6A59]" />}
          <div>
            <h2 className="text-[20px] font-bold text-[#000000] font-poppins leading-tight">{title}</h2>
            {subtitle && <p className="mt-1 text-[12px] font-medium text-[#000000] font-poppins">{subtitle}</p>}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {hint && <span className="text-xs text-slate-400">{hint}</span>}
          <ChevronUp className={`h-6 w-6 flex-shrink-0 text-[#106959] transition-transform ${open ? '' : 'rotate-180'}`} />
        </div>
      </button>
      {open && <div className="px-6 pb-6 space-y-6">{children}</div>}
    </div>
  )
}

/**
 * "Files" picker from the design — selects which knowledge bases the agent
 * answers from. Multi-select, because an agent can hold several; the Knowledge
 * tab edits the same attachment list.
 */
function KnowledgeBaseSelect({ value, onChange }: { value: string[]; onChange: (ids: string[]) => void }) {
  const [options, setOptions] = useState<{ id: string; name: string }[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    apiClient.get<{ id: string; name: string }[]>(API_ENDPOINTS.KNOWLEDGE_BASES)
      .then(r => setOptions(r.data || []))
      .catch(() => setOptions([]))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const selectedNames = options.filter(o => value.includes(o.id)).map(o => o.name)
  const label = loading
    ? 'Loading…'
    : selectedNames.length === 0 ? 'Select File'
    : selectedNames.length === 1 ? selectedNames[0]
    : `${selectedNames.length} files selected`

  const toggle = (id: string) =>
    onChange(value.includes(id) ? value.filter(v => v !== id) : [...value, id])

  return (
    <div className="relative" ref={boxRef}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex h-[42px] w-full items-center justify-between rounded-[8px] border border-[#000000] bg-[#0F6A590A] px-3 text-[14px] font-poppins text-[#000000]"
      >
        <span className={selectedNames.length ? 'text-[#000000] font-medium' : 'text-slate-500 font-medium'}>{label}</span>
        <ChevronDown className="h-5 w-5 flex-shrink-0 text-[#106959]" />
      </button>

      {open && (
        <div className="absolute z-30 mt-1 max-h-56 w-full overflow-y-auto rounded-md border border-slate-200 bg-white p-1 shadow-lg">
          {options.length === 0 ? (
            <p className="px-3 py-2.5 text-sm text-slate-400">No knowledge bases yet</p>
          ) : (
            options.map(o => (
              <button
                key={o.id}
                type="button"
                onClick={() => toggle(o.id)}
                className="flex w-full items-center gap-2 rounded px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
              >
                <span className={`flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border ${
                  value.includes(o.id) ? 'border-[#0F6A59] bg-[#0F6A59] text-white' : 'border-slate-300'
                }`}>
                  {value.includes(o.id) && <Check className="h-3 w-3" />}
                </span>
                <span className="truncate">{o.name}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Assistant name and description. These live in the side rail next to the
 * "Create Assistant" action, matching the design.
 */
export function AgentIdentityFields({ form, set }: {
  form: AgentFormState; set: (key: keyof AgentFormState, value: any) => void
}) {
  return (
    <div className="space-y-4 rounded-[10px] border border-[#000000] bg-white p-5">
      <div className="space-y-2">
        <Label className="text-[14px] font-bold text-[#000000] font-poppins block">Assistant Name <span className="text-red-500">*</span></Label>
        <Input
          placeholder="e.g. Riley"
          value={form.name}
          onChange={e => set('name', e.target.value)}
          required
          className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-3 text-[14px]"
        />
      </div>
      <div className="space-y-2">
        <Label className="text-[14px] font-bold text-[#000000] font-poppins block mt-1">Description</Label>
        <Textarea
          placeholder="What does this assistant do?"
          value={form.description}
          onChange={e => set('description', e.target.value)}
          rows={3}
          className="w-full rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-3 py-2 text-[14px]"
        />
      </div>
    </div>
  )
}

function ProviderBadge({ badge }: { badge: string }) {
  if (!badge) return null
  return <span className="ml-2 rounded bg-[#0F6A59]/10 px-1.5 py-0.5 text-xs font-medium text-[#0F6A59]">{badge}</span>
}

// ── Tab content ───────────────────────────────────────────────────────────────

export function AgentTabContent({ tab, form, set }: {
  tab: AgentTabId; form: AgentFormState; set: (key: keyof AgentFormState, value: any) => void
}) {

  if (tab === 'basic') {
    return (
      <div className="flex flex-col w-[85%]">
        <SectionCard title="Model" subtitle="Configure the behaviour of the assistant">
          <div className="grid gap-x-10 gap-y-6 lg:grid-cols-2">
            {/* Left column */}
            <div className="space-y-6">
              <div className="space-y-2">
                <Label className="text-[15px] font-bold text-[#000000] font-poppins block">First Message</Label>
                <Input 
                  value={form.first_message} 
                  onChange={e => set('first_message', e.target.value)} 
                  placeholder="Thank you for calling Wellness Partners..."
                  className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-4 py-2"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[15px] font-bold text-[#000000] font-poppins block mt-4">System Prompt</Label>
                <Textarea
                  placeholder="You are a helpful voice assistant."
                  value={form.system_prompt} 
                  onChange={e => set('system_prompt', e.target.value)}
                  rows={13} required
                  className="w-full rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-4 py-3 leading-relaxed text-[13px]"
                />
              </div>
            </div>

            {/* Right column */}
            <div className="space-y-6">
              <div className="space-y-2">
                <Label className="text-[15px] font-bold text-[#000000] font-poppins block">Provider</Label>
                {/* Visual match for Provider via input style */}
                <div className="relative">
                   <Input 
                     value={LLM_PROVIDERS.find(p => p.value === form.llm_provider)?.label || 'open.ai'}
                     readOnly
                     className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-4 font-medium"
                   />
                   <Select value={form.llm_provider || 'openai'} onValueChange={v => { set('llm_provider', v); set('llm_model', (LLM_MODELS[v] || LLM_MODELS.openai)[0]?.value || 'gpt-5.4-nano') }}>
                     <SelectTrigger className="absolute inset-0 opacity-0 cursor-pointer h-[45px]"><SelectValue/></SelectTrigger>
                     <SelectContent>
                       {LLM_PROVIDERS.map(p => (
                         <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                       ))}
                     </SelectContent>
                   </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-[15px] font-bold text-[#000000] font-poppins block">Model</Label>
                {/* Visual match for Model via input style */}
                <div className="relative">
                   <Input 
                     value={(LLM_MODELS[form.llm_provider] || []).find(m => m.value === form.llm_model)?.label.split(' ')[0] || 'GPT-4'}
                     readOnly
                     className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-4 font-medium"
                   />
                   <Select value={form.llm_model || (LLM_MODELS[form.llm_provider] || [])[0]?.value || ''} onValueChange={v => set('llm_model', v)}>
                     <SelectTrigger className="absolute inset-0 opacity-0 cursor-pointer h-[45px]"><SelectValue/></SelectTrigger>
                     <SelectContent>
                       {(LLM_MODELS[form.llm_provider] || []).map(m => (
                         <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                       ))}
                     </SelectContent>
                   </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-[15px] font-bold text-[#000000] font-poppins block">Files</Label>
                <KnowledgeBaseSelect
                  value={form.knowledge_base_ids}
                  onChange={ids => set('knowledge_base_ids', ids)}
                />
              </div>

              <div className="pt-2">
                 <SliderField label="Temperature" value={form.llm_temperature} min={0} max={2} step={0.1}
                 format={v => v.toFixed(1)} onChange={v => set('llm_temperature', v)}/>
              </div>

              <div className="space-y-2 pt-2">
                <Label className="text-[15px] font-bold text-[#000000] font-poppins flex items-center gap-2">
                  Max Token <span className="flex h-[14px] w-[14px] items-center justify-center rounded-full border border-black text-[9px] font-bold leading-none">i</span>
                </Label>
                <Input
                  type="number" min={100} max={4000} step={50}
                  value={form.llm_max_tokens}
                  onChange={e => set('llm_max_tokens', parseInt(e.target.value) || 0)}
                  className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-4 font-medium"
                />
              </div>
            </div>
          </div>
        </SectionCard>
      </div>
    )
  }

  if (tab === 'llm') return (
    <div className="flex flex-col w-[85%]">
      <SectionCard title="LLM Selection" subtitle="Pick the model that powers the conversation" icon={Cpu} hint={`${LLM_PROVIDERS.length} providers`}>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label className="text-[14px] font-bold text-[#000000] font-poppins block">Provider</Label>
          <Select value={form.llm_provider || 'openai'} onValueChange={v => { set('llm_provider', v); set('llm_model', (LLM_MODELS[v] || LLM_MODELS.openai)[0]?.value || 'gpt-5.4-nano') }}>
            <SelectTrigger className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-3"><SelectValue/></SelectTrigger>
            <SelectContent>
              {LLM_PROVIDERS.map(p => (
                <SelectItem key={p.value} value={p.value}>
                  {p.label}{p.badge && <ProviderBadge badge={p.badge}/>}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label className="text-[14px] font-bold text-[#000000] font-poppins block">Model</Label>
          <Select value={form.llm_model || (LLM_MODELS[form.llm_provider] || [])[0]?.value || ''} onValueChange={v => set('llm_model', v)}>
            <SelectTrigger className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-3"><SelectValue/></SelectTrigger>
            <SelectContent>
              {(LLM_MODELS[form.llm_provider] || []).map(m => (
                <SelectItem key={m.value} value={m.value}>
                  <div><span className="font-medium">{m.label}</span><span className="ml-2 text-xs text-slate-400">{m.latency}</span></div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {form.llm_provider === 'custom' && (
        <div className="space-y-2">
          <Label className="text-[14px] font-bold text-[#000000] font-poppins block">Custom LLM Endpoint URL</Label>
          <Input value={form.llm_custom_url} onChange={e => set('llm_custom_url', e.target.value)}
            placeholder="https://your-llm-server.com/v1" className="font-mono text-sm"/>
          <p className="text-xs text-slate-400">Must be OpenAI-compatible (chat completions endpoint)</p>
        </div>
      )}

      <div className="grid gap-5 sm:grid-cols-2">
        <SliderField label="Temperature" value={form.llm_temperature} min={0} max={2} step={0.1}
          format={v => v.toFixed(1)} onChange={v => set('llm_temperature', v)}
          hints={['0 · Deterministic', '2 · Creative', '1 · Balanced']}/>
        <SliderField label="Max Token" value={form.llm_max_tokens} min={100} max={4000} step={100}
          format={v => String(v)} onChange={v => set('llm_max_tokens', v)}
          hints={['100 · Short', '4000 · Long']}/>
      </div>
    </SectionCard>
    </div>
  )

  if (tab === 'voice') {
    const currentVoices = TTS_VOICES[form.tts_provider] || TTS_VOICES.elevenlabs
    const defaultVoiceId = currentVoices[0]?.value || '21m00Tcm4TlvDq8ikWAM'

    return (
    <div className="flex flex-col w-[85%]">
      <SectionCard title="Voice Selection" subtitle="Choose how the assistant sounds" icon={Volume2} hint={`${TTS_PROVIDERS.length} providers`}>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label className="text-[14px] font-bold text-[#000000] font-poppins block">Provider</Label>
            <Select value={form.tts_provider || 'elevenlabs'} onValueChange={v => { set('tts_provider', v); set('tts_voice_id', (TTS_VOICES[v] || TTS_VOICES.elevenlabs)[0]?.value || '21m00Tcm4TlvDq8ikWAM') }}>
              <SelectTrigger className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-3"><SelectValue/></SelectTrigger>
              <SelectContent>
                {TTS_PROVIDERS.map(p => (
                  <SelectItem key={p.value} value={p.value}>
                    {p.label}<span className="ml-2 text-xs text-slate-400">{p.badge}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label className="text-[14px] font-bold text-[#000000] font-poppins block">Voice</Label>
            <Select value={form.tts_voice_id || defaultVoiceId || (currentVoices[0]?.value ?? '')} onValueChange={v => set('tts_voice_id', v)}>
              <SelectTrigger className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-3"><SelectValue/></SelectTrigger>
              <SelectContent>
                {currentVoices.map(v => (
                  <SelectItem key={v.value} value={v.value}>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{v.label}</span>
                      <span className="text-xs text-slate-400">{v.gender} · {v.style}</span>
                    </div>
                  </SelectItem>
                ))}
                <SelectItem value="_custom">Custom voice ID</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {form.tts_voice_id === '_custom' && (
          <div className="space-y-2">
            <Label className="text-[14px] font-bold text-[#000000] font-poppins block">Custom Voice ID</Label>
            <Input value=""
              onChange={e => set('tts_voice_id', e.target.value)}
              placeholder="Enter provider-specific voice ID" className="font-mono text-sm"/>
          </div>
        )}

        <div className="grid gap-5 sm:grid-cols-2">
          <SliderField label="Speech Speed" value={form.tts_speed} min={0.5} max={2.0} step={0.1}
            format={v => `${v.toFixed(1)}x`} onChange={v => set('tts_speed', v)}
            hints={['0.5x · Slow', '2.0x · Fast', '1.0x · Normal']}/>
          <SliderField label="Pitch" value={form.tts_pitch} min={0.5} max={2.0} step={0.1}
            format={v => v.toFixed(1)} onChange={v => set('tts_pitch', v)}
            hints={['0.5 · Low', '2.0 · High', '1.0 · Normal']}/>
        </div>
      </SectionCard>
      </div>
    )
  }

  if (tab === 'stt') {
    const sttModels = STT_MODELS[form.stt_provider] || STT_MODELS.deepgram
    const defaultSttModel = sttModels[0]?.value || 'nova-2'
    return (
    <div className="flex flex-col w-[85%]">
      <SectionCard title="Transcriber" subtitle="Speech-to-text engine for incoming audio" icon={Mic} hint={`${STT_PROVIDERS.length} providers`}>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-2">
            <Label className="text-[14px] font-bold text-[#000000] font-poppins block">Provider</Label>
            <Select value={form.stt_provider || 'deepgram'} onValueChange={v => { set('stt_provider', v); set('stt_model', (STT_MODELS[v] || STT_MODELS.deepgram)[0]?.value || 'nova-2') }}>
              <SelectTrigger className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-3"><SelectValue/></SelectTrigger>
              <SelectContent>
                {STT_PROVIDERS.map(p => (
                  <SelectItem key={p.value} value={p.value}>
                    <div><span>{p.label}</span><span className="ml-2 text-xs text-slate-400">{p.badge}</span></div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label className="text-[14px] font-bold text-[#000000] font-poppins block">Model</Label>
            <Select value={form.stt_model || defaultSttModel} onValueChange={v => set('stt_model', v)}>
              <SelectTrigger className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-3"><SelectValue/></SelectTrigger>
              <SelectContent>
                {sttModels.map(m => (
                  <SelectItem key={m.value} value={m.value}>
                    <div className="flex items-center gap-2"><span>{m.label}</span><span className="text-xs text-slate-400">{m.desc}</span></div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label className="text-[14px] font-bold text-[#000000] font-poppins block">Language</Label>
            <Select value={form.stt_language} onValueChange={v => set('stt_language', v)}>
              <SelectTrigger className="w-full h-[45px] rounded-[8px] border border-[#000000] bg-[#0F6A590A] text-[#000000] font-poppins px-3"><SelectValue/></SelectTrigger>
              <SelectContent>
                {LANGUAGES.map(l => <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>
      </SectionCard>
      </div>
    )
  }

  if (tab === 'conversation') return (
    <div className="flex flex-col w-[85%]">
      <SectionCard title="Conversation" subtitle="Turn-taking and call limits" icon={MessageSquare}>
      <div className="flex items-center justify-between rounded-[8px] border border-[#000000] bg-[#0F6A590A] px-4 py-3">
        <div>
          <p className="text-sm font-medium text-slate-800">Allow Interruptions (Barge-in)</p>
          <p className="text-xs text-slate-400 mt-0.5">User can speak while agent is talking</p>
        </div>
        <Toggle enabled={form.interrupt_enabled} onChange={v => set('interrupt_enabled', v)}/>
      </div>
      {form.interrupt_enabled && (
        <SliderField label="Interrupt Sensitivity" value={form.interrupt_sensitivity} min={0} max={1} step={0.1}
          format={v => v.toFixed(1)} onChange={v => set('interrupt_sensitivity', v)}
          hints={['0 · Low', '1 · High']}/>
      )}
      <SliderField label="Silence Timeout" value={form.silence_timeout} min={500} max={10000} step={500}
        format={v => v < 1000 ? `${v}ms` : `${(v/1000).toFixed(1)}s`}
        onChange={v => set('silence_timeout', v)} hints={['500ms', '10s']}/>
      <p className="text-xs text-slate-400 -mt-2">How long to wait after user stops speaking before responding.</p>
      <SliderField label="Max Call Duration" value={form.max_call_duration} min={60} max={7200} step={60}
        format={v => `${Math.floor(v/60)}m`} onChange={v => set('max_call_duration', v)} hints={['1m', '120m']}/>
    </SectionCard>
    </div>
  )

  if (tab === 'advanced') return (
    <div className="flex flex-col w-[85%]">
      <SectionCard title="Advanced" subtitle="Extra signal processing and analysis" icon={Settings}>
      {[
        { key: 'background_noise_reduction', label: 'Background Noise Reduction', desc: 'Filter background noise from audio input' },
        { key: 'sentiment_analysis_enabled', label: 'Sentiment Analysis',          desc: 'Detect user sentiment in real-time during calls' },
        { key: 'emotion_detection_enabled',  label: 'Emotion Detection',           desc: 'Analyze emotional tone from voice patterns' },
      ].map(({ key, label, desc }) => (
        <div key={key} className="flex items-center justify-between rounded-[8px] border border-[#000000] bg-[#0F6A590A] px-4 py-3">
          <div>
            <p className="text-sm font-medium text-slate-800">{label}</p>
            <p className="text-xs text-slate-400 mt-0.5">{desc}</p>
          </div>
          <Toggle enabled={(form as any)[key]} onChange={v => set(key as keyof AgentFormState, v)}/>
        </div>
      ))}
    </SectionCard>
    </div>
  )

  return null
}

// ── Tab nav bar ───────────────────────────────────────────────────────────────

/**
 * Step row from the design — a green dot per step, the active step in bold
 * slate with a green underline.
 */
export function AgentTabBar({ activeTab, onChange }: { activeTab: AgentTabId; onChange: (tab: AgentTabId) => void }) {
  return (
    <div className="flex items-center gap-7 overflow-x-auto border-b border-[#E5E7EB] pt-1">
      {AGENT_TABS.map(({ id, label }) => {
        const active = activeTab === id
        return (
          <button
            key={id}
            type="button"
            onClick={() => onChange(id)}
            title={label}
            className={`flex items-center gap-2 whitespace-nowrap pb-[14px] text-[15px] font-poppins transition-colors relative ${
              active
                ? 'font-bold text-[#000000]'
                : 'font-medium text-[#000000] hover:opacity-80'
            }`}
          >
            <span className={`h-2.5 w-2.5 flex-shrink-0 rounded-full ${active ? 'bg-[#106959]' : 'bg-[#106959]'}`} />
            {label}
            {active && (
              <span className="absolute bottom-[-1px] left-0 w-full h-[3px] bg-[#106959] rounded-t-sm" />
            )}
          </button>
        )
      })}
    </div>
  )
}
