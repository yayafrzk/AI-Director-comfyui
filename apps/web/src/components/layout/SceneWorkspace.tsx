import { useQuery } from '@tanstack/react-query'

import { getProjectScenes } from '../../services/scenes'
import { SceneCard } from './SceneCard'

type SceneWorkspaceProps = {
  projectId: string | null
}

export function SceneWorkspace({ projectId }: SceneWorkspaceProps) {
  const scenesQuery = useQuery({
    queryKey: ['projects', projectId, 'scenes'],
    queryFn: () => getProjectScenes(projectId!),
    enabled: projectId !== null,
  })
  const scenes = scenesQuery.data ?? []

  return (
    <main className="min-w-0 bg-[var(--canvas)] p-4 sm:p-5 lg:p-6" aria-labelledby="scene-workspace-heading">
      <div className="flex items-end justify-between gap-4 border-b border-[color:var(--border-subtle)] pb-4">
        <div>
          <p className="font-mono text-[0.625rem] tracking-[0.16em] text-[color:var(--text-muted)]">SCENES / EDITING BAY</p>
          <h2 id="scene-workspace-heading" className="mt-1 text-base font-semibold text-[color:var(--text-primary)]">
            分镜工作区
          </h2>
        </div>
        <span className="font-mono text-xs text-[color:var(--text-muted)]">{scenes.length} 个镜头</span>
      </div>

      {projectId === null ? (
        <EmptySceneState title="请选择项目" description="从左侧选择一个项目后，即可查看其分镜。" />
      ) : null}

      {projectId !== null && scenesQuery.isLoading ? (
        <section className="mt-5 grid min-h-[22rem] place-items-center border border-[color:var(--border-subtle)] bg-[var(--surface-base)] p-6 sm:min-h-[28rem]">
          <p className="text-sm text-[color:var(--text-muted)]">加载分镜...</p>
        </section>
      ) : null}

      {projectId !== null && scenesQuery.isError ? (
        <section className="mt-5 border-l-2 border-[color:var(--status-offline)] bg-[var(--surface-base)] px-4 py-4">
          <p className="text-sm text-[color:var(--text-primary)]">分镜加载失败</p>
          <p className="mt-1 text-xs text-[color:var(--text-muted)]">
            {scenesQuery.error instanceof Error ? scenesQuery.error.message : '请稍后重试'}
          </p>
        </section>
      ) : null}

      {projectId !== null && !scenesQuery.isLoading && !scenesQuery.isError && scenes.length === 0 ? (
        <EmptySceneState title="暂无分镜" description="后续将在这里管理 Scene。" />
      ) : null}

      {projectId !== null && !scenesQuery.isLoading && !scenesQuery.isError && scenes.length > 0 ? (
        <section className="mt-5 space-y-3" aria-label="分镜列表">
          {scenes.map((scene) => (
            <SceneCard key={scene.id} scene={scene} />
          ))}
        </section>
      ) : null}
    </main>
  )
}

type EmptySceneStateProps = {
  title: string
  description: string
}

function EmptySceneState({ title, description }: EmptySceneStateProps) {
  return (
    <section
      aria-labelledby="empty-scenes-heading"
      className="mt-5 grid min-h-[22rem] place-items-center border border-dashed border-[color:var(--border-strong)] bg-[var(--surface-base)] p-6 sm:min-h-[28rem]"
    >
      <div className="max-w-sm text-center">
        <div className="mb-5 flex items-center justify-center gap-3" aria-hidden="true">
          <span className="h-px w-8 bg-[var(--accent)]" />
          <span className="font-mono text-xs tracking-[0.2em] text-[color:var(--accent)]">00</span>
          <span className="h-px w-8 bg-[var(--accent)]" />
        </div>
        <p className="font-mono text-[0.625rem] tracking-[0.16em] text-[color:var(--text-muted)]">SCENE QUEUE</p>
        <h3 id="empty-scenes-heading" className="mt-3 text-lg font-medium text-[color:var(--text-primary)]">
          {title}
        </h3>
        <p className="mt-2 text-sm leading-6 text-[color:var(--text-muted)]">{description}</p>
      </div>
    </section>
  )
}
