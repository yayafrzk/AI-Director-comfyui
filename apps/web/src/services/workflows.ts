import type { WorkflowTemplate } from '../types/workflow'

type ApiError = { code: string; message: string }
type ApiResponse<T> = { data: T; error: ApiError | null }

export class WorkflowRequestError extends Error {
  readonly code: string

  constructor(code: string, message: string) {
    super(message)
    this.code = code
  }
}

async function request<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init)
  const payload = (await response.json()) as ApiResponse<T>
  if (!response.ok || payload.error) {
    throw new WorkflowRequestError(payload.error?.code ?? 'WORKFLOW_REQUEST_FAILED', payload.error?.message ?? 'Workflow 请求失败')
  }
  return payload.data
}

export function workflowTemplatesKey() {
  return ['workflow-templates'] as const
}

export function getWorkflowTemplates(): Promise<WorkflowTemplate[]> {
  return request<WorkflowTemplate[]>('/api/v1/workflow-templates')
}
