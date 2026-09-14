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
export type WorkflowTemplateImportPayload = {
  name: string
  slug: string
  version: string
  template_path: string
  manifest_path: string
  is_enabled: boolean
}

export function importWorkflowTemplate(
  payload: WorkflowTemplateImportPayload,
): Promise<WorkflowTemplate> {
  return requestJson<WorkflowTemplate>(
    '/api/v1/workflow-templates/import',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    'WORKFLOW_TEMPLATE_IMPORT_FAILED',
    'Workflow 注册失败，请重试。',
  )
}
