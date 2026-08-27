import { type FormEvent, useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { createProject, getProjects } from '../../services/projects'
import type { Project } from '../../types/project'

const projectQueryKey = ['projects']
const emptyProjects: Project[] = []

type ProjectSidebarProps = {
  selectedProjectId: string | null
  onSelectProject: (projectId: string) => void
}

export function ProjectSidebar({ selectedProjectId, onSelectProject }: ProjectSidebarProps) {
  const queryClient = useQueryClient()
  const [isCreating, setIsCreating] = useState(false)
  const [projectName, setProjectName] = useState('')
  const [createError, setCreateError] = useState<string | null>(null)
  const projectsQuery = useQuery({ queryKey: projectQueryKey, queryFn: getProjects })
  const createProjectMutation = useMutation({
    mutationFn: createProject,
    onSuccess: (project) => {
      queryClient.setQueryData<Project[]>(projectQueryKey, (projects = []) => [...projects, project])
      onSelectProject(project.id)
      setProjectName('')
      setCreateError(null)
      setIsCreating(false)
    },
  })

  const projects = projectsQuery.data ?? emptyProjects
  const currentProjectId = selectedProjectId ?? projects[0]?.id ?? null

  useEffect(() => {
    if (selectedProjectId === null && projects[0]) {
      onSelectProject(projects[0].id)
    }
  }, [onSelectProject, projects, selectedProjectId])

  function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = projectName.trim()

    if (!name) {
      setCreateError('请输入项目名称')
      return
    }

    setCreateError(null)
    createProjectMutation.mutate({
      name,
      description: '',
      aspect_ratio: '9:16',
      width: 1080,
      height: 1920,
      fps: 30,
    })
  }

  function cancelCreate() {
    setProjectName('')
    setCreateError(null)
    createProjectMutation.reset()
    setIsCreating(false)
  }

  return (
    <aside
      aria-labelledby="projects-heading"
      className="border-b border-[color:var(--border-subtle)] bg-[var(--surface-base)] p-4 lg:border-r lg:border-b-0 lg:p-5"
    >
      <div className="flex items-end justify-between gap-3 border-b border-[color:var(--border-subtle)] pb-4">
        <div>
          <p className="font-mono text-[0.625rem] tracking-[0.16em] text-[color:var(--text-muted)]">PROJECTS</p>
          <h2 id="projects-heading" className="mt-1 text-sm font-semibold text-[color:var(--text-primary)]">
            项目
          </h2>
        </div>
        <span className="font-mono text-xs text-[color:var(--text-muted)]">
          {String(projects.length).padStart(2, '0')}
        </span>
      </div>

      {projectsQuery.isLoading ? <p className="mt-4 text-xs text-[color:var(--text-muted)]">加载项目...</p> : null}
      {projectsQuery.isError ? <p className="mt-4 text-xs text-[color:var(--text-muted)]">项目加载失败</p> : null}
      {!projectsQuery.isLoading && !projectsQuery.isError && projects.length === 0 ? (
        <p className="mt-4 text-xs text-[color:var(--text-muted)]">暂无项目</p>
      ) : null}

      {projects.length > 0 ? (
        <ul className="mt-4 space-y-2" aria-label="项目列表">
          {projects.map((project, index) => {
            const isCurrent = project.id === currentProjectId

            return (
              <li key={project.id}>
                <button
                  type="button"
                  onClick={() => onSelectProject(project.id)}
                  className={[
                    'flex w-full items-center gap-3 border px-3 py-3 text-left',
                    isCurrent
                      ? 'border-[color:var(--accent)] bg-[var(--accent-soft)]'
                      : 'border-[color:var(--border-subtle)] bg-[var(--surface-raised)]',
                  ].join(' ')}
                >
                  <span
                    aria-hidden="true"
                    className="font-mono text-[0.625rem] tracking-[0.12em] text-[color:var(--text-muted)]"
                  >
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-sm text-[color:var(--text-primary)]">{project.name}</span>
                  {isCurrent ? (
                    <span className="font-mono text-[0.625rem] tracking-[0.1em] text-[color:var(--accent)]">当前</span>
                  ) : null}
                </button>
              </li>
            )
          })}
        </ul>
      ) : null}

      {isCreating ? (
        <form onSubmit={handleCreate} className="mt-4 border border-[color:var(--border-subtle)] bg-[var(--surface-raised)] p-3">
          <label htmlFor="project-name" className="text-xs text-[color:var(--text-primary)]">
            项目名称
          </label>
          <input
            id="project-name"
            value={projectName}
            onChange={(event) => setProjectName(event.target.value)}
            className="mt-2 w-full border border-[color:var(--border-subtle)] bg-[var(--surface-base)] px-2 py-2 text-sm text-[color:var(--text-primary)] outline-none focus:border-[color:var(--accent)]"
            disabled={createProjectMutation.isPending}
          />
          {createError ? <p className="mt-2 text-xs text-[color:var(--text-muted)]">{createError}</p> : null}
          {createProjectMutation.isError ? (
            <p className="mt-2 text-xs text-[color:var(--text-muted)]">
              {createProjectMutation.error instanceof Error ? createProjectMutation.error.message : '创建项目失败'}
            </p>
          ) : null}
          <div className="mt-3 flex gap-2">
            <button
              type="submit"
              disabled={createProjectMutation.isPending}
              className="border border-[color:var(--accent)] bg-[var(--accent-soft)] px-3 py-2 text-xs text-[color:var(--accent)] disabled:opacity-70"
            >
              {createProjectMutation.isPending ? '创建中...' : '创建'}
            </button>
            <button
              type="button"
              onClick={cancelCreate}
              disabled={createProjectMutation.isPending}
              className="border border-[color:var(--border-subtle)] px-3 py-2 text-xs text-[color:var(--text-muted)] disabled:opacity-70"
            >
              取消
            </button>
          </div>
        </form>
      ) : (
        <button
          type="button"
          onClick={() => setIsCreating(true)}
          className="mt-4 w-full border border-[color:var(--border-subtle)] px-3 py-2 text-left text-xs text-[color:var(--text-muted)] hover:border-[color:var(--accent)] hover:text-[color:var(--text-primary)]"
        >
          + 新建项目
        </button>
      )}
    </aside>
  )
}
