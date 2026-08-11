/**
 * Documentation navigation registry.
 *
 * One tree drives the sidebar, the on-page table of contents, the search
 * index, and prev/next paging. Adding a docs page means adding an entry here
 * and creating the matching `app/docs/<href>/page.tsx` — no other wiring.
 *
 * `sections` must mirror the `<H2 id>` anchors on the page, in document order.
 * They are the page's table of contents and its searchable sub-entries, so a
 * heading missing here is a heading nobody can jump to.
 */

export interface DocSection {
  /** Matches the heading's `id`, used as the `#fragment`. */
  id: string
  title: string
}

export interface DocPageMeta {
  title: string
  href: string
  /** One line under the title, and the search result's subtitle. */
  description: string
  sections: DocSection[]
  /** Extra search terms that do not appear in the title or description. */
  keywords?: string[]
}

/**
 * Per-section colour tokens.
 *
 * Brand green stays the interface colour everywhere — links, buttons, active
 * states. These accents are wayfinding only: the rail marker, the page
 * eyebrow, and the hub card. Used sparingly they make a section recognisable;
 * used on body copy they would turn the docs into a rainbow.
 *
 * Written as literal class strings because Tailwind scans this file (see the
 * `./src/lib/**` glob in tailwind.config.ts) and cannot resolve interpolation.
 */
export interface AccentTokens {
  /** Eyebrow label and small icons. */
  text: string
  /** Soft icon chip: background + foreground. */
  chip: string
  /** Solid bar — rail marker, heading underline. */
  bar: string
  /** Hover border on hub cards. */
  edge: string
}

export const ACCENTS: Record<string, AccentTokens> = {
  emerald: {
    text: 'text-emerald-700',
    chip: 'bg-emerald-50 text-emerald-600',
    bar: 'bg-emerald-500',
    edge: 'hover:border-emerald-300',
  },
  brand: {
    text: 'text-brand-700',
    chip: 'bg-brand-50 text-brand-600',
    bar: 'bg-brand-500',
    edge: 'hover:border-brand-300',
  },
  violet: {
    text: 'text-violet-700',
    chip: 'bg-violet-50 text-violet-600',
    bar: 'bg-violet-500',
    edge: 'hover:border-violet-300',
  },
  amber: {
    text: 'text-amber-700',
    chip: 'bg-amber-50 text-amber-600',
    bar: 'bg-amber-500',
    edge: 'hover:border-amber-300',
  },
  orange: {
    text: 'text-orange-700',
    chip: 'bg-orange-50 text-orange-600',
    bar: 'bg-orange-500',
    edge: 'hover:border-orange-300',
  },
  blue: {
    text: 'text-blue-700',
    chip: 'bg-blue-50 text-blue-600',
    bar: 'bg-blue-500',
    edge: 'hover:border-blue-300',
  },
  teal: {
    text: 'text-teal-700',
    chip: 'bg-teal-50 text-teal-600',
    bar: 'bg-teal-500',
    edge: 'hover:border-teal-300',
  },
  rose: {
    text: 'text-rose-700',
    chip: 'bg-rose-50 text-rose-600',
    bar: 'bg-rose-500',
    edge: 'hover:border-rose-300',
  },
  slate: {
    text: 'text-slate-700',
    chip: 'bg-slate-100 text-slate-600',
    bar: 'bg-slate-500',
    edge: 'hover:border-slate-300',
  },
  indigo: {
    text: 'text-indigo-700',
    chip: 'bg-indigo-50 text-indigo-600',
    bar: 'bg-indigo-500',
    edge: 'hover:border-indigo-300',
  },
}

export interface DocGroup {
  title: string
  /** Lucide icon name, resolved in the sidebar's icon map. */
  icon: string
  /** Rail label. Must fit an 88px column, so roughly 10 characters. */
  short: string
  /** Key into ACCENTS. */
  accent: keyof typeof ACCENTS
  /** One line describing the section, shown on the hub and the panel header. */
  blurb: string
  pages: DocPageMeta[]
}

