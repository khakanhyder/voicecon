import type { Chatbot } from '@/lib/chatbots'

/** Whether a chatbot is showing on sites, and if not, why not. */
export function ChatbotStatus({ chatbot }: { chatbot: Chatbot }) {
  const [label, style] = !chatbot.agent
    ? ['Needs an agent', 'bg-amber-50 text-amber-700 ring-amber-600/20']
    : !chatbot.enabled
      ? ['Off', 'bg-slate-100 text-slate-600 ring-slate-500/15']
      : !chatbot.agent.is_active
        ? ['Agent paused', 'bg-amber-50 text-amber-700 ring-amber-600/20']
        : ['Live', 'bg-emerald-50 text-emerald-700 ring-emerald-600/20']
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${style}`}>
      {chatbot.live && <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />}
      {label}
    </span>
  )
}
