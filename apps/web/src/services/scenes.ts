import { requestJson } from './api'
import type { GenerationJob, GenerationStatus } from '../types/generation'
import type { Scene, SceneCreate, SceneUpdate } from '../types/scene'

const sceneFallback = '分镜请求失败'

export function getProjectScenes(projectId: string): Promise<Scene[]> {
  return requestJson<Scene[]>(
    '/api/v1/projects/' + projectId + '/scenes',
    undefined,
    'SCENE_REQUEST_FAILED',
    sceneFallback,
  )
}

export function createScene(projectId: string, scene: SceneCreate): Promise<Scene> {
  return requestJson<Scene>(
    '/api/v1/projects/' + encodeURIComponent(projectId) + '/scenes',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(scene),
    },
    'SCENE_REQUEST_FAILED',
    sceneFallback,
  )
}

export function reorderScenes(projectId: string, sceneIds: string[]): Promise<Scene[]> {
  return requestJson<Scene[]>(
    '/api/v1/projects/' + projectId + '/scenes/reorder',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scene_ids: sceneIds }),
    },
    'SCENE_REQUEST_FAILED',
    sceneFallback,
  )
}

export function updateScene(sceneId: string, sceneUpdate: SceneUpdate): Promise<Scene> {
  return requestJson<Scene>(
    '/api/v1/scenes/' + sceneId,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(sceneUpdate),
    },
    'SCENE_REQUEST_FAILED',
    sceneFallback,
  )
}

export function deleteScene(sceneId: string): Promise<{ id: string }> {
  return requestJson<{ id: string }>(
    '/api/v1/scenes/' + encodeURIComponent(sceneId),
    { method: 'DELETE' },
    'SCENE_REQUEST_FAILED',
    sceneFallback,
  )
}

export type GenerationSubmit = { job_id: string; status: GenerationStatus }

export function getSceneGenerationJobs(sceneId: string): Promise<GenerationJob[]> {
  return requestJson<GenerationJob[]>(
    '/api/v1/scenes/' + sceneId + '/generation-jobs',
    undefined,
    'GENERATION_REQUEST_FAILED',
    '生成历史请求失败',
  )
}

export function selectSceneAsset(sceneId: string, assetId: string): Promise<Scene> {
  return requestJson<Scene>(
    '/api/v1/scenes/' + sceneId + '/assets/' + assetId + '/select',
    { method: 'POST' },
    'SCENE_REQUEST_FAILED',
    sceneFallback,
  )
}

export function cancelGenerationJob(jobId: string): Promise<GenerationJob> {
  return requestJson<GenerationJob>(
    '/api/v1/generation-jobs/' + jobId + '/cancel',
    { method: 'POST' },
    'GENERATION_REQUEST_FAILED',
    '取消任务失败，请重试。',
  )
}

export function retryGenerationJob(jobId: string): Promise<GenerationSubmit> {
  return requestJson<GenerationSubmit>(
    '/api/v1/generation-jobs/' + jobId + '/retry',
    { method: 'POST' },
    'GENERATION_REQUEST_FAILED',
    '重试任务失败，请重试。',
  )
}

export function generateScene(sceneId: string, workflowTemplateId: string): Promise<GenerationSubmit> {
  return requestJson<GenerationSubmit>(
    '/api/v1/scenes/' + sceneId + '/generate',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workflow_template_id: workflowTemplateId, params: {} }),
    },
    'GENERATION_REQUEST_FAILED',
    '生成提交失败',
  )
}
