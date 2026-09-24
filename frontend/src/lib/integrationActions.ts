/**
 * Integration actions grouped by what they do to the data in the connected
 * app. The backend labels every action with an `operation`
 * (see backend action_registry.operation_of) and flags deletes as
 * `destructive`, so pickers can group them and warn before a delete.
 */

export type ActionOperation = 'read' | 'create' | 'update' | 'delete'

export interface OperationAware {
  action: string
  label: string
  operation?: ActionOperation
  destructive?: boolean
}

const GROUPS: { operation: ActionOperation; label: string }[] = [
  { operation: 'read', label: 'Find & read' },
  { operation: 'create', label: 'Create & send' },
  { operation: 'update', label: 'Update existing' },
  { operation: 'delete', label: 'Delete / cancel' },
]

/** Actions in picker order, grouped by operation; empty groups are dropped. */
export function groupActions<T extends OperationAware>(actions: T[]): { label: string; actions: T[] }[] {
  return GROUPS.map((g) => ({
    label: g.label,
    actions: actions.filter((a) => (a.operation ?? 'create') === g.operation),
  })).filter((g) => g.actions.length > 0)
}

/** Update and delete actions change data that already exists in the app. */
export function changesExistingData(action?: OperationAware | null): boolean {
  return action?.operation === 'update' || action?.operation === 'delete'
}
