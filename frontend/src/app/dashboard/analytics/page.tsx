'use client'

import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '@/lib/api'
import {
  Phone, Clock, DollarSign, TrendingUp, TrendingDown,
  Users, Zap, RefreshCw, Download, Activity,
  CheckCircle, XCircle, AlertCircle, BarChart3,
} from 'lucide-react'
import { exportDashboardSummary } from '@/lib/analytics-export'

// ---- API types matching the backend ----
interface DashboardData {
  realtime: {
    active_calls: number
    calls_today: number
    calls_last_hour: number
    cost_today: number
    system_health: string
    error_rate: number
  }
  today: {
    total_calls: number
    total_minutes: number
    total_cost: number
    success_rate: number
    sentiment_score: number | null
  }
  agents: {
    active_count: number
    total_interactions: number
    top_performers: any[]
  }
  integrations: {
    active_count: number
    total_executions: number
    avg_health: number | null
  }
  trends: {
    call_volume_change: number
    cost_change: number
    sentiment_change: number
  }
}

interface CallMetrics {
  total_calls: number
  completed_calls: number
  failed_calls: number
  missed_calls: number
  total_duration_seconds: number
  avg_duration_seconds: number | null
  total_cost: number
  avg_cost_per_call: number | null
  success_rate: number | null
  avg_sentiment_score: number | null
  positive_sentiment_count: number
  negative_sentiment_count: number
  neutral_sentiment_count: number
}

interface RealtimeMetrics {
  current_active_calls: number
  calls_today: number
  calls_last_hour: number
  calls_last_5_minutes: number
  cost_today: number
  cost_last_hour: number
  active_agents: number
  active_integrations: number
  system_health: string
  error_rate_last_hour: number | null
  recent_calls: any[]
  last_updated: string
}

// ---- Helpers ----
function fmt(n: number | null | undefined, decimals = 0) {
  if (n == null) return '—'
  return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

function fmtCost(n: number | null | undefined) {
  if (n == null) return '—'
  return `$${n.toFixed(2)}`
}

function fmtDuration(seconds: number | null | undefined) {
  if (!seconds) return '0s'
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return s > 0 ? `${m}m ${s}s` : `${m}m`
}

function fmtPct(n: number | null | undefined) {
  if (n == null) return '—'
  return `${n.toFixed(1)}%`
}

function TrendBadge({ value }: { value: number }) {
  if (value === 0) return <span className="text-xs text-slate-400">No change</span>
  const up = value > 0
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${up ? 'text-emerald-600' : 'text-red-500'}`}>
      {up ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
      {Math.abs(value)}%
    </span>
  )
}

function HealthBadge({ health }: { health: string }) {
  const map: Record<string, { label: string; color: string; icon: typeof CheckCircle }> = {
    healthy: { label: 'Healthy', color: 'text-emerald-700 bg-emerald-50 border-emerald-200', icon: CheckCircle },
    degraded: { label: 'Degraded', color: 'text-amber-700 bg-amber-50 border-amber-200', icon: AlertCircle },
    down: { label: 'Down', color: 'text-red-700 bg-red-50 border-red-200', icon: XCircle },
  }
  const cfg = map[health] || map.healthy
  const Icon = cfg.icon
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${cfg.color}`}>
      <Icon className="h-3.5 w-3.5" />
      {cfg.label}
    </span>
  )
}

