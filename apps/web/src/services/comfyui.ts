import { requestJson } from './api'
import type { ComfyUIHealth } from '../types/comfyui'

export function comfyUIHealthKey() {
  return ['comfyui', 'health'] as const
}

export function getComfyUIHealth(): Promise<ComfyUIHealth> {
  return requestJson<ComfyUIHealth>(
    '/api/v1/comfyui/health',
    undefined,
    'COMFYUI_REQUEST_FAILED',
    'ComfyUI 请求失败',
  )
}
