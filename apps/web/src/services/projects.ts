import type { Project, ProjectCreate } from '../types/project'

type ApiError = {
  code: string
  message: string
}

type ApiResponse<T> = {
  data: T
  error: ApiError | null
}

const projectsPath = '/api/v1/projects'

async function request<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init)
  const payload = (await response.json()) as ApiResponse<T>

  if (!response.ok || payload.error) {
    throw new Error(payload.error?.message ?? '项目请求失败')
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