// ---- Skeleton loader ----
function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse bg-slate-200 rounded-lg ${className}`} />
}

// ---- Main component ----
export default function AnalyticsPage() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [callMetrics, setCallMetrics] = useState<CallMetrics | null>(null)
  const [realtime, setRealtime] = useState<RealtimeMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [dateRange, setDateRange] = useState({
    start: new Date(Date.now() - 30 * 86_400_000).toISOString().split('T')[0],
    end: new Date().toISOString().split('T')[0],
  })

  const fetchAll = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    try {
      const [dashRes, metricsRes, rtRes] = await Promise.allSettled([
        apiClient.get<DashboardData>('/api/v1/analytics/dashboard'),
        apiClient.get<CallMetrics>(`/api/v1/analytics/call-metrics?start_date=${dateRange.start}&end_date=${dateRange.end}`),
        apiClient.get<RealtimeMetrics>('/api/v1/analytics/realtime'),
      ])

      if (dashRes.status === 'fulfilled') setDashboard(dashRes.value.data)
      if (metricsRes.status === 'fulfilled') setCallMetrics(metricsRes.value.data)
      if (rtRes.status === 'fulfilled') setRealtime(rtRes.value.data)
      setLastUpdated(new Date())
    } catch (e) {
      console.error('Analytics fetch error:', e)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [dateRange.start, dateRange.end])

  useEffect(() => { fetchAll() }, [fetchAll])

  // Auto-refresh every 60s
  useEffect(() => {
    const id = setInterval(() => fetchAll(true), 60_000)
    return () => clearInterval(id)
  }, [fetchAll])

  const handleExport = () => {
    if (!callMetrics) return
    exportDashboardSummary({
      totalCalls: callMetrics.total_calls,
      totalCost: callMetrics.total_cost,
      avgDuration: callMetrics.avg_duration_seconds ?? 0,
      successRate: callMetrics.success_rate ?? 0,
    }, 'csv')
  }

  return (
    <div className="space-y-6">
      {/* Header controls */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {lastUpdated && (
            <span className="text-xs text-slate-400">Updated {lastUpdated.toLocaleTimeString()}</span>
          )}
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">
          <input type="date" value={dateRange.start} onChange={e => setDateRange(r => ({ ...r, start: e.target.value }))}
            className="border-0 outline-none text-slate-700 bg-transparent text-sm" />
          <span className="text-slate-300">→</span>
          <input type="date" value={dateRange.end} onChange={e => setDateRange(r => ({ ...r, end: e.target.value }))}
            className="border-0 outline-none text-slate-700 bg-transparent text-sm" />
        </div>
        <button
          onClick={() => fetchAll(true)}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </button>
        <button
          onClick={handleExport}
          className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
        >
          <Download className="h-4 w-4" />
          Export CSV
        </button>
      </div>

      {/* System health banner */}
      {loading ? (
        <Skeleton className="h-16 w-full" />
      ) : (
        <div className={`flex flex-wrap items-center justify-between gap-4 rounded-xl border p-4 ${
          dashboard?.realtime.system_health === 'healthy' ? 'bg-emerald-50 border-emerald-200' :
          dashboard?.realtime.system_health === 'degraded' ? 'bg-amber-50 border-amber-200' :
          'bg-red-50 border-red-200'
        }`}>
          <div className="flex items-center gap-3">
            <span className={`h-2.5 w-2.5 rounded-full animate-pulse ${
              dashboard?.realtime.system_health === 'healthy' ? 'bg-emerald-500' :
              dashboard?.realtime.system_health === 'degraded' ? 'bg-amber-500' : 'bg-red-500'
            }`} />
            <span className="font-semibold text-slate-800">System Status</span>
            <HealthBadge health={dashboard?.realtime.system_health ?? 'healthy'} />
          </div>
          <div className="flex flex-wrap items-center gap-6 text-sm text-slate-600">
            <span>Active calls: <strong className="text-slate-900">{dashboard?.realtime.active_calls ?? 0}</strong></span>
            <span>Calls/hour: <strong className="text-slate-900">{realtime?.calls_last_hour ?? 0}</strong></span>
            <span>Active agents: <strong className="text-slate-900">{realtime?.active_agents ?? 0}</strong></span>
            <span>Error rate: <strong className="text-slate-900">{fmtPct(realtime?.error_rate_last_hour ?? 0)}</strong></span>
          </div>
        </div>
      )}

      {/* KPI cards — 4 columns */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            label: 'Total Calls',
            value: loading ? null : fmt(callMetrics?.total_calls),
            sub: loading ? null : `${fmt(callMetrics?.completed_calls)} completed`,
            icon: Phone,
            color: 'text-blue-600',
            bg: 'bg-blue-50',
            trend: dashboard?.trends.call_volume_change,
          },
          {
            label: 'Avg Duration',
            value: loading ? null : fmtDuration(callMetrics?.avg_duration_seconds),
            sub: loading ? null : `Total: ${fmtDuration(callMetrics?.total_duration_seconds)}`,
            icon: Clock,
            color: 'text-violet-600',
            bg: 'bg-violet-50',
            trend: null,
          },
          {
            label: 'Success Rate',
            value: loading ? null : fmtPct(callMetrics?.success_rate),
            sub: loading ? null : `${fmt(callMetrics?.failed_calls)} failed`,
            icon: TrendingUp,
            color: 'text-emerald-600',
            bg: 'bg-emerald-50',
            trend: null,
          },
          {
            label: 'Total Cost',
            value: loading ? null : fmtCost(callMetrics?.total_cost),
            sub: loading ? null : `Avg ${fmtCost(callMetrics?.avg_cost_per_call)}/call`,
            icon: DollarSign,
            color: 'text-amber-600',
            bg: 'bg-amber-50',
            trend: dashboard?.trends.cost_change,
          },
        ].map((card) => {
          const Icon = card.icon
          return (
            <div key={card.label} className="bg-white rounded-xl border border-slate-200 p-5 card-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${card.bg}`}>
                  <Icon className={`h-5 w-5 ${card.color}`} />
                </div>
                {card.trend != null && <TrendBadge value={card.trend} />}
              </div>
              {loading ? (
                <>
                  <Skeleton className="h-7 w-24 mb-1" />
                  <Skeleton className="h-4 w-32" />
                </>
              ) : (
                <>
                  <div className="text-2xl font-bold text-slate-900">{card.value}</div>
                  <div className="text-xs text-slate-500 mt-0.5">{card.sub}</div>
                </>
              )}
              <div className="text-sm text-slate-500 mt-2 font-medium">{card.label}</div>
            </div>
          )
        })}
      </div>

      {/* Middle row: Call breakdown + Sentiment + Today */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Call outcomes */}
        <div className="bg-white rounded-xl border border-slate-200 card-shadow p-5 lg:col-span-1">
          <h3 className="text-sm font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-slate-400" />
            Call Outcomes
          </h3>
          {loading ? (
            <div className="space-y-3">
              {[1,2,3,4].map(i => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : (
            <div className="space-y-3">
              {[
                { label: 'Completed', value: callMetrics?.completed_calls ?? 0, color: 'bg-emerald-500', text: 'text-emerald-700' },
                { label: 'Failed', value: callMetrics?.failed_calls ?? 0, color: 'bg-red-400', text: 'text-red-600' },
                { label: 'Missed', value: callMetrics?.missed_calls ?? 0, color: 'bg-amber-400', text: 'text-amber-600' },
              ].map((row) => {
                const total = callMetrics?.total_calls || 1
                const pct = Math.round((row.value / total) * 100)
                return (
                  <div key={row.label}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-slate-600">{row.label}</span>
                      <span className={`text-xs font-semibold ${row.text}`}>{row.value} <span className="text-slate-400 font-normal">({pct}%)</span></span>
                    </div>
                    <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${row.color} transition-all duration-500`} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )
              })}

              <div className="pt-3 border-t border-slate-100 mt-3">
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span>Total calls in period</span>
                  <span className="font-semibold text-slate-800">{fmt(callMetrics?.total_calls)}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Sentiment */}
        <div className="bg-white rounded-xl border border-slate-200 card-shadow p-5">
          <h3 className="text-sm font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Activity className="h-4 w-4 text-slate-400" />
            Sentiment Analysis
          </h3>
          {loading ? (
            <div className="space-y-3">
              {[1,2,3].map(i => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : callMetrics?.avg_sentiment_score == null ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Activity className="h-8 w-8 text-slate-200 mb-2" />
              <p className="text-sm text-slate-400">No sentiment data yet</p>
              <p className="text-xs text-slate-300 mt-1">Will appear after calls are processed</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="text-center">
                <div className="text-4xl font-bold text-slate-900">{(callMetrics.avg_sentiment_score * 100).toFixed(0)}</div>
                <div className="text-xs text-slate-500 mt-1">Avg sentiment score (out of 100)</div>
              </div>
              {[
                { label: 'Positive', value: callMetrics.positive_sentiment_count, color: 'bg-emerald-500', text: 'text-emerald-600' },
                { label: 'Neutral', value: callMetrics.neutral_sentiment_count, color: 'bg-slate-300', text: 'text-slate-500' },
                { label: 'Negative', value: callMetrics.negative_sentiment_count, color: 'bg-red-400', text: 'text-red-500' },
              ].map((row) => {
                const total = (callMetrics.positive_sentiment_count + callMetrics.neutral_sentiment_count + callMetrics.negative_sentiment_count) || 1
                const pct = Math.round((row.value / total) * 100)
                return (
                  <div key={row.label}>
                    <div className="flex justify-between mb-1">
                      <span className="text-xs font-medium text-slate-600">{row.label}</span>
                      <span className={`text-xs font-semibold ${row.text}`}>{pct}%</span>
                    </div>
                    <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${row.color}`} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Today snapshot */}
        <div className="bg-white rounded-xl border border-slate-200 card-shadow p-5">
          <h3 className="text-sm font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Zap className="h-4 w-4 text-slate-400" />
            Today&apos;s Snapshot
          </h3>
          {loading ? (
            <div className="space-y-3">
              {[1,2,3,4,5].map(i => <Skeleton key={i} className="h-8 w-full" />)}
            </div>
          ) : (
            <div className="divide-y divide-slate-100 space-y-0">
              {[
                { label: 'Calls today', value: fmt(dashboard?.today.total_calls) },
                { label: 'Minutes today', value: fmt(dashboard?.today.total_minutes) + 'm' },
                { label: 'Cost today', value: fmtCost(dashboard?.today.total_cost) },
                { label: 'Success rate', value: fmtPct(dashboard?.today.success_rate) },
                { label: 'Active agents', value: fmt(dashboard?.agents.active_count) },
                { label: 'Active integrations', value: fmt(dashboard?.integrations.active_count) },
              ].map((row) => (
                <div key={row.label} className="flex items-center justify-between py-2.5">
                  <span className="text-xs text-slate-500">{row.label}</span>
                  <span className="text-sm font-semibold text-slate-800">{row.value}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Real-time + Top performers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Real-time metrics */}
        <div className="bg-white rounded-xl border border-slate-200 card-shadow p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              Real-time Metrics
            </h3>
            {realtime?.last_updated && (
              <span className="text-xs text-slate-400">
                {new Date(realtime.last_updated).toLocaleTimeString()}
              </span>
            )}
          </div>
          {loading ? (
            <div className="grid grid-cols-2 gap-3">
              {[1,2,3,4].map(i => <Skeleton key={i} className="h-20" />)}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Active calls', value: fmt(realtime?.current_active_calls), icon: Phone, color: 'text-blue-600', bg: 'bg-blue-50' },
                { label: 'Last 5 min', value: fmt(realtime?.calls_last_5_minutes), icon: Clock, color: 'text-violet-600', bg: 'bg-violet-50' },
                { label: 'Cost last hour', value: fmtCost(realtime?.cost_last_hour), icon: DollarSign, color: 'text-amber-600', bg: 'bg-amber-50' },
                { label: 'Active agents', value: fmt(realtime?.active_agents), icon: Users, color: 'text-emerald-600', bg: 'bg-emerald-50' },
              ].map((item) => {
                const Icon = item.icon
                return (
                  <div key={item.label} className={`rounded-lg p-3 ${item.bg}`}>
                    <Icon className={`h-4 w-4 ${item.color} mb-2`} />
                    <div className={`text-xl font-bold ${item.color}`}>{item.value}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{item.label}</div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Top agents */}
        <div className="bg-white rounded-xl border border-slate-200 card-shadow p-5">
          <h3 className="text-sm font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Users className="h-4 w-4 text-slate-400" />
            Top Performing Agents
          </h3>
          {loading ? (
            <div className="space-y-3">
              {[1,2,3].map(i => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : (dashboard?.agents.top_performers ?? []).length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Users className="h-8 w-8 text-slate-200 mb-2" />
              <p className="text-sm text-slate-400">No agent data yet</p>
              <p className="text-xs text-slate-300 mt-1">Create agents and make calls to see performance</p>
            </div>
          ) : (
            <div className="space-y-2">
              {(dashboard?.agents.top_performers ?? []).map((agent: any, i: number) => (
                <div key={agent.id ?? i} className="flex items-center gap-3 rounded-lg border border-slate-100 p-3">
                  <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-700 text-xs font-bold">
                    #{i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800 truncate">{agent.name ?? `Agent ${i + 1}`}</p>
                    <p className="text-xs text-slate-400">{agent.total_calls ?? 0} calls</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-emerald-600">{fmtPct(agent.success_rate)}</p>
                    <p className="text-xs text-slate-400">success</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
