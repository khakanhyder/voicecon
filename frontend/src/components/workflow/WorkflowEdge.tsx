'use client'

import { memo } from 'react'
import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  type EdgeProps,
} from '@xyflow/react'
import { Plus, X } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface WorkflowEdgeData extends Record<string, unknown> {
  onInsert?: (edgeId: string) => void
  onDelete?: (edgeId: string) => void
}

/**
 * Edge with hover controls: insert a node inline, or remove the connection.
 *
 * Inserting on an edge is how a flow gets built without rewiring by hand — the
 * new node is spliced between the two endpoints.
 */
function WorkflowEdgeComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  label,
  data,
  selected,
}: EdgeProps) {
  const [path, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 12,
  })

  const edgeData = data as WorkflowEdgeData | undefined

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        style={{
          strokeWidth: 2,
          stroke: selected ? 'hsl(var(--primary))' : 'hsl(var(--muted-foreground) / 0.45)',
        }}
      />

      <EdgeLabelRenderer>
        <div
          style={{
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
          }}
          className="pointer-events-auto absolute nodrag nopan group"
        >
          <div className="flex items-center gap-1">
            {label ? (
              <span
                className={cn(
                  'rounded-full border bg-background px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide',
                  label === 'true'
                    ? 'border-emerald-500/40 text-emerald-600 dark:text-emerald-400'
                    : 'border-rose-500/40 text-rose-600 dark:text-rose-400'
                )}
              >
                {label}
              </span>
            ) : null}

            <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
              <button
                type="button"
                title="Insert step here"
                onClick={(e) => {
                  e.stopPropagation()
                  edgeData?.onInsert?.(id)
                }}
                className="flex h-5 w-5 items-center justify-center rounded-full border bg-background text-muted-foreground shadow-sm hover:bg-primary hover:text-primary-foreground"
              >
                <Plus className="h-3 w-3" />
              </button>
              <button
                type="button"
                title="Remove connection"
                onClick={(e) => {
                  e.stopPropagation()
                  edgeData?.onDelete?.(id)
                }}
                className="flex h-5 w-5 items-center justify-center rounded-full border bg-background text-muted-foreground shadow-sm hover:bg-destructive hover:text-destructive-foreground"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          </div>
        </div>
      </EdgeLabelRenderer>
    </>
  )
}

export const WorkflowEdge = memo(WorkflowEdgeComponent)
