/**
 * Workflow node type registry.
 *
 * One descriptor per node type drives the palette, the canvas node rendering,
 * and the configuration panel. Adding a node type means adding a descriptor
 * here — no changes to the canvas or panel components.
 */

export type FieldType =
  | 'text'
  | 'textarea'
  | 'number'
  | 'select'
  | 'json'
  | 'nodeRef'
  /** Picks one of the org's connected integrations. */
  | 'connection'
  /** Picks an action on the connection chosen in `dependsOn`. */
  | 'connectionAction'
  /** Editable list of key -> value assignments. */
  | 'keyValue'
  /** Ordered rule list that drives a switch node's outputs. */
  | 'rules'
  /** Declares the workflow's input parameters, on the trigger node. */
  | 'inputs'

export interface FieldDescriptor {
  name: string
  label: string
  type: FieldType
  placeholder?: string
  help?: string
  required?: boolean
  options?: { value: string; label: string }[]
  default?: unknown
  /** Only show this field when another field has one of these values. */
  showWhen?: { field: string; equals: string[] }
  /** For dynamic fields: the config key this field's options depend on. */
  dependsOn?: string
}

export interface NodeDescriptor {
  type: string
  label: string
  description: string
  category: 'Trigger' | 'Conversation' | 'Logic' | 'Actions' | 'AI'
  /** Tailwind classes for the node's icon chip. */
  accent: string
  /** Lucide icon name, resolved in the icon map. */
  icon: string
  /** Output handle ids. Empty means terminal. */
  outputs: { id: string; label?: string }[]
  /**
   * Outputs that depend on configuration (switch rules). When present this
   * wins over `outputs`.
   */
  dynamicOutputs?: (config: Record<string, any>) => { id: string; label?: string }[]
  hasInput: boolean
  fields: FieldDescriptor[]
  /** Short line rendered on the canvas node under the title. */
  summary: (config: Record<string, any>) => string
}

/** Resolve a node's outputs, accounting for configuration-driven handles. */
export function outputsFor(
  type: string,
  config: Record<string, any> = {}
): { id: string; label?: string }[] {
  const descriptor = getDescriptor(type)
  return descriptor.dynamicOutputs
    ? descriptor.dynamicOutputs(config)
    : descriptor.outputs
}

const OUT = [{ id: 'out' }]
const NONE: { id: string; label?: string }[] = []

