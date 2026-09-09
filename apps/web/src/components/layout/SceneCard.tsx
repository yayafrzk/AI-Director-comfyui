import type { DragEvent, MouseEvent } from 'react'

import { formatGenerationStatus, type GenerationJob } from '../../types/generation'
import type { Scene } from '../../types/scene'

type SceneCardProps = {
  scene: Scene
  generationJob?: GenerationJob
  position: number
  isSorting: boolean
  dragDisabled: boolean
  generating: boolean
  cancelling: boolean
  retrying: boolean
  generationError?: string | null
  cancelError?: string | null
  retryError?: string | null
  onGenerate: (scene: Scene) => void
  onCancel: (job: GenerationJob) => void
  onRetry: (job: GenerationJob) => void
  onDragStart: (event: DragEvent<HTMLButtonElement>, sceneId: string) => void
  onDragEnter: (sceneId: string) => void
  onDragEnd: () => void
  onOpen: (sceneId: string) => void
}

export function SceneCard({ scene, generationJob, position, isSorting, dragDisabled, generating, cancelling, retrying, generationError, cancelError, retryError, onGenerate, onCancel, onRetry, onDragStart, onDragEnter, onDragEnd, onOpen }: SceneCardProps) {
  const sceneNumber = isSorting ? position + 1 : scene.scene_number
  const canCancel = generationJob?.status === 'queued' || generationJob?.status === 'running' || generationJob?.status === 'pending'
  const canRetry = generationJob?.status === 'failed'
  const needsWorkflow = !scene.workflow_template_id

  return <article onClick={() => onOpen(scene.id)} onDragEnter={() => onDragEnter(scene.id)} onDragOver={(event) => event.preventDefault()} className="border border-[color:var(--border-subtle)] bg-[var(--surface-raised)] p-4 sm:p-5">
    <div className="flex items-start gap-4"><button type="button" draggable={!dragDisabled} disabled={dragDisabled} onDragStart={(event) => onDragStart(event, scene.id)} onDragEnd={onDragEnd} onClick={(event: MouseEvent<HTMLButtonElement>) => event.stopPropagation()} aria-label={`拖动分镜 ${sceneNumber} 排序`} className="grid size-7 shrink-0 cursor-grab place-items-center border border-[color:var(--border-subtle)]">≡</button><span className="grid size-10 shrink-0 place-items-center border border-[color:var(--accent)] bg-[var(--accent-soft)] font-mono text-sm text-[color:var(--accent)]">{String(sceneNumber).padStart(2, '0')}</span><div className="min-w-0 flex-1"><h3 className="truncate text-base font-semibold">{scene.title.trim() || '未命名分镜'}</h3><p className="mt-2 line-clamp-2 text-sm text-[color:var(--text-muted)]">{scene.prompt?.trim() || '暂无 Prompt'}</p></div><div className="flex shrink-0 gap-2"><button
  type="button"
  disabled={!needsWorkflow && generating}
  onClick={(event) => {
    event.stopPropagation()
    if (needsWorkflow) {
      onOpen(scene.id)
      return
    }
    onGenerate(scene)
  }}
  className="border border-[color:var(--accent)] px-3 py-1.5 text-xs text-[color:var(--accent)] transition-colors hover:bg-[var(--accent-soft)] disabled:cursor-not-allowed disabled:opacity-40"
>
  {needsWorkflow ? '去配置' : generating ? '提交中...' : '生成'}
</button>{canCancel && generationJob ? <button type="button" disabled={cancelling} onClick={(event) => { event.stopPropagation(); onCancel(generationJob) }} className="border border-[color:var(--status-offline)] px-3 py-1.5 text-xs text-[color:var(--status-offline)] disabled:opacity-40">{cancelling ? '取消中...' : '取消'}</button> : null}{canRetry && generationJob ? <button type="button" disabled={retrying} onClick={(event) => { event.stopPropagation(); onRetry(generationJob) }} className="border border-[color:var(--accent)] px-3 py-1.5 text-xs text-[color:var(--accent)] disabled:opacity-40">{retrying ? '重试中...' : '重试'}</button> : null}</div></div>
    <dl className="mt-4 grid gap-x-5 gap-y-3 border-t border-[color:var(--border-subtle)] pt-4 text-xs sm:grid-cols-2 lg:grid-cols-4">
      <div>
        <dt className="font-mono text-[0.625rem] text-[color:var(--text-muted)]">时长</dt>
        <dd className="mt-1">{scene.duration_seconds} 秒</dd>
      </div>
      <div>
        <dt className="font-mono text-[0.625rem] text-[color:var(--text-muted)]">生成状态</dt>
        <dd className="mt-1">{formatGenerationStatus(generationJob)}</dd>
      </div>
      {scene.seed !== null ? (
        <div>
          <dt className="font-mono text-[0.625rem] text-[color:var(--text-muted)]">SEED</dt>
          <dd className="mt-1 font-mono">{scene.seed}</dd>
        </div>
      ) : null}
      <div>
        <dt className="font-mono text-[0.625rem] text-[color:var(--text-muted)]">配置</dt>
        <dd className={needsWorkflow ? 'mt-1 text-[color:var(--accent)]' : 'mt-1'}>
          {needsWorkflow ? '未选择 Workflow' : '已选择 Workflow'}
        </dd>
        {scene.workflow_template_id ? (
          <dd className="mt-1 truncate font-mono text-[color:var(--text-muted)]">{scene.workflow_template_id}</dd>
        ) : null}
      </div>
    </dl>
    {generationError ? <p role="alert" className="mt-3 text-xs leading-5 text-[color:var(--status-offline)]">{generationError}</p> : null}
    {cancelError ? <p role="alert" className="mt-2 text-xs leading-5 text-[color:var(--status-offline)]">{cancelError}</p> : null}
    {retryError ? <p role="alert" className="mt-2 text-xs leading-5 text-[color:var(--status-offline)]">{retryError}</p> : null}
  </article>
}
