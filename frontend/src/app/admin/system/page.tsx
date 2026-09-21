'use client'

import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, Database, RefreshCw, Server, XCircle } from 'lucide-react'
import { adminApi } from '@/lib/admin'
import { AdminButton, Callout, Detail, PageHeader, Panel, errorText, humanize, timeAgo } from '@/components/admin/ui'

function Check({ ok, label, detail }: { ok: boolean; label: string; detail?: React.ReactNode }) {
  return (
    <li className="flex items-start gap-3 py-2.5">
      {ok ? <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-600" /> : <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-rose-600" />}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-slate-800">{label}</p>
        {detail && <p className="text-xs text-slate-500">{detail}</p>}
      </div>
      <span className={`text-xs font-medium ${ok ? 'text-emerald-700' : 'text-rose-700'}`}>{ok ? 'OK' : 'Problem'}</span>
    </li>
  )
}

export default function SystemPage() {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['admin', 'health'],
    queryFn: adminApi.health,
    refetchInterval: 30_000,
  })

  return (
    <>
      <PageHeader
        title="System Health"
        description="Live status of the services this deployment depends on. Refreshes every 30 seconds."
        actions={<AdminButton icon={RefreshCw} loading={isFetching && !isLoading} onClick={() => refetch()}>Refresh</AdminButton>}
      />
      {error ? <Callout tone="danger" title="Health check failed">{errorText(error)}</Callout> : null}
      {isLoading && <div className="h-64 animate-pulse rounded-xl bg-white" />}

      {data && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Panel title="Infrastructure">
            <ul className="divide-y divide-slate-100">
              <Check ok={data.database.ok} label="Database" detail={data.database.ok ? `${data.database.latency_ms} ms` : data.database.error} />
              <Check
                ok={data.redis.ok}
                label="Redis"
                detail={data.redis.ok ? `${data.redis.latency_ms} ms` : `${data.redis.error ?? 'Unavailable'} — rate limiting falls back to per-process counters`}
              />
              {data.schedulers.map((s) => (
                <Check key={s.name} ok={s.running} label={s.name} detail={s.running ? 'Running in this API process' : 'Not running in this API process'} />
              ))}
            </ul>
          </Panel>

          <Panel title="Deployment">
            <dl className="grid grid-cols-2 gap-4">
              <Detail label="Environment"><span className="inline-flex items-center gap-1.5"><Server className="h-3.5 w-3.5 text-slate-400" />{data.app.environment}</span></Detail>
              <Detail label="Version">{data.app.version}</Detail>
              <Detail label="Debug mode">{data.app.debug ? 'On' : 'Off'}</Detail>
              <Detail label="Email delivery">{humanize(data.email_provider)}</Detail>
              <Detail label="Dashboard settings applied">
                <span className="inline-flex items-center gap-1.5"><Database className="h-3.5 w-3.5 text-slate-400" />{data.runtime_settings.overrides_applied}</span>
              </Detail>
              <Detail label="Settings last checked">{timeAgo(data.runtime_settings.checked_at)}</Detail>
            </dl>
            {Object.keys(data.runtime_settings.errors).length > 0 && (
              <div className="mt-4">
                <Callout tone="danger" title="Some dashboard settings could not be applied">
                  {Object.entries(data.runtime_settings.errors).map(([k, v]) => (
                    <p key={k}><span className="font-mono">{k}</span>: {v}</p>
                  ))}
                </Callout>
              </div>
            )}
          </Panel>

          <Panel title="Server secrets" description="Set only in the server environment; never stored in the database.">
            <ul className="divide-y divide-slate-100">
              {data.bootstrap.map((b) => (
                <Check key={b.key} ok={b.ok} label={b.key} detail={b.note} />
              ))}
            </ul>
          </Panel>

          <Panel
            title="Providers"
            actions={<Link href="/admin/api-keys" className="text-xs font-medium text-brand-700 hover:underline">Manage keys</Link>}
          >
            <ul className="divide-y divide-slate-100">
              {data.providers.map((p) => (
                <Check key={p.id} ok={p.configured} label={p.label} detail={p.configured ? 'Credentials present' : 'Missing credentials'} />
              ))}
            </ul>
          </Panel>
        </div>
      )}
    </>
  )
}
