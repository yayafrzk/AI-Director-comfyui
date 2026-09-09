import { requestJson } from './api'
import type { WorkflowTemplate } from '../types/workflow'

export function workflowTemplatesKey() {
  return ['workflow-templates'] as const
}

export function getWorkflowTemplates(): Promise<WorkflowTemplate[]> {
  return requestJson<WorkflowTemplate[]>(
    '/api/v1/workflow-templates',
    undefined,
    'WORKFLOW_REQUEST_FAILED',
    'Workflow 请求失败',
  )
}
