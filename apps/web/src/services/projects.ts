import { fetchApi, readApiError, requestJson } from './api'
import type { Project, ProjectCreate, ProjectExportResult } from '../types/project'

const projectsPath = '/api/v1/projects'

export function projectsKey() {
  return ['projects'] as const
}

export function getProjects(): Promise<Project[]> {
  return requestJson<Project[]>(projectsPath, undefined, 'PROJECT_REQUEST_FAILED', '项目请求失败')
}

export function createProject(project: ProjectCreate): Promise<Project> {
  return requestJson<Project>(
    projectsPath,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(project),
    },
    'PROJECT_REQUEST_FAILED',
    '项目请求失败',
  )
}

export function exportProject(projectId: string): Promise<ProjectExportResult> {
  const path = projectsPath + '/' + encodeURIComponent(projectId) + '/export'
  return requestJson<ProjectExportResult>(path, { method: 'POST' }, 'EXPORT_FAILED', '导出失败，请重试。')
}

export async function downloadProjectExport(projectId: string, exportId: string): Promise<void> {
  const path =
    projectsPath +
    '/' +
    encodeURIComponent(projectId) +
    '/exports/' +
    encodeURIComponent(exportId) +
    '/download'
  const response = await fetchApi(path)

  if (!response.ok) {
    throw await readApiError(response, 'EXPORT_DOWNLOAD_FAILED', '下载失败，请重试。')
  }

  const blob = await response.blob()
  const contentDisposition = response.headers.get('content-disposition')
  const filename = contentDisposition?.match(/filename="([^"]+)"/)?.[1] ?? 'export-' + exportId + '.zip'
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')

  try {
    anchor.href = objectUrl
    anchor.download = filename
    anchor.hidden = true
    document.body.append(anchor)
    anchor.click()
  } finally {
    anchor.remove()
    URL.revokeObjectURL(objectUrl)
  }
}
