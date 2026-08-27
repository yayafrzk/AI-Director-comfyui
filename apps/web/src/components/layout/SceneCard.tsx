import type { DragEvent } from 'react'

import type { Scene } from '../../types/scene'

type SceneCardProps = {
  scene: Scene
  position: number
  isSorting: boolean
  dragDisabled: boolean
  onDragStart: (event: DragEvent<HTMLButtonElement>, sceneId: string) => void
  onDragEnter: (sceneId: string) => void
  onDragEnd: () => void
}

export function SceneCard({ scene, position, isSorting, dragDisabled, onDragStart, onDragEnter, onDragEnd }: SceneCardProps) {
  const title = scene.title.trim() || '未命名分镜'
  const prompt = scene.prompt?.trim() || '暂无 Prompt'
  const sceneNumber = isSorting ? position + 1 : scene.scene_number

  return (
    <article
      onDragEnter={() => onDragEnter(scene.id)}
      onDragOver={(event) => event.preventDefault()}
      className="border border-[color:var(--border-subtle)] bg-[var(--surface-raised)] p-4 sm:p-5"
    >
      <div className="flex items-start gap-4">
        <button
          type="button"
          draggable={!dragDisabled}
          disabled={dragDisabled}
          onDragStart={(event) => onDragStart(event, scene.id)}
          onDragEnd={onDragEnd}
          aria-label={`拖动分镜 ${sceneNumber} 排序`}
          className="grid size-7 shrink-0 cursor-grab place-items-center border border-[color:var(--border-subtle)] font-mono text-sm text-[color:var(--text-muted)] active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-50"
        >
          ≡
        </button>
        <span
          aria-label={`分镜 ${sceneNumber}`}
          className="grid size-10 shrink-0 place-items-center border border-[color:var(--accent)] bg-[var(--accent-soft)] font-mono text-sm tracking-[0.08em] text-[color:var(--accent)]"
        >
          {String(sceneNumber).padStart(2, '0')}
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
