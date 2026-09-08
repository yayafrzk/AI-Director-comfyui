import type { ComfyUIHealth } from '../types/comfyui'

type ApiError = {
  code: string
  message: string
}

type ApiResponse<T> = {
  data: T
  error: ApiError | null
}

export class ComfyUIRequestError extends Error {
  readonly code: string

  constructor(code: string, message: string) {
    super(message)
    this.name = 'ComfyUIRequestError'
    this.code = code
  }
}

async function request<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init)
  const payload = (await response.json()) as ApiResponse<T>

  if (!response.ok || payload.error) {
    throw new ComfyUIRequestError(
      payload.error?.code ?? 'COMFYUI_REQUEST_FAILED',
      payload.error?.message ?? 'ComfyUI 请求失败',
    )
  }

  return payload.data
}

export function comfyUIHealthKey() {
  return ['comfyui', 'health'] as const
}

export function getComfyUIHealth(): Promise<ComfyUIHealth> {
  return request<ComfyUIHealth>('/api/v1/comfyui/health')
}
