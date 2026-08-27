import type { Scene } from '../../types/scene'

type SceneCardProps = {
  scene: Scene
}

export function SceneCard({ scene }: SceneCardProps) {
  const title = scene.title.trim() || '未命名分镜'
  const prompt = scene.prompt?.trim() || '暂无 Prompt'

  return (
    <article className="border border-[color:var(--border-subtle)] bg-[var(--surface-raised)] p-4 sm:p-5">
      <div className="flex items-start gap-4">
        <span
          aria-label={`分镜 ${scene.scene_number}`}
          className="grid size-10 shrink-0 place-items-center border border-[color:var(--accent)] bg-[var(--accent-soft)] font-mono text-sm tracking-[0.08em] text-[color:var(--accent)]"
        >
          {String(scene.scene_number).padStart(2, '0')}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-base font-semibold text-[color:var(--text-primary)]">{title}</h3>
          <p className="mt-2 line-clamp-2 text-sm leading-6 text-[color:var(--text-muted)]">{prompt}</p>
        </div>
      </div>

      <dl className="mt-4 grid gap-x-5 gap-y-3 border-t border-[color:var(--border-subtle)] pt-4 text-xs sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="font-mono text-[0.625rem] tracking-[0.12em] text-[color:var(--text-muted)]">时长</dt>
          <dd className="mt-1 text-[color:var(--text-primary)]">{scene.duration_seconds} 秒</dd>
        </div>
        <div>
          <dt className="font-mono text-[0.625rem] tracking-[0.12em] text-[color:var(--text-muted)]">状态</dt>
          <dd className="mt-1 text-[color:var(--text-primary)]">{scene.status}</dd>
        </div>
        {scene.seed !== null ? (
          <div>
            <dt className="font-mono text-[0.625rem] tracking-[0.12em] text-[color:var(--text-muted)]">SEED</dt>
            <dd className="mt-1 font-mono text-[color:var(--text-primary)]">{scene.seed}</dd>
          </div>
        ) : null}
        {scene.workflow_template_id ? (
          <div className="min-w-0">
            <dt className="font-mono text-[0.625rem] tracking-[0.12em] text-[color:var(--text-muted)]">WORKFLOW</dt>
            <dd className="mt-1 truncate font-mono text-[color:var(--text-primary)]" title={scene.workflow_template_id}>
              {scene.workflow_template_id}
            </dd>
          </div>
        ) : null}
      </dl>
    </article>
  )
}
