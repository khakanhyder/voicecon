'use client'

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { AlertCircle, Bot, Check, Loader2, MessageSquare, Phone, PhoneCall, Plus, RefreshCw } from 'lucide-react'
import { PhoneDialog } from './PhoneDialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  type OwnAccountNumber, type OwnProvider, type PhoneNumber,
  formatPhoneNumber, friendlyPhoneError, hasSms, hasVoice, phoneNumberService,
} from '@/lib/phoneNumbers'

interface Props {
  /** The connected account to list; null closes the dialog. */
  provider: OwnProvider | null
  onClose: () => void
  agents: { id: string; name: string; is_active?: boolean }[]
  onImported: (number: PhoneNumber) => void
  /** The account has no numbers yet: go and buy one on it. */
  onBuy: (provider: OwnProvider) => void
}

// Radix Select can't use an empty value, so "attach later" gets a sentinel.
const LATER = '__later__'

const selectTriggerClass =
  'h-11 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-[14px] text-slate-900 outline-none transition-colors hover:border-slate-300 focus:border-[#0F6A59] focus:ring-2 focus:ring-[#0F6A59]/15 data-[state=open]:border-[#0F6A59] data-[state=open]:ring-2 data-[state=open]:ring-[#0F6A59]/15'

/**
 * Numbers already on the user's own carrier account — including ones they
 * bought directly with the carrier — and a one-click way to bring each into
 * Voicecon. Nothing is bought here and nothing is released later: removing an
 * added number from Voicecon leaves it on their account.
 */
