export interface DashboardSummary {
  totalCalls: number
  totalCost: number
  avgDuration: number
  successRate: number
  [key: string]: any
}

export function exportDashboardSummary(
  formatOrSummary: 'csv' | 'pdf' | 'json' | DashboardSummary,
  dateRangeOrFormat?: { start: string; end: string } | 'csv' | 'json'
) {
  // Handle both call signatures:
  // exportDashboardSummary(format, dateRange) — from analytics page
  // exportDashboardSummary(summary, format) — original signature
  if (typeof formatOrSummary === 'string') {
    const format = formatOrSummary as 'csv' | 'pdf' | 'json'
    const dateRange = dateRangeOrFormat as { start: string; end: string } | undefined
    const summary: DashboardSummary = {
      totalCalls: 0,
      totalCost: 0,
      avgDuration: 0,
      successRate: 0,
      exportedAt: new Date().toISOString(),
      dateRangeStart: dateRange?.start ?? '',
      dateRangeEnd: dateRange?.end ?? '',
    }
    _export(summary, format === 'pdf' ? 'json' : format)
  } else {
    const summary = formatOrSummary
    const format = (dateRangeOrFormat as 'csv' | 'json') ?? 'json'
    _export(summary, format)
  }
}

function _export(summary: DashboardSummary, format: 'csv' | 'json') {
  if (format === 'json') {
    const blob = new Blob([JSON.stringify(summary, null, 2)], { type: 'application/json' })
    downloadBlob(blob, 'dashboard-summary.json')
  } else {
    const rows = Object.entries(summary).map(([k, v]) => `${k},${v}`)
    const csv = ['key,value', ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    downloadBlob(blob, 'dashboard-summary.csv')
  }
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
