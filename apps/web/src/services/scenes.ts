import type { Scene, SceneUpdate } from '../types/scene'

type ApiError = {
  code: string
  message: string
}

type ApiResponse<T> = {
  data: T
  error: ApiError | null
}

async function request<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init)
  const payload = (await response.json()) as ApiResponse<T>

  if (!response.ok || payload.error) {
    throw new Error(payload.error?.message ?? '分镜请求失败')
  }

  return payload.data
}

export function getProjectScenes(projectId: string): Promise<Scene[]> {
  return request<Scene[]>(`/api/v1/projects/${projectId}/scenes`)
}

export function reorderScenes(projectId: string, sceneIds: string[]): Promise<Scene[]> {
  return request<Scene[]>(`/api/v1/projects/${projectId}/scenes/reorder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scene_ids: sceneIds }),
  })
}

export function updateScene(sceneId: string, sceneUpdate: SceneUpdate): Promise<Scene> {
  return request<Scene>(`/api/v1/scenes/${sceneId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(sceneUpdate),
  })
}
