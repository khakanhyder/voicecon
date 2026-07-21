'use client'

import { useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  MessageSquare,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export interface StepResult {
  step_id: string
  step_name: string
  status: 'success' | 'failed'
  duration_ms?: number
  result?: unknown
  error?: string | null
}

export interface TranscriptEntry {
  role: string
  type: string
  text?: string
  destination?: string
}

export interface ExecutionResult {
  id: string
  status: string
  duration_ms?: number | null
  steps_executed: number
  steps_successful: number
  steps_failed: number
  error_message?: string | null
  result_data?: {
    steps?: StepResult[]
    transcript?: TranscriptEntry[]
    final_context?: Record<string, unknown>
    simulated?: boolean
  } | null
}

/**
 * Results of the most recent test run.
 *
 * Shows each step's outcome, timing, output, and error, plus the simulated
 * transcript — previously the only way to see any of this was to read the raw
 * result_data blob out of the database.
 */
export function ExecutionPanel({
  execution,
  onClose,
  onSelectNode,
}: {
  execution: ExecutionResult
  onClose: () => void
  onSelectNode: (nodeId: string) => void
}) {
  const [tab, setTab] = useState<'steps' | 'transcript' | 'context'>('steps')

  const steps = execution.result_data?.steps ?? []
  const transcript = execution.result_data?.transcript ?? []
  const context = execution.result_data?.final_context ?? {}
  const failed = execution.status !== 'completed'

  return (
    <div className="flex h-72 shrink-0 flex-col border-t bg-card">
      <div className="flex items-center justify-between gap-3 border-b px-4 py-2">
        <div className="flex items-center gap-3">
          <span
            className={cn(
              'flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium',
              failed
                ? 'bg-destructive/10 text-destructive'
                : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
            )}
          >
            {failed ? (
              <AlertCircle className="h-3.5 w-3.5" />
            ) : (
              <CheckCircle2 className="h-3.5 w-3.5" />
            )}
            {execution.status}
          </span>

          <span className="text-xs text-muted-foreground">
            {execution.steps_successful}/{execution.steps_executed} steps
            {execution.duration_ms != null && ` · ${execution.duration_ms}ms`}
          </span>

          {execution.result_data?.simulated && (
            <span className="rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
              simulated
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          {(['steps', 'transcript', 'context'] as const).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={cn(
                'rounded-md px-2.5 py-1 text-xs font-medium capitalize transition-colors',
                tab === key
                  ? 'bg-accent text-foreground'
                  : 'text-muted-foreground hover:bg-accent/60'
              )}
            >
              {key}
            </button>
          ))}
          <button
            type="button"
            onClick={onClose}
            className="ml-1 rounded-md p-1 text-muted-foreground hover:bg-accent"
            title="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {execution.error_message && (
          <p className="mb-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
            {execution.error_message}
          </p>
        )}

        {tab === 'steps' &&
          (steps.length === 0 ? (
            <Empty>No steps ran.</Empty>
          ) : (
            steps.map((step, index) => (
              <StepRow
                key={`${step.step_id}-${index}`}
                step={step}
                onSelect={() => onSelectNode(step.step_id)}
              />
            ))
          ))}

        {tab === 'transcript' &&
          (transcript.length === 0 ? (
            <Empty>Nothing was spoken in this run.</Empty>
          ) : (
            <div className="space-y-1 px-1">
              {transcript.map((entry, index) => (
                <div key={index} className="flex gap-2 text-xs">
                  <span
                    className={cn(
                      'w-14 shrink-0 font-medium',
                      entry.role === 'agent'
                        ? 'text-primary'
                        : entry.role === 'caller'
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : 'text-muted-foreground'
                    )}
                  >
                    {entry.role}
                  </span>
                  <span className="text-muted-foreground">
                    {entry.text ?? entry.destination ?? entry.type}
                  </span>
                </div>
              ))}
            </div>
          ))}

        {tab === 'context' && (
          <pre className="overflow-x-auto rounded-md bg-muted/50 p-3 font-mono text-[11px] leading-relaxed">
            {JSON.stringify(context, null, 2)}
          </pre>
        )}
      </div>
    </div>
  )
}

function StepRow({ step, onSelect }: { step: StepResult; onSelect: () => void }) {
  const [open, setOpen] = useState(false)
  const failed = step.status === 'failed'

  return (
    <div className="rounded-md border-b border-transparent">
      <div className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-accent/60">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="text-muted-foreground"
        >
          {open ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
        </button>

        {failed ? (
          <AlertCircle className="h-3.5 w-3.5 shrink-0 text-destructive" />
        ) : (
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
        )}

        <button
          type="button"
          onClick={onSelect}
          className="min-w-0 flex-1 truncate text-left text-xs font-medium hover:underline"
          title="Show this step on the canvas"
        >
          {step.step_name}
        </button>

        {step.duration_ms != null && (
          <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
            <Clock className="h-3 w-3" />
            {step.duration_ms}ms
          </span>
        )}
      </div>

      {open && (
        <div className="px-8 pb-2">
          {step.error && (
            <p className="mb-1.5 rounded border border-destructive/30 bg-destructive/5 px-2 py-1 text-[11px] text-destructive">
              {step.error}
            </p>
          )}
          <pre className="overflow-x-auto rounded bg-muted/50 p-2 font-mono text-[11px]">
            {JSON.stringify(step.result ?? null, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full items-center justify-center gap-2 text-xs text-muted-foreground">
      <MessageSquare className="h-3.5 w-3.5" />
      {children}
    </div>
  )
}