export const DOCS_NAV: DocGroup[] = [
  {
    title: 'Get Started',
    icon: 'Rocket',
    short: 'Start',
    accent: 'emerald',
    blurb: 'What Voicecon is, and how to ship your first agent.',
    pages: [
      {
        title: 'Introduction',
        href: '/docs',
        description: 'What Voicecon is, and how its pieces fit together.',
        sections: [
          { id: 'start-here', title: 'Start here' },
          { id: 'the-building-blocks', title: 'The building blocks' },
          { id: 'how-they-fit-together', title: 'How they fit together' },
          { id: 'two-ways-to-build', title: 'Two ways to build a call' },
          { id: 'browse', title: 'Browse the documentation' },
        ],
        keywords: ['overview', 'voice ai', 'getting started', 'platform', 'home'],
      },
      {
        title: 'Quickstart',
        href: '/docs/quickstart',
        description: 'Build, test, and phone-enable your first agent in about ten minutes.',
        sections: [
          { id: 'before-you-start', title: 'Before you start' },
          { id: 'step-1-create-agent', title: 'Step 1 — Create an agent' },
          { id: 'step-2-write-prompt', title: 'Step 2 — Write the prompt' },
          { id: 'step-3-pick-voice', title: 'Step 3 — Pick a model and voice' },
          { id: 'step-4-test', title: 'Step 4 — Test it in the browser' },
          { id: 'step-5-phone-number', title: 'Step 5 — Attach a phone number' },
          { id: 'step-6-review', title: 'Step 6 — Review the call' },
          { id: 'next-steps', title: 'Next steps' },
        ],
        keywords: ['tutorial', 'first agent', 'hello world', 'setup'],
      },
      {
        title: 'Core Concepts',
        href: '/docs/concepts',
        description: 'The vocabulary of the platform, and what each object owns.',
        sections: [
          { id: 'object-model', title: 'The object model' },
          { id: 'agent', title: 'Agent' },
          { id: 'tool', title: 'Tool' },
          { id: 'workflow', title: 'Workflow' },
          { id: 'integration', title: 'Integration' },
          { id: 'knowledge-base', title: 'Knowledge base' },
          { id: 'phone-number', title: 'Phone number' },
          { id: 'call', title: 'Call' },
          { id: 'workspace', title: 'Workspace' },
          { id: 'glossary', title: 'Glossary' },
        ],
        keywords: ['glossary', 'terminology', 'data model', 'definitions'],
      },
    ],
  },
  {
    title: 'Agents',
    icon: 'Bot',
    short: 'Agents',
    accent: 'brand',
    blurb: 'The voice on the call — prompt, model, voice, turn-taking.',
    pages: [
      {
        title: 'Agents Overview',
        href: '/docs/agents',
        description: 'What an agent is, what it does on a call, and how to create one.',
        sections: [
          { id: 'what-is-an-agent', title: 'What is an agent?' },
          { id: 'the-voice-loop', title: 'The voice loop' },
          { id: 'creating-an-agent', title: 'Creating an agent' },
          { id: 'agent-lifecycle', title: 'Activating, cloning, and deleting' },
          { id: 'agent-anatomy', title: 'Anatomy of a configured agent' },
        ],
        keywords: ['assistant', 'create agent', 'new agent', 'voice agent'],
      },
      {
        title: 'Agent Configuration',
        href: '/docs/agents/configuration',
        description: 'Every setting on the agent editor, what it changes, and how to choose.',
        sections: [
          { id: 'prompt', title: 'Prompt' },
          { id: 'llm', title: 'LLM selection' },
          { id: 'transcriber', title: 'Transcriber (speech-to-text)' },
          { id: 'voice', title: 'Voice (text-to-speech)' },
          { id: 'conversation', title: 'Conversation' },
          { id: 'advanced', title: 'Advanced' },
          { id: 'knowledge', title: 'Knowledge base' },
          { id: 'tools-tab', title: 'Tools' },
          { id: 'tuning-for-latency', title: 'Tuning for latency' },
        ],
        keywords: [
          'system prompt', 'first message', 'temperature', 'max tokens', 'openai',
          'anthropic', 'elevenlabs', 'deepgram', 'interrupt', 'silence timeout',
          'barge-in', 'stt', 'tts', 'model', 'voice id',
        ],
      },
      {
        title: 'Testing & Channels',
        href: '/docs/agents/testing',
        description: 'Test in the browser, place real calls, and embed the chat widget.',
        sections: [
          { id: 'browser-test', title: 'Testing in the browser' },
          { id: 'what-to-check', title: 'What to check on a test call' },
          { id: 'outbound-calls', title: 'Placing an outbound call' },
          { id: 'chat-widget', title: 'The chat widget' },
          { id: 'debugging', title: 'Debugging a bad call' },
        ],
        keywords: ['test', 'web call', 'widget', 'embed', 'outbound', 'debug'],
      },
      {
        title: 'Squads',
        href: '/docs/agents/squads',
        description: 'Route one call across several specialised agents.',
        sections: [
          { id: 'what-is-a-squad', title: 'What is a squad?' },
          { id: 'members-and-roles', title: 'Members and roles' },
          { id: 'transfer-rules', title: 'Transfer rules' },
          { id: 'squad-vs-workflow', title: 'Squad or workflow?' },
        ],
        keywords: ['multi-agent', 'handoff', 'transfer', 'specialist'],
      },
    ],
  },
  {
    title: 'Workflows',
    icon: 'GitBranch',
    short: 'Workflows',
    accent: 'violet',
    blurb: 'Visual automations that run steps in a defined order.',
    pages: [
      {
        title: 'Workflows Overview',
        href: '/docs/workflows',
        description: 'Visual automations that run steps in a defined order.',
        sections: [
          { id: 'what-is-a-workflow', title: 'What is a workflow?' },
          { id: 'when-to-use', title: 'When to use a workflow' },
          { id: 'the-builder', title: 'The builder' },
          { id: 'creating-a-workflow', title: 'Creating a workflow' },
          { id: 'connecting-nodes', title: 'Connecting nodes' },
          { id: 'validation', title: 'Validation' },
        ],
        keywords: ['builder', 'canvas', 'automation', 'flow', 'nodes', 'graph'],
      },
      {
        title: 'Triggers',
        href: '/docs/workflows/triggers',
        description: 'The six ways a workflow can start, and what each one passes in.',
        sections: [
          { id: 'trigger-types', title: 'The six trigger types' },
          { id: 'manual', title: 'Manual' },
          { id: 'schedule', title: 'Schedule' },
          { id: 'webhook', title: 'Webhook' },
          { id: 'call-started', title: 'Call started' },
          { id: 'call-completed', title: 'Call completed' },
          { id: 'integration-event', title: 'Integration event' },
          { id: 'declaring-inputs', title: 'Declaring inputs' },
        ],
        keywords: ['cron', 'schedule', 'webhook', 'event', 'call_completed', 'inputs'],
      },
      {
        title: 'Variables & Expressions',
        href: '/docs/workflows/variables',
        description: 'How data moves between steps, and the {{ }} templating rules.',
        sections: [
          { id: 'the-context-object', title: 'The context object' },
          { id: 'reference-syntax', title: 'Reference syntax' },
          { id: 'type-preservation', title: 'Type preservation' },
          { id: 'missing-references', title: 'Missing references' },
          { id: 'publishing-variables', title: 'Publishing your own variables' },
          { id: 'loop-variables', title: 'Loop variables' },
          { id: 'examples', title: 'Worked examples' },
        ],
        keywords: [
          'templating', 'interpolation', 'mustache', 'trigger', 'steps', 'vars',
          'expression', 'reference', 'json path',
        ],
      },
      {
        title: 'Running & History',
        href: '/docs/workflows/execution',
        description: 'Test runs, live execution streaming, retries, and the run log.',
        sections: [
          { id: 'test-run', title: 'Running a test' },
          { id: 'execution-model', title: 'The execution model' },
          { id: 'error-handling', title: 'Error handling and retries' },
          { id: 'execution-history', title: 'Execution history' },
          { id: 'reading-a-run', title: 'Reading a failed run' },
        ],
        keywords: ['execute', 'run', 'history', 'retry', 'failure', 'concurrency'],
      },
    ],
  },
  {
    title: 'Node Reference',
    icon: 'Boxes',
    short: 'Nodes',
    accent: 'amber',
    blurb: 'Every node type, with all of its parameters.',
    pages: [
      {
        title: 'All Nodes',
        href: '/docs/nodes',
        description: 'Every node type at a glance, grouped by category.',
        sections: [
          { id: 'categories', title: 'The four categories' },
          { id: 'quick-reference', title: 'Quick reference table' },
          { id: 'anatomy', title: 'Anatomy of a node' },
          { id: 'common-fields', title: 'Field types you will meet' },
        ],
        keywords: ['node types', 'palette', 'reference', 'list'],
      },
      {
        title: 'Trigger Node',
        href: '/docs/nodes/trigger',
        description: 'Where every workflow starts, and where its inputs are declared.',
        sections: [
          { id: 'purpose', title: 'Purpose' },
          { id: 'parameters', title: 'Parameters' },
          { id: 'inputs-as-tool-parameters', title: 'Inputs become tool parameters' },
          { id: 'example', title: 'Example' },
        ],
        keywords: ['start', 'inputs', 'entry point'],
      },
      {
        title: 'Conversation Nodes',
        href: '/docs/nodes/conversation',
        description: 'Speak, Ask Question, Transfer Call, and End Call.',
        sections: [
          { id: 'speak', title: 'Speak' },
          { id: 'ask', title: 'Ask Question' },
          { id: 'transfer', title: 'Transfer Call' },
          { id: 'end', title: 'End Call' },
          { id: 'designing-conversation', title: 'Designing the conversation' },
        ],
        keywords: ['speak', 'ask', 'question', 'dtmf', 'transfer', 'hang up', 'farewell'],
      },
      {
        title: 'Logic Nodes',
        href: '/docs/nodes/logic',
        description: 'Branch, Switch, Filter, Merge, Loop, Set Fields, Code, and Wait.',
        sections: [
          { id: 'condition', title: 'Branch' },
          { id: 'switch', title: 'Switch' },
          { id: 'filter', title: 'Filter' },
          { id: 'merge', title: 'Merge' },
          { id: 'loop', title: 'Loop Over Items' },
          { id: 'transform', title: 'Set Fields' },
          { id: 'code', title: 'Code' },
          { id: 'delay', title: 'Wait' },
          { id: 'operators', title: 'Operator reference' },
        ],
        keywords: [
          'branch', 'condition', 'switch', 'filter', 'merge', 'loop', 'transform',
          'set fields', 'code', 'python', 'javascript', 'delay', 'wait', 'operators',
        ],
      },
      {
        title: 'Action Nodes',
        href: '/docs/nodes/actions',
        description: 'Run Tool, Webhook, and Integration.',
        sections: [
          { id: 'tool', title: 'Run Tool' },
          { id: 'webhook', title: 'Webhook' },
          { id: 'action', title: 'Integration' },
          { id: 'choosing', title: 'Choosing between them' },
        ],
        keywords: ['webhook', 'http', 'integration', 'action', 'run tool', 'api'],
      },
      {
        title: 'AI Node',
        href: '/docs/nodes/ai',
        description: 'Let the model compose a reply mid-workflow.',
        sections: [
          { id: 'purpose', title: 'Purpose' },
          { id: 'parameters', title: 'Parameters' },
          { id: 'writing-context', title: 'Writing good context' },
          { id: 'example', title: 'Example' },
        ],
        keywords: ['ai response', 'llm', 'generate', 'context', 'constraints'],
      },
    ],
  },
  {
    title: 'Tools',
    icon: 'Wrench',
    short: 'Tools',
    accent: 'orange',
    blurb: 'How an agent acts — and every tool it can be given.',
    pages: [
      {
        title: 'Tools Overview',
        href: '/docs/tools',
        description: 'How an agent decides to act, and how tools are created and assigned.',
        sections: [
          { id: 'what-is-a-tool', title: 'What is a tool?' },
          { id: 'how-the-agent-chooses', title: 'How the agent chooses a tool' },
          { id: 'the-four-families', title: 'The four families' },
          { id: 'creating-a-tool', title: 'Creating a tool' },
          { id: 'assigning-to-agents', title: 'Assigning a tool to an agent' },
          { id: 'testing-a-tool', title: 'Testing a tool' },
        ],
        keywords: ['function calling', 'tool', 'create tool', 'assign', 'test'],
      },
      {
        title: 'Tool Parameters',
        href: '/docs/tools/parameters',
        description: 'The parameter builder — the contract between the agent and your tool.',
        sections: [
          { id: 'why-parameters', title: 'Why parameters matter' },
          { id: 'the-fields', title: 'The four fields' },
          { id: 'types', title: 'Parameter types' },
          { id: 'writing-descriptions', title: 'Writing descriptions the model can use' },
          { id: 'required-vs-optional', title: 'Required vs optional' },
          { id: 'allowed-values', title: 'Allowed values (enums)' },
          { id: 'using-in-templates', title: 'Using parameters in templates' },
          { id: 'generated-schema', title: 'The generated schema' },
        ],
        keywords: [
          'parameters', 'json schema', 'required', 'enum', 'description', 'string',
          'number', 'boolean', 'object', 'array', 'placeholder',
        ],
      },
      {
        title: 'Workflow Tools',
        href: '/docs/tools/workflow',
        description: 'The bridge from a live call to a multi-step automation.',
        sections: [
          { id: 'run-workflow', title: 'Run Workflow' },
          { id: 'parameters', title: 'Parameters' },
          { id: 'the-chain', title: 'The agent → tool → workflow chain' },
          { id: 'holding-line', title: 'Avoiding dead air' },
          { id: 'example', title: 'Example' },
        ],
        keywords: ['run workflow', 'filler', 'holding line', 'chain'],
      },
      {
        title: 'Phone Call Tools',
        href: '/docs/tools/phone-call',
        description: 'Transfer, hang up, voicemail, DTMF, SMS, and SIP.',
        sections: [
          { id: 'transfer-call', title: 'Transfer Call' },
          { id: 'hang-up', title: 'Hang Up' },
          { id: 'leave-voicemail', title: 'Leave Voicemail' },
          { id: 'dtmf', title: 'DTMF' },
          { id: 'send-sms', title: 'Send Text' },
          { id: 'sip-request', title: 'SIP Request' },
          { id: 'summary', title: 'At a glance' },
        ],
        keywords: ['transfer', 'hangup', 'voicemail', 'dtmf', 'sms', 'text', 'sip'],
      },
      {
        title: 'Assistant Tools',
        href: '/docs/tools/assistant',
        description: 'Handoff and Query Knowledge Base.',
        sections: [
          { id: 'handoff', title: 'Handoff' },
          { id: 'query-knowledge-base', title: 'Query Knowledge Base' },
          { id: 'linked-vs-tool', title: 'Linked knowledge base or query tool?' },
          { id: 'handoff-vs-transfer', title: 'Handoff or Transfer Call?' },
        ],
        keywords: ['handoff', 'human agent', 'queue', 'knowledge base', 'rag'],
      },
      {
        title: 'Integration Tools',
        href: '/docs/tools/integration',
        description: 'Connected Integration, API Request, MCP, Slack, Sheets, Calendar, and more.',
        sections: [
          { id: 'connected-integration', title: 'Connected Integration' },
          { id: 'api-request', title: 'API Request' },
          { id: 'custom-tool', title: 'Custom Tool' },
          { id: 'mcp', title: 'MCP' },
          { id: 'slack', title: 'Slack' },
          { id: 'google-sheets', title: 'Google Sheets' },
          { id: 'google-calendar', title: 'Google Calendar' },
          { id: 'gohighlevel', title: 'GoHighLevel' },
          { id: 'choosing', title: 'Choosing between them' },
        ],
        keywords: [
          'api request', 'http', 'mcp', 'slack', 'sheets', 'calendar',
          'gohighlevel', 'ghl', 'custom tool', 'bearer', 'basic auth', 'webhook',
        ],
      },
    ],
  },
  {
    title: 'Integrations',
    icon: 'Plug',
    short: 'Apps',
    accent: 'blue',
    blurb: 'Connect an app once, then use it everywhere.',
    pages: [
      {
        title: 'Integrations Overview',
        href: '/docs/integrations',
        description: 'Connect an app once, then use it from tools and workflows.',
        sections: [
          { id: 'connectors-and-connections', title: 'Connectors and connections' },
          { id: 'connecting-oauth', title: 'Connecting with OAuth' },
          { id: 'connecting-api-key', title: 'Connecting with an API key' },
          { id: 'testing-a-connection', title: 'Testing a connection' },
          { id: 'actions', title: 'Actions and their parameters' },
          { id: 'resource-pickers', title: 'Resource pickers' },
          { id: 'connection-defaults', title: 'Connection defaults' },
          { id: 'health', title: 'Rate limits, errors, and health' },
        ],
        keywords: [
          'oauth', 'api key', 'connect', 'connection', 'connector', 'actions',
          'resources', 'defaults', 'rate limit',
        ],
      },
      {
        title: 'Integration Catalog',
        href: '/docs/integrations/catalog',
        description: 'Every supported app and the actions it exposes.',
        sections: [
          { id: 'crm', title: 'CRM and sales' },
          { id: 'productivity', title: 'Productivity and project management' },
          { id: 'calendar', title: 'Calendar and scheduling' },
          { id: 'messaging', title: 'Messaging and email' },
          { id: 'telephony', title: 'Telephony' },
          { id: 'data', title: 'Data and infrastructure' },
        ],
        keywords: [
          'hubspot', 'salesforce', 'notion', 'clickup', 'trello', 'monday',
          'airtable', 'slack', 'sendgrid', 'whatsapp', 'stripe', 'twilio',
          'telnyx', 'vonage', 'calendly', 'cal.com', 'google', 'supabase',
          'langfuse', 'gohighlevel', 'catalog',
        ],
      },
    ],
  },
  {
    title: 'Telephony',
    icon: 'Phone',
    short: 'Telephony',
    accent: 'teal',
    blurb: 'Phone numbers, live calls, and the record of both.',
    pages: [
      {
        title: 'Phone Numbers',
        href: '/docs/phone-numbers',
        description: 'Search, buy, assign, and configure the numbers your agents answer on.',
        sections: [
          { id: 'how-numbers-work', title: 'How numbers work' },
          { id: 'providers', title: 'Choosing a provider' },
          { id: 'searching', title: 'Searching for a number' },
          { id: 'provisioning', title: 'Buying a number' },
          { id: 'assigning', title: 'Assigning an agent' },
          { id: 'configuration', title: 'Configuration reference' },
          { id: 'releasing', title: 'Releasing a number' },
        ],
        keywords: [
          'twilio', 'telnyx', 'vonage', 'buy number', 'provision', 'area code',
          'webhook', 'sms', 'voice', 'capabilities', 'release',
        ],
      },
      {
        title: 'Calls & Call Logs',
        href: '/docs/calls',
        description: 'Review transcripts, recordings, analysis, and cost for every call.',
        sections: [
          { id: 'call-lifecycle', title: 'The call lifecycle' },
          { id: 'directions', title: 'Directions and statuses' },
          { id: 'the-call-list', title: 'The call list' },
          { id: 'call-detail', title: 'The call detail view' },
          { id: 'transcripts', title: 'Transcripts and recordings' },
          { id: 'analysis', title: 'Summary and analysis' },
          { id: 'event-log', title: 'The event log' },
          { id: 'costs', title: 'Cost breakdown' },
          { id: 'contacts', title: 'Contacts' },
        ],
        keywords: [
          'call log', 'transcript', 'recording', 'sentiment', 'intent', 'topics',
          'cost', 'disconnection reason', 'status', 'inbound', 'outbound',
        ],
      },
    ],
  },
  {
    title: 'Knowledge',
    icon: 'BookOpen',
    short: 'Knowledge',
    accent: 'rose',
    blurb: 'Documents your agents can search and answer from.',
    pages: [
      {
        title: 'Knowledge Base',
        href: '/docs/knowledge-base',
        description: 'Give agents documents to answer from, with retrieval you control.',
        sections: [
          { id: 'how-rag-works', title: 'How retrieval works' },
          { id: 'creating-a-kb', title: 'Creating a knowledge base' },
          { id: 'chunking', title: 'Chunking settings' },
          { id: 'adding-documents', title: 'Adding documents' },
          { id: 'processing', title: 'Processing status' },
          { id: 'connecting-to-agents', title: 'Connecting to an agent' },
          { id: 'link-settings', title: 'Link settings reference' },
          { id: 'testing-retrieval', title: 'Testing retrieval' },
          { id: 'writing-for-retrieval', title: 'Writing documents for retrieval' },
        ],
        keywords: [
          'rag', 'embedding', 'chunk', 'chunk size', 'overlap', 'similarity',
          'vector', 'documents', 'upload', 'pdf', 'search', 'auto-inject',
        ],
      },
    ],
  },
  {
    title: 'Workspace',
    icon: 'Settings',
    short: 'Workspace',
    accent: 'slate',
    blurb: 'Analytics, team roles, keys, and billing.',
    pages: [
      {
        title: 'Analytics',
        href: '/docs/analytics',
        description: 'Call volume, agent performance, integration health, and spend.',
        sections: [
          { id: 'dashboard', title: 'The dashboard' },
          { id: 'call-metrics', title: 'Call metrics' },
          { id: 'agent-metrics', title: 'Agent metrics' },
          { id: 'integration-metrics', title: 'Integration metrics' },
          { id: 'realtime', title: 'Real-time view' },
          { id: 'interpreting', title: 'Interpreting the numbers' },
        ],
        keywords: ['analytics', 'metrics', 'reporting', 'dashboard', 'volume', 'spend'],
      },
      {
        title: 'Team & Permissions',
        href: '/docs/workspace/team',
        description: 'Workspaces, roles, invitations, and exactly what each role may do.',
        sections: [
          { id: 'workspaces', title: 'Workspaces' },
          { id: 'roles', title: 'The four roles' },
          { id: 'permission-matrix', title: 'Permission matrix' },
          { id: 'inviting', title: 'Inviting people' },
          { id: 'changing-roles', title: 'Changing roles and removing members' },
          { id: 'ownership', title: 'Transferring ownership' },
        ],
        keywords: [
          'roles', 'owner', 'admin', 'member', 'viewer', 'permissions', 'invite',
          'team', 'workspace', 'ownership',
        ],
      },
      {
        title: 'API Keys',
        href: '/docs/workspace/api-keys',
        description: 'Programmatic access, scopes, and the ceiling a key cannot exceed.',
        sections: [
          { id: 'creating-a-key', title: 'Creating a key' },
          { id: 'using-a-key', title: 'Using a key' },
          { id: 'scopes', title: 'Scopes' },
          { id: 'the-ceiling', title: 'The permission ceiling' },
          { id: 'rotating', title: 'Rotating and revoking' },
        ],
        keywords: ['api key', 'scopes', 'authentication', 'bearer', 'rotate', 'revoke'],
      },
      {
        title: 'Billing & Plans',
        href: '/docs/workspace/billing',
        description: 'Trials, plans, usage limits, and invoices.',
        sections: [
          { id: 'free-trial', title: 'The free trial' },
          { id: 'plans', title: 'Plans and entitlements' },
          { id: 'usage', title: 'Usage and limits' },
          { id: 'changing-plan', title: 'Changing or cancelling a plan' },
          { id: 'invoices', title: 'Invoices' },
          { id: 'what-costs-money', title: 'What a call costs' },
        ],
        keywords: ['billing', 'trial', 'plan', 'subscription', 'invoice', 'usage', 'stripe'],
      },
      {
        title: 'Account Settings',
        href: '/docs/workspace/account',
        description: 'Profile, password, notifications, and onboarding.',
        sections: [
          { id: 'profile', title: 'Profile' },
          { id: 'password', title: 'Password and sign-in' },
          { id: 'notifications', title: 'Notifications' },
          { id: 'onboarding', title: 'Onboarding' },
        ],
        keywords: ['profile', 'password', 'notifications', 'account', 'onboarding'],
      },
    ],
  },
  {
    title: 'Reference',
    icon: 'Code',
    short: 'Reference',
    accent: 'indigo',
    blurb: 'The REST API, and fixes for common failures.',
    pages: [
      {
        title: 'API Reference',
        href: '/docs/api',
        description: 'REST endpoints, authentication, and conventions.',
        sections: [
          { id: 'base-url', title: 'Base URL and versioning' },
          { id: 'authentication', title: 'Authentication' },
          { id: 'conventions', title: 'Conventions' },
          { id: 'agents-endpoints', title: 'Agents' },
          { id: 'calls-endpoints', title: 'Calls' },
          { id: 'workflows-endpoints', title: 'Workflows' },
          { id: 'tools-endpoints', title: 'Tools' },
          { id: 'knowledge-endpoints', title: 'Knowledge base' },
          { id: 'integrations-endpoints', title: 'Integrations' },
          { id: 'phone-endpoints', title: 'Phone numbers' },
          { id: 'errors', title: 'Errors' },
        ],
        keywords: ['api', 'rest', 'endpoints', 'curl', 'http', 'reference'],
      },
      {
        title: 'Troubleshooting',
        href: '/docs/troubleshooting',
        description: 'The failures people hit most, and what actually fixes them.',
        sections: [
          { id: 'agent-issues', title: 'The agent sounds wrong' },
          { id: 'tool-issues', title: 'A tool never fires' },
          { id: 'workflow-issues', title: 'A workflow fails' },
          { id: 'integration-issues', title: 'An integration breaks' },
          { id: 'phone-issues', title: 'Calls do not connect' },
          { id: 'knowledge-issues', title: 'The agent ignores the knowledge base' },
        ],
        keywords: ['troubleshooting', 'errors', 'debug', 'not working', 'help', 'fix'],
      },
    ],
  },
]

