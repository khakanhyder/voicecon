/**
 * Component tests for the Tabs primitive.
 *
 * A hand-rolled implementation rather than a Radix wrapper, so the
 * controlled/uncontrolled duality is ours to get right: passing `value` must
 * hand control to the parent completely, and omitting it must let the component
 * manage its own. Mixing the two up produces a tab strip that either ignores
 * clicks or ignores the parent — both of which look like a data bug elsewhere.
 */
import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Tabs, TabsContent, TabsList, TabsTrigger } from './tabs'

function Basic(props: React.ComponentProps<typeof Tabs>) {
  return (
    <Tabs {...props}>
      <TabsList>
        <TabsTrigger value="general">General</TabsTrigger>
        <TabsTrigger value="voice">Voice</TabsTrigger>
      </TabsList>
      <TabsContent value="general">General settings</TabsContent>
      <TabsContent value="voice">Voice settings</TabsContent>
    </Tabs>
  )
}

describe('uncontrolled', () => {
  it('shows the panel named by defaultValue', () => {
    render(<Basic defaultValue="general" />)

    expect(screen.getByText('General settings')).toBeInTheDocument()
    expect(screen.queryByText('Voice settings')).not.toBeInTheDocument()
  })

  it('switches panel when another tab is clicked', async () => {
    const user = userEvent.setup()
    render(<Basic defaultValue="general" />)

    await user.click(screen.getByRole('tab', { name: 'Voice' }))

    expect(screen.getByText('Voice settings')).toBeInTheDocument()
    expect(screen.queryByText('General settings')).not.toBeInTheDocument()
  })

  it('shows no panel when nothing is selected', () => {
    // With no defaultValue the internal value is "", which matches no panel.
    render(<Basic />)

    expect(screen.queryByText('General settings')).not.toBeInTheDocument()
    expect(screen.queryByText('Voice settings')).not.toBeInTheDocument()
  })

  it('renders only the active panel, not hidden ones', () => {
    // Panels are unmounted rather than hidden with CSS, so an inactive panel
    // must not be reachable — including by a screen reader.
    render(<Basic defaultValue="general" />)

    expect(screen.queryByText('Voice settings')).not.toBeInTheDocument()
  })
})

describe('controlled', () => {
  it('shows the panel the parent selects', () => {
    render(<Basic value="voice" onValueChange={() => {}} />)

    expect(screen.getByText('Voice settings')).toBeInTheDocument()
  })

  it('reports a click to the parent instead of switching itself', async () => {
    // The parent owns the value; switching internally would desync the two.
    const user = userEvent.setup()
    const onValueChange = vi.fn()
    render(<Basic value="general" onValueChange={onValueChange} />)

    await user.click(screen.getByRole('tab', { name: 'Voice' }))

    expect(onValueChange).toHaveBeenCalledWith('voice')
    expect(screen.getByText('General settings')).toBeInTheDocument()
  })

  it('follows the parent when it updates the value', async () => {
    const user = userEvent.setup()

    function Controlled() {
      const [tab, setTab] = useState('general')
      return <Basic value={tab} onValueChange={setTab} />
    }
    render(<Controlled />)

    await user.click(screen.getByRole('tab', { name: 'Voice' }))

    expect(screen.getByText('Voice settings')).toBeInTheDocument()
  })
})

describe('triggers', () => {
  it('renders real buttons under the tab role', () => {
    // role="tab" is the ARIA semantics; the element underneath stays a real
    // <button> so keyboard activation and focus order come for free.
    render(<Basic defaultValue="general" />)

    expect(screen.getByRole('tab', { name: 'General' }).tagName).toBe('BUTTON')
  })

  it('does not submit a surrounding form', async () => {
    // A tab strip inside a settings form must not submit it. This is why the
    // trigger sets type="button" explicitly.
    const user = userEvent.setup()
    const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault())
    render(
      <form onSubmit={onSubmit}>
        <Basic defaultValue="general" />
      </form>
    )

    await user.click(screen.getByRole('tab', { name: 'Voice' }))

    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('styles the active tab differently from the inactive one', async () => {
    const user = userEvent.setup()
    render(<Basic defaultValue="general" />)

    const general = screen.getByRole('tab', { name: 'General' })
    const voice = screen.getByRole('tab', { name: 'Voice' })
    expect(general.className).not.toBe(voice.className)

    await user.click(voice)

    expect(voice.className).not.toBe(general.className)
  })

  it('activates from the keyboard', async () => {
    const user = userEvent.setup()
    render(<Basic defaultValue="general" />)

    await user.tab()
    await user.tab()
    await user.keyboard('{Enter}')

    expect(screen.getByText('Voice settings')).toBeInTheDocument()
  })
})

describe('accessibility wiring', () => {
  it('exposes tablist / tab / tabpanel semantics', () => {
    render(<Basic defaultValue="general" />)

    expect(screen.getByRole('tablist')).toBeInTheDocument()
    expect(screen.getAllByRole('tab')).toHaveLength(2)
    expect(screen.getByRole('tabpanel')).toBeInTheDocument()
  })

  it('marks only the active tab as selected', async () => {
    const user = userEvent.setup()
    render(<Basic defaultValue="general" />)

    expect(screen.getByRole('tab', { name: 'General' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Voice' })).toHaveAttribute('aria-selected', 'false')

    await user.click(screen.getByRole('tab', { name: 'Voice' }))

    expect(screen.getByRole('tab', { name: 'Voice' })).toHaveAttribute('aria-selected', 'true')
  })

  it('points each tab at the panel it controls', () => {
    // A screen reader user moving into the panel needs to hear which tab it
    // belongs to, and vice versa.
    render(<Basic defaultValue="general" />)

    const tab = screen.getByRole('tab', { name: 'General' })
    const panel = screen.getByRole('tabpanel')

    expect(tab).toHaveAttribute('aria-controls', panel.id)
    expect(panel).toHaveAttribute('aria-labelledby', tab.id)
  })
})
