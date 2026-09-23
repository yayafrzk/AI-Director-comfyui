import type { DragEvent, MouseEvent } from 'react'

import { formatGenerationStatus, type GenerationJob } from '../../types/generation'
import type { Scene } from '../../types/scene'

type SceneCardProps = {
  scene: Scene
  generationJob?: GenerationJob
  position: number
  isSorting: boolean
  dragDisabled: boolean
  cancelling: boolean
  cancelError?: string | null
  onCancel: (job: GenerationJob) => void
  onDragStart: (event: DragEvent<HTMLButtonElement>, sceneId: string) => void
  onDragEnter: (sceneId: string) => void
  onDragEnd: () => void
  onOpen: (sceneId: string) => void
  onImport: (sceneId: string) => void
}

export function SceneCard({ scene, generationJob, position, isSorting, dragDisabled, cancelling, cancelError, onCancel, onDragStart, onDragEnter, onDragEnd, onOpen, onImport }: SceneCardProps) {
  const sceneNumber = isSorting ? position + 1 : scene.scene_number
  const canCancel = generationJob?.status === 'queued' || generationJob?.status === 'running' || generationJob?.status === 'pending'
  const needsWorkflow = !scene.workflow_template_id
  const generationProgress =
    generationJob?.status === 'running' && typeof generationJob.progress === 'number'
      ? Math.max(0, Math.min(1, generationJob.progress))
      : null

  return <article onClick={() => onOpen(scene.id)} onDragEnter={() => onDragEnter(scene.id)} onDragOver={(event) => event.preventDefault()} className="border border-[color:var(--border-subtle)] bg-[var(--surface-raised)] p-4 sm:p-5">
    <div className="flex items-start gap-4"><button type="button" draggable={!dragDisabled} disabled={dragDisabled} onDragStart={(event) => onDragStart(event, scene.id)} onDragEnd={onDragEnd} onClick={(event: MouseEvent<HTMLButtonElement>) => event.stopPropagation()} aria-label={`拖动分镜 ${sceneNumber} 排序`} className="grid size-7 shrink-0 cursor-grab place-items-center border border-[color:var(--border-subtle)]">≡</button><span className="grid size-10 shrink-0 place-items-center border border-[color:var(--accent)] bg-[var(--accent-soft)] font-mono text-sm text-[color:var(--accent)]">{String(sceneNumber).padStart(2, '0')}</span><div className="min-w-0 flex-1"><h3 className="truncate text-base font-semibold">{scene.title.trim() || '未命名分镜'}</h3><p className="mt-2 line-clamp-2 text-sm text-[color:var(--text-muted)]">{scene.prompt?.trim() || '暂无 Prompt'}</p></div><div className="flex shrink-0 gap-2"><button type="button" onClick={(event) => { event.stopPropagation(); onImport(scene.id) }} className="border border-[color:var(--accent)] bg-[var(--accent-soft)] px-3 py-1.5 text-xs text-[color:var(--accent)] transition-colors hover:bg-[var(--surface-base)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]">导入结果</button>{canCancel && generationJob ? <button type="button" disabled={cancelling} onClick={(event) => { event.stopPropagation(); onCancel(generationJob) }} className="border border-[color:var(--status-offline)] px-3 py-1.5 text-xs text-[color:var(--status-offline)] disabled:opacity-40">{cancelling ? '取消中...' : '取消'}</button> : null}</div></div>
    <dl className="mt-4 grid gap-x-5 gap-y-3 border-t border-[color:var(--border-subtle)] pt-4 text-xs sm:grid-cols-2 lg:grid-cols-4">
      <div>
        <dt className="font-mono text-[0.625rem] text-[color:var(--text-muted)]">时长</dt>
        <dd className="mt-1">{scene.duration_seconds} 秒</dd>
      </div>
      <div>
        <dt className="font-mono text-[0.625rem] text-[color:var(--text-muted)]">最近任务</dt>
        <dd className="mt-1">{generationJob ? formatGenerationStatus(generationJob) : '尚无结果'}</dd>
      </div>
      {scene.seed !== null ? (
        <div>
          <dt className="font-mono text-[0.625rem] text-[color:var(--text-muted)]">SEED</dt>
          <dd className="mt-1 font-mono">{scene.seed}</dd>
        </div>
      ) : null}
      <div>
        <dt className="font-mono text-[0.625rem] text-[color:var(--text-muted)]">在线 Workflow</dt>
        <dd className={needsWorkflow ? 'mt-1 text-[color:var(--accent)]' : 'mt-1'}>
          {needsWorkflow ? '手动导入无需配置' : '已选择 Workflow'}
        </dd>
        {scene.workflow_template_id ? (
          <dd className="mt-1 truncate font-mono text-[color:var(--text-muted)]">{scene.workflow_template_id}</dd>
        ) : null}
      </div>
    </dl>
    {generationProgress !== null ? (
      <div
        role="progressbar"
        aria-label="生成进度"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(generationProgress * 100)}
        className="mt-3 h-1 overflow-hidden bg-[var(--canvas)]"
      >
        <div className="h-full bg-[var(--accent)] transition-[width] duration-200" style={{ width: `${generationProgress * 100}%` }} />
      </div>
    ) : null}
    {cancelError ? <p role="alert" className="mt-2 text-xs leading-5 text-[color:var(--status-offline)]">{cancelError}</p> : null}
  </article>
}