export const NODE_TYPES: Record<string, NodeDescriptor> = {
  trigger: {
    type: 'trigger',
    label: 'Trigger',
    description: 'Where the workflow starts',
    category: 'Trigger',
    accent: 'bg-emerald-500',
    icon: 'Play',
    outputs: OUT,
    hasInput: false,
    fields: [
      {
        name: 'inputs',
        label: 'Inputs',
        type: 'inputs',
        default: [],
        help:
          'Declared inputs become the parameters a voice agent extracts when ' +
          'it calls this workflow as a tool. Reference them as {{trigger.name}}.',
      },
    ],
    summary: (c) => {
      const n = ((c.inputs as any[]) || []).length
      return n ? `${n} input${n > 1 ? 's' : ''}` : 'When this workflow runs'
    },
  },

  speak: {
    type: 'speak',
    label: 'Speak',
    description: 'Say something to the caller',
    category: 'Conversation',
    accent: 'bg-blue-500',
    icon: 'Volume2',
    outputs: OUT,
    hasInput: true,
    fields: [
      {
        name: 'message',
        label: 'Message',
        type: 'textarea',
        required: true,
        placeholder: 'Hello, thanks for calling…',
        help: 'Use {{variable}} to insert values from earlier steps.',
      },
      {
        name: 'voice',
        label: 'Voice',
        type: 'text',
        placeholder: 'Default',
      },
    ],
    summary: (c) => c.message || 'No message set',
  },

  ask: {
    type: 'ask',
    label: 'Ask Question',
    description: 'Ask the caller and capture the answer',
    category: 'Conversation',
    accent: 'bg-purple-500',
    icon: 'MessageCircleQuestion',
    outputs: OUT,
    hasInput: true,
    fields: [
      {
        name: 'question',
        label: 'Question',
        type: 'textarea',
        required: true,
        placeholder: 'What is your account number?',
      },
      {
        name: 'variable',
        label: 'Save answer as',
        type: 'text',
        required: true,
        placeholder: 'account_number',
        help: 'Later steps reference this as {{account_number}}.',
      },
      {
        name: 'input_type',
        label: 'Input type',
        type: 'select',
        default: 'speech',
        options: [
          { value: 'speech', label: 'Speech' },
          { value: 'dtmf', label: 'Keypad (DTMF)' },
        ],
      },
      { name: 'timeout', label: 'Timeout (seconds)', type: 'number', default: 10 },
    ],
    summary: (c) => c.question || 'No question set',
  },

  condition: {
    type: 'condition',
    label: 'Branch',
    description: 'Split the flow on a condition',
    category: 'Logic',
    accent: 'bg-amber-500',
    icon: 'GitBranch',
    outputs: [
      { id: 'true', label: 'true' },
      { id: 'false', label: 'false' },
    ],
    hasInput: true,
    fields: [
      {
        name: 'variable',
        label: 'Variable',
        type: 'text',
        required: true,
        placeholder: 'account_number',
      },
      {
        name: 'operator',
        label: 'Operator',
        type: 'select',
        default: 'equals',
        options: [
          { value: 'equals', label: 'equals' },
          { value: 'not_equals', label: 'does not equal' },
          { value: 'contains', label: 'contains' },
          { value: 'not_contains', label: 'does not contain' },
          { value: 'starts_with', label: 'starts with' },
          { value: 'ends_with', label: 'ends with' },
          { value: 'greater_than', label: 'is greater than' },
          { value: 'less_than', label: 'is less than' },
          { value: 'is_empty', label: 'is empty' },
          { value: 'is_not_empty', label: 'is not empty' },
        ],
      },
      {
        name: 'value',
        label: 'Value',
        type: 'text',
        placeholder: 'yes',
        showWhen: {
          field: 'operator',
          equals: [
            'equals',
            'not_equals',
            'contains',
            'not_contains',
            'starts_with',
            'ends_with',
            'greater_than',
            'less_than',
          ],
        },
      },
    ],
    summary: (c) =>
      c.variable
        ? `${c.variable} ${(c.operator || 'equals').replace(/_/g, ' ')} ${c.value ?? ''}`.trim()
        : 'No condition set',
  },

  switch: {
    type: 'switch',
    label: 'Switch',
    description: 'Route to one of several branches',
    category: 'Logic',
    accent: 'bg-yellow-500',
    icon: 'Split',
    outputs: [{ id: 'fallback', label: 'else' }],
    dynamicOutputs: (config) => {
      const rules = (config.rules as any[]) || []
      return [
        ...rules.map((rule, index) => ({
          id: `branch-${index}`,
          label: rule?.label || `Rule ${index + 1}`,
        })),
        { id: 'fallback', label: 'else' },
      ]
    },
    hasInput: true,
    fields: [
      {
        name: 'rules',
        label: 'Rules',
        type: 'rules',
        default: [],
        help: 'The first matching rule wins. Anything else takes “else”.',
      },
    ],
    summary: (c) => {
      const n = ((c.rules as any[]) || []).length
      return n ? `${n} branch${n > 1 ? 'es' : ''} + else` : 'No rules set'
    },
  },

  filter: {
    type: 'filter',
    label: 'Filter',
    description: 'Continue only when a condition holds',
    category: 'Logic',
    accent: 'bg-lime-500',
    icon: 'FilterIcon',
    outputs: OUT,
    hasInput: true,
    fields: [
      {
        name: 'variable',
        label: 'Variable',
        type: 'text',
        required: true,
        placeholder: 'trigger.score',
      },
      {
        name: 'operator',
        label: 'Operator',
        type: 'select',
        default: 'equals',
        options: [
          { value: 'equals', label: 'equals' },
          { value: 'not_equals', label: 'does not equal' },
          { value: 'contains', label: 'contains' },
          { value: 'greater_than', label: 'is greater than' },
          { value: 'less_than', label: 'is less than' },
          { value: 'is_empty', label: 'is empty' },
          { value: 'is_not_empty', label: 'is not empty' },
        ],
      },
      {
        name: 'value',
        label: 'Value',
        type: 'text',
        showWhen: {
          field: 'operator',
          equals: [
            'equals',
            'not_equals',
            'contains',
            'greater_than',
            'less_than',
          ],
        },
      },
    ],
    summary: (c) =>
      c.variable
        ? `Only if ${c.variable} ${(c.operator || 'equals').replace(/_/g, ' ')} ${c.value ?? ''}`.trim()
        : 'No condition set',
  },

  merge: {
    type: 'merge',
    label: 'Merge',
    description: 'Join parallel branches back together',
    category: 'Logic',
    accent: 'bg-fuchsia-500',
    icon: 'GitMerge',
    outputs: OUT,
    hasInput: true,
    fields: [],
    summary: () => 'Waits for incoming branches',
  },

  loop: {
    type: 'loop',
    label: 'Loop Over Items',
    description: 'Run steps once per item in a list',
    category: 'Logic',
    accent: 'bg-emerald-600',
    icon: 'Repeat',
    outputs: [
      { id: 'loop', label: 'each item' },
      { id: 'done', label: 'done' },
    ],
    hasInput: true,
    fields: [
      {
        name: 'items',
        label: 'Items',
        type: 'text',
        placeholder: 'trigger.customers',
        help: 'A reference to a list. Inside the loop use {{loop.item}}.',
      },
      {
        name: 'max_iterations',
        label: 'Max iterations',
        type: 'number',
        default: 100,
      },
    ],
    summary: (c) => (c.items ? `For each ${c.items}` : 'No list set'),
  },

  transfer: {
    type: 'transfer',
    label: 'Transfer Call',
    description: 'Hand the call to a human or another number',
    category: 'Conversation',
    accent: 'bg-teal-500',
    icon: 'PhoneForwarded',
    outputs: NONE,
    hasInput: true,
    fields: [
      {
        name: 'destination',
        label: 'Destination',
        type: 'text',
        required: true,
        placeholder: '+1 555 000 1234',
      },
      {
        name: 'transfer_type',
        label: 'Transfer type',
        type: 'select',
        default: 'blind',
        options: [
          { value: 'blind', label: 'Blind' },
          { value: 'warm', label: 'Warm' },
        ],
      },
      { name: 'message', label: 'Message before transfer', type: 'textarea' },
    ],
    summary: (c) => c.destination || 'No destination set',
  },

  tool: {
    type: 'tool',
    label: 'Run Tool',
    description: 'Execute a configured tool or function',
    category: 'Actions',
    accent: 'bg-orange-500',
    icon: 'Wrench',
    outputs: OUT,
    hasInput: true,
    fields: [
      {
        name: 'tool_id',
        label: 'Tool ID',
        type: 'text',
        required: true,
        placeholder: 'tool_xxxxxxxx',
        help: 'Find tool IDs in the Tools section.',
      },
      { name: 'parameters', label: 'Parameters (JSON)', type: 'json', default: '{}' },
    ],
    summary: (c) => c.tool_id || 'No tool selected',
  },

  webhook: {
    type: 'webhook',
    label: 'Webhook',
    description: 'Call an external HTTP endpoint',
    category: 'Actions',
    accent: 'bg-cyan-500',
    icon: 'Globe',
    outputs: OUT,
    hasInput: true,
    fields: [
      {
        name: 'url',
        label: 'URL',
        type: 'text',
        required: true,
        placeholder: 'https://api.example.com/hook',
      },
      {
        name: 'method',
        label: 'Method',
        type: 'select',
        default: 'POST',
        options: [
          { value: 'GET', label: 'GET' },
          { value: 'POST', label: 'POST' },
          { value: 'PUT', label: 'PUT' },
          { value: 'PATCH', label: 'PATCH' },
          { value: 'DELETE', label: 'DELETE' },
        ],
      },
      { name: 'headers', label: 'Headers (JSON)', type: 'json', default: '{}' },
      {
        name: 'body',
        label: 'Body (JSON)',
        type: 'json',
        default: '{}',
        showWhen: { field: 'method', equals: ['POST', 'PUT', 'PATCH', 'DELETE'] },
      },
    ],
    summary: (c) => (c.url ? `${c.method || 'POST'} ${c.url}` : 'No URL set'),
  },

  ai: {
    type: 'ai',
    label: 'AI Response',
    description: 'Let the AI respond using context',
    category: 'AI',
    accent: 'bg-violet-500',
    icon: 'Sparkles',
    outputs: OUT,
    hasInput: true,
    fields: [
      {
        name: 'context',
        label: 'Context',
        type: 'textarea',
        required: true,
        placeholder: 'You are helping the caller troubleshoot their router.',
      },
      { name: 'constraints', label: 'Constraints', type: 'textarea' },
      {
        name: 'variable',
        label: 'Save reply as',
        type: 'text',
        placeholder: 'ai_reply',
      },
    ],
    summary: (c) => c.context || 'No context set',
  },

  action: {
    type: 'action',
    label: 'Integration',
    description: 'Run an action on a connected app',
    category: 'Actions',
    accent: 'bg-indigo-500',
    icon: 'Plug',
    outputs: OUT,
    hasInput: true,
    fields: [
      {
        name: 'connection_id',
        label: 'Connection',
        type: 'connection',
        required: true,
        help: 'Connect apps in the Integrations section.',
      },
      {
        name: 'action',
        label: 'Action',
        type: 'connectionAction',
        required: true,
        dependsOn: 'connection_id',
      },
      {
        name: 'parameters',
        label: 'Parameters',
        type: 'keyValue',
        default: {},
        help: 'Values may reference earlier steps, e.g. {{steps.ask.answer}}.',
      },
    ],
    summary: (c) => c.action || 'No action selected',
  },

  transform: {
    type: 'transform',
    label: 'Set Fields',
    description: 'Build or reshape values for later steps',
    category: 'Logic',
    accent: 'bg-sky-500',
    icon: 'Braces',
    outputs: OUT,
    hasInput: true,
    fields: [
      {
        name: 'transformations',
        label: 'Fields',
        type: 'keyValue',
        default: {},
        help: 'Each field becomes available to later steps by name.',
      },
    ],
    summary: (c) => {
      const count = Object.keys(c.transformations || {}).length
      return count ? `${count} field${count > 1 ? 's' : ''}` : 'No fields set'
    },
  },

  delay: {
    type: 'delay',
    label: 'Wait',
    description: 'Pause before continuing',
    category: 'Logic',
    accent: 'bg-slate-500',
    icon: 'Clock',
    outputs: OUT,
    hasInput: true,
    fields: [
      {
        name: 'delay_seconds',
        label: 'Wait (seconds)',
        type: 'number',
        required: true,
        default: 5,
      },
    ],
    summary: (c) => `Wait ${c.delay_seconds ?? 0}s`,
  },

  end: {
    type: 'end',
    label: 'End Call',
    description: 'Finish the conversation',
    category: 'Conversation',
    accent: 'bg-rose-500',
    icon: 'PhoneOff',
    outputs: NONE,
    hasInput: true,
    fields: [
      {
        name: 'farewell',
        label: 'Farewell message',
        type: 'textarea',
        placeholder: 'Thanks for calling. Goodbye!',
      },
    ],
    summary: (c) => c.farewell || 'Ends the call',
  },
}

export const PALETTE_CATEGORIES: NodeDescriptor['category'][] = [
  'Conversation',
  'Logic',
  'Actions',
  'AI',
]

export function getDescriptor(type: string): NodeDescriptor {
  return NODE_TYPES[type] ?? NODE_TYPES.speak
}

/** Build a config object populated with the descriptor's defaults. */
export function defaultConfig(type: string): Record<string, any> {
  const config: Record<string, any> = {}
  for (const field of getDescriptor(type).fields) {
    if (field.default !== undefined) config[field.name] = field.default
  }
  return config
}

/** Whether a field should be visible given the current config. */
export function isFieldVisible(
  field: FieldDescriptor,
  config: Record<string, any>
): boolean {
  if (!field.showWhen) return true
  const current = config[field.showWhen.field]
  return field.showWhen.equals.includes(String(current))
}

/**
 * Generate a collision-free node id.
 *
 * Date.now() alone collided when two nodes were added in the same millisecond,
 * which corrupted edge targeting because ids are edge keys.
 */
export function newNodeId(): string {
  return `n_${Math.random().toString(36).slice(2, 10)}`
}
