import { requestJson } from './api'
import type { GenerationJob } from '../types/generation'

export type OutputInboxSettings = {
  configured: boolean
  output_dir: string | null
}

export type OutputInboxItem = {
  id: string
  relative_path: string
  filename: string
  type: 'image' | 'video'
  size_bytes: number
  modified_at: string
  archived: boolean
  archived_scene_id: string | null
}

export type OutputInboxImportPayload = {
  relative_path: string
  prompt_snapshot: string
  negative_prompt_snapshot: string
  seed: null
  select_as_final: false
}

export function outputInboxSettingsKey() {
  return ['output-inbox', 'settings'] as const
}

export function outputInboxItemsKey() {
  return ['output-inbox', 'items'] as const
}

export function getOutputInboxSettings(): Promise<OutputInboxSettings> {
  return requestJson<OutputInboxSettings>(
    '/api/v1/output-inbox/settings', undefined, 'OUTPUT_INBOX_SETTINGS_FAILED', '读取输出目录设置失败',
  )
}

export function updateOutputInboxSettings(outputDir: string): Promise<OutputInboxSettings> {
  return requestJson<OutputInboxSettings>(
    '/api/v1/output-inbox/settings',
    { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ output_dir: outputDir }) },
    'OUTPUT_INBOX_SETTINGS_FAILED',
    '保存输出目录失败',
  )
}

export function getOutputInboxItems(): Promise<OutputInboxItem[]> {
  return requestJson<OutputInboxItem[]>(
    '/api/v1/output-inbox/items', undefined, 'OUTPUT_INBOX_ITEMS_FAILED', '读取最新结果失败',
  )
}

export function outputInboxContentUrl(relativePath: string): string {
  return '/api/v1/output-inbox/content?path=' + encodeURIComponent(relativePath)
}

export function importOutputInboxItem(sceneId: string, payload: OutputInboxImportPayload): Promise<GenerationJob> {
  return requestJson<GenerationJob>(
    '/api/v1/scenes/' + encodeURIComponent(sceneId) + '/output-inbox/import',
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) },
    'OUTPUT_INBOX_IMPORT_FAILED',
    '归档结果失败',
  )
}