export function ImportNumbersDialog({ provider, onClose, agents, onImported, onBuy }: Props) {
  const [numbers, setNumbers] = useState<OwnAccountNumber[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [agentId, setAgentId] = useState('')
  const [adding, setAdding] = useState<string | null>(null)

  const connectionId = provider?.connection_id ?? null
  const activeAgents = agents.filter((a) => a.is_active !== false)

  const load = useCallback(async () => {
    if (!connectionId) return
    setLoading(true)
    setError(null)
    try {
      setNumbers(await phoneNumberService.ownAccountNumbers(connectionId))
    } catch (e) {
      setError(friendlyPhoneError(e, 'own_list'))
    } finally {
      setLoading(false)
    }
  }, [connectionId])

  useEffect(() => {
    if (!connectionId) return
    setNumbers([])
    setAgentId(activeAgents.length === 1 ? activeAgents[0].id : '')
    load()
    // Only when a different account is opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectionId, load])

  const add = async (num: OwnAccountNumber) => {
    if (!connectionId) return
    setAdding(num.phone_number)
    try {
      const created = await phoneNumberService.importNumber({
        connection_id: connectionId,
        phone_number: num.phone_number,
        agent_id: agentId || null,
      })
      setNumbers((list) =>
        list.map((n) =>
          n.phone_number === num.phone_number ? { ...n, phone_number_id: created.id, available: false } : n
        )
      )
      const agentName = agents.find((a) => a.id === created.agent_id)?.name
      toast.success(
        agentName
          ? `${formatPhoneNumber(num.phone_number)} added — calls now go to ${agentName}`
          : `${formatPhoneNumber(num.phone_number)} added — attach an assistant when you’re ready`
      )
      onImported(created)
    } catch (e) {
      toast.error(friendlyPhoneError(e, 'import'))
    } finally {
      setAdding(null)
    }
  }

  const name = provider?.name ?? 'provider'

  return (
    <PhoneDialog
      open={provider !== null}
      onClose={onClose}
      busy={adding !== null}
      size="md"
      title={`Numbers on your ${name} account`}
      description={
        <>
          Add numbers you already own to Voicecon. They stay on your {name} account and billing — removing one
          later only disconnects it from Voicecon.
        </>
      }
      icon={<Phone className="h-5 w-5" />}
      footer={
        <button
          type="button"
          onClick={onClose}
          disabled={adding !== null}
          className="inline-flex h-11 items-center justify-center rounded-xl border border-slate-200 bg-white px-5 text-[14px] font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          Done
        </button>
      }
    >
      <div className="space-y-5">
        <div>
          <label htmlFor="import-agent" className="mb-1.5 block text-[13px] font-semibold text-slate-700">
            Who answers the numbers you add?
          </label>
          <Select value={agentId || LATER} onValueChange={(v) => setAgentId(v === LATER ? '' : v)}>
            <SelectTrigger id="import-agent" className={selectTriggerClass}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent searchable={activeAgents.length > 6}>
              <SelectItem value={LATER} textValue="Attach later">
                <span className="text-slate-500">Attach an assistant later</span>
              </SelectItem>
              {activeAgents.map((a) => (
                <SelectItem key={a.id} value={a.id} textValue={a.name}>
                  <span className="flex items-center gap-2">
                    <Bot className="h-3.5 w-3.5 flex-shrink-0 text-[#0F6A59]" />
                    {a.name}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="mt-1.5 text-[12px] text-slate-500">You can attach, change or detach it any time from the Phone Numbers list.</p>
        </div>

        {loading ? (
          <ul className="space-y-2" aria-busy="true">
            {[1, 2, 3].map((i) => (
              <li key={i} className="flex animate-pulse items-center gap-3 rounded-xl border border-slate-200 p-4">
                <div className="h-9 w-9 rounded-lg bg-slate-100" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-36 rounded bg-slate-100" />
                  <div className="h-3 w-20 rounded bg-slate-100" />
                </div>
              </li>
            ))}
          </ul>
        ) : error ? (
          <div role="alert" className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-500" />
            <p className="flex-1 text-[13px] leading-relaxed text-red-800">{error}</p>
            <button
              type="button"
              onClick={load}
              className="inline-flex flex-shrink-0 items-center gap-1 text-[13px] font-semibold text-red-700 hover:underline"
            >
              <RefreshCw className="h-3.5 w-3.5" /> Retry
            </button>
          </div>
        ) : numbers.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 px-5 py-8 text-center">
            <p className="text-[14px] font-semibold text-slate-800">No numbers on this account yet</p>
            <p className="mt-1 text-[13px] text-slate-500">Buy one on your {name} account to get started.</p>
            {provider && (
              <button
                type="button"
                onClick={() => onBuy(provider)}
                className="mt-4 inline-flex h-10 items-center gap-1.5 rounded-xl bg-[#0F6A59] px-4 text-[13px] font-semibold text-white hover:bg-[#0c5a4b]"
              >
                <Plus className="h-4 w-4" /> Buy a number here
              </button>
            )}
          </div>
        ) : (
          <ul className="space-y-2">
            {numbers.map((num) => {
              const added = num.phone_number_id !== null
              const elsewhere = !added && !num.available
              return (
                <li key={num.phone_number} className="flex items-center gap-3 rounded-xl border border-slate-200 p-3.5">
                  <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-[#0F6A59]/10">
                    <Phone className="h-4 w-4 text-[#0F6A59]" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[14px] font-semibold tabular-nums text-slate-900">{formatPhoneNumber(num.phone_number)}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-1">
                      {num.friendly_name && num.friendly_name !== num.phone_number && (
                        <span className="mr-1 truncate text-[12px] text-slate-500">{num.friendly_name}</span>
                      )}
                      {hasVoice(num.capabilities) && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">
                          <PhoneCall className="h-3 w-3" /> Voice
                        </span>
                      )}
                      {hasSms(num.capabilities) && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">
                          <MessageSquare className="h-3 w-3" /> SMS
                        </span>
                      )}
                    </div>
                  </div>
                  {added ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 text-[12px] font-semibold text-emerald-700">
                      <Check className="h-3.5 w-3.5" /> Added
                    </span>
                  ) : elsewhere ? (
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[12px] font-medium text-slate-500">
                      In another workspace
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => add(num)}
                      disabled={adding !== null || !hasVoice(num.capabilities)}
                      title={hasVoice(num.capabilities) ? undefined : 'This number can’t take voice calls'}
                      className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-[#0F6A59] px-3.5 text-[13px] font-semibold text-white transition-colors hover:bg-[#0c5a4b] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {adding === num.phone_number ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                      Add
                    </button>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </PhoneDialog>
  )
}
