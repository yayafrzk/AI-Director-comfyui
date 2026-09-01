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
