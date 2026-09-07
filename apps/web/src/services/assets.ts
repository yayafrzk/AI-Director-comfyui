import type { Asset, AssetType } from '../types/asset'

type ApiEnvelope<T> = { data: T; error: null } | { data: null; error: { code: string; message: string } }

export class AssetRequestError extends Error {
  readonly code: string

  constructor(code: string, message: string) {
    super(message)
    this.code = code
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  const payload = (await response.json()) as ApiEnvelope<T>
  if (!response.ok || payload.error !== null) {
    throw new AssetRequestError(payload.error?.code ?? 'ASSET_REQUEST_FAILED', payload.error?.message ?? '素材请求失败')
  }
  return payload.data
}

export function projectAssetsKey(projectId: string) {
  return ['projects', projectId, 'assets'] as const
}

export function getProjectAssets(projectId: string, sceneId?: string): Promise<Asset[]> {
  const params = sceneId ? `?scene_id=${encodeURIComponent(sceneId)}` : ''
  return request<Asset[]>(`/api/v1/projects/${encodeURIComponent(projectId)}/assets${params}`)
}

export type AssetUploadInput = { projectId: string; file: File; type: AssetType; role: string; sceneId?: string }

export function uploadAsset({ projectId, file, type, role, sceneId }: AssetUploadInput): Promise<Asset> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('type', type)
  formData.append('role', role)
  if (sceneId !== undefined) formData.append('scene_id', sceneId)
  return request<Asset>(`/api/v1/projects/${encodeURIComponent(projectId)}/assets/upload`, { method: 'POST', body: formData })
}

export function assetContentUrl(assetId: string): string {
  return `/api/v1/assets/${encodeURIComponent(assetId)}/content`
}