/** Every page, flattened in sidebar order — the basis for prev/next paging. */
export const DOCS_PAGES: DocPageMeta[] = DOCS_NAV.flatMap((group) => group.pages)

/** Look up a page by its href. */
export function getDocPage(href: string): DocPageMeta | undefined {
  return DOCS_PAGES.find((page) => page.href === href)
}

/** The group a page belongs to, for the breadcrumb. */
export function getDocGroup(href: string): DocGroup | undefined {
  return DOCS_NAV.find((group) => group.pages.some((page) => page.href === href))
}

/** Previous and next pages in reading order. */
export function getDocNeighbours(href: string): {
  previous?: DocPageMeta
  next?: DocPageMeta
} {
  const index = DOCS_PAGES.findIndex((page) => page.href === href)
  if (index === -1) return {}
  return {
    previous: index > 0 ? DOCS_PAGES[index - 1] : undefined,
    next: index < DOCS_PAGES.length - 1 ? DOCS_PAGES[index + 1] : undefined,
  }
}

export interface SearchEntry {
  title: string
  href: string
  description: string
  group: string
  /** Set when the entry is a heading rather than a whole page. */
  section?: string
  haystack: string
}

/**
 * Flat search index over pages and their headings.
 *
 * Built once at module load — the corpus is static, so rebuilding it per
 * keystroke would burn cycles for an identical result.
 */
