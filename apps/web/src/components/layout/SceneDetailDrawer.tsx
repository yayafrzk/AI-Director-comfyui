import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { updateScene } from '../../services/scenes'
import type { Scene, SceneUpdate } from '../../types/scene'

type SceneDetailDrawerProps = {
  projectId: string
  scene: Scene
  onClose: () => void
}

type SceneDraft = {
  title: string
  description: string
  prompt: string
  negativePrompt: string
  seed: string
  durationSeconds: string
}

function sceneQueryKey(projectId: string) {
  return ['projects', projectId, 'scenes'] as const
}

function createDraft(scene: Scene): SceneDraft {
  return {
    title: scene.title,
    description: scene.description ?? '',
    prompt: scene.prompt ?? '',
    negativePrompt: scene.negative_prompt ?? '',
    seed: scene.seed?.toString() ?? '',
    durationSeconds: scene.duration_seconds.toString(),
  }
}

export function SceneDetailDrawer({ projectId, scene, onClose }: SceneDetailDrawerProps) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<SceneDraft>(() => createDraft(scene))
  const [validationError, setValidationError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const saveMutation = useMutation({
    mutationFn: (sceneUpdate: SceneUpdate) => updateScene(scene.id, sceneUpdate),
    onSuccess: (updatedScene) => {
      queryClient.setQueryData<Scene[]>(sceneQueryKey(projectId), (scenes = []) =>
        scenes.map((currentScene) => (currentScene.id === updatedScene.id ? updatedScene : currentScene)),
      )
      onClose()
    },
    onError: (error) => {
      setSaveError(error instanceof Error ? error.message : '分镜保存失败')
    },
  })

  function updateDraft(field: keyof SceneDraft, value: string) {
    setDraft((currentDraft) => ({ ...currentDraft, [field]: value }))
    setValidationError(null)
    setSaveError(null)
  }

  function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const durationSeconds = Number(draft.durationSeconds)
    if (draft.durationSeconds.trim() === '' || !Number.isFinite(durationSeconds)) {
      setValidationError('时长必须是有效数字')
      return
    }

    let seed: number | null
    if (draft.seed.trim() === '') {
      seed = null
    } else {
      seed = Number(draft.seed)
      if (!Number.isSafeInteger(seed)) {
        setValidationError('Seed 必须是有效整数')
        return
      }
    }

    const sceneUpdate: SceneUpdate = {}
    if (draft.title !== scene.title) sceneUpdate.title = draft.title
    if (draft.description !== (scene.description ?? '')) sceneUpdate.description = draft.description
    if (draft.prompt !== (scene.prompt ?? '')) sceneUpdate.prompt = draft.prompt
    if (draft.negativePrompt !== (scene.negative_prompt ?? '')) sceneUpdate.negative_prompt = draft.negativePrompt
    if (seed !== scene.seed) sceneUpdate.seed = seed
    if (durationSeconds !== scene.duration_seconds) sceneUpdate.duration_seconds = durationSeconds

    if (Object.keys(sceneUpdate).length === 0) {
      onClose()
      return
    }

    setValidationError(null)
    setSaveError(null)
    saveMutation.mutate(sceneUpdate)
  }

  const sceneNumber = String(scene.scene_number).padStart(2, '0')

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        aria-label="关闭分镜详情"
        onClick={onClose}
        disabled={saveMutation.isPending}
        className="absolute inset-0 cursor-default bg-black/60 disabled:cursor-not-allowed"
      />
      <aside
        aria-labelledby="scene-detail-heading"
        className="relative flex h-full w-full max-w-xl flex-col border-l border-[color:var(--border-strong)] bg-[var(--surface-base)] shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4 border-b border-[color:var(--border-subtle)] px-5 py-4 sm:px-6">
          <div>
            <p className="font-mono text-[0.625rem] tracking-[0.16em] text-[color:var(--text-muted)]">SCENE DETAIL</p>
            <h2 id="scene-detail-heading" className="mt-1 text-base font-semibold text-[color:var(--text-primary)]">
              Scene {sceneNumber} / 分镜 {sceneNumber}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={saveMutation.isPending}
            aria-label="关闭"
            className="grid size-8 place-items-center border border-[color:var(--border-subtle)] text-lg leading-none text-[color:var(--text-muted)] hover:border-[color:var(--accent)] hover:text-[color:var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            ×
          </button>
        </header>

        <form onSubmit={handleSave} className="flex min-h-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-5 py-5 sm:px-6">
            <section>
              <p className="font-mono text-[0.625rem] tracking-[0.16em] text-[color:var(--accent)]">基础信息</p>
              <div className="mt-3 space-y-4">
                <Field label="标题" htmlFor="scene-title">
                  <input
                    id="scene-title"
                    value={draft.title}
                    onChange={(event) => updateDraft('title', event.target.value)}
                    className={inputClassName}
                    disabled={saveMutation.isPending}
                  />
                </Field>
                <Field label="描述" htmlFor="scene-description">
                  <textarea
                    id="scene-description"
                    rows={4}
                    value={draft.description}
                    onChange={(event) => updateDraft('description', event.target.value)}
                    className={textareaClassName}
                    disabled={saveMutation.isPending}
                  />
                </Field>
                <Field label="时长（秒）" htmlFor="scene-duration">
                  <input
                    id="scene-duration"
                    type="number"
                    step="any"
                    value={draft.durationSeconds}
                    onChange={(event) => updateDraft('durationSeconds', event.target.value)}
                    className={inputClassName}
                    disabled={saveMutation.isPending}
                  />
                </Field>
              </div>
            </section>

            <section>
              <p className="font-mono text-[0.625rem] tracking-[0.16em] text-[color:var(--accent)]">PROMPT</p>
              <div className="mt-3 space-y-4">
                <Field label="Prompt" htmlFor="scene-prompt">
                  <textarea
                    id="scene-prompt"
                    rows={6}
                    value={draft.prompt}
                    onChange={(event) => updateDraft('prompt', event.target.value)}
                    className={textareaClassName}
                    disabled={saveMutation.isPending}
                  />
                </Field>
                <Field label="Negative Prompt" htmlFor="scene-negative-prompt">
                  <textarea
                    id="scene-negative-prompt"
                    rows={5}
                    value={draft.negativePrompt}
                    onChange={(event) => updateDraft('negativePrompt', event.target.value)}
                    className={textareaClassName}
                    disabled={saveMutation.isPending}
                  />
                </Field>
              </div>
            </section>

            <section>
              <p className="font-mono text-[0.625rem] tracking-[0.16em] text-[color:var(--accent)]">生成参数</p>
              <div className="mt-3">
                <Field label="Seed" htmlFor="scene-seed">
                  <input
                    id="scene-seed"
                    type="number"
                    step="1"
                    value={draft.seed}
                    onChange={(event) => updateDraft('seed', event.target.value)}
                    className={inputClassName}
                    disabled={saveMutation.isPending}
                  />
                </Field>
              </div>
            </section>

            {validationError ? <DrawerError message={validationError} /> : null}
            {saveError ? <DrawerError message={saveError} /> : null}
          </div>

          <footer className="flex justify-end gap-3 border-t border-[color:var(--border-subtle)] bg-[var(--surface-base)] px-5 py-4 sm:px-6">
            <button
              type="button"
              onClick={onClose}
              disabled={saveMutation.isPending}
              className="border border-[color:var(--border-subtle)] px-4 py-2 text-sm text-[color:var(--text-muted)] hover:border-[color:var(--accent)] hover:text-[color:var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={saveMutation.isPending}
              className="border border-[color:var(--accent)] bg-[var(--accent-soft)] px-4 py-2 text-sm text-[color:var(--accent)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saveMutation.isPending ? '保存中...' : '保存'}
            </button>
          </footer>
        </form>
      </aside>
    </div>
  )
}

type FieldProps = {
  label: string
  htmlFor: string
  children: React.ReactNode
}

function Field({ label, htmlFor, children }: FieldProps) {
  return (
    <div>
      <label htmlFor={htmlFor} className="text-xs text-[color:var(--text-primary)]">
        {label}
      </label>
      <div className="mt-2">{children}</div>
    </div>
  )
}

function DrawerError({ message }: { message: string }) {
  return (
    <div className="border-l-2 border-[color:var(--status-offline)] bg-[var(--surface-raised)] px-3 py-3">
      <p className="text-xs leading-5 text-[color:var(--text-primary)]">{message}</p>
    </div>
  )
}

const inputClassName =
  'w-full border border-[color:var(--border-subtle)] bg-[var(--surface-raised)] px-3 py-2 text-sm text-[color:var(--text-primary)] outline-none focus:border-[color:var(--accent)] disabled:cursor-not-allowed disabled:opacity-60'

const textareaClassName =
  'w-full resize-y border border-[color:var(--border-subtle)] bg-[var(--surface-raised)] px-3 py-2 text-sm leading-6 text-[color:var(--text-primary)] outline-none focus:border-[color:var(--accent)] disabled:cursor-not-allowed disabled:opacity-60'
