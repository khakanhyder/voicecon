import { describe, expect, it } from 'vitest'
import {
  LANGUAGES, STT_MODEL_LANGUAGES, defaultGreeting, isDefaultGreeting, spokenGreeting,
  spokenWordCount, sttModelFor, sttModelSupports,
} from './agentLanguages'

describe('speech-to-text model for a language', () => {
  it('every language has at least one model, and the fallback takes them all', () => {
    for (const { value } of LANGUAGES) {
      expect(STT_MODEL_LANGUAGES['nova-3']).toContain(value)
      expect(sttModelSupports(sttModelFor('nova', value), value)).toBe(true)
    }
  })

  it('keeps a model that works and replaces one that does not', () => {
    expect(sttModelFor('nova-2', 'es')).toBe('nova-2')
    expect(sttModelFor('nova-2', 'ar')).toBe('nova-3')
    expect(sttModelFor('enhanced', 'fi')).toBe('nova-3')
  })

  it('leaves an unknown model or language to the server', () => {
    expect(sttModelFor('whisper', 'ar')).toBe('whisper')
    expect(sttModelFor('nova', 'xx')).toBe('nova')
  })
})

describe('greeting', () => {
  it('an untouched default follows the language', () => {
    expect(spokenGreeting('Hello! How can I help you today?', 'es-MX')).toBe(defaultGreeting('es'))
    expect(spokenGreeting(defaultGreeting('fr'), 'de')).toBe(defaultGreeting('de'))
    expect(spokenGreeting('', 'zh-TW')).toBe(defaultGreeting('zh-TW'))
    expect(defaultGreeting('zh-TW')).not.toBe(defaultGreeting('zh'))
  })

  it('a written greeting is left alone', () => {
    expect(isDefaultGreeting('Thanks for calling Pearl Dental.')).toBe(false)
    expect(spokenGreeting('Thanks for calling Pearl Dental.', 'es')).toBe('Thanks for calling Pearl Dental.')
  })
})

describe('spokenWordCount', () => {
  it('counts words in any script', () => {
    expect(spokenWordCount("I'd like to book")).toBe(4)
    expect(spokenWordCount('Здравствуйте, я хочу записаться')).toBe(4)
    expect(spokenWordCount('你好，我想预约')).toBe(3)
    expect(spokenWordCount('はい')).toBe(1)
    expect(spokenWordCount('')).toBe(0)
  })
})