export const DOCS_SEARCH_INDEX: SearchEntry[] = DOCS_NAV.flatMap((group) =>
  group.pages.flatMap((page) => {
    const pageEntry: SearchEntry = {
      title: page.title,
      href: page.href,
      description: page.description,
      group: group.title,
      haystack: [
        page.title,
        page.description,
        group.title,
        ...(page.keywords ?? []),
        ...page.sections.map((section) => section.title),
      ]
        .join(' ')
        .toLowerCase(),
    }

    const sectionEntries: SearchEntry[] = page.sections.map((section) => ({
      title: section.title,
      href: `${page.href}#${section.id}`,
      description: page.title,
      group: group.title,
      section: page.title,
      haystack: `${section.title} ${page.title} ${group.title}`.toLowerCase(),
    }))

    return [pageEntry, ...sectionEntries]
  })
)

/**
 * Rank index entries against a query.
 *
 * Scoring is deliberately simple: every whitespace-separated term must appear
 * somewhere in the entry, and entries whose *title* matches rank above ones
 * that only matched on keywords. Whole-page hits outrank their own headings so
 * a search for "tools" lands on the overview, not an arbitrary subsection.
 */
export function searchDocs(query: string, limit = 8): SearchEntry[] {
  const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean)
  if (terms.length === 0) return []

  const scored = DOCS_SEARCH_INDEX.map((entry) => {
    if (!terms.every((term) => entry.haystack.includes(term))) return null

    const title = entry.title.toLowerCase()
    let score = 0
    for (const term of terms) {
      if (title === term) score += 12
      else if (title.startsWith(term)) score += 8
      else if (title.includes(term)) score += 5
      else score += 1
    }
    if (!entry.section) score += 3

    return { entry, score }
  }).filter((hit): hit is { entry: SearchEntry; score: number } => hit !== null)

  return scored
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((hit) => hit.entry)
}
