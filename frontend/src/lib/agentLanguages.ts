/**
 * The agent's language, as the editor needs it.
 *
 * Mirrors backend/app/services/voice/languages.py, which is what a call
 * actually runs on; backend/tests/unit/test_agent_languages.py fails when the
 * two drift apart. Change both together.
 */

export const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "en-US", label: "English (US)" },
  { value: "en-GB", label: "English (UK)" },
  { value: "en-AU", label: "English (AU)" },
  { value: "es", label: "Spanish" },
  { value: "es-MX", label: "Spanish (Mexico)" },
  { value: "fr", label: "French" },
  { value: "fr-CA", label: "French (Canada)" },
  { value: "de", label: "German" },
  { value: "it", label: "Italian" },
  { value: "pt", label: "Portuguese" },
  { value: "pt-BR", label: "Portuguese (Brazil)" },
  { value: "nl", label: "Dutch" },
  { value: "pl", label: "Polish" },
  { value: "ja", label: "Japanese" },
  { value: "ko", label: "Korean" },
  { value: "zh", label: "Chinese (Mandarin)" },
  { value: "zh-TW", label: "Chinese (Traditional)" },
  { value: "ar", label: "Arabic" },
  { value: "hi", label: "Hindi" },
  { value: "ru", label: "Russian" },
  { value: "tr", label: "Turkish" },
  { value: "sv", label: "Swedish" },
  { value: "da", label: "Danish" },
  { value: "fi", label: "Finnish" },
  { value: "no", label: "Norwegian" },
] as const

/** The one speech-to-text model that takes every language. */
export const FALLBACK_STT_MODEL = 'nova-3'

/**
 * Which languages each speech-to-text model accepts. The provider refuses a
 * pair outside this table, and the call then hears nothing, so the editor
 * only offers pairs that are in it.
 */
export const STT_MODEL_LANGUAGES: Record<string, readonly string[]> = {
  "nova-3": ["en", "en-US", "en-GB", "en-AU", "es", "es-MX", "fr", "fr-CA", "de", "it", "pt", "pt-BR", "nl", "pl", "ja", "ko", "zh", "zh-TW", "ar", "hi", "ru", "tr", "sv", "da", "fi", "no"],
  "nova-2": ["en", "en-US", "en-GB", "en-AU", "es", "es-MX", "fr", "fr-CA", "de", "it", "pt", "pt-BR", "nl", "pl", "ja", "ko", "zh", "zh-TW", "hi", "ru", "tr", "sv", "da", "fi", "no"],
  "nova": ["en", "en-US", "en-GB", "en-AU", "es"],
  "enhanced": ["en", "en-US", "es", "fr", "de", "it", "pt", "pt-BR", "nl", "pl", "ja", "ko", "hi", "sv", "da", "no"],
  "base": ["en", "en-US", "en-GB", "en-AU", "es", "fr", "fr-CA", "de", "it", "pt", "pt-BR", "nl", "pl", "ja", "ko", "zh", "zh-TW", "hi", "ru", "tr", "sv", "da", "no"],
}

/** The editor's default greeting in each language (regions use their language's). */
export const DEFAULT_GREETINGS: Record<string, string> = {
  "en": "Hello! How can I help you today?",
  "es": "¡Hola! ¿En qué puedo ayudarle hoy?",
  "fr": "Bonjour ! Comment puis-je vous aider aujourd'hui ?",
  "de": "Hallo! Wie kann ich Ihnen heute helfen?",
  "it": "Buongiorno! Come posso aiutarla oggi?",
  "pt": "Olá! Como posso ajudar hoje?",
  "nl": "Hallo! Waarmee kan ik u vandaag helpen?",
  "pl": "Dzień dobry! W czym mogę dziś pomóc?",
  "ja": "こんにちは。本日はどのようなご用件でしょうか。",
  "ko": "안녕하세요! 무엇을 도와드릴까요?",
  "zh": "您好！请问今天有什么可以帮您？",
  "zh-TW": "您好！請問今天有什麼可以為您服務的？",
  "ar": "مرحباً! كيف يمكنني مساعدتك اليوم؟",
  "hi": "नमस्ते! आज मैं आपकी क्या मदद करूँ?",
  "ru": "Здравствуйте! Чем я могу вам помочь?",
  "tr": "Merhaba! Bugün size nasıl yardımcı olabilirim?",
  "sv": "Hej! Hur kan jag hjälpa dig idag?",
  "da": "Hej! Hvordan kan jeg hjælpe dig i dag?",
  "fi": "Hei! Kuinka voin auttaa tänään?",
  "no": "Hei! Hvordan kan jeg hjelpe deg i dag?",
}

const baseLanguage = (code: string) => (code || 'en').split('-')[0].toLowerCase()

export const isEnglish = (code: string) => baseLanguage(code) === 'en'

export const languageLabel = (code: string) =>
  LANGUAGES.find(l => l.value === code)?.label ?? code

/** Whether a speech-to-text model can be used with a language. */
export function sttModelSupports(model: string, language: string): boolean {
  const supported = STT_MODEL_LANGUAGES[model]
  // A model or language this table does not know is left to the server.
  if (!supported || !LANGUAGES.some(l => l.value === language)) return true
  return supported.includes(language)
}

/** The model to keep when the language changes: the current one if it still
 *  works, otherwise the one that supports everything. */
export const sttModelFor = (model: string, language: string) =>
  sttModelSupports(model, language) ? model : FALLBACK_STT_MODEL

export const defaultGreeting = (language: string) =>
  DEFAULT_GREETINGS[language] ?? DEFAULT_GREETINGS[baseLanguage(language)] ?? DEFAULT_GREETINGS.en

const normalise = (text: string) => text.trim().split(/\s+/).join(' ').toLowerCase()

/** The greeting is one of the untouched defaults, in whatever language. */
export const isDefaultGreeting = (text: string) =>
  Object.values(DEFAULT_GREETINGS).some(g => normalise(g) === normalise(text || ''))

/**
 * What a call opens with. A greeting the customer wrote is spoken as written;
 * an untouched default follows the agent's language.
 */
export const spokenGreeting = (firstMessage: string, language: string) =>
  !firstMessage?.trim() || isDefaultGreeting(firstMessage) ? defaultGreeting(language) : firstMessage

// Characters of scripts written without spaces (Chinese, Japanese).
const UNSPACED = /[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/g

/**
 * How many words were said, in any script — what barge-in counts. Two
 * characters of an unspaced script count as one word. Mirrors `word_count`
 * in backend/app/services/voice/turn_taking.py.
 */
export function spokenWordCount(text: string): number {
  const unspaced = (text.match(UNSPACED) || []).length
  const spaced = text.replace(UNSPACED, ' ').trim().split(/[\s.,!?;:。、，！？]+/).filter(Boolean).length
  return spaced + Math.ceil(unspaced / 2)
}
