import { describe, expect, it } from 'vitest'

import { asJsonText } from './NodeInspector'

describe('showing a JSON field', () => {
  it('passes text through untouched', () => {
    expect(asJsonText('{"a": 1}')).toBe('{"a": 1}')
  })

  it('renders a parsed object as JSON rather than [object Object]', () => {
    // Handing the object straight to the textarea showed "[object Object]",
    // and the first keystroke saved that back over the real headers.
    expect(asJsonText({ city: 'Austin' })).toBe('{\n  "city": "Austin"\n}')
  })

  it('renders an empty object as an empty object', () => {
    expect(asJsonText({})).toBe('{}')
  })

  it('shows nothing for an unset field', () => {
    expect(asJsonText(undefined)).toBe('')
    expect(asJsonText(null)).toBe('')
  })
})
