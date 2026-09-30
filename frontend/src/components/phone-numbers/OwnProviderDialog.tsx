'use client'

import Link from 'next/link'
import { ArrowRight, CheckCircle2, Download, Info, Plug } from 'lucide-react'
import { PhoneDialog } from './PhoneDialog'
import { getIconUrl } from '@/components/integrations/IntegrationCard'
import type { OwnProvider, PurchaseOptions } from '@/lib/phoneNumbers'

interface Props {
  open: boolean
  onClose: () => void
  options: PurchaseOptions | null
  /** Continue to buying a number on one of the connected accounts. */
  onUseAccount: (provider: OwnProvider) => void
  /** Bring in numbers already on one of the connected accounts. */
  onImportFrom: (provider: OwnProvider) => void
}

/**
 * The advanced flow: bring your own carrier account.
 *
 * This is deliberately the only place provider names appear. Connecting
 * happens on the provider's Integrations page (credentials, test, save);
 * once connected, the account shows here: numbers already on it can be added,
 * and new ones bought on it.
 */
export function OwnProviderDialog({ open, onClose, options, onUseAccount, onImportFrom }: Props) {
  const own = options?.own_providers ?? []
  const supported = options?.supported_providers ?? []

  return (
    <PhoneDialog
      open={open}
      onClose={onClose}
      size="md"
      title="Connect your own provider"
      description="Already have a Twilio or Telnyx account? Use your own numbers and billing."
      icon={<Plug className="h-5 w-5" />}
      footer={
        <button
          type="button"
          onClick={onClose}
          className="inline-flex h-11 items-center justify-center rounded-xl border border-slate-200 bg-white px-5 text-[14px] font-semibold text-slate-700 hover:bg-slate-50"
        >
          Close
        </button>
      }
    >
      <div className="space-y-6">
        {own.length > 0 && (
          <section>
            <h3 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-slate-500">Connected accounts</h3>
            <ul className="space-y-2">
              {own.map((p) => (
                <li
                  key={p.connection_id ?? p.slug}
                  className="flex flex-col gap-3 rounded-xl border border-slate-200 p-4 sm:flex-row sm:items-center"
                >
                  <ProviderLogo slug={p.slug} name={p.name} />
                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-1.5 text-[14px] font-semibold text-slate-900">
                      {p.name}
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" aria-label="Connected" />
                    </p>
                    <p className="truncate text-[12px] text-slate-500">{p.connection_name || 'Your account'}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => onImportFrom(p)}
                      className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl bg-[#0F6A59] px-4 text-[13px] font-semibold text-white hover:bg-[#0c5a4b]"
                    >
                      <Download className="h-4 w-4" /> Use my numbers
                    </button>
                    <button
                      type="button"
                      onClick={() => onUseAccount(p)}
                      className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 text-[13px] font-semibold text-slate-700 hover:bg-slate-50"
                    >
                      Buy new <ArrowRight className="h-4 w-4" />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section>
          <h3 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-slate-500">
            {own.length > 0 ? 'Connect another' : 'Supported providers'}
          </h3>
          <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {supported.map((p) => (
              <li key={p.slug}>
                <Link
                  href={`/dashboard/integrations/${p.slug}`}
                  className="group flex h-full items-start gap-3 rounded-xl border border-slate-200 p-4 transition-colors hover:border-[#0F6A59]/40 hover:bg-[#0F6A59]/[0.03]"
                >
                  <ProviderLogo slug={p.slug} name={p.name} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2 text-[14px] font-semibold text-slate-900">
                      {p.name}
                      {p.connected && (
                        <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
                          Connected
                        </span>
                      )}
                    </span>
                    <span className="mt-0.5 block text-[12px] leading-relaxed text-slate-500">{p.description}</span>
                    <span className="mt-2 inline-flex items-center gap-1 text-[12px] font-semibold text-[#0F6A59]">
                      {p.connected ? 'Manage' : 'Connect'} <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>

        <p className="flex items-start gap-2 rounded-xl bg-slate-50 px-4 py-3 text-[12px] leading-relaxed text-slate-600">
          <Info className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-slate-400" />
          Numbers on your own account — ones you already have and ones you buy here — are billed by your provider, not by Voicecon. You’ll need your
          account’s API credentials to connect it.
        </p>
      </div>
    </PhoneDialog>
  )
}

function ProviderLogo({ slug, name }: { slug: string; name: string }) {
  const src = getIconUrl(slug)
  return (
    <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-white">
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" className="h-6 w-6 object-contain" />
      ) : (
        <span className="text-[13px] font-bold text-slate-600">{name.charAt(0)}</span>
      )}
    </span>
  )
}
