import { requestJson } from './api'
import type { Asset, AssetType } from '../types/asset'

export function projectAssetsKey(projectId: string) {
  return ['projects', projectId, 'assets'] as const
}

export function getProjectAssets(projectId: string, sceneId?: string): Promise<Asset[]> {
  const params = sceneId ? '?scene_id=' + encodeURIComponent(sceneId) : ''
  const path = '/api/v1/projects/' + encodeURIComponent(projectId) + '/assets' + params
  return requestJson<Asset[]>(path, undefined, 'ASSET_REQUEST_FAILED', '素材请求失败')
}

export type AssetUploadInput = { projectId: string; file: File; type: AssetType; role: string; sceneId?: string }

export function uploadAsset({ projectId, file, type, role, sceneId }: AssetUploadInput): Promise<Asset> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('type', type)
  formData.append('role', role)
  if (sceneId !== undefined) formData.append('scene_id', sceneId)
  const path = '/api/v1/projects/' + encodeURIComponent(projectId) + '/assets/upload'
  return requestJson<Asset>(path, { method: 'POST', body: formData }, 'ASSET_UPLOAD_FAILED', '素材上传失败，请重试。')
}

export function assetContentUrl(assetId: string): string {
  return '/api/v1/assets/' + encodeURIComponent(assetId) + '/content'
}
