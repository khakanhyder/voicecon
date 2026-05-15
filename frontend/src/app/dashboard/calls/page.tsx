'use client'

export default function CallsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Calls</h1>
        <p className="text-muted-foreground">
          View and manage your call history
        </p>
      </div>

      <div className="rounded-lg border bg-card p-8 text-center">
        <div className="mx-auto max-w-md space-y-4">
          <div className="text-6xl">📞</div>
          <h2 className="text-2xl font-semibold">No calls yet</h2>
          <p className="text-muted-foreground">
            Your call history will appear here once you start making calls with your agents
          </p>
        </div>
      </div>
    </div>
  )
}
