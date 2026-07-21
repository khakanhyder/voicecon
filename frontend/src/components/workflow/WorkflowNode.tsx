'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Braces,
  Filter as FilterIcon,
  GitBranch,
  GitMerge,
  Globe,
  Loader2,
  MessageCircleQuestion,
  PhoneForwarded,
  PhoneOff,
  Plug,
  Play,
  Repeat,
  Sparkles,
  Split,
  Volume2,
  Wrench,
  type LucideIcon,
} from 'lucide-react'
import { getDescriptor, outputsFor } from '@/lib/workflow/nodeTypes'
import type { FlowNodeData } from '@/lib/workflow/graph'
import { cn } from '@/lib/utils'

const ICONS: Record<string, LucideIcon> = {
  Play,
  Volume2,
  MessageCircleQuestion,
  GitBranch,
  PhoneForwarded,
  Wrench,
  Plug,
  Braces,
  Split,
  FilterIcon,
  GitMerge,
  Repeat,
  Globe,
  Sparkles,
  Clock,
  PhoneOff,
}

const HANDLE_CLASS =
  '!h-3 !w-3 !border-2 !border-background !bg-muted-foreground transition-colors hover:!bg-primary'

interface WorkflowNodeProps extends NodeProps {
  data: FlowNodeData
  onDelete?: (id: string) => void
  onDuplicate?: (id: string) => void
}

/**
 * Canvas node for every step type.
 *
 * Appearance and handles come from the type descriptor, so a new node type
 * needs no changes here.
 */
function WorkflowNodeComponent({ data, selected }: WorkflowNodeProps) {
  const descriptor = getDescriptor(data.nodeType)
  const Icon = ICONS[descriptor.icon] ?? Volume2
  const summary = descriptor.summary(data.config || {})
  // Switch nodes grow an output per rule, so handles come from the config.
  const outputs = outputsFor(data.nodeType, data.config || {})
  const isBranch = outputs.length > 1

  return (
    <div
      className={cn(
        'group relative w-[280px] rounded-xl border bg-card shadow-sm transition-all',
        selected
          ? 'border-primary ring-2 ring-primary/20'
          : 'border-border hover:border-primary/40 hover:shadow-md',
        data.status === 'running' && 'ring-2 ring-blue-400',
        data.status === 'success' && 'border-emerald-500/60',
        data.status === 'failed' && 'border-rose-500/60'
      )}
    >
      {descriptor.hasInput && (
        <Handle
          type="target"
          position={Position.Top}
          id="in"
          className={HANDLE_CLASS}
        />
      )}

      <div className="flex items-start gap-3 p-3">
        <div
          className={cn(
            'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-white',
            descriptor.accent
          )}
        >
          <Icon className="h-[18px] w-[18px]" />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <p className="truncate text-sm font-semibold leading-tight">
              {data.label}
            </p>
            <StatusBadge status={data.status} />
          </div>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">{summary}</p>
        </div>
      </div>

      {data.status === 'failed' && data.error && (
        <div className="border-t border-rose-500/30 bg-rose-500/10 px-3 py-1.5">
          <p className="truncate text-[11px] text-rose-600 dark:text-rose-400">
            {data.error}
          </p>
        </div>
      )}

      {/* Branch nodes label their outputs so the canvas reads without clicking. */}
      {isBranch ? (
        <div className="flex items-stretch border-t text-[10px] font-medium">
          {outputs.map((output: { id: string; label?: string }) => (
            <span
              key={output.id}
              className={cn(
                'flex-1 truncate px-1.5 py-1 text-center uppercase tracking-wide',
                output.id === 'true' && 'text-emerald-600 dark:text-emerald-400',
                output.id === 'false' && 'text-rose-600 dark:text-rose-400',
                output.id === 'fallback' && 'text-muted-foreground',
                output.id === 'loop' && 'text-emerald-600 dark:text-emerald-400',
                output.id === 'done' && 'text-muted-foreground'
              )}
              title={output.label ?? output.id}
            >
              {output.label ?? output.id}
            </span>
          ))}
        </div>
      ) : null}

      {outputs.map((output: { id: string; label?: string }, index: number) => (
        <Handle
          key={output.id}
          type="source"
          position={Position.Bottom}
          id={output.id}
          className={cn(
            HANDLE_CLASS,
            (output.id === 'true' || output.id === 'loop') &&
              'hover:!bg-emerald-500',
            output.id === 'false' && 'hover:!bg-rose-500'
          )}
          style={
            isBranch
              ? {
                  // Space handles evenly across the node's width so each one
                  // sits under its own label.
                  left: `${((index + 0.5) / outputs.length) * 100}%`,
                }
              : undefined
          }
        />
      ))}
    </div>
  )
}

function StatusBadge({ status }: { status?: FlowNodeData['status'] }) {
  if (!status) return null

  if (status === 'running') {
    return <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-blue-500" />
  }
  if (status === 'success') {
    return <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
  }
  if (status === 'failed') {
    return <AlertCircle className="h-3.5 w-3.5 shrink-0 text-rose-500" />
  }
  return null
}

export const WorkflowNode = memo(WorkflowNodeComponent)

/**
 * The trigger node: entry point of the flow, no input handle, cannot be deleted.
 */
function TriggerNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as FlowNodeData

  return (
    <div
      className={cn(
        'relative w-[280px] rounded-xl border-2 bg-card px-3 py-2.5 shadow-sm transition-all',
        selected
          ? 'border-emerald-500 ring-2 ring-emerald-500/20'
          : 'border-emerald-500/50 hover:border-emerald-500'
      )}
    >
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500 text-white">
          <Play className="h-[18px] w-[18px] fill-current" />
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold leading-tight">
            {nodeData.label || 'When workflow runs'}
          </p>
          <p className="text-xs text-muted-foreground">Trigger</p>
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} id="out" className={HANDLE_CLASS} />
    </div>
  )
}

export const TriggerNode = memo(TriggerNodeComponent)
