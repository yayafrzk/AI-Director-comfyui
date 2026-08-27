import type { Scene } from '../types/scene'

type ApiError = {
  code: string
  message: string
}

type ApiResponse<T> = {
  data: T
  error: ApiError | null
}

async function request<T>(input: RequestInfo): Promise<T> {
  const response = await fetch(input)
  const payload = (await response.json()) as ApiResponse<T>

  if (!response.ok || payload.error) {
    throw new Error(payload.error?.message ?? '分镜请求失败')
  }

  return payload.data
}

export function getProjectScenes(projectId: string): Promise<Scene[]> {
  return request<Scene[]>(`/api/v1/projects/${projectId}/scenes`)
}
