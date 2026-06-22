import { Node, Edge } from 'reactflow'

export interface FlowSnapshot {
  nodes: Node[]
  edges: Edge[]
}

export class FlowHistory {
  private history: FlowSnapshot[] = []
  private index: number = -1
  private readonly maxSize: number

  constructor(maxSize = 50) {
    this.maxSize = maxSize
  }

  push(snapshot: FlowSnapshot) {
    // Drop any future states
    this.history = this.history.slice(0, this.index + 1)
    this.history.push(JSON.parse(JSON.stringify(snapshot)))
    if (this.history.length > this.maxSize) {
      this.history.shift()
    } else {
      this.index++
    }
  }

  undo(): FlowSnapshot | null {
    if (this.index <= 0) return null
    this.index--
    return JSON.parse(JSON.stringify(this.history[this.index]))
  }

  redo(): FlowSnapshot | null {
    if (this.index >= this.history.length - 1) return null
    this.index++
    return JSON.parse(JSON.stringify(this.history[this.index]))
  }

  canUndo(): boolean {
    return this.index > 0
  }

  canRedo(): boolean {
    return this.index < this.history.length - 1
  }

  clear() {
    this.history = []
    this.index = -1
  }
}

export function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout>
  return (...args: Parameters<T>) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delay)
  }
}
