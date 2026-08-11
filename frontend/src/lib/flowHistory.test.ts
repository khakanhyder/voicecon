/**
 * Unit tests for the flow-builder undo/redo stack and the debounce helper.
 *
 * The property that makes undo trustworthy is that snapshots are deep copies.
 * The builder mutates its nodes in place as the user drags them, so a stack
 * holding references would see its history rewritten underneath it and "undo"
 * would restore the state you are already in.
 */
import { describe, expect, it, vi } from 'vitest'

import { FlowHistory, debounce, type FlowSnapshot } from './flowHistory'

function snapshot(label: string): FlowSnapshot {
  return {
    nodes: [{ id: 'n1', position: { x: 0, y: 0 }, data: { label } }] as never,
    edges: [],
  }
}

function labelOf(snap: FlowSnapshot | null): string | undefined {
  return (snap?.nodes[0] as never as { data: { label: string } } | undefined)?.data.label
}

describe('undo and redo', () => {
  it('has nothing to undo with a single state', () => {
    // The first push is the starting point, not an edit.
    const history = new FlowHistory()
    history.push(snapshot('a'))

    expect(history.canUndo()).toBe(false)
    expect(history.undo()).toBeNull()
  })

  it('steps back to the previous state', () => {
    const history = new FlowHistory()
    history.push(snapshot('a'))
    history.push(snapshot('b'))

    expect(history.canUndo()).toBe(true)
    expect(labelOf(history.undo())).toBe('a')
  })

  it('steps forward again after an undo', () => {
    const history = new FlowHistory()
    history.push(snapshot('a'))
    history.push(snapshot('b'))
    history.undo()

    expect(history.canRedo()).toBe(true)
    expect(labelOf(history.redo())).toBe('b')
  })

  it('has nothing to redo at the newest state', () => {
    const history = new FlowHistory()
    history.push(snapshot('a'))
    history.push(snapshot('b'))

    expect(history.canRedo()).toBe(false)
    expect(history.redo()).toBeNull()
  })

  it('walks back through several states in order', () => {
    const history = new FlowHistory()
    ;['a', 'b', 'c'].forEach((l) => history.push(snapshot(l)))

    expect(labelOf(history.undo())).toBe('b')
    expect(labelOf(history.undo())).toBe('a')
    expect(history.undo()).toBeNull()
  })

  it('discards the redo branch once you edit after undoing', () => {
    // Standard undo semantics: editing from a past state forks history, and the
    // abandoned future must not be reachable with redo.
    const history = new FlowHistory()
    history.push(snapshot('a'))
    history.push(snapshot('b'))
    history.undo()

    history.push(snapshot('c'))

    expect(history.canRedo()).toBe(false)
    expect(labelOf(history.undo())).toBe('a')
  })
})

describe('snapshots are isolated', () => {
  it('does not observe later mutation of a pushed object', () => {
    // The builder mutates nodes in place while dragging. Storing a reference
    // would let those edits rewrite history retroactively.
    const history = new FlowHistory()
    const live = snapshot('original')
    history.push(live)
    history.push(snapshot('second'))
    ;(live.nodes[0] as never as { data: { label: string } }).data.label = 'mutated'

    expect(labelOf(history.undo())).toBe('original')
  })

  it('hands back a copy, so the caller cannot corrupt the stack', () => {
    const history = new FlowHistory()
    history.push(snapshot('a'))
    history.push(snapshot('b'))

    const restored = history.undo()!
    ;(restored.nodes[0] as never as { data: { label: string } }).data.label = 'tampered'
    history.redo()

    expect(labelOf(history.undo())).toBe('a')
  })
})

describe('bounded size', () => {
  it('keeps only the most recent states', () => {
    // Snapshots are whole graphs; an unbounded stack is a memory leak on a long
    // editing session.
    const history = new FlowHistory(3)
    ;['a', 'b', 'c', 'd'].forEach((l) => history.push(snapshot(l)))

    expect(labelOf(history.undo())).toBe('c')
    expect(labelOf(history.undo())).toBe('b')
    expect(history.undo()).toBeNull()
  })
})

describe('clear', () => {
  it('empties the stack', () => {
    const history = new FlowHistory()
    history.push(snapshot('a'))
    history.push(snapshot('b'))

    history.clear()

    expect(history.canUndo()).toBe(false)
    expect(history.canRedo()).toBe(false)
  })
})

describe('debounce', () => {
  it('runs once after the quiet period', () => {
    vi.useFakeTimers()
    const fn = vi.fn()
    const debounced = debounce(fn, 100)

    debounced()
    debounced()
    debounced()
    vi.advanceTimersByTime(100)

    expect(fn).toHaveBeenCalledTimes(1)
    vi.useRealTimers()
  })

  it('does not run before the delay elapses', () => {
    vi.useFakeTimers()
    const fn = vi.fn()
    const debounced = debounce(fn, 100)

    debounced()
    vi.advanceTimersByTime(99)

    expect(fn).not.toHaveBeenCalled()
    vi.useRealTimers()
  })

  it('passes the most recent arguments through', () => {
    // Autosave debounces on every keystroke; sending the first draft rather
    // than the latest would save stale text.
    vi.useFakeTimers()
    const fn = vi.fn()
    const debounced = debounce(fn, 50)

    debounced('first')
    debounced('latest')
    vi.advanceTimersByTime(50)

    expect(fn).toHaveBeenCalledWith('latest')
    vi.useRealTimers()
  })

  it('runs again for a burst that arrives after the first fired', () => {
    vi.useFakeTimers()
    const fn = vi.fn()
    const debounced = debounce(fn, 50)

    debounced()
    vi.advanceTimersByTime(50)
    debounced()
    vi.advanceTimersByTime(50)

    expect(fn).toHaveBeenCalledTimes(2)
    vi.useRealTimers()
  })
})
