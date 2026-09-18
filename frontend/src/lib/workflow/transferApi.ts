import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import {
  buildExport,
  createPayload,
  downloadJson,
  exportFileName,
  parseImportFile,
  planImport,
  type ConnectionRef,
  type ExportableWorkflow,
  type ImportPlan,
  type ToolRef,
} from './transfer'

async function listConnections(): Promise<ConnectionRef[]> {
  const res = await apiClient.get<{ connections?: ConnectionRef[] } | ConnectionRef[]>(
    API_ENDPOINTS.INTEGRATION_CONNECTIONS
  )
  const data = res.data as any
  return Array.isArray(data) ? data : data?.connections ?? []
}

async function listTools(): Promise<ToolRef[]> {
  const res = await apiClient.get<{ tools?: ToolRef[] } | ToolRef[]>(API_ENDPOINTS.TOOLS)
  const data = res.data as any
  return Array.isArray(data) ? data : data?.tools ?? []
}

/** Download the saved version of a workflow as a JSON file. */
export async function downloadWorkflow(workflowId: string): Promise<void> {
  const [workflow, connections, tools] = await Promise.all([
    apiClient.get<ExportableWorkflow>(API_ENDPOINTS.WORKFLOW(workflowId)).then((r) => r.data),
    listConnections().catch(() => []),
    listTools().catch(() => []),
  ])
  const file = buildExport(workflow, connections, tools)
  downloadJson(exportFileName(workflow.name), file)
}

/** Create a new workflow from an exported file. */
export async function importWorkflow(
  file: File,
  existingNames: string[]
): Promise<{ id: string; name: string; plan: ImportPlan }> {
  const parsed = parseImportFile(await file.text())
  const [connections, tools] = await Promise.all([listConnections(), listTools()])
  const plan = planImport(parsed, connections, tools)
  const res = await apiClient.post<{ id: string; name: string }>(
    API_ENDPOINTS.WORKFLOWS,
    createPayload(plan.workflow, existingNames)
  )
  return { id: res.data.id, name: res.data.name, plan }
}
