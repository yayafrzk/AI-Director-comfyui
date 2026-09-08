import { useQuery } from '@tanstack/react-query'

import { getComfyUIHealth, comfyUIHealthKey } from '../../services/comfyui'
import { getProjects, projectsKey } from '../../services/projects'

type TopBarProps = {
  selectedProjectId: string | null
}

type HealthState = 'online' | 'offline' | 'loading' | 'error'

export function TopBar({ selectedProjectId }: TopBarProps) {
  const projectsQuery = useQuery({
    queryKey: projectsKey(),
    queryFn: getProjects,
  })
  const comfyUIHealthQuery = useQuery({
    queryKey: comfyUIHealthKey(),
    queryFn: getComfyUIHealth,
    refetchInterval: 5000,
    retry: false,
  })

  const projects = projectsQuery.data ?? []
  const selectedProject =
    selectedProjectId === null
      ? null
      : projects.find((project) => project.id === selectedProjectId) ?? null

  const projectLabel = projectsQuery.isLoading
    ? '加载中...'
    : projectsQuery.isError
      ? '项目加载失败'
      : selectedProjectId === null
        ? '未选择项目'
        : selectedProject === null
          ? '项目不可用'
          : selectedProject.name

  const healthState: HealthState = comfyUIHealthQuery.isError
    ? 'error'
    : comfyUIHealthQuery.data?.status === 'online'
      ? 'online'
      : comfyUIHealthQuery.data?.status === 'offline'
        ? 'offline'
        : 'loading'

  const healthLabel =
    healthState === 'online'
      ? '已连接'
      : healthState === 'offline'
        ? '未连接'
        : healthState === 'error'
          ? '检查失败'
          : '检查中...'

  const healthDotClass =
    healthState === 'online'
      ? 'bg-[var(--accent)]'
      : healthState === 'offline'
        ? 'bg-[var(--status-offline)]'
        : 'bg-[var(--text-muted)]'

  return (
    <header className="border-b border-[color:var(--border-subtle)] bg-[var(--surface-base)] px-4 py-3 sm:px-5 lg:px-6">
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
        <div className="flex min-w-0 items-center gap-3">
          <span
            aria-hidden="true"
            className="grid size-7 shrink-0 place-items-center border border-[color:var(--accent)] font-mono text-[0.625rem] tracking-[0.08em] text-[color:var(--accent)]"
          >
            AD
          </span>
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold tracking-[0.01em] text-[color:var(--text-primary)]">
              AI Director
            </h1>
            <p className="truncate text-xs text-[color:var(--text-muted)]">本地 AI 视频导演台</p>
          </div>
          <span aria-hidden="true" className="hidden h-8 w-px bg-[var(--border-subtle)] sm:block" />
          <div className="min-w-0">
            <p className="font-mono text-[0.625rem] tracking-[0.14em] text-[color:var(--text-muted)]">
              当前项目
            </p>
            <p className="truncate text-sm text-[color:var(--text-primary)]">{projectLabel}</p>
          </div>
        </div>

        <div
          aria-label={'ComfyUI 状态：' + healthLabel}
          role="status"
          className="flex items-center gap-2 border border-[color:var(--border-subtle)] bg-[var(--surface-raised)] px-3 py-2"
        >
          <span aria-hidden="true" className={'size-2 rounded-full ' + healthDotClass} />
          <div className="leading-tight">
            <p className="font-mono text-[0.625rem] tracking-[0.12em] text-[color:var(--text-muted)]">
              COMFYUI
            </p>
            <p className="text-xs text-[color:var(--text-primary)]">{healthLabel}</p>
          </div>
        </div>
      </div>
    </header>
  )
}
