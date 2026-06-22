import { Node, Edge } from 'reactflow'

export interface ValidationError {
  nodeId?: string
  message: string
  severity: 'error' | 'warning'
}

export interface ValidationResult {
  valid: boolean
  errors: ValidationError[]
  warnings: ValidationError[]
}

export function validateFlow(nodes: Node[], edges: Edge[]): ValidationResult {
  const errors: ValidationError[] = []
  const warnings: ValidationError[] = []

  const startNodes = nodes.filter((n) => n.type === 'start')
  const endNodes = nodes.filter((n) => n.type === 'end')

  if (startNodes.length === 0) {
    errors.push({ message: 'Flow must have a Start node', severity: 'error' })
  }
  if (startNodes.length > 1) {
    errors.push({ message: 'Flow can only have one Start node', severity: 'error' })
  }
  if (endNodes.length === 0) {
    warnings.push({ message: 'Flow has no End node', severity: 'warning' })
  }

  // Check for disconnected nodes
  const connectedIds = new Set<string>()
  edges.forEach((e) => {
    connectedIds.add(e.source)
    connectedIds.add(e.target)
  })
  nodes.forEach((n) => {
    if (n.type !== 'start' && !connectedIds.has(n.id)) {
      warnings.push({
        nodeId: n.id,
        message: `Node "${n.data?.label || n.id}" is not connected`,
        severity: 'warning',
      })
    }
  })

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  }
}

export function validateNodeData(node: Node): ValidationError[] {
  const errors: ValidationError[] = []
  const data = node.data || {}

  if (node.type === 'message' && !data.message) {
    errors.push({ nodeId: node.id, message: 'Message node requires message text', severity: 'error' })
  }
  if (node.type === 'question' && !data.question) {
    errors.push({ nodeId: node.id, message: 'Question node requires question text', severity: 'error' })
  }
  if (node.type === 'function' && !data.functionName) {
    errors.push({ nodeId: node.id, message: 'Function node requires a function name', severity: 'error' })
  }

  return errors
}
