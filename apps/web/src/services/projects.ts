import type { Project, ProjectCreate, ProjectExportResult } from '../types/project'

type ApiError = {
  code: string
  message: string
}

type ApiResponse<T> = {
  data: T
  error: ApiError | null
}

const projectsPath = '/api/v1/projects'

export class ProjectRequestError extends Error {
  code: string

  constructor(code: string, message: string) {
    super(message)
    this.name = 'ProjectRequestError'
    this.code = code
  }
}

async function request<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init)
  const payload = (await response.json()) as ApiResponse<T>

  if (!response.ok || payload.error) {
    throw new ProjectRequestError(payload.error?.code ?? 'PROJECT_REQUEST_FAILED', payload.error?.message ?? '项目请求失败')
  }

  return payload.data
}

export function getProjects(): Promise<Project[]> {
  return request<Project[]>(projectsPath)
}

export function createProject(project: ProjectCreate): Promise<Project> {
  return request<Project>(projectsPath, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(project),
  })
}

export function exportProject(projectId: string): Promise<ProjectExportResult> {
  return request<ProjectExportResult>(`${projectsPath}/${encodeURIComponent(projectId)}/export`, {
    method: 'POST',
  })
}

export async function downloadProjectExport(projectId: string, exportId: string): Promise<void> {
  const response = await fetch(
    `${projectsPath}/${encodeURIComponent(projectId)}/exports/${encodeURIComponent(exportId)}/download`,
  )

  if (!response.ok) {
    let errorCode = 'EXPORT_DOWNLOAD_FAILED'
    let errorMessage = '下载失败，请重试。'
    try {
      const payload = (await response.json()) as ApiResponse<never>
      errorCode = payload.error?.code ?? errorCode
      errorMessage = payload.error?.message ?? errorMessage
    } catch {
      // The download endpoint may return a non-JSON error response.
    }
    throw new ProjectRequestError(errorCode, errorMessage)
  }

  const blob = await response.blob()
  const contentDisposition = response.headers.get('content-disposition')
  const filename = contentDisposition?.match(/filename="([^"]+)"/)?.[1] ?? `export-${exportId}.zip`
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
