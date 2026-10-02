/**
 * The agent editor only offers transcriber models that work for the agent's
 * language, and says so when the greeting has to be written in it.
 */
import { render, screen } from '@testing-library/react'
import React from 'react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('./VoiceSelection', () => ({ VoiceSelection: () => null }))

import { AgentTabContent, DEFAULT_FORM } from './AgentForm'

const form = (over: Partial<typeof DEFAULT_FORM>) => ({ ...DEFAULT_FORM, ...over })

describe('agent editor language', () => {
  it('shows a model that supports the language, not the stored one that does not', () => {
    render(<AgentTabContent tab="stt" form={form({ stt_language: 'ar', stt_model: 'nova-2' })} set={vi.fn()} />)
    expect(screen.getByLabelText('Model').textContent).toContain('Nova 3')
    expect(screen.getByLabelText('Language').textContent).toContain('Arabic')
  })

  it('keeps the stored model when it supports the language', () => {
    render(<AgentTabContent tab="stt" form={form({ stt_language: 'es', stt_model: 'nova-2' })} set={vi.fn()} />)
    expect(screen.getByLabelText('Model').textContent).toContain('Nova 2')
  })

  it('tells the customer to write the greeting in the agent language', () => {
    const { rerender } = render(<AgentTabContent tab="basic" form={form({ stt_language: 'es-MX' })} set={vi.fn()} />)
    expect(screen.getByText(/write it in Spanish \(Mexico\)/)).toBeTruthy()
    rerender(<AgentTabContent tab="basic" form={form({ stt_language: 'en-GB' })} set={vi.fn()} />)
    expect(screen.queryByText(/write it in/)).toBeNull()
  })
})